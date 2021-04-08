import grp
import json
import os
import pwd
import struct
import tempfile
import time
import yaml

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

        self.log.debug("Establishing Job connection.")
        return self.socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.job_port,
            send_ready=False,
        )

    def transfer_connect(self):
        """Connect to a transfer socket and return the socket.

        :returns: Object
        """

        self.log.debug("Establishing transfer connection.")
        return self.socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.transfer_port,
            send_ready=False,
        )

    def heatbeat_connect(self):
        """Connect to a heartbeat socket and return the socket.

        :returns: Object
        """

        self.log.debug("Establishing Heartbeat connection.")
        return self.socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.heartbeat_port,
        )

    def reset_heartbeat(self):
        """Reset the connection on the heartbeat socket.

        Returns a new ttl after reconnect.

        :returns: Float
        """

        self.poller.unregister(self.bind_heatbeat)
        self.log.debug("Unregistered heartbeat.")
        self.bind_heatbeat.close()
        self.log.debug("Heartbeat connection closed.")
        self.bind_heatbeat = self.heatbeat_connect()
        return self.get_heartbeat

    def run_heartbeat(self):
        """Execute the heartbeat loop.

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.

        This loop tracks heartbeat messages and should the heartbeat
        interval take longer than the expire time, and fail more than 5
        times the connection will be reset after a failure cooldown.
        """

        self.bind_heatbeat = self.heatbeat_connect()
        heartbeat_at = self.get_heartbeat
        heartbeat_misses = 0
        while True:
            self.log.debug("Heartbeat misses [ %s ]", heartbeat_misses)
            socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
            if socks.get(self.bind_heatbeat) == zmq.POLLIN:
                (
                    _,
                    _,
                    command,
                    _,
                    info,
                ) = self.socket_multipart_recv(zsocket=self.bind_heatbeat)
                self.log.debug(
                    "Heartbeat received from server [ %s ]",
                    self.connection_string,
                )
                if command == b"reset":
                    self.log.warn(
                        "Received heartbeat reset command. Connection resetting."
                    )
                    self.reset_heartbeat()
                    heartbeat_at = self.get_expiry
                else:
                    heartbeat_at = struct.unpack("<f", info)[0]
                    heartbeat_misses = 0

                self.heartbeat_failure_interval = 2
            else:
                if time.time() > heartbeat_at and heartbeat_misses > 5:
                    self.log.error("Heartbeat failure, can't reach server")
                    self.log.warn(
                        "Reconnecting in {}s...".format(
                            self.heartbeat_failure_interval
                        )
                    )

                    time.sleep(self.heartbeat_failure_interval)
                    if self.heartbeat_failure_interval < 32:
                        self.heartbeat_failure_interval *= 2

                    self.log.debug("Running reconnection.")
                    self.reset_heartbeat()
                    heartbeat_at = self.get_expiry
                else:
                    heartbeat_misses += 1
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        control=self.heartbeat_notice,
                    )
                    self.log.debug(
                        "Sent heartbeat to server [ %s ]",
                        self.connection_string,
                    )

    def _run_command(self, command, cache, stdout_arg=None):
        """Run file command operation.

        Command operations are rendered with cached data from the args dict.

        :param command: Work directory path.
        :type command: String
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param stdout_arg: Argument name used to store stdout in cache.
        :type stdout_arg: String
        :returns: tuple
        """

        if "args" in cache:
            t_command = self.template.from_string(command)
            command = t_command.render(**cache["args"])

        info, success = utils.run_command(command=command)

        if stdout_arg:
            clean_info = info.decode().strip()
            if "args" in cache:
                cache_args = cache["args"]
                cache_args[stdout_arg] = clean_info
                cache["args"] = cache_args
            else:
                cache["args"] = {stdout_arg: clean_info}

        return info.strip() or command, success

    def _run_workdir(self, workdir, cache):
        """Run file work directory operation.

        :param workdir: Work directory path.
        :type workdir: String
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :returns: tuple
        """

        if "args" in cache:
            t_workdir = self.template.from_string(workdir)
            workdir = t_workdir.render(**cache["args"])

        try:
            os.makedirs(workdir, exist_ok=True)
        except (FileExistsError, PermissionError) as e:
            return str(e), False
        else:
            return "", True

    def _run_transfer(
        self,
        file_to,
        job_id,
        source_file,
        cache,
        user=None,
        group=None,
        file_sha1=None,
        blueprint=False,
    ):
        """Run file transfer operation.

        File transfer operations will look at the cache, then look for an
        existing file, and finally compare the original SHA1 to what is on
        disk. If everything checks out the client will request the file
        from the server.

        If the user and group arguments are defined the file ownership
        will be set accordingly.

        :param file_to: Location where the file will be transferred to.
        :type file_to: String
        :param job_id: Job information marker.
        :type job_id: String
        :param source_file: Original file location on server.
        :type source_file: String
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param user: User name
        :type user: String
        :param group: Group name
        :type group: String
        :param file_sha1: Original file SHA1
        :type file_sha1: String
        :param blueprint: Enable|Disable blueprinting a given file.
        :type blueprint: Boolean
        :returns: tuple
        """

        def blueprinter():
            if blueprint and "args" in cache:
                with open(file_to) as f:
                    file_contents = f.read()

                t_file_contents = self.template.from_string(file_contents)
                file_contents = t_file_contents.render(**cache["args"])
                with open(file_to, "w") as f:
                    f.write(file_contents)

                self.log.info("File %s has been blueprinted.", file_to)

        if os.path.isfile(file_to) and self.file_sha1(file_to) == file_sha1:
            info = "File exists {} and SHA1 {} matches, nothing to transfer".format(
                file_to, file_sha1
            )
            self.log.info(info)
            self.socket_multipart_send(
                zsocket=self.bind_transfer,
                msg_id=job_id.encode(),
                control=self.transfer_end,
            )
            blueprinter()
            return info, True
        else:
            self.log.debug(
                "Requesting transfer of source file:%s", source_file
            )
            self.socket_multipart_send(
                zsocket=self.bind_transfer,
                msg_id=job_id.encode(),
                control=self.job_ack,
                command=b"transfer",
                info=source_file,
            )
        try:
            with open(file_to, "wb") as f:
                while True:
                    try:
                        (
                            _,
                            control,
                            _,
                            data,
                            info,
                        ) = self.socket_multipart_recv(
                            zsocket=self.bind_transfer
                        )
                        if control == self.transfer_end:
                            break
                    except Exception:
                        break
                    else:
                        f.write(data)
        except (FileNotFoundError, NotADirectoryError) as e:
            self.log.critical("Failure when creating file. FAILURE:%s", e)
            return "Failure when creating file", False

        blueprinter()
        info = self.file_sha1(file_to)
        success = True
        if user:
            try:
                if isinstance(user, int):
                    uid = user
                else:
                    uid = pwd.getpwnam(user).pw_uid

                if group:
                    if isinstance(group, int):
                        gid = group
                    else:
                        gid = grp.getgrnam(group).gr_gid
                else:
                    gid = -1
            except KeyError:
                success = False
                info = (
                    "Failed to set ownership properties."
                    " USER:{} GROUP:{}".format(user, group)
                )
                self.log.warn(info)
            else:
                os.chown(file_to, uid, gid)
                success = True

        return info, success

    def _job_loop(self, cache):
        """Execute the job loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        :param cache: Cached access object.
        :type cache: Object
        """

        socks = dict(self.poller.poll(self.heartbeat_interval * 1000))
        if self.bind_job in socks:
            (
                _,
                _,
                command,
                data,
                info,
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

            job_skip_cache = job.get("skip_cache", False)
            if job_skip_cache and command in [b"ADD", b"COPY"]:
                job_skip_cache = False

            _cache_hit = (
                not job_skip_cache and cache.get(job_sha1) == self.job_end
            )
            # Caching does not work for transfers at this stage.
            _cache_allowed = command not in [b"ADD", b"COPY", b"ARG", b"ENV"]

            with utils.ClientStatus(
                socket=self.bind_job, job_id=job_id.encode(), ctx=self
            ) as c:
                if _cache_hit and _cache_allowed:
                    # TODO: Figure out how to skip cache when file transfering.
                    self.log.debug(
                        "Cache hit on {}, task skipped.".format(job_sha1)
                    )
                    c.info = b"job skipped"
                    c.job_state = self.job_end
                    return
                elif command == b"RUN":
                    status, success = self._run_command(
                        command=job["command"],
                        cache=cache,
                        stdout_arg=job.get("stdout_arg"),
                    )
                elif command in [b"ADD", b"COPY"]:
                    status, success = self._run_transfer(
                        file_to=job["file_to"],
                        job_id=job_id,
                        user=job.get("user"),
                        group=job.get("group"),
                        file_sha1=job.get("file_sha1sum"),
                        source_file=info,
                        cache=cache,
                        blueprint=job.get("blueprint", False),
                    )
                elif command == b"WORKDIR":
                    status, success = self._run_workdir(
                        workdir=job["workdir"], cache=cache
                    )
                elif command in [b"ARG", b"ENV"]:
                    cache_args = dict()
                    if "args" in cache:
                        cache_args = cache["args"]
                    for k, v in job["args"].items():
                        cache_args[k] = v
                    else:
                        cache["args"] = cache_args

                    status, success = (b"ARG(s) added to Cache", True)
                elif command == b"CACHEFILE":
                    try:
                        with open(job["cachefile"]) as f:
                            cachefile_args = yaml.safe_load(f)
                    except Exception as e:
                        status = str(e)
                        success = False
                    else:
                        if "args" in cache:
                            cache_args = cache["args"]
                            cache_args.update(cachefile_args)
                            cache["args"] = cache_args
                        else:
                            cache["args"] = cachefile_args

                        status, success = (b"Cache file loaded", True)
                else:
                    self.log.warn(
                        "Unknown command - COMMAND:%s ID:%s",
                        command.decode(),
                        job_id,
                    )
                    return

                if status:
                    if not isinstance(status, bytes):
                        status = status.encode()
                    c.info = status

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
        self.bind_transfer = self.transfer_connect()
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
