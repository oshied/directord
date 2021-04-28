import grp
import json
import os
import pwd
import struct
import time
import yaml

import diskcache
import zmq

from directord import manager
from directord import utils


class Client(manager.Interface):
    """Directord client class."""

    def __init__(self, args):
        """Initialize the Directord client.

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

    def heartbeat_connect(self):
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
        self.bind_heatbeat = self.heartbeat_connect()
        return self.get_heartbeat

    def run_heartbeat(self):
        """Execute the heartbeat loop.

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.

        This loop tracks heartbeat messages and should the heartbeat
        interval take longer than the expire time, and fail more than 5
        times the connection will be reset after a failure cooldown.
        """

        self.bind_heatbeat = self.heartbeat_connect()
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
                    self.log.warning(
                        "Received heartbeat reset command. Connection"
                        " resetting."
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
                    self.log.warning(
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

        command = self.blueprinter(content=command, values=cache.get("args"))
        if not command:
            return None, False

        info, success = utils.run_command(
            command=command, env=cache.get("envs")
        )

        if stdout_arg:
            clean_info = info.decode().strip()
            self.set_cache(
                cache=cache,
                key="args",
                value={stdout_arg: clean_info},
                value_update=True,
                tag="args",
            )

        return info.strip() or command, success

    def _run_workdir(self, workdir, cache):
        """Run file work directory operation.

        :param workdir: Work directory path.
        :type workdir: String
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :returns: tuple
        """

        workdir = self.blueprinter(content=workdir, values=cache.get("args"))
        if not workdir:
            return None, False
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

        file_to = self.blueprinter(content=file_to, values=cache.get("args"))
        if os.path.isfile(file_to) and self.file_sha1(file_to) == file_sha1:
            info = (
                "File exists {} and SHA1 {} matches, nothing to"
                " transfer".format(file_to, file_sha1)
            )
            self.log.info(info)
            self.socket_multipart_send(
                zsocket=self.bind_transfer,
                msg_id=job_id.encode(),
                control=self.transfer_end,
            )
            if blueprint and not self.file_blueprinter(
                cache=cache, file_to=file_to
            ):
                return None, False

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

        if blueprint and not self.file_blueprinter(
            cache=cache, file_to=file_to
        ):
            return None, False

        info = self.file_sha1(file_to)
        success = True
        if user:
            try:
                try:
                    uid = int(user)
                except ValueError:
                    uid = pwd.getpwnam(user).pw_uid

                if group:
                    try:
                        gid = int(group)
                    except ValueError:
                        gid = grp.getgrnam(group).gr_gid
                else:
                    gid = -1
            except KeyError:
                success = False
                info = (
                    "Failed to set ownership properties."
                    " USER:{} GROUP:{}".format(user, group)
                )
                self.log.warning(info)
            else:
                os.chown(file_to, uid, gid)
                success = True

        return info, success

    def _job_executor(
        self,
        conn,
        cache,
        info,
        job,
        job_parent_id,
        job_id,
        job_sha1,
        cached,
        command,
    ):
        """Execute a given job.

        :param conn: Connection object used to store information used in a
                     return message.
        :type conn: Object
        :param cache: Cached access object.
        :type cache: Object
        :param info: Information that was sent over with the original message.
        :type info: Bytes
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :param job_parent_id: Parent UUID for a given job.
        :type job_parent_id: String
        :param job_id: Job UUID
        :type job_id: String
        :param job_sha1: Job fingerprint in SHA1 format.
        :type job_sha1: String
        :param cached: Boolean option to determin if a command is to be
                       treated as cached.
        :type cached: Boolean
        :param command: Byte encoded command used to run a given job.
        :type command: Bytes
        :returns: Tuple
        """

        # Set the parent ID value to True, if set False all jobs with
        # this parent ID will halt and fail.
        if job_parent_id and cache.get(job_parent_id):
            if cache.get(job_parent_id) is False:
                status = (
                    "Job [ {} ] was not allowed to run because there"
                    " was a failure under this partent ID"
                    " [ {} ]".format(job_id, job_parent_id)
                )
                self.log.error(status)
                conn.info = status.encode()
                conn.job_state = self.job_failed
                self.set_cache(
                    cache=cache, key=job_sha1, value=conn.job_state, tag="jobs"
                )
                return None, None
        else:
            # Parent ID information is set to automatically expire
            # after 24 hours.
            self.set_cache(
                cache=cache, key=job_parent_id, value=True, tag="parents"
            )

        if cached:
            # TODO: Figure out how to skip cache when file transfering.
            self.log.debug("Cache hit on {}, task skipped.".format(job_sha1))
            conn.info = b"job skipped"
            conn.job_state = self.job_end
            return None, None
        elif command == b"RUN":
            conn.start_processing()
            return self._run_command(
                command=job["command"],
                cache=cache,
                stdout_arg=job.get("stdout_arg"),
            )
        elif command in [b"ADD", b"COPY"]:
            conn.start_processing()
            return self._run_transfer(
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
            conn.start_processing()
            return self._run_workdir(workdir=job["workdir"], cache=cache)
        elif command in [b"ARG", b"ENV"]:
            conn.start_processing()
            # Sets the cache type to "args" or "envs"
            cache_type = "{}s".format(command.decode().lower())
            self.set_cache(
                cache=cache,
                key=cache_type,
                value=job[cache_type],
                value_update=True,
                tag=cache_type,
            )
            return "{} added to cache".format(cache_type).encode(), True
        elif command == b"CACHEFILE":
            conn.start_processing()
            try:
                with open(job["cachefile"]) as f:
                    cachefile_args = yaml.safe_load(f)
            except Exception as e:
                return str(e), False
            else:
                self.set_cache(
                    cache=cache,
                    key="args",
                    value=cachefile_args,
                    value_update=True,
                    tag="args",
                )
                return b"Cache file loaded", True
        elif command == b"CACHEEVICT":
            conn.start_processing()
            tag = job["cacheevict"]
            if tag == "all":
                evicted = cache.clear()
            else:
                evicted = cache.evict(tag)
            return (
                "Evicted {} items, tagged {}".format(evicted, tag).encode(),
                True,
            )
        elif command == b"QUERY":
            conn.start_processing()
            args = cache.get("args")
            if args:
                query = json.dumps(args.get(job["query"])).encode()
            else:
                query = None
            return query, True
        else:
            self.log.warning(
                "Unknown command - COMMAND:%s ID:%s",
                command.decode(),
                job_id,
            )
            return None, None

    def file_blueprinter(self, cache, file_to):
        """Read a file and blueprint its contents.

        :param cache: Cached access object.
        :type cache: Object
        :param file_to: String path to a file which will blueprint.
        :type file_to: String
        :returns: Boolean
        """

        with open(file_to) as f:
            file_contents = self.blueprinter(
                content=f.read(), values=cache.get("args")
            )
            if not file_contents:
                return False

        with open(file_to, "w") as f:
            f.write(file_contents)

        self.log.info("File %s has been blueprinted.", file_to)
        return True

    def blueprinter(self, content, values):
        """Return blue printed content.

        :param content: A string item that will be interpreted and blueprinted.
        :type content: String
        :param values: Dictionary items that will be used to render a
                       blueprinted item.
        :type values: Dictionary
        :returns: String | None
        """

        if values:
            _contents = self.blueprint.from_string(content)
            try:
                return _contents.render(**values)
            except Exception:
                return
        else:
            return content

    @staticmethod
    def set_cache(
        cache, key, value, value_update=False, expire=28800, tag=None
    ):
        """Set a cached item.

        :param cache: Cached access object.
        :type cache: Object
        :param key: Key for the cached item.
        :type key: String
        :param value: Value for the cached item.
        :type value: ANY
        :param value_update: Instructs the method to update a Dictionary with
                             another dictionary.
        :type value_update: Boolean
        :param expire: Sets the expire time, defaults to 12 hours.
        :type expire: Integer
        :param tag: Sets the index for a given cached item.
        :type tag: String
        """

        if value_update:
            orig = cache.pop(key, default=dict())
            value = utils.merge_dict(orig, value)

        cache.set(key, value, tag=tag, expire=expire)

    def run_job(self):
        """Job entry point.

        This creates a cached access object, connects to the socket and begins
        the loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 128.
        """

        self.bind_job = self.job_connect()
        self.bind_transfer = self.transfer_connect()
        poller_time = time.time()
        poller_interval = 1024
        cache_check_time = time.time()

        # Ensure that the cache path exists before executing.
        os.makedirs(self.args.cache_path, exist_ok=True)
        with diskcache.Cache(self.args.cache_path) as cache:
            while True:
                if time.time() > poller_time + 64:
                    if poller_interval != 2048:
                        self.log.info("Directord client entering idle state.")
                    poller_interval = 2048

                elif time.time() > poller_time + 32:
                    if poller_interval != 1024:
                        self.log.info("Directord client ramping down.")
                    poller_interval = 1024

                if time.time() > cache_check_time + 4096:
                    self.log.info(
                        "Current estimated cache size: %s KiB",
                        cache.volume() / 1024,
                    )
                    cache.cull()
                    warnings = cache.check()
                    if warnings:
                        self.log.warning(
                            "Client cache noticed %s warnings.", len(warnings)
                        )
                        for item in warnings:
                            self.log.warning(
                                "Client Cache Warning: [ %s ].",
                                str(item.message),
                            )
                    cache_check_time = time.time()

                if self.bind_job in dict(self.poller.poll(poller_interval)):
                    poller_interval, poller_time = 128, time.time()
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

                    job_skip_cache = job.get(
                        "skip_cache", job.get("ignore_cache", False)
                    )

                    job_parent_id = job.get("parent_id")

                    cache_hit = (
                        not job_skip_cache
                        and cache.get(job_sha1) == self.job_end
                    )

                    # Caching does not work for transfers at this stage.
                    cache_allowed = command not in [
                        b"ADD",
                        b"COPY",
                        b"ARG",
                        b"ENV",
                        b"CACHEFILE",
                        b"CACHEEVICT",
                        b"QUERY",
                    ]
                    cached = cache_hit and cache_allowed
                    success, status, state = False, None, self.nullbyte
                    with utils.ClientStatus(
                        socket=self.bind_job,
                        job_id=job_id.encode(),
                        command=command,
                        ctx=self,
                    ) as c:
                        with self.timeout(
                            time=job.get("timeout", 600), job_id=job_id
                        ):
                            status, success = self._job_executor(
                                conn=c,
                                cache=cache,
                                info=info,
                                job=job,
                                job_parent_id=job_parent_id,
                                job_id=job_id,
                                job_sha1=job_sha1,
                                cached=cached,
                                command=command,
                            )

                        if command == b"QUERY":
                            c.data = json.dumps(job).encode()

                        if status:
                            if not isinstance(status, bytes):
                                status = status.encode()
                            c.info = status

                        if success is False:
                            state = c.job_state = self.job_failed
                            self.log.error("Job failed {}".format(job_id))
                            self.set_cache(
                                cache=cache,
                                key=job_parent_id,
                                value=False,
                                tag="parents",
                            )

                        elif success is True:
                            state = c.job_state = self.job_end
                            self.log.info("Job complete {}".format(job_id))

                    self.set_cache(
                        cache=cache, key=job_sha1, value=state, tag="jobs"
                    )

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
