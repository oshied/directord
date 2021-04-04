import grp
import json
import os
import pwd
import time

import zmq

from director import manager
from director import utils


class Client(manager.Interface):
    """Director client class."""

    def __init__(self, args):
        """Initialize the Director client.

        Sets up the client object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Client, self).__init__(args=args)

        self.heartbeat_failure_interval = 2

    def job_connect(self):
        """Connect to a job socket and return the socket.

        :returns: Object
        """

        return self.socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.job_port,
            send_ready=False,
        )

    def heatbeat_connect(self):
        """Connect to a heartbeat socket and return the socket.

        :returns: Object
        """

        return self.socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.heartbeat_port,
        )

    def run_heartbeat(self):
        """Execute the heartbeat loop.

        The heartbeat message from the server will always be a multipart
        message conainting the following information.

            [
                {"valid_json": true}
            ]

        The heartbeat message to the server will always be a single
        message containing the following information.

            b"ASCII Control Characters"

        All of the supported controll characters are defined within the
        Interface class. For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.
        """

        self.bind_heatbeat = self.heatbeat_connect()
        heartbeat_at = self.get_heartbeat
        while True:
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            if socks.get(self.bind_heatbeat) == zmq.POLLIN:
                message = self.bind_heatbeat.recv_multipart()
                message = json.loads(message[0].decode())
                heartbeat_at = message["expire"]
                self.heartbeat_failure_interval = 2
            else:
                self.bind_heatbeat.send(self.heartbeat_notice)
                if time.time() > heartbeat_at:
                    print("W: Heartbeat failure, can't reach queue")
                    print(
                        "W: Reconnecting in {}s...".format(
                            self.heartbeat_failure_interval
                        )
                    )
                    time.sleep(self.heartbeat_failure_interval)

                    if self.heartbeat_failure_interval < 32:
                        self.heartbeat_failure_interval *= 2

                    self.poller.unregister(self.bind_heatbeat)
                    self.bind_heatbeat.close()
                    self.bind_heatbeat = self.heatbeat_connect()
                    heartbeat_at = self.get_heartbeat

    def run_job(self):
        """Execute the job loop.

        The job message from the server will always be a multipart
        message conainting the following information.

            [
                {"valid_json": true}
            ]

        The job message to the server will always be a multipart
        message conainting the following information.

            [
                b"UUID",
                b"ASCII Control Characters"
            ]

        All of the supported controll characters are defined within the
        Interface class. For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.
        """

        self.bind_job = self.job_connect()
        while True:
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            if self.bind_job in socks:
                # This is procecssing the work queue
                message = self.bind_job.recv_multipart()
                job = json.loads(message[0].decode())
                job_id = job["task"]
                print("received job", job_id)
                self.bind_job.send_multipart(
                    [job_id.encode(), self.job_ack, self.nullbyte]
                )

                with utils.ClientStatus(
                    socket=self.bind_job, job_id=job_id.encode(), ctx=self
                ) as c:
                    command = job.get("command")
                    if command:
                        info, success = utils.run_command(command=command)
                        if info:
                            c.info = info

                        if not success:
                            c.job_state = self.job_failed
                        else:
                            c.job_state = self.job_end

                    file_to = job.get("file_to")
                    if file_to:
                        with open(file_to, "wb") as f:
                            while True:
                                try:
                                    chunk = self.bind_job.recv()
                                    if chunk == self.transfer_end:
                                        break
                                except Exception:
                                    break
                                else:
                                    f.write(chunk)

                        user = job.get("user")
                        group = job.get("group")
                        try:
                            uid = pwd.getpwnam(user).pw_uid
                            if group:
                                gid = grp.getgrnam(group).gr_gid
                            else:
                                gid = -1
                        except KeyError:
                            c.job_state = self.job_failed
                        else:
                            os.chown(file_to, uid, gid)

                        c.job_state = self.job_end

                    workdir = job.get("workdir")
                    if workdir:
                        utils.mkdir_p(workdir)
                        c.job_state = self.job_end

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            self.thread(target=self.run_heartbeat),
            self.thread(target=self.run_job),
        ]
        self.run_threads(threads=threads)
