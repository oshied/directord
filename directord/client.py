#   Copyright Peznauts <kevin@cloudnull.com>. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.

import datetime
import json
import os
import struct
import time

import diskcache

import directord
from directord import components
from directord import interface
from directord import utils


class Client(interface.Interface):
    """Directord client class."""

    def __init__(self, args):
        """Initialize the Directord client.

        Sets up the client object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Client, self).__init__(args=args)

        self.heartbeat_failure_interval = 2
        self.bind_heatbeat = None
        self.q_async = self.get_queue()
        self.q_general = self.get_queue()
        self.q_return = self.get_queue()
        self.base_component = components.ComponentBase()

    def update_heartbeat(self):
        with open("/proc/uptime", "r") as f:
            uptime = float(f.readline().split()[0])

        self.driver.socket_send(
            socket=self.bind_heatbeat,
            control=self.driver.heartbeat_notice,
            data=json.dumps(
                {
                    "version": directord.__version__,
                    "uptime": str(datetime.timedelta(seconds=uptime)),
                }
            ).encode(),
        )
        self.log.debug(
            "Sent heartbeat to server.",
        )

    def run_heartbeat(self, sentinel=False, heartbeat_misses=0):
        """Execute the heartbeat loop.

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.

        This loop tracks heartbeat messages and should the heartbeat
        interval take longer than the expire time, and fail more than 5
        times the connection will be reset after a failure cooldown.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean

        :param heartbeat_misses: Sets the current misses.
        :type heartbeat_misses: Integer
        """

        self.bind_heatbeat = self.driver.heartbeat_connect()
        self.update_heartbeat()
        heartbeat_at = self.driver.get_heartbeat(
            interval=self.heartbeat_interval
        )
        while True:
            self.log.debug("Heartbeat misses [ %s ]", heartbeat_misses)
            if self.bind_heatbeat and self.driver.bind_check(
                interval=self.heartbeat_interval, bind=self.bind_heatbeat
            ):
                (
                    _,
                    _,
                    command,
                    _,
                    info,
                    _,
                    _,
                ) = self.driver.socket_recv(socket=self.bind_heatbeat)
                self.log.debug("Heartbeat received from server.")
                if command == b"reset":
                    self.log.warning(
                        "Received heartbeat reset command. Connection"
                        " resetting."
                    )
                    (
                        heartbeat_at,
                        self.bind_heatbeat,
                    ) = self.driver.heartbeat_reset(
                        bind_heatbeat=self.bind_heatbeat
                    )
                else:
                    heartbeat_at = struct.unpack("<f", info)[0]
                    heartbeat_misses = 0

                self.heartbeat_failure_interval = 2
            else:
                if time.time() > heartbeat_at and heartbeat_misses > 5:
                    self.log.error("Heartbeat failure, can't reach server")
                    self.log.warning(
                        "Reconnecting in [ %s ]...",
                        self.heartbeat_failure_interval,
                    )

                    time.sleep(self.heartbeat_failure_interval)
                    if self.heartbeat_failure_interval < 32:
                        self.heartbeat_failure_interval *= 2

                    self.log.debug("Running reconnection.")
                    (
                        heartbeat_at,
                        self.bind_heatbeat,
                    ) = self.driver.heartbeat_reset(
                        bind_heatbeat=self.bind_heatbeat
                    )
                    heartbeat_at = self.driver.get_expiry(
                        heartbeat_interval=self.heartbeat_interval,
                        interval=self.heartbeat_liveness,
                    )
                else:
                    heartbeat_misses += 1
                    self.update_heartbeat()

            if sentinel:
                break

    def _job_executor(
        self,
        conn,
        info,
        job,
        job_id,
        cached,
        command,
    ):
        """Queue a given job.

        :param conn: Connection object used to store information used in a
                     return message.
        :type conn: Object
        :param info: Information that was sent over with the original message.
        :type info: Bytes
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :param job_id: Job UUID
        :type job_id: String
        :param cached: Boolean option to determin if a command is to be
                       treated as cached.
        :type cached: Boolean
        :param command: Byte encoded command used to run a given job.
        :type command: Bytes
        :returns: Tuple
        """

        self.log.debug("Running component:%s", command.decode())
        component_kwargs = dict(cache=None, job=job)
        conn.start_processing()
        if job.get("parent_async"):
            self.log.debug("Running [ %s ] in parent async", job_id)
            self.q_async.put((component_kwargs, command, info, cached))
            conn.info = b"job queued"
        else:
            self.log.debug("Running [ %s ] in general queue", job_id)
            self.q_general.put((component_kwargs, command, info, cached))
            conn.info = b"job queued"

    def job_q_component_run(
        self, component_kwargs, command, info, cached, lock
    ):
        success, _, component = directord.component_import(
            component=command.decode().lower(),
            job_id=component_kwargs["job"]["job_id"],
        )

        if not success:
            self.log.warning(component)
            self.q_return.put(
                (None, None, success, None, component_kwargs["job"], command)
            )
            return

        if cached and component.cacheable:
            self.log.info(
                "Cache hit on [ %s ], task skipped.",
                component_kwargs["job"]["job_id"],
            )
            self.q_return.put(
                (None, None, "skipped", None, component_kwargs["job"], command)
            )
            return

        # Set the comment command argument
        setattr(component, "command", command)
        setattr(component, "info", info)
        setattr(component, "driver", self.driver)

        locked = False
        if component.requires_lock:
            lock.acquire()
            locked = True

        with self.timeout(
            time=component_kwargs["job"].get("timeout", 600),
            job_id=component_kwargs["job"]["job_id"],
        ):
            with diskcache.Cache(
                self.args.cache_path,
                tag_index=True,
                disk=diskcache.JSONDisk,
            ) as cache:
                component_kwargs["cache"] = cache
                try:
                    self.q_return.put(
                        component.client(**component_kwargs)
                        + (component_kwargs["job"], command)
                    )
                finally:
                    if locked:
                        lock.release()

    def job_q_processor(self, queue, processes=1):
        lock = self.get_lock()
        while True:
            threads = list()
            for _ in range(processes):
                try:
                    (
                        component_kwargs,
                        command,
                        info,
                        cached,
                    ) = queue.get_nowait()
                except Exception:
                    time.sleep(0.1)
                else:
                    t = self.thread(
                        target=self.job_q_component_run,
                        args=(
                            component_kwargs,
                            command,
                            info,
                            cached,
                            lock,
                        ),
                    )
                    t.daemon = True
                    t.start()
                    threads.append(t)
                    self.log.debug("Worker threads: %s", len(threads))
            else:
                for t in threads:
                    t.join()

    def job_q_results(self):
        try:
            (
                stdout,
                stderr,
                outcome,
                return_info,
                job,
                command,
            ) = self.q_return.get_nowait()
        except Exception:
            pass
        else:
            self.log.debug("Found job results for job [ %s ].", job["job_id"])
            with utils.ClientStatus(
                socket=self.bind_job,
                job_id=job["job_id"].encode(),
                command=command,
                ctx=self,
            ) as c:
                self._set_job_status(
                    stdout,
                    stderr,
                    outcome,
                    return_info,
                    job,
                    command,
                    c,
                )

    def run_job(self, sentinel=False):
        """Job entry point.

        This creates a cached access object, connects to the socket and begins
        the loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 128.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_job = self.driver.job_connect()
        poller_time = time.time()
        poller_interval = 128
        cache_check_time = time.time()

        # Ensure that the cache path exists before executing.
        os.makedirs(self.args.cache_path, exist_ok=True)
        while True:
            self.job_q_results()

            if time.time() > poller_time + 64:
                if poller_interval != 2048:
                    self.log.info("Directord client entering idle state.")
                poller_interval = 2048
            elif time.time() > poller_time + 32:
                if poller_interval != 1024:
                    self.log.info("Directord client ramping down.")
                poller_interval = 1024

            if time.time() > cache_check_time + 4096:
                with diskcache.Cache(
                    self.args.cache_path, tag_index=True
                ) as cache:
                    self.log.info(
                        "Current estimated cache size: %s KiB",
                        cache.volume() / 1024,
                    )

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

                    cache.expire()
                    cache_check_time = time.time()

            if self.driver.bind_check(
                bind=self.bind_job, constant=poller_interval
            ):
                with diskcache.Cache(
                    self.args.cache_path,
                    tag_index=True,
                    disk=diskcache.JSONDisk,
                ) as cache:
                    poller_interval, poller_time = 64, time.time()
                    (
                        _,
                        _,
                        command,
                        data,
                        info,
                        _,
                        _,
                    ) = self.driver.socket_recv(socket=self.bind_job)
                    job = json.loads(data.decode())
                    job["job_id"] = job_id = job.get("task", utils.get_uuid())
                    job["job_sha256"] = job_sha256 = job.get(
                        "task_sha256sum", utils.object_sha256(job)
                    )
                    self.driver.socket_send(
                        socket=self.bind_job,
                        msg_id=job_id.encode(),
                        control=self.driver.job_ack,
                    )

                    job_skip_cache = job.get(
                        "skip_cache", job.get("ignore_cache", False)
                    )

                    job_parent_id = job.get("parent_id")
                    job_parent_sha1 = job.get("parent_sha1")

                    self.log.info(
                        "Job received: parent job UUID [ %s ],"
                        " parent job SHA1 [ %s ], task UUID [ %s ],"
                        " task SHA256 [ %s ]",
                        job_parent_id,
                        job_parent_sha1,
                        job_id,
                        job_sha256,
                    )

                    cache_hit = (
                        cache.get(job_sha256) == self.driver.job_end.decode()
                        and not job_skip_cache
                    )

                    with utils.ClientStatus(
                        socket=self.bind_job,
                        job_id=job_id.encode(),
                        command=command,
                        ctx=self,
                    ) as c:
                        if (
                            cache.get(job_parent_id)
                            == self.driver.job_failed.decode()
                        ):
                            self.log.error(
                                "Parent failure %s skipping %s",
                                job_parent_id,
                                job_id,
                            )
                            status = (
                                "Job [ {} ] was not allowed to run because"
                                " there was a failure under this partent ID"
                                " [ {} ]".format(job_id, job_parent_id)
                            )

                            self.log.error(status)
                            c.info = status.encode()
                            c.job_state = self.driver.job_failed

                            self.base_component.set_cache(
                                cache=cache,
                                key=job_sha256,
                                value=self.driver.job_failed,
                                tag="jobs",
                            )

                            if sentinel:
                                break

                            continue

                        _job_exec = self._job_executor(
                            conn=c,
                            info=info,
                            job=job,
                            job_id=job_id,
                            cached=cache_hit,
                            command=command,
                        )

                        if _job_exec is None:
                            c.job_state = self.driver.job_processing
                        else:
                            self._set_job_status(
                                *_job_exec,
                                c,
                            )

            if sentinel:
                break

    def _set_job_status(
        self, stdout, stderr, outcome, return_info, job, command, c
    ):
        if stdout:
            stdout = stdout.strip()
            if not isinstance(stdout, bytes):
                stdout = stdout.encode()
            c.stdout = stdout
            self.log.debug("Job [ %s ], stdout: %s", job["job_id"], stdout)

        if stderr:
            stderr = stderr.strip()
            if not isinstance(stderr, bytes):
                stderr = stderr.encode()
            c.stderr = stderr
            self.log.error(stderr)

        c.info = b"job finished"
        if outcome is False:
            state = c.job_state = self.driver.job_failed
            self.log.error("Job failed %s", job["job_id"])
        elif outcome is True:
            state = c.job_state = self.driver.job_end
            self.log.info("Job complete %s", job["job_id"])
        elif outcome == "skipped":
            c.info = b"job skipped"
            state = c.job_state = self.driver.job_end
        else:
            state = self.driver.nullbyte

        if return_info:
            c.info = return_info

        if command == b"QUERY":
            c.data = json.dumps(job).encode()
            if stdout:
                c.info = stdout

        with diskcache.Cache(
            self.args.cache_path,
            tag_index=True,
            disk=diskcache.JSONDisk,
        ) as cache:
            if job["parent_id"]:
                self.base_component.set_cache(
                    cache=cache,
                    key=job["parent_id"],
                    value=state,
                    tag="parents",
                )

            self.base_component.set_cache(
                cache=cache,
                key=job["job_sha256"],
                value=state,
                tag="jobs",
            )

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            (self.thread(target=self.run_heartbeat), True),
            (self.thread(target=self.run_job), True),
            (
                self.thread(
                    target=self.job_q_processor, args=(self.q_general,)
                ),
                False,
            ),
            (
                self.thread(
                    target=self.job_q_processor,
                    args=(
                        self.q_async,
                        4,
                    ),
                ),
                False,
            ),
        ]
        self.run_threads(threads=threads)
