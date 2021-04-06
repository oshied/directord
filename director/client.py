import grp
import json
import os
import pwd
import tempfile
import time

import diskcache
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

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.
        """

        self.bind_heatbeat = self.heatbeat_connect()
        heartbeat_at = self.get_heartbeat
        while True:
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            if socks.get(self.bind_heatbeat) == zmq.POLLIN:
                (
                    _,
                    _,
                    _,
                    data,
                    _,
                ) = self.socket_multipart_recv(zsocket=self.bind_heatbeat)

                data = json.loads(data.decode())
                heartbeat_at = data["expire"]
                self.heartbeat_failure_interval = 2
            else:
                if time.time() > heartbeat_at:
                    self.log.warn("Heartbeat failure, can't reach queue")
                    self.log.warn(
                        "Reconnecting in {}s...".format(
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
                else:
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        control=self.heartbeat_notice,
                    )

    def _run_command(self, cache, job_sha1, command):
        """Run file command operation.

        :param cache: Cached access object.
        :type cache: Object
        :param job_sha1: SHA1SUM of the original job schematic.
        :type job_sha1: String
        :param command: Work directory path.
        :type command: String
        :returns: tuple
        """

        if cache.get(job_sha1) == self.job_end:
            self.log.debug("Cache hit on {}, task skipped.".format(job_sha1))
            return self.nullbyte, True

        info, success = utils.run_command(command=command)
        return info, success

    def _run_workdir(self, cache, job_sha1, workdir):
        """Run file work directory operation.

        :param cache: Cached access object.
        :type cache: Object
        :param job_sha1: SHA1SUM of the original job schematic.
        :type job_sha1: String
        :param workdir: Work directory path.
        :type workdir: String
        :returns: tuple
        """

        if cache.get(job_sha1) == self.job_end:
            self.log.debug("Cache hit on {}, task skipped.".format(job_sha1))
            return self.nullbyte, True

        os.makedirs(workdir, exist_ok=True)
        return "", True

    def _run_transfer(self, job):
        """Run file transfer operation.

        :param job: Job dictionary containing metadata about a given task.
        :type job: Dictionary
        :returns: tuple
        """

        # TODO: Add short-circut to file transfers.
        file_to = job["file_to"]
        with open(file_to, "wb") as f:
            while True:
                try:
                    (
                        _,
                        control,
                        _,
                        data,
                        _,
                    ) = self.socket_multipart_recv(zsocket=self.bind_job)
                    if control == self.transfer_end:
                        break
                except Exception:
                    break
                else:
                    f.write(data)
        success = True
        user = job.get("user")
        group = job.get("group")
        if user:
            try:
                uid = pwd.getpwnam(user).pw_uid
                if group:
                    gid = grp.getgrnam(group).gr_gid
                else:
                    gid = -1
            except KeyError:
                success = False
            else:
                os.chown(file_to, uid, gid)
                success = True

        return self.file_sha1(file_to), success

    def _job_loop(self, cache):
        """Execute the job loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        :param cache: Cached access object.
        :type cache: Object
        """

        socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
        if self.bind_job in socks:
            # This is procecssing the work queue
            (
                _,
                _,
                _,
                data,
                _,
            ) = self.socket_multipart_recv(zsocket=self.bind_job)
            job = json.loads(data.decode())
            job_id = job["task"]
            job_sha1 = job.get("task_sha1sum")
            self.log.info("Job received {}".format(job_id))
            self.socket_multipart_send(
                zsocket=self.bind_job,
                msg_id=job_id.encode(),
                control=self.job_ack,
            )

            with utils.ClientStatus(
                socket=self.bind_job, job_id=job_id.encode(), ctx=self
            ) as c:
                if "command" in job:
                    info, success = self._run_command(
                        cache=cache, job_sha1=job_sha1, command=job["command"]
                    )
                elif "file_to" in job:
                    info, success = self._run_transfer(job=job)
                elif "workdir" in job:
                    info, success = self._run_workdir(
                        cache=cache, job_sha1=job_sha1, workdir=job["workdir"]
                    )

                c.info = info

                if not success:
                    state = c.job_state = self.job_failed
                    self.log.error("Job failed {}".format(job_id))
                else:
                    state = c.job_state = self.job_end
                    self.log.info("Job complete {}".format(job_id))

                cache[job_sha1] = state

    def run_job(self):
        """Job entry point.

        This creates a cached access object, connects to the socket and begins
        the loop.
        """

        self.bind_job = self.job_connect()
        with diskcache.Cache(tempfile.gettempdir()) as cache:
            while True:
                self._job_loop(cache=cache)

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
