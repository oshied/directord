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
        self.cache = dict()
        self.start_time = time.time()

    def update_heartbeat(self):
        with open("/proc/uptime", "r") as f:
            uptime = float(f.readline().split()[0])

        self.driver.socket_send(
            socket=self.bind_heatbeat,
            control=self.driver.heartbeat_notice,
            data=json.dumps(
                {
                    "version": directord.__version__,
                    "host_uptime": str(datetime.timedelta(seconds=uptime)),
                    "agent_uptime": str(
                        datetime.timedelta(
                            seconds=(time.time() - self.start_time)
                        )
                    ),
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
        lock=None,
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
        :param parent_lock: Locking object, used if defined.
        :type parent_lock: Object
        """

        if not lock:
            lock = self.get_lock()

        component_kwargs = dict(cache=None, job=job)
        if job.get("parent_async_bypass") is True:
            self.log.debug(
                "Running component:%s, job_id:[ %s ] in bypass",
                job_id,
                command.decode(),
            )
            self._thread_spawn(
                component_kwargs=component_kwargs,
                command=command,
                info=info,
                cached=cached,
                lock=lock,
            )
            conn.info = b"bypass task executing"
        elif job.get("parent_async") is True:
            self.log.debug(
                "Running component:%s, job_id:[ %s ] in async queue",
                job_id,
                command.decode(),
            )
            self.q_async.put((component_kwargs, command, info, cached))
            conn.info = b"async task queued"
        else:
            self.log.debug(
                "Running component:%s, job_id:[ %s ] in general queue",
                job_id,
                command.decode(),
            )
            self.q_general.put((component_kwargs, command, info, cached))
            conn.info = b"general task queued"

    def _thread_spawn(
        self,
        component_kwargs,
        command,
        info,
        cached,
        lock=None,
        parent_lock=None,
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
        :param parent_lock: Locking object, used if defined.
        :type parent_lock: Object
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
                parent_lock,
            ),
        )
        thread.daemon = True
        thread.start()
        return thread

    def job_q_processor(self, queue, processes=1, lock=None):
        """Process a given work queue.

        The defined `queue` is processed. The `processes` arg allows this
        method to spawn N processes.

        :param queue: Multiprocessing queue object.
        :type queue: Object
        :param processes: Number of possible processes to spawn
        :type processes: Integer
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        if not lock:
            lock = self.get_lock()

        interval = 0.25
        parent_locks_tracker = set()
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
                except ValueError as e:
                    self.log.critical(
                        "Queue object value error [ %s ]", str(e)
                    )
                    interval = 1
                except Exception:
                    interval = 1
                else:
                    interval = 0.25
                    parent_lock = None
                    parent_sha3_224 = component_kwargs["job"].get(
                        "parent_sha3_224"
                    )
                    if parent_sha3_224:
                        if not hasattr(self, parent_sha3_224):
                            parent_lock = self.get_lock()
                            setattr(self, parent_sha3_224, parent_lock)
                            self.log.debug(
                                "Set dynamic class lock: %s", parent_sha3_224
                            )
                        else:
                            parent_lock = getattr(self, parent_sha3_224, None)
                            self.log.debug(
                                "Got dynamic class lock: %s", parent_sha3_224
                            )

                    if parent_lock:
                        parent_lock.acquire()
                        setattr(parent_lock, "used", time.time())
                        parent_locks_tracker.add(parent_sha3_224)
                        self.log.debug(
                            "Parent lock acquired for [ %s ] on [ %s ]",
                            parent_sha3_224,
                            component_kwargs["job"]["job_id"],
                        )

                    threads.append(
                        self._thread_spawn(
                            component_kwargs=component_kwargs,
                            command=command,
                            info=info,
                            cached=cached,
                            lock=lock,
                            parent_lock=parent_lock,
                        )
                    )
            else:
                for t in threads:
                    t.join()

            if not threads:
                time.sleep(interval)
            else:
                self.log.debug("Worker threads: %s", len(threads))

            self.prune_locks(
                queue=queue, parent_locks_tracker=parent_locks_tracker
            )

    def purge_queue(self, job_id):
        """Purge all jobs from the works queues.

        :param job_id: Job UUID
        :type job_id: String
        :returns: String
        """

        total_count = 0
        for q in [self.q_async, self.q_general]:
            count = 0
            while not q.empty():
                try:
                    (
                        _kwargs,
                        _command,
                        _,
                        _,
                    ) = q.get_nowait()
                    count += 1
                    total_count += 1
                except ValueError as e:
                    self.log.critical(
                        "Queue object value error [ %s ]", str(e)
                    )
                    break
                except Exception:
                    break
                else:
                    self.q_return.put(
                        (
                            None,
                            None,
                            False,
                            "Omitted due to sentinel from {}".format(job_id),
                            _kwargs["job"],
                            _command,
                            0,
                            None,
                        )
                    )
            else:
                self.log.info("Purged %s items from the queue", count)
        else:
            clear_info = "Cleared {} items from the work queues.".format(
                total_count
            )
            self.log.info(clear_info)
            return clear_info

    def job_q_component_run(
        self, component_kwargs, command, info, cached, lock, parent_lock
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
        :param parent_lock: Locking object, used if defined.
        :type parent_lock: Object
        """

        job = component_kwargs["job"]
        job_id = job["job_id"]
        success, _, component = directord.component_import(
            component=command.decode().lower(),
            job_id=job_id,
        )
        parent_sha3_224 = job.get("parent_sha3_224")

        if not success:
            self.log.warning("Component lookup failure [ %s ]", component)
            self.q_return.put(
                (
                    None,
                    None,
                    success,
                    None,
                    job,
                    command,
                    0,
                    None,
                )
            )
        elif cached and component.cacheable is True:
            self.log.info(
                "Cache hit on [ %s ], task skipped.",
                job_id,
            )
            self.q_return.put(
                (
                    None,
                    None,
                    "skipped",
                    None,
                    job,
                    command,
                    0,
                    None,
                )
            )
        else:
            self.log.debug(
                "Starting component execution for job [ %s ].",
                job_id,
            )
            # Set the comment command argument
            setattr(component, "command", command)
            setattr(component, "info", info)
            setattr(component, "driver", self.driver)

            locked = False
            if component.requires_lock or job.get("force_lock", False) is True:
                lock.acquire()
                locked = True

            with self.timeout(
                time=job.get("timeout", 600),
                job_id=job_id,
            ):
                _starttime = time.time()
                component_return = component.client(cache=self.cache, job=job)
                job[
                    "component_exec_timestamp"
                ] = datetime.datetime.fromtimestamp(time.time()).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            if component.queue_sentinel:
                self.log.info("Worker queue sentinel received.")
                component_return = list(component_return)
                component_return.pop()
                component_return.append(self.purge_queue(job_id=job_id))
                component_return = tuple(component_return)

            self.q_return.put(
                component_return
                + (
                    job,
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
                    job_id=block_on_task_data["job_id"],
                ):
                    while block_on_task:
                        if self.cache.get(
                            block_on_task_data["job_sha3_224"]
                        ) in [
                            self.driver.job_end.decode(),
                            self.driver.job_failed.decode(),
                        ]:
                            block_on_task = False
                        else:
                            self.log.debug(
                                "waiting for callback job to complete. %s",
                                block_on_task_data,
                            )
                            time.sleep(0.5)

                self.log.debug(
                    "Task sha [ %s ] callback complete",
                    block_on_task_data["job_sha3_224"],
                )

            self.log.debug(
                "Component execution complete for job [ %s ].",
                job["job_id"],
            )

        if parent_lock:
            parent_lock.release()
            self.log.debug(
                "Parent lock released for [ %s ] on [ %s ]",
                parent_sha3_224,
                job_id,
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
            self.log.warning(stderr)

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

        job["return_timestamp"] = datetime.datetime.fromtimestamp(
            time.time()
        ).strftime("%Y-%m-%d %H:%M:%S")

        if "new_tasks" in job:
            conn.data = json.dumps(job).encode()
        else:
            minimal_data = {
                "execution_time": job["execution_time"],
                "return_timestamp": job["return_timestamp"],
            }
            component_timestamp = job.get("component_exec_timestamp")
            if component_timestamp:
                minimal_data["component_exec_timestamp"] = component_timestamp

            conn.data = json.dumps(minimal_data).encode()

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
        except ValueError as e:
            self.log.critical("Return object value error [ %s ]", str(e))
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

    def prune_locks(self, queue, parent_locks_tracker):
        """Prune inactive parent lock items.

        When the async queue is empty and parent lock has not been used for
        more than 60 seconds, and is not currently locked, this method will
        prune the locked objects from the parent_locks_tracker.

        > If a parent lock is older that 2400 seconds, and the queue async
          queue is empty, the parent lock will be considered stale and pruned.

        :param queue: Queue object
        :type queue: Object
        :param parent_locks_tracker: Set of lock object references
        :type parent_locks_tracker: Set
        """

        if not queue.empty():
            self.log.debug(
                "Queue not empty, nothing to prune while work is being"
                " processes."
            )
        else:
            for item in list(parent_locks_tracker):
                locker = getattr(self, item, None)
                if not locker:
                    parent_locks_tracker.remove(item)
                    self.log.debug(
                        "Lock item:%s removed as it is no longer active.",
                        item,
                    )
                else:
                    locked = locker.acquire(block=False)
                    if locked and time.time() > locker.used + 60:
                        delattr(self, item)
                        parent_locks_tracker.remove(item)
                        self.log.debug("Pruned parent lock [ %s ]", item)
                    elif time.time() > locker.used + 2400:
                        delattr(self, item)
                        parent_locks_tracker.remove(item)
                        self.log.warning(
                            "Stale parent lock found [ %s ], pruned", item
                        )
                    try:
                        if locked:
                            locker.release()
                    except ValueError:
                        pass

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

    def run_job(self, lock=None, sentinel=False):
        """Job entry point.

        This creates a cached access object, connects to the socket and begins
        the loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 128.

        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        if not lock:
            lock = self.get_lock()

        self.bind_job = self.driver.job_connect()
        poller_time = time.time()
        poller_interval = 8
        cache_check_time = time.time()

        # Ensure that the cache path exists before executing.
        os.makedirs(self.args.cache_path, exist_ok=True)
        while True:
            self.job_q_results()
            cache_check_time = self.prune_cache(
                cache_check_time=cache_check_time
            )

            if (
                self.q_async.empty()
                and self.q_general.empty()
                and self.q_return.empty()
            ):
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
                poller_interval, poller_time = 8, time.time()
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
                            lock=lock,
                        )

            if sentinel:
                break

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        lock = self.get_lock()
        threads = [
            (self.thread(target=self.run_heartbeat), True),
            (self.thread(target=self.run_job, kwargs=dict(lock=lock)), False),
            (
                self.thread(
                    target=self.job_q_processor,
                    kwargs=dict(queue=self.q_general, lock=lock),
                ),
                False,
            ),
            (
                self.thread(
                    target=self.job_q_processor,
                    kwargs=dict(queue=self.q_async, processes=4, lock=lock),
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
