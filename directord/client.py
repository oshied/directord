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

import collections
import datetime
import json
import os
import time

import directord
from directord import components
from directord import interface
from directord import iodict
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

        self.q_return = self.driver.get_queue(name="q_return")
        self.q_processes = self.driver.get_queue(name="q_processes")
        self.base_component = components.ComponentBase()
        self.cache = dict()
        self.start_time = time.time()

    def exit_gracefully(self, *args, **kwargs):
        """Set the driver event to begin the shutdown of the application."""

        self.log.warning(
            "Shutdown signal intercepted. Starting client shutdown."
        )
        self.driver.event.set()

    def q_processor(self, queue, lock):
        """Process jobs from the known queue.

        :param queue: queue object.
        :type queue: Object
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        for item in queue.getter():
            component_kwargs, command, info = item
            self.log.debug(
                "Job received [ %s ]", component_kwargs["job"]["job_id"]
            )
            self.job_q_component_run(component_kwargs, command, info, lock)

            if self.driver.event.is_set():
                return

    def job_q_processor(self, q_processes, lock=None):
        """Process a given work queue.

        The defined `queue` is processed. The `processes` arg allows this
        method to spawn N processes.

        :param q_processes: Queue object
        :type q_processes: Object
        :param lock: Locking object, used if a component requires it.
        :type lock: Object
        """

        def _get_pending_bypass_threads(parents):
            """Return the current non-bypass thread objects.

            :param parents: Dictionary of all parent objects.
            :type parents: Dictionary
            :returns: List
            """

            return [
                i["t"].name
                for i in parents.values()
                if i["bypass"]
                and not i["t"].is_alive()
                and i["t"].ident is None
            ]

        def _get_pending_threads(parents):
            """Return the current non-bypass thread objects.

            :param parents: Dictionary of all parent objects.
            :type parents: Dictionary
            :returns: List
            """

            return [
                i["t"].name
                for i in parents.values()
                if not i["bypass"]
                and not i["t"].is_alive()
                and i["t"].ident is None
            ]

        def _get_thread_count(parents):
            """Return the current non-bypass thread count.

            :param parents: Dictionary of all parent objects.
            :type parents: Dictionary
            :returns: Integer
            """

            return len(
                [
                    True
                    for i in parents.values()
                    if not i["bypass"] and i["t"].is_alive()
                ]
            )

        if not lock:
            lock = self.driver.get_lock()

        parent_tracker_recover = iodict.DurableQueue(
            path=os.path.join(self.args.cache_path, "parent_tracker"),
            lock=lock,
        )
        parent_tracker = collections.OrderedDict()
        for item in parent_tracker_recover.getter():
            k, v = item
            q = self.driver.get_queue(name=k)
            parent_tracker[k] = dict(t=None, q=q, bypass=v)
            parent_tracker[k]["t"] = self.driver.thread_processor(
                target=self.q_processor,
                kwargs=dict(
                    queue=parent_tracker[k]["q"],
                    lock=lock,
                ),
                name=k,
                daemon=True,
            )

        while not q_processes.empty() or parent_tracker:
            try:
                (
                    component_kwargs,
                    command,
                    info,
                ) = q_processes.get_nowait()
            except ValueError as e:
                self.log.critical("Queue object value error [ %s ]", str(e))
            except Exception:
                sleep_interval = 0.1
            else:
                sleep_interval = 0.001
                lower_command = command.lower()
                job = component_kwargs["job"]
                self.log.debug("Received job_id [ %s ]", job["job_id"])
                # NOTE(cloudnull): If the command is queuesentinel purge all
                #                  queued items. This is on the ONE component
                #                  where we intercept and react outside of
                #                  the component structure.
                if lower_command == "queuesentinel":
                    count = 0
                    for value in list(parent_tracker.values()):
                        count = 0
                        for item in value["q"].getter():
                            _kwargs, _command, _ = item
                            self.q_return.put(
                                (
                                    None,
                                    None,
                                    False,
                                    "Omitted due to sentinel from {}".format(
                                        job["job_id"]
                                    ),
                                    _kwargs["job"],
                                    _command,
                                    0,
                                    None,
                                )
                            )
                            count += 1
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

                if _q_name not in parent_tracker:
                    parent_tracker.setdefault(
                        _q_name,
                        dict(
                            t=None,
                            q=self.driver.get_queue(name=_q_name),
                            bypass=job.get("parent_async_bypass", False),
                        ),
                    )
                    parent_tracker[_q_name][
                        "t"
                    ] = self.driver.thread_processor(
                        target=self.q_processor,
                        kwargs=dict(
                            queue=parent_tracker[_q_name]["q"],
                            lock=lock,
                        ),
                        name=_q_name,
                        daemon=True,
                    )
                    self.log.info("Parent queue [ %s ] created.", _q_name)

                parent_tracker[_q_name]["q"].put(
                    (component_kwargs, command, info)
                )

            for t in _get_pending_bypass_threads(parents=parent_tracker):
                self.log.info("Starting bypass process [ %s ]", t)
                parent_tracker[t]["t"].start()

            while _get_thread_count(parents=parent_tracker) <= self.cpu_count:
                for t in _get_pending_threads(parents=parent_tracker):
                    self.log.info("Starting process [ %s ]", t)
                    parent_tracker[t]["t"].start()
                else:
                    break

            for key, value in list(parent_tracker.items()):
                if value["t"].is_alive() or value["t"].ident is None:
                    continue
                else:
                    timestamp = time.time()
                    timeout = timestamp - value.get("timeout", timestamp) > 5
                    if value["q"].empty() and timeout:
                        self.terminate_process(process=value["t"])
                        parent_tracker.pop(key)
                        self.log.info("Pruned parent [ %s ]", key)
                    elif not value["q"].empty():
                        self.log.warning(
                            "Parent thread was terminated but the queue [ %s ]"
                            " had items in it, respawning",
                            key,
                        )
                        parent_tracker[key].pop("timeout", None)
                        parent_tracker[key][
                            "t"
                        ] = self.driver.thread_processor(
                            target=self.q_processor,
                            kwargs=dict(
                                queue=parent_tracker[key]["q"],
                                lock=lock,
                            ),
                            name=key,
                            daemon=True,
                        )
                    elif "timeout" not in parent_tracker[key]:
                        self.log.info("Starting to prune parent [ %s ]", key)
                        parent_tracker[key]["timeout"] = timestamp

            if self.driver.event.is_set():
                for k, v in parent_tracker.items():
                    v["q"].flush()
                    parent_tracker_recover.put((k, v["bypass"]))
                return

            time.sleep(sleep_interval)

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
        command_lower = command.lower()
        success, _, component = directord.component_import(
            component=command_lower,
            job_id=job_id,
        )

        cached = self.cache.get(
            job["job_sha3_224"]
        ) == self.driver.job_end and not job.get(
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
            if component.requires_lock:
                lock_name = "__lock_{}__".format(
                    getattr(component, "lock_name", command_lower)
                )
                try:
                    lock = getattr(self, lock_name)
                except AttributeError:
                    self.log.debug(
                        "No component lock found for [ %s ], falling back"
                        " to global lock",
                        lock_name,
                    )
                else:
                    self.log.debug(
                        "Found component lock [ %s ]",
                        lock_name,
                    )

                locked = lock.acquire()
                self.log.debug("Lock acquired for [ %s ]", job_id)

            _starttime = time.time()
            try:
                stdout, stderr, outcome, info = component.client(
                    cache=self.cache, job=job
                )
            except Exception as e:
                stderr = "Job [ {} ] Component Failure: {}".format(
                    job_id, str(e)
                )
                self.log.critical(stderr)
                stdout = None
                outcome = False
                info = e.__traceback__

            job["component_exec_timestamp"] = datetime.datetime.fromtimestamp(
                time.time()
            ).strftime("%Y-%m-%d %H:%M:%S")

            try:
                if component.block_on_tasks:
                    block_on_tasks_data = [
                        i
                        for i in component.block_on_tasks
                        if self.driver.identity in i.get("targets", list())
                    ]
                    if outcome and block_on_tasks_data:
                        outcome = None
                        info = "Waiting for callback tasks to complete"
                else:
                    block_on_tasks_data = None

                component_return = (
                    stdout,
                    stderr,
                    outcome,
                    info,
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
                self.log.debug("Lock released for [ %s ]", job_id)

            self.q_return.put(component_return)

            try:
                block_on_task_data = block_on_tasks_data[-1]
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
                block_on_task_success = False
                while True:
                    if self.cache.get(block_on_task_data["job_sha3_224"]) in [
                        self.driver.job_end,
                        self.driver.job_failed,
                    ]:
                        block_on_task_success = True
                        break
                    else:
                        self.log.debug(
                            "waiting for callback job from [ %s ] to"
                            " complete. %s",
                            job["job_id"],
                            block_on_task_data,
                        )
                        time.sleep(1)

                if block_on_task_success:
                    self.log.debug(
                        "Job [ %s ] callback complete", job["job_id"]
                    )
                    self.q_return.put(
                        (
                            stdout,
                            stderr,
                            True,
                            "Callback [ {} ] completed".format(
                                block_on_task_data["job_id"]
                            ),
                            job,
                            command,
                            time.time() - _starttime,
                            None,
                        )
                    )
                else:
                    self.log.error(
                        "Job [ %s ] callback never completed",
                        job["job_id"],
                    )
                    self.q_return.put(
                        (
                            stdout,
                            stderr,
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
            conn.stdout = stdout
            self.log.debug("Job [ %s ], stdout: %s", job["job_id"], stdout)

        if stderr:
            stderr = stderr.strip()
            conn.stderr = stderr
            self.log.warning("Job [ %s ], stderr: %s", job["job_id"], stderr)

        if outcome is False:
            state = conn.job_state = self.driver.job_failed
            self.log.error("Job failed [ %s ]", job["job_id"])
            conn.info = "task failed"
        elif outcome is True:
            state = conn.job_state = self.driver.job_end
            self.log.info("Job complete [ %s ]", job["job_id"])
            conn.info = "task finished"
        elif outcome == "skipped":
            self.log.info("Job skipped [ %s ]", job["job_id"])
            conn.info = "task skipped"
            state = conn.job_state = self.driver.job_end
        else:
            state = conn.job_state = self.driver.job_processing
            conn.info = "task processing"

        if return_info:
            conn.info = return_info

        if block_on_tasks:
            job["new_tasks"] = block_on_tasks

        job["return_timestamp"] = datetime.datetime.fromtimestamp(
            time.time()
        ).strftime("%Y-%m-%d %H:%M:%S")

        if "new_tasks" in job:
            conn.data = json.dumps(job)
        else:
            minimal_data = {
                "execution_time": job["execution_time"],
                "return_timestamp": job["return_timestamp"],
            }
            component_timestamp = job.get("component_exec_timestamp")
            if component_timestamp:
                minimal_data["component_exec_timestamp"] = component_timestamp

            conn.data = json.dumps(minimal_data)

        if job["parent_id"]:
            self.base_component.set_cache(
                cache=self.cache,
                key=job["parent_id"],
                value=state,
            )

        self.base_component.set_cache(
            cache=self.cache,
            key=job["job_sha3_224"],
            value=state,
        )

    def job_q_results(self):
        """Job results queue processor.

        Results are retrieved from the queue and status is set.

        :returns: Boolean
        """

        results = False
        for item in self.q_return.getter():
            results = True
            (
                stdout,
                stderr,
                outcome,
                return_info,
                job,
                command,
                execution_time,
                block_on_tasks,
            ) = item
            self.log.debug("Found task results for [ %s ].", job["job_id"])
            with utils.ClientStatus(
                job_id=job["job_id"],
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

        return results

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
        if cache.get(job["parent_id"]) == self.driver.job_failed:
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
            conn.info = status
            conn.job_state = self.driver.job_failed
            return False
        else:
            return True

    def run_job(self, lock=None):
        """Job entry point.

        This creates a cached access object, connects to the socket and begins
        the loop.

        > When a file transfer is initiated the client will enter a loop
          waiting for data chunks until an `transfer_end` signal is passed.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 1.
        """

        self.driver.job_init()
        poller_time = time.time()
        heartbeat_time = time.time()
        poller_interval = 1
        run_q_processor_thread = None
        startup = True
        while True:
            if self.terminate_process(process=run_q_processor_thread):
                run_q_processor_thread = None

            if (
                not self.q_processes.empty() and not run_q_processor_thread
            ) or startup:
                run_q_processor_thread = self.driver.thread_processor(
                    target=self.job_q_processor,
                    kwargs=dict(q_processes=self.q_processes, lock=lock),
                    name="job_q_processor",
                    daemon=False,
                )
                run_q_processor_thread.start()
                startup = False

            if time.time() > heartbeat_time:
                with open("/proc/uptime", "r") as f:
                    uptime = float(f.readline().split()[0])

                version = directord.__version__
                host_uptime = str(datetime.timedelta(seconds=uptime))
                agent_uptime = str(
                    datetime.timedelta(seconds=(time.time() - self.start_time))
                )
                self.driver.heartbeat_send(
                    host_uptime=host_uptime,
                    agent_uptime=agent_uptime,
                    version=version,
                    driver=self.args.driver,
                )
                heartbeat_time = time.time() + 30

            if self.job_q_results():
                poller_interval, poller_time = 1, time.time()

            while self.driver.job_check(constant=poller_interval):
                poller_interval, poller_time = 1, time.time()
                (
                    _,
                    _,
                    command,
                    data,
                    info,
                    _,
                    _,
                ) = self.driver.job_recv()
                self.handle_job(command=command, data=data, info=info)

            poller_interval = utils.return_poller_interval(
                poller_time=poller_time,
                poller_interval=poller_interval,
                log=self.log,
            )

            if self.driver.event.is_set():
                self.driver.job_close()
                break

    def handle_job(
        self,
        command,
        data,
        info,
    ):
        """Handle a job interaction.

        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        """

        job = json.loads(data)
        job["job_id"] = job_id = job.get("job_id", utils.get_uuid())
        job["job_sha3_224"] = job_sha3_224 = job.get(
            "job_sha3_224", utils.object_sha3_224(job)
        )
        job_parent_id = job.get("parent_id")
        job_parent_sha3_224 = job.get("parent_sha3_224")
        self.log.debug(
            "Item received: parent job UUID [ %s ],"
            " parent job sha3_224 [ %s ], job UUID [ %s ],"
            " job sha3_224 [ %s ]",
            job_parent_id,
            job_parent_sha3_224,
            job_id,
            job_sha3_224,
        )

        with utils.ClientStatus(
            job_id=job_id,
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
                        "Job omitted, parent failure",
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
                    command,
                    job_id,
                )
                c.info = "task queued"
                self.q_processes.put(
                    (
                        component_kwargs,
                        command,
                        info,
                    )
                )

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        lock = self.driver.get_lock()
        for known_component in utils.component_lock_search():
            lock_name = "__lock_{}__".format(known_component.lower())
            if not hasattr(self, lock_name):
                self.log.debug("Creating a new lock for [ %s ]", lock_name)
                setattr(
                    self,
                    lock_name,
                    self.driver.get_lock(),
                )

        threads = [
            (
                self.driver.thread_processor(
                    name="run_job", target=self.run_job, kwargs=dict(lock=lock)
                ),
                False,
            ),
        ]
        self.cache = iodict.Cache(
            path=os.path.join(self.args.cache_path, "client"),
            lock=self.driver.get_lock(),
        )
        self.run_threads(threads=threads, stop_event=self.driver.event)
        self.driver.shutdown()
        self.q_return.flush()
        self.q_processes.flush()
