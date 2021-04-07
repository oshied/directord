import base64
import hashlib
import json
import os
import socket
import time

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
                (
                    identity,
                    _,
                    control,
                    _,
                    _,
                    _,
                ) = self.socket_multipart_recv(zsocket=self.bind_heatbeat)

                if control in [self.heartbeat_ready, self.heartbeat_notice]:
                    self.log.debug(
                        "Received Heartbeat from {}, client online".format(
                            identity
                        )
                    )
                    expire = self.workers[identity] = self.get_expiry
                    heartbeat_at = self.get_heartbeat
                    data = dict(expire=expire)
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        identity=identity,
                        data=json.dumps(data).encode(),
                    )

            # Send heartbeats to idle workers if it's time
            elif time.time() > idel_time and self.workers:
                for worker in list(self.workers.keys()):
                    self.log.warn(
                        "Sending idle worker {} a heartbeat".format(worker)
                    )
                    expire = self.workers.get(worker) or self.get_expiry
                    data = dict(expire=expire)
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        identity=worker,
                        command=b"reset",
                        data=json.dumps(data).encode(),
                    )
                    if time.time() > idel_time + 3:
                        self.log.warn("Removing dead worker {}".format(worker))
                        self.workers.pop(worker)

            self.wq_prune(workers=self.workers)

    def _set_job_status(self, job_status, job_id, identity, job_output):
        """Set job status.

        This will update the manager object for job tracking, allowing the
        user to know what happened within the environment.

        :param job_status: ASCII Control Character
        :type job_status: Bytes
        :param job_id: UUID for job
        :type job_id: String
        :param identity: Node name
        :type identity: String
        :param job_output: Job output information
        :type job_output: String
        """

        # NOTE(cloudnull): This is where we would need to implement a
        #                  callback plugin for the client.
        job_metadata = self.return_jobs.get(job_id, {})
        _time = job_metadata["_time"] = job_metadata.get("_time", time.time())
        job_metadata["EXECUTION_TIME"] = time.time() - _time
        if job_status in [self.job_ack, self.job_processing]:
            job_metadata["PROCESSING"] = True
            job_metadata["SUCCESS"] = False
            job_metadata["INFO"] = job_output
            self.log.info("{} processing {}".format(identity, job_id))
        elif job_status in [self.job_end, self.nullbyte]:
            self.log.info(
                "{} processing {} completed".format(identity, job_id)
            )
            job_metadata["PROCESSING"] = False
            job_metadata["SUCCESS"] = True
            job_metadata["INFO"] = job_output
        elif job_status == self.job_failed:
            job_metadata["PROCESSING"] = False
            job_metadata["SUCCESS"] = False
            if "FAILED" in job_metadata:
                job_metadata["FAILED"].append(identity)
            else:
                job_metadata["FAILED"] = [identity]
            job_metadata["INFO"] = job_output
            self.log.error("{} processing {} failed".format(identity, job_id))

        self.return_jobs[job_id] = job_metadata

    def _run_transfer(self, identity, verb, file_path):
        """Run file transfer job.

        The transfer process will transfer all files from a given meta data
        set using strict identity targetting.

        When a file is initiated all chunks will be sent over the wire.

        :param identity: Node name
        :type identity: String
        :param verb: Action taken
        :type verb: Bytes
        :param file_path: Path of file to transfer.
        :type file_path: String
        """

        self.log.debug("Processing file [ %s ]", file_path)
        if not os.path.isfile(file_path):
            self.log.warn("File was not found. File path:%s", file_path)
            return

        self.log.info("File transfer for [ %s ] starting", file_path)
        with open(file_path, "rb") as f:
            for chunk in self.read_in_chunks(file_object=f):
                self.socket_multipart_send(
                    zsocket=self.bind_job,
                    identity=identity,
                    command=verb,
                    data=chunk,
                )
            else:
                self.socket_multipart_send(
                    zsocket=self.bind_job,
                    identity=identity,
                    control=self.transfer_end,
                    command=verb,
                )

    def _run_job(self, job_item, identity):
        """Run an encoded job.

        :param job_item: Dictionary item containing job meta data.
        :type job_item: Dictionary
        :param identity: Node name
        :type identity: String
        """

        self.socket_multipart_send(
            zsocket=self.bind_job,
            identity=identity,
            command=job_item["verb"].encode(),
            data=json.dumps(job_item).encode(),
        )

    def run_job(self):
        """Execute the job loop.

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
                    msg_id,
                    control,
                    command,
                    _,
                    info,
                ) = self.socket_multipart_recv(zsocket=self.bind_job)
                if command == b"transfer":
                    self.log.debug(
                        "Executing transfer for [ %s ]", info.decode()
                    )
                    self._run_transfer(
                        identity=identity,
                        verb=b"ADD",
                        file_path=os.path.abspath(
                            os.path.expanduser(info.decode())
                        ),
                    )
                self._set_job_status(
                    job_status=control,
                    job_id=msg_id.decode(),
                    identity=identity.decode(),
                    job_output=info.decode(),
                )
            elif self.workers:
                try:
                    job_item = self.job_queue.get(block=False, timeout=1)
                except Exception:
                    pass
                else:
                    job_target = job_item.get("target")
                    if job_target:
                        job_target = job_target.encode()
                        targets = list()
                        if job_target in self.workers:
                            targets.append(job_target)
                        else:
                            self.log.critical(
                                "Target {} is in an unknown state.".format(
                                    job_target
                                )
                            )
                    else:
                        targets = self.workers.keys()

                    task = job_item.get("task")
                    if task and task not in self.return_jobs:
                        self.return_jobs[task] = {
                            "ACCEPTED": True,
                            "INFO": self.nullbyte.decode(),
                            "_time": time.time(),
                        }

                    for identity in targets:
                        if job_item["verb"] in ["ADD", "COPY"]:
                            for file_path in job_item["from"]:
                                job_item["file_sha1sum"] = self.file_sha1(
                                    file_path=file_path
                                )
                                job_item["file_to"] = os.path.join(
                                    job_item["to"],
                                    os.path.basename(file_path),
                                )
                                self.socket_multipart_send(
                                    zsocket=self.bind_job,
                                    identity=identity,
                                    command=job_item["verb"].encode(),
                                    data=json.dumps(job_item).encode(),
                                    info=file_path.encode(),
                                )
                        else:
                            self._run_job(job_item=job_item, identity=identity)

                        self.log.info(
                            "Sent job {} to {}".format(task, identity)
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
                json_data = json.loads(data_decoded)
                if "manage" in json_data:
                    manage = json_data["manage"]
                    if manage == "list-nodes":
                        data = [
                            (
                                i.decode(),
                                {"expiry": self.workers[i] - time.time()},
                            )
                            for i in self.workers.keys()
                        ]
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
                        json_data["task"] = self.get_uuid

                    # Returns the message in reverse to show a return. This will
                    # be a standard client return in JSON format under normal
                    # circomstances.
                    conn.sendall(
                        "Job recieved. Task ID: {}".format(
                            json_data["task"]
                        ).encode()
                    )
                    self.log.debug("Data sent to queue, {}".format(json_data))
                    self.job_queue.put(json_data)
            finally:
                conn.close()

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            self.thread(target=self.run_socket_server),
            self.thread(target=self.run_heartbeat),
            self.thread(target=self.run_job),
        ]
        self.run_threads(threads=threads)
