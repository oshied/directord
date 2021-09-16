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
        self.q_processes = self.get_queue()
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

    def q_processor(self, queue, lock):
        """Process jobs from the known queue.

        :param queue: Multiprocessing queue object.
        :type queue: Object
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        while True:
            try:
                (component_kwargs, command, info) = queue.get(timeout=0.5)
            except ValueError as e:
                self.log.critical("Queue object value error [ %s ]", str(e))
                break
            except Exception:
                break
            else:
                self.log.debug(
                    "Job received [ %s ]", component_kwargs["job"]["job_id"]
                )
                self.job_q_component_run(component_kwargs, command, info, lock)

    def _process_spawn(
        self, lock, queue, threads=0, processes=5, name=None, bypass=False
    ):
        """Spawn a new thread and return it.

        :param processes: Number of possible processes to spawn
        :type processes: Integer
        :returns: Object
        """

        if (threads <= processes) or bypass:
            self.log.debug(
                "Executing new thread for parent queue [ %s ]",
                name,
            )
            thread = self.thread(
                target=self.q_processor,
                kwargs=dict(
                    queue=queue,
                    lock=lock,
                ),
                name=name,
                daemon=True,
            )
            thread.start()
            return thread

    def job_q_processor(self, lock=None):
        """Process a given work queue.

        The defined `queue` is processed. The `processes` arg allows this
        method to spawn N processes.

        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        if not lock:
            lock = self.get_lock()

        parent_tracker = dict()
        poller_time = time.time()
        poller_interval = 8
        while True:
            poller_interval = utils.return_poller_interval(
                poller_time=poller_time,
                poller_interval=poller_interval,
                log=self.log,
            )
            try:
                (
                    component_kwargs,
                    command,
                    info,
                ) = self.q_processes.get_nowait()
            except ValueError as e:
                self.log.critical("Queue object value error [ %s ]", str(e))
                continue
            except Exception:
                for key, value in list(parent_tracker.items()):
                    if value["t"]:
                        if value["t"].exitcode is None:
                            parent_tracker[key].pop("time", None)
                        elif value["q"].empty():
                            timestamp = time.time()
                            if timestamp - value.get("time", timestamp) >= 30:
                                parent_tracker.pop(key)
                                self.log.info("Pruned parent [ %s ]", key)
                            else:
                                if "time" not in value:
                                    parent_tracker[key]["time"] = timestamp
                                    self.log.debug(
                                        "Process [ %s ] finished, begining"
                                        " prune",
                                        key,
                                    )
                        else:
                            self.log.info(
                                "Dead parent [ %s ] found with queue items,"
                                " resetting parent thread",
                                key,
                            )
                            parent_tracker[key]["t"] = None
                            parent_tracker[key].pop("time", None)
                    else:
                        if value["bypass"]:
                            _threads = len(
                                [
                                    True
                                    for i in parent_tracker.values()
                                    if i["t"]
                                    and i["t"].is_alive()
                                    and i["bypass"]
                                ]
                            )
                        else:
                            _threads = len(
                                [
                                    True
                                    for i in parent_tracker.values()
                                    if i["t"]
                                    and i["t"].is_alive()
                                    and not i["bypass"]
                                ]
                            )
                        t = parent_tracker[key]["t"] = self._process_spawn(
                            lock=lock,
                            queue=value["q"],
                            threads=_threads,
                            processes=10 if value["bypass"] else 5,
                            name=key,
                        )
                        if t:
                            parent_tracker[key].pop("time", None)

                if poller_interval > 8 and parent_tracker:
                    self.log.debug("All pending parents %s", parent_tracker)

                time.sleep(poller_interval * 0.001)
            else:
                job = component_kwargs["job"]
                self.log.debug("Received job_id [ %s ]", job["job_id"])
                # NOTE(cloudnull): If the command is queuesentinel purge all
                #                  queued items. This is on the ONE component
                #                  where we intercept and react outside of
                #                  the component structure.
                if command.decode().lower() == "queuesentinel":
                    count = 0
                    for key, value in list(parent_tracker.items()):
                        count += self.purge_queue(
                            queue=value["q"], job_id=job["job_id"]
                        )
                    self.log.info(
                        "Purged %s items from the work queues", count
                    )

                if job.get("parent_async_bypass") is True:
                    _q_name = "q_bypass_{}".format(
                        job.get("parent_id", job["job_id"])
                    )
                elif job.get("parent_async") is True:
                    _q_name = "q_async_{}".format(
                        job.get("parent_id", job["job_id"])
                    )
                else:
                    _q_name = "q_general"

                if _q_name in parent_tracker:
                    _parent = parent_tracker[_q_name]
                else:
                    _parent = parent_tracker[_q_name] = dict(
                        t=None, q=self.get_queue(), bypass=False
                    )
                    self.log.info("Parent queue [ %s ] created.", _q_name)

                _parent["q"].put((component_kwargs, command, info))
                poller_interval, poller_time = 8, time.time()

                if _parent["t"] and _parent["t"].is_alive():
                    continue
                elif _q_name.startswith("q_bypass"):
                    t = parent_tracker[_q_name]["t"] = self._process_spawn(
                        lock=lock,
                        queue=_parent["q"],
                        threads=len(
                            [
                                True
                                for i in parent_tracker.values()
                                if i["t"] and i["t"].is_alive() and i["bypass"]
                            ]
                        ),
                        processes=10,
                        name=_q_name,
                    )
                    parent_tracker[_q_name]["bypass"] = True
                else:
                    t = parent_tracker[_q_name]["t"] = self._process_spawn(
                        lock=lock,
                        queue=_parent["q"],
                        threads=len(
                            [
                                True
                                for i in parent_tracker.values()
                                if i["t"]
                                and i["t"].is_alive()
                                and not i["bypass"]
                            ]
                        ),
                        name=_q_name,
                    )

    def purge_queue(self, queue, job_id):
        """Purge all jobs from the queue.

        :param queue: Queue object
        :type queue: Object
        :param job_id: Job UUID
        :type job_id: String
        :returns: Integer
        """

        total_count = 0
        while not queue.empty():
            try:
                (
                    _kwargs,
                    _command,
                    _,
                    _,
                ) = queue.get_nowait()
                total_count += 1
            except ValueError as e:
                self.log.critical("Queue object value error [ %s ]", str(e))
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

        self.log.info("Cleared %s items from the work queue", total_count)
        return total_count

    def job_q_component_run(self, component_kwargs, command, info, lock):
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
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        job = component_kwargs["job"]
        job_id = job["job_id"]
        success, _, component = directord.component_import(
            component=command.decode().lower(),
            job_id=job_id,
        )

        cached = self.cache.get(
            job["job_sha3_224"]
        ) == self.driver.job_end.decode() and not job.get(
            "skip_cache", job.get("ignore_cache", False)
        )

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
                locked = lock.acquire()
                self.log.debug("Component lock acquired for [ %s ]", job_id)

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

            try:
                component_return = component_return + (
                    job,
                    command,
                    time.time() - _starttime,
                    component.block_on_tasks,
                )
            except UnboundLocalError:
                component.block_on_tasks = list()
                component_return = (
                    None,
                    None,
                    False,
                    "Job was unable to finish",
                    job,
                    command,
                    time.time() - _starttime,
                    None,
                )

            if locked:
                lock.release()
                self.log.debug("Component lock released for [ %s ]", job_id)

            self.q_return.put(component_return)

            try:
                block_on_task_data = [
                    i
                    for i in component.block_on_tasks
                    if self.driver.identity in i.get("targets", list())
                ][-1]
            except IndexError:
                self.log.debug(
                    "Job [ %s ] no valid callbacks for this node %s.",
                    job["job_id"],
                    self.driver.identity,
                )
            except TypeError:
                self.log.debug("No callbacks defined.")
            else:
                self.log.info(
                    "Job [ %s ] number of job call backs [ %s ]",
                    job["job_id"],
                    len(component.block_on_tasks),
                )
                self.log.debug("Job call backs: %s ", component.block_on_tasks)
                block_on_task = False
                with self.timeout(
                    time=block_on_task_data.get("timeout", 600),
                    job_id=block_on_task_data["job_id"],
                ):
                    count = 0
                    while True:
                        if self.cache.get(
                            block_on_task_data["job_sha3_224"]
                        ) in [
                            self.driver.job_end.decode(),
                            self.driver.job_failed.decode(),
                        ]:
                            block_on_task = True
                            break
                        else:

                            self.log.debug(
                                "waiting for callback job from [ %s ] to"
                                " complete. %s",
                                job["job_id"],
                                block_on_task_data,
                            )
                            count += 1
                            time.sleep(count if count < 5 else 5)

                if block_on_task:
                    self.log.debug(
                        "Job [ %s ] task sha [ %s ] callback complete",
                        job["job_id"],
                        block_on_task_data["job_sha3_224"],
                    )
                else:
                    self.log.error(
                        "Job [ %s ] task sha [ %s ] callback never completed",
                        job["job_id"],
                        block_on_task_data["job_sha3_224"],
                    )
                    self.q_return.put(
                        (
                            component_return[0],
                            component_return[1],
                            False,
                            "Callback [ {} ] never completed".format(
                                block_on_task_data["job_id"]
                            ),
                            job,
                            command,
                            time.time() - _starttime,
                            None,
                        )
                    )

            self.log.debug(
                "Component execution complete for job [ %s ].",
                job["job_id"],
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
            self.log.warning("Job [ %s ], stderr: %s", job["job_id"], stderr)

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
          present, the poll interval is 1.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_job = self.driver.job_connect()
        poller_time = time.time()
        poller_interval = 1
        cache_check_time = time.time()

        while True:
            self.job_q_results()
            if self.q_return.empty():
                poller_interval = utils.return_poller_interval(
                    poller_time=poller_time,
                    poller_interval=poller_interval,
                    log=self.log,
                )

            if self.driver.bind_check(
                bind=self.bind_job, constant=poller_interval
            ):
                poller_interval, poller_time = 1, time.time()
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
                    else:
                        c.job_state = self.driver.job_processing
                        component_kwargs = dict(cache=None, job=job)
                        self.log.debug(
                            "Queuing component [ %s ], job_id [ %s ]",
                            command.decode(),
                            job_id,
                        )
                        c.info = b"task queued"
                        self.q_processes.put(
                            (
                                component_kwargs,
                                command,
                                info,
                            )
                        )
            else:
                cache_check_time = self.prune_cache(
                    cache_check_time=cache_check_time
                )
                time.sleep(poller_interval * 0.001)

            if sentinel:
                break

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        lock = self.get_lock()
        threads = [
            (
                self.thread(name="run_heartbeat", target=self.run_heartbeat),
                True,
            ),
            (self.thread(name="run_job", target=self.run_job), True),
            (
                self.thread(
                    name="job_q_processor",
                    target=self.job_q_processor,
                    kwargs=dict(lock=lock),
                ),
                False,
            ),
        ]
        # Ensure that the cache path exists before executing.
        os.makedirs(self.args.cache_path, exist_ok=True)
        with diskcache.Cache(
            self.args.cache_path,
            tag_index=True,
            disk=diskcache.JSONDisk,
        ) as cache:
            self.cache = cache
            self.run_threads(threads=threads)
