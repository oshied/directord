import base64
import hashlib
import json
import os
import socket
import time
import uuid

import zmq

from director import manager


class Server(manager.Interface):
    """Director server class."""

    def __init__(self, args):
        """Initialize the Server class.

        Sets up the server object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Server, self).__init__(args=args)

    def heartbeat_bind(self):
        """Bind an address to a heartbeat socket and return the socket.

        :returns: Object
        """

        return self.socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.heartbeat_port,
        )

    def job_bind(self):
        """Bind an address to a job socket and return the socket.

        :returns: Object
        """

        return self.socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.job_port,
        )

    def run_heartbeat(self):
        """Execute the heartbeat loop.

        The heartbeat message from the client will always be a multipart
        message conainting the following information.

            [
                b"Identity",
                b"ASCII Control Characters"
            ]

        The heartbeat message to the client will always be a multipart
        message containing the following information.

            [
                b"Identity",
                {"valid_json": true}
            ]

        All of the supported controll characters are defined within the
        Interface class. For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        If the heartbeat loop detects a problem, the server will send a
        heartbeat probe to the client to ensure that it is alive. At the
        end of the loop workers without a valid heartbeat will be pruned
        from the available pool.
        """

        self.bind_heatbeat = self.heartbeat_bind()
        heartbeat_at = self.get_heartbeat
        while True:
            idel_time = heartbeat_at + (self.heartbeat_interval * 3)
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            if socks.get(self.bind_heatbeat) == zmq.POLLIN:
                identity, message = self.bind_heatbeat.recv_multipart()
                if message in [self.heartbeat_ready, self.heartbeat_notice]:
                    print(
                        "Received Heartbeat from {}, client online".format(
                            identity
                        )
                    )
                    expire = self.workers[identity] = self.get_expiry
                    heartbeat_at = self.get_heartbeat
                    data = dict(expire=expire)
                    self.bind_heatbeat.send_multipart(
                        [identity, json.dumps(data).encode()]
                    )

            # Send heartbeats to idle workers if it's time
            elif time.time() > idel_time and self.workers:
                for worker in list(self.workers.keys()):
                    print("Sending idle worker {} a heartbeat".format(worker))
                    expire = self.workers.get(worker) or self.get_expiry
                    data = dict(expire=expire)
                    self.bind_heatbeat.send_multipart(
                        [worker, json.dumps(data).encode()]
                    )
                    if time.time() > idel_time + 3:
                        print("Removing dead worker {}".format(worker))
                        self.workers.pop(worker)

            self.wq_prune(workers=self.workers)

    def run_job(self):
        """Execute the job loop.

        The job message from the client will always be a multipart
        message conainting the following information.

            [
                b"Identity",
                b"Job ID",
                b"ASCII Control Characters",
                b"Task Output"
            ]

        The job message to the client will always be a multipart
        message conainting the following information.

            [
                b"Identity",
                {"valid_json": true}
            ]

        All of the supported controll characters are defined within the
        Interface class. For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        As the job loop executes it will interrogate the job item as returned
        from the queue. If the item contains a "target" definition the
        job loop will only send the message to the one target, assuming the
        target is known within the workers object, otherwise all targets will
        receive the message. If a defined target is not found within the
        workers object no job will be executed.
        """

        self.bind_job = self.job_bind()
        while True:
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            # Handle worker activity on backend
            if socks.get(self.bind_job) == zmq.POLLIN:
                (
                    identity,
                    job_id,
                    job_status,
                    job_output,
                ) = self.bind_job.recv_multipart()
                job_output = job_output.decode()
                job_id = job_id.decode()

                # NOTE(cloudnull): This is where we would need to implement a
                #                  callback plugin for the client.
                if job_status in [self.job_ack, self.job_processing]:
                    self.return_jobs[job_id] = {
                        "PROCESSING": True,
                        "INFO": job_output,
                    }
                    print("{} processing {}".format(identity, job_id))
                elif job_status == self.job_end:
                    print(
                        "{} processing {} completed".format(identity, job_id)
                    )
                    try:
                        self.return_jobs[job_id] = {
                            "SUCCESS": True,
                            "INFO": job_output,
                        }
                    except KeyError:
                        pass
                elif job_status == self.job_failed:
                    self.return_jobs[job_id] = {
                        "FAILED": True,
                        "INFO": job_output,
                    }
                    print("{} processing {} failed".format(identity, job_id))

            elif self.workers:
                try:
                    job_item = self.job_queue.get(block=False, timeout=1)
                except Exception:
                    job_item = None
                else:
                    job_target = job_item.get("target")
                    if job_target:
                        job_target = job_target.encode()
                        targets = list()
                        if job_target in self.workers:
                            targets.append(job_target)
                        else:
                            print(
                                "Target {} is in an unknown state.".format(
                                    job_target
                                )
                            )
                    else:
                        targets = self.workers.keys()

                    self.return_jobs[job_item["task"]] = {
                        "ACCEPTED": True,
                        "INFO": self.nullbyte.decode(),
                    }
                    for identity in targets:
                        if "from" in job_item:
                            for file_path in job_item["from"]:
                                job_item["file_to"] = os.path.join(
                                    job_item["to"],
                                    os.path.basename(file_path),
                                )
                                # TODO(cloudull): figure out how to shortcircut
                                # the transfer if the SHA1 SUM matches an
                                # existing file.
                                job_item["file_sha1sum"] = self.file_sha1(
                                    file_path=file_path
                                )
                                self.bind_job.send_multipart(
                                    [
                                        identity,
                                        json.dumps(job_item).encode(),
                                    ]
                                )
                                with open(file_path, "rb") as f:
                                    for chunk in self.read_in_chunks(
                                        file_object=f
                                    ):
                                        print('sending chunk')
                                        self.bind_job.send_multipart(
                                            [
                                                identity,
                                                chunk,
                                            ]
                                        )
                                    else:
                                        self.bind_job.send_multipart(
                                            [
                                                identity,
                                                self.transfer_end,
                                            ]
                                        )
                        else:
                            self.bind_job.send_multipart(
                                [identity, json.dumps(job_item).encode()]
                            )
                        print(
                            "Sent job {} to {}".format(
                                job_item["task"], identity
                            )
                        )

    def run_socket_server(self):
        """Start a socket server.

        The socket server is used to broker a connection from the end user
        into the director sub-system. The socket server will allow for 1
        message of 10M before requiring the client to reconnect.

        All received data is expected to be JSON serialized data. Before
        being added to the queue, a task ID and SHA1 SUM is added to the
        content. This is done for tracking and caching purposes. The task
        ID can be defined in the data. If a task ID is not defined one will
        be generated.
        """

        try:
            os.unlink(self.args.socket_path)
        except OSError:
            if os.path.exists(self.args.socket_path):
                raise SystemExit(
                    "Socket path already exists: {}".format(
                        self.args.socket_path
                    )
                )

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.args.socket_path)
        sock.listen(1)

        while True:
            conn, _ = sock.accept()
            try:
                data = conn.recv(10240000)
                if not data:
                    pass

                data_decoded = data.decode()
                print("Data recieved {}".format(data))
                json_data = json.loads(data_decoded)
                if "manage" in json_data:
                    manage = json_data["manage"]
                    if manage == "list-nodes":
                        data = [i.decode() for i in self.workers.keys()]
                    elif manage == "list-jobs":
                        data = [
                            (str(k), v) for k, v in self.return_jobs.items()
                        ]
                    elif manage == "purge-nodes":
                        self.wq_empty(workers=self.workers)
                        data = {"success": True}
                    elif manage == "purge-jobs":
                        self.wq_empty(workers=self.return_jobs)
                        data = {"success": True}
                    else:
                        conn.sendall(json.dumps({"failed": True}).encode())

                    conn.sendall(json.dumps(data).encode())
                else:
                    json_data["task_sha1sum"] = hashlib.sha1(data).hexdigest()
                    if "task" not in json_data:
                        json_data["task"] = str(uuid.uuid4())

                    # Returns the message in reverse to show a return. This will
                    # be a standard client return in JSON format under normal
                    # circomstances.
                    conn.sendall(
                        "Job recieved. Task ID: {}".format(
                            json_data["task"]
                        ).encode()
                    )
                    print("Data sent to queue, {}".format(json_data))
                    self.job_queue.put(json_data)
            finally:
                conn.close()

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        # # Simulate populating the job queue with random tasks.
        # for _ in range(1, 100):
        #     self.job_queue.put({"task": str(uuid.uuid4())})

        threads = [
            self.thread(target=self.run_socket_server),
            self.thread(target=self.run_heartbeat),
            self.thread(target=self.run_job),
        ]
        self.run_threads(threads=threads)
