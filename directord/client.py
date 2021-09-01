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
        self.manager = self.get_manager()
        self.l_manager = self.manager.dict()
        self.base_component = components.ComponentBase()
        self.cache = dict()

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
        :param job: Information containing the original task specification.
        :type job: Dictionary
        :param job_id: Job UUID
        :type job_id: String
        :param cached: Boolean option to determin if a command is to be
                       treated as cached.
        :type cached: Boolean
        :param command: Byte encoded command used to run a given job.
        :type command: Bytes
        """

        self.log.debug("Running component:%s", command.decode())
        component_kwargs = dict(cache=None, job=job)
        if job.get("parent_async_bypass") is True:
            self.log.debug("Running [ %s ] in bypass queue", job_id)
            self._thread_spawn(
                component_kwargs=component_kwargs,
                command=command,
                info=info,
                cached=cached,
            )
            conn.info = b"bypass task executing"
        elif job.get("parent_async") is True:
            self.log.debug("Running [ %s ] in async queue", job_id)
            self.q_async.put((component_kwargs, command, info, cached))
            conn.info = b"async task queued"
        else:
            self.log.debug("Running [ %s ] in general queue", job_id)
            self.q_general.put((component_kwargs, command, info, cached))
            conn.info = b"general task queued"

    def _thread_spawn(
        self, component_kwargs, command, info, cached, lock=None
    ):
        """Return a thread object.

        Executes a component job and returns the thread object.

        :param component_kwargs: Named arguments used with the componenet
                                 client.
        :type component_kwargs: Dictionary
        :param command: Byte encoded command used to run a given job.
        :type command: Bytes
        :param info: Information that was sent over with the original message.
        :type info: Bytes
        :param cached: Boolean option to determin if a command is to be
                       treated as cached.
        :type cached: Boolean
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        :param daemon: Enable|Disable deamonic threads.
        :type daemon: Boolean
        :returns: Object
        """

        if not lock:
            lock = self.get_lock()

        thread = self.thread(
            target=self.job_q_component_run,
            args=(
                component_kwargs,
                command,
                info,
                cached,
                lock,
            ),
        )
        thread.daemon = True
        thread.start()
        return thread

    def job_q_processor(self, queue, processes=1):
        """Process a given work queue.

        The defined `queue` is processed. The `processes` arg allows this
        method to spawn N processes.

        :param queue: Multiprocessing queue object.
        :type queue: Object
        :param processes: Number of possible processes to spawn
        :type processes: Integer
        """

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
                    ) = queue.get()
                except Exception:
                    time.sleep(0.1)
                else:
                    threads.append(
                        self._thread_spawn(
                            component_kwargs=component_kwargs,
                            command=command,
                            info=info,
                            cached=cached,
                            lock=lock,
                        )
                    )
            else:
                self.log.debug("Worker threads: %s", len(threads))
                for t in threads:
                    t.join()

    def job_q_component_run(
        self, component_kwargs, command, info, cached, lock
    ):
        """Execute a component operation.

        Components are dynamically loaded based on the given component name.
        Upon execution, the results are put into the results queue.

        :param component_kwargs: Named arguments used with the componenet
                                 client.
        :type component_kwargs: Dictionary
        :param command: Byte encoded command used to run a given job.
        :type command: Bytes
        :param info: Information that was sent over with the original message.
        :type info: Bytes
        :param cached: Boolean option to determin if a command is to be
                       treated as cached.
        :type cached: Boolean
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        success, _, component = directord.component_import(
            component=command.decode().lower(),
            job_id=component_kwargs["job"]["job_id"],
        )

        if not success:
            self.log.warning("Component lookup failure [ %s ]", component)
            self.q_return.put(
                (
                    None,
                    None,
                    success,
                    None,
                    component_kwargs["job"],
                    command,
                    0,
                    None,
                )
            )
        elif cached and component.cacheable is True:
            self.log.info(
                "Cache hit on [ %s ], task skipped.",
                component_kwargs["job"]["job_id"],
            )
            self.q_return.put(
                (
                    None,
                    None,
                    "skipped",
                    None,
                    component_kwargs["job"],
                    command,
                    0,
                    None,
                )
            )
        else:
            self.log.debug(
                "Starting component execution for job [ %s ].",
                component_kwargs["job"]["job_id"],
            )
            # Set the comment command argument
            setattr(component, "command", command)
            setattr(component, "info", info)
            setattr(component, "driver", self.driver)

            locked = False
            parent_lock = self.l_manager.get(
                component_kwargs["job"].get("parent_sha3_224")
            )
            with self.timeout(
                time=component_kwargs["job"].get("timeout", 600),
                job_id=component_kwargs["job"]["job_id"],
            ):
                if parent_lock:
                    parent_lock["lock"].acquire()
                    parent_lock["locked"] = True

                if component.requires_lock:
                    lock.acquire()
                    locked = True

                _starttime = time.time()
                self.q_return.put(
                    component.client(
                        cache=self.cache, job=component_kwargs["job"]
                    )
                    + (
                        component_kwargs["job"],
                        command,
                        time.time() - _starttime,
                        component.block_on_tasks,
                    )
                )

            if locked:
                lock.release()

            if component.block_on_tasks:
                block_on_task_data = component.block_on_tasks[-1]
                block_on_task = True
                with self.timeout(
                    time=block_on_task_data.get("timeout", 600),
                    job_id=block_on_task_data["job_sha3_224"],
                ):
                    while block_on_task:
                        if self.cache.get(
                            block_on_task_data["job_sha3_224"]
                        ) in [
                            self.driver.job_end.decode(),
                            self.driver.job_failed.decode(),
                            self.driver.nullbyte.decode(),
                        ]:
                            block_on_task = False
                        else:
                            self.log.debug(
                                "waiting for callback job to complete. %s",
                                block_on_task_data,
                            )
                            time.sleep(1)

                self.log.debug(
                    "Task sha [ %s ] callback complete",
                    block_on_task_data["job_sha3_224"],
                )

            if parent_lock:
                parent_lock["used"] = time.time()
                parent_lock["lock"].release()
                parent_lock["locked"] = False

            self.log.debug(
                "Component execution complete for job [ %s ].",
                component_kwargs["job"]["job_id"],
            )

    def _set_job_status(
        self, stdout, stderr, outcome, return_info, job, block_on_tasks, conn
    ):
        """Set job status.

        :param stdout: Execution standard output.
        :type stdout: String|Bytes
        :param stderr: Execution standard error.
        :type stderr: String|Bytes
        :param outcome: Outcome status information.
        :type outcome: Boolean|String
        :param return_info: Information returning from component execution.
        :type return_info: Bytes
        :param job: Job definition
        :type job: Dictionary
        :param block_on_tasks: Job to post back to the server to create
                               a new task which the client will wait
                               for.
        :type block_on_tasks: List
        :param conn: Job bind connection object.
        :type conn: Object
        """

        if stdout:
            stdout = stdout.strip()
            if not isinstance(stdout, bytes):
                stdout = stdout.encode()
            conn.stdout = stdout
            self.log.debug("Job [ %s ], stdout: %s", job["job_id"], stdout)

        if stderr:
            stderr = stderr.strip()
            if not isinstance(stderr, bytes):
                stderr = stderr.encode()
            conn.stderr = stderr
            self.log.error(stderr)

        if outcome is False:
            state = conn.job_state = self.driver.job_failed
            self.log.error("Job failed [ %s ]", job["job_id"])
        elif outcome is True:
            state = conn.job_state = self.driver.job_end
            self.log.info("Job complete [ %s ]", job["job_id"])
        elif outcome == "skipped":
            self.log.info("Job skipped [ %s ]", job["job_id"])
            conn.info = b"task skipped"
            state = conn.job_state = self.driver.job_end
        else:
            state = conn.job_state = self.driver.nullbyte

        conn.info = b"task finished"
        if return_info:
            conn.info = return_info

        if block_on_tasks:
            job["new_tasks"] = block_on_tasks

        if "new_tasks" in job:
            conn.data = json.dumps(job).encode()
        else:
            conn.data = json.dumps(
                {"execution_time": job["execution_time"]}
            ).encode()

        if job["parent_id"]:
            self.base_component.set_cache(
                cache=self.cache,
                key=job["parent_id"],
                value=state,
                tag="parents",
            )

        self.base_component.set_cache(
            cache=self.cache,
            key=job["job_sha3_224"],
            value=state,
            tag="jobs",
        )

    def job_q_results(self):
        """Job results queue processor.

        Results are retrieved from the queue and status is set.
        """

        try:
            (
                stdout,
                stderr,
                outcome,
                return_info,
                job,
                command,
                execution_time,
                block_on_tasks,
            ) = self.q_return.get_nowait()
        except Exception:
            pass
        else:
            self.log.debug("Found task results for [ %s ].", job["job_id"])
            with utils.ClientStatus(
                socket=self.bind_job,
                job_id=job["job_id"].encode(),
                command=command,
                ctx=self,
            ) as c:
                job["execution_time"] = execution_time
                self._set_job_status(
                    stdout,
                    stderr,
                    outcome,
                    return_info,
                    job,
                    block_on_tasks,
                    c,
                )

    def _parent_check(self, conn, cache, job):
        """Check if a parent job has failed.

        This will check if tasks under a given parent job are allowed to
        continue executing.

        :param conn: Job bind connection object.
        :type conn: Object
        :param cache: Caching object used to save information to the local
                      client.
        :type cache: Object
        :param job: Job definition
        :type job: Dictionary

        :returns: Boolean
        """
        if cache.get(job["parent_id"]) == self.driver.job_failed.decode():
            self.log.error(
                "Parent failure %s skipping %s",
                job["parent_id"],
                job["job_id"],
            )
            status = (
                "Job [ {} ] was not allowed to run because"
                " there was a failure under this partent ID"
                " [ {} ]".format(job["job_id"], job["parent_id"])
            )

            self.log.error(status)
            conn.info = status.encode()
            conn.job_state = self.driver.job_failed
            return False
        else:
            return True

    def prune_locks(self):
        """Prune inactive parent lock items.

        When the async queue is empty and parent lock has not been used for
        more than 60 seconds, and is not currently locked, this method will
        prune the locked objects from the l_manager.

        > If a parent lock is older that 2400 seconds, and the queue async
          queue is empty, the parent lock will be considered stale and pruned.
        """

        if self.q_async.empty():
            for key, value in self.l_manager.items():
                if time.time() > value["used"] + 60:
                    if not value["locked"]:
                        self.log.debug("Pruning parent lock [ %s ]", key)
                        self.l_manager.pop(key)
                elif time.time() > value["used"] + 2400:
                    self.log.warning(
                        "Stale parent lock found [ %s ], pruning", key
                    )
                    self.l_manager.pop(key)

    def prune_cache(self, cache_check_time):
        """Prune the local cache to ensure a tidy environment.

        If there are any warnings when pruning, they will be logged.

        :param cache_check_time: Timestamp from last prune.
        :type cache_check_time: Float
        :returns: Float
        """

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
                return time.time()

        return cache_check_time

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
            self.prune_locks()
            cache_check_time = self.prune_cache(
                cache_check_time=cache_check_time
            )

            if time.time() > poller_time + 64:
                if poller_interval != 2048:
                    self.log.info("Directord client entering idle state.")
                poller_interval = 2048
            elif time.time() > poller_time + 32:
                if poller_interval != 1024:
                    self.log.info("Directord client ramping down.")
                poller_interval = 1024

            if self.driver.bind_check(
                bind=self.bind_job, constant=poller_interval
            ):
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
                job["job_id"] = job_id = job.get("job_id", utils.get_uuid())
                job["job_sha3_224"] = job_sha3_224 = job.get(
                    "job_sha3_224", utils.object_sha3_224(job)
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
                job_parent_sha3_224 = job.get("parent_sha3_224")
                if job_parent_sha3_224:
                    self.l_manager[job_parent_sha3_224] = {
                        "lock": self.manager.Lock(),
                        "used": time.time(),
                        "locked": False,
                    }

                self.log.info(
                    "Item received: parent job UUID [ %s ],"
                    " parent job sha3_224 [ %s ], job UUID [ %s ],"
                    " job sha3_224 [ %s ]",
                    job_parent_id,
                    job_parent_sha3_224,
                    job_id,
                    job_sha3_224,
                )

                with utils.ClientStatus(
                    socket=self.bind_job,
                    job_id=job_id.encode(),
                    command=command,
                    ctx=self,
                ) as c:
                    if job_parent_id and not self._parent_check(
                        conn=c, cache=self.cache, job=job
                    ):
                        self.q_return.put(
                            (
                                None,
                                None,
                                False,
                                b"Job omitted, parent failure",
                                job,
                                command,
                                0,
                                None,
                            )
                        )
                        if sentinel:
                            break
                    else:
                        c.job_state = self.driver.job_processing
                        self._job_executor(
                            conn=c,
                            info=info,
                            job=job,
                            job_id=job_id,
                            cached=(
                                self.cache.get(job_sha3_224)
                                == self.driver.job_end.decode()
                                and not job_skip_cache
                            ),
                            command=command,
                        )

            if sentinel:
                break

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            (self.thread(target=self.run_heartbeat), True),
            (self.thread(target=self.run_job), False),
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
        with diskcache.Cache(
            self.args.cache_path,
            tag_index=True,
            disk=diskcache.JSONDisk,
        ) as cache:
            self.cache = cache
            self.run_threads(threads=threads)
