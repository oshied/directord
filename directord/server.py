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

import decimal
import grp
import json
import os
import socket
import time
import urllib.parse as urlparse

import directord

from directord import interface
from directord import utils


class Server(interface.Interface):
    """Directord server class."""

    def __init__(self, args):
        """Initialize the Server class.

        Sets up the server object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Server, self).__init__(args=args)
        self.job_queue = self.get_queue()
        self.send_queue = self.get_queue()
        datastore = getattr(self.args, "datastore", None)
        if not datastore or datastore == "memory":
            self.log.info("Connecting to internal datastore")
            directord.plugin_import(plugin=".datastores.internal")
            manager = self.get_manager()
            self.workers = manager.document()
            self.return_jobs = manager.document()
        else:
            url = urlparse.urlparse(datastore)
            if url.scheme in ["file"]:
                disc = directord.plugin_import(plugin=".datastores.disc")
                self.log.debug("Disc base document store initialized")
                path = os.path.abspath(os.path.expanduser(url.path))
                # Ensure that the cache path exists before executing.
                os.makedirs(path, exist_ok=True)
                self.workers = disc.BaseDocument(
                    url=os.path.join(path, "workers")
                )
                self.workers.empty()
                self.return_jobs = disc.BaseDocument(
                    url=os.path.join(path, "jobs")
                )
            if url.scheme in ["redis", "rediss"]:
                self.log.info("Connecting to redis datastore")
                try:
                    db = int(url.path.lstrip("/"))
                except ValueError:
                    db = 0
                self.log.debug("Redis keyspace base is %s", db)
                redis = directord.plugin_import(plugin=".datastores.redis")

                self.workers = redis.BaseDocument(
                    url=url._replace(path="").geturl(), database=(db + 1)
                )
                self.return_jobs = redis.BaseDocument(
                    url=url._replace(path="").geturl(), database=(db + 2)
                )

    def _set_job_status(
        self,
        job_status,
        job_id,
        identity,
        job_output,
        job_stdout=None,
        job_stderr=None,
        execution_time=None,
        return_timestamp=None,
        component_exec_timestamp=None,
        recv_time=None,
    ):
        """Set job status.

        This will update the object for job tracking, allowing the
        user to know what happened within the environment.

        :param job_status: ASCII Control Character
        :type job_status: Bytes
        :param job_id: UUID for job
        :type job_id: String
        :param identity: Node name
        :type identity: String
        :param job_output: Job output information
        :type job_output: String
        :param job_stdout: Job output information
        :type job_stdout: String
        :param job_stderr: Job error information
        :type job_stderr: String
        :param execution_time: Time the task took to execute
        :type execution_time: Float
        :param return_timestamp: Timestamp from the job return.
        :type return_timestamp: String
        :param component_exec_timestamp: Timestamp from the component return.
        :type component_exec_timestamp: String
        :param recv_time: Time a task return was received.
        :type recv_tim: Float
        """

        def _set_time():
            _createtime = job_metadata.get("_createtime")
            if not _createtime:
                _createtime = job_metadata["_createtime"] = time.time()

            if isinstance(recv_time, (int, float)):
                job_metadata["_roundtripltime"][identity] = (
                    float(recv_time) - _createtime
                )
                job_metadata["ROUNDTRIP_TIME"] = "{:.8f}".format(
                    decimal.Decimal(
                        sum(job_metadata["_roundtripltime"].values())
                        / len(job_metadata["_roundtripltime"].keys())
                    )
                )

            if isinstance(execution_time, (int, float)):
                job_metadata["_executiontime"][identity] = float(
                    execution_time
                )
                job_metadata["EXECUTION_TIME"] = "{:.8f}".format(
                    decimal.Decimal(
                        sum(job_metadata["_executiontime"].values())
                        / len(job_metadata["_executiontime"].keys())
                    )
                )

        job_metadata = self.return_jobs.get(job_id)
        if not job_metadata:
            return

        if job_output and job_output is not self.driver.nullbyte.decode():
            job_metadata["INFO"][identity] = job_output

        if job_stdout and job_stdout is not self.driver.nullbyte.decode():
            job_metadata["STDOUT"][identity] = job_stdout

        if job_stderr and job_stderr is not self.driver.nullbyte.decode():
            job_metadata["STDERR"][identity] = job_stderr

        self.log.debug("current job [ %s ] state [ %s ]", job_id, job_status)
        job_metadata["_processing"][identity] = job_status.decode()
        if job_status == self.driver.job_ack:
            self.log.debug("%s received job %s", identity, job_id)
        elif job_status == self.driver.job_processing:
            self.log.debug("%s is processing %s", identity, job_id)
        elif job_status == self.driver.job_end:
            _set_time()
            self.log.debug("%s finished processing %s", identity, job_id)
            if "SUCCESS" in job_metadata:
                job_metadata["SUCCESS"].append(identity)
            else:
                job_metadata["SUCCESS"] = [identity]
            job_metadata["_processing"][
                identity
            ] = self.driver.job_end.decode()
        elif job_status == self.driver.job_failed:
            _set_time()
            self.log.debug("%s failed %s", identity, job_id)
            if "FAILED" in job_metadata:
                job_metadata["FAILED"].append(identity)
            else:
                job_metadata["FAILED"] = [identity]

        if return_timestamp:
            job_metadata["RETURN_TIMESTAMP"] = return_timestamp

        if component_exec_timestamp:
            job_metadata["COMPONENT_TIMESTAMP"] = component_exec_timestamp

        for process in job_metadata["_processing"].values():
            if process == self.driver.job_processing.decode():
                job_metadata[
                    "PROCESSING"
                ] = self.driver.job_processing.decode()
                break
        else:
            job_metadata["PROCESSING"] = self.driver.job_end.decode()

        self.return_jobs[job_id] = job_metadata

    def create_return_jobs(self, task, job_item, targets):
        return self.return_jobs.set(
            task,
            {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": [i.decode() for i in targets],
                "VERB": job_item["verb"],
                "TRANSFERS": list(),
                "JOB_SHA3_224": job_item["job_sha3_224"],
                "JOB_DEFINITION": job_item,
                "PARENT_JOB_ID": job_item.get("parent_id"),
                "_createtime": time.time(),
                "_executiontime": dict(),
                "_roundtripltime": dict(),
                "_processing": dict(),
            },
        )

    def run_job(self, sentinel=False):
        """Run a job interaction

        As the job loop executes it will interrogate the job item as returned
        from the queue. If the item contains a "targets" definition the
        job loop will only send the message to the given targets, assuming the
        target is known within the workers object, otherwise all targets will
        receive the message. If a defined target is not found within the
        workers object no job will be executed.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        :returns: Tuple
        """

        self.log.info("Starting run process.")
        while not self.job_queue.empty():
            try:
                job_item = self.job_queue.get(timeout=60)
            except Exception:
                break
            else:
                self.log.debug("Job item received [ %s ]", job_item)
                restrict_sha3_224 = job_item.get("restrict")
                if restrict_sha3_224:
                    if job_item["job_sha3_224"] not in restrict_sha3_224:
                        self.log.debug(
                            "Job restriction %s is unknown.", restrict_sha3_224
                        )
                        if sentinel:
                            break
                        else:
                            continue

                targets = list()
                self.log.debug("Processing targets.")
                for target in (
                    job_item.pop("targets", None) or self.workers.keys()
                ):
                    try:
                        target = target.encode()
                    except AttributeError:
                        pass

                    if target in self.workers.keys():
                        self.log.debug("Target identified [ %s ].", target)
                        targets.append(target)
                    else:
                        self.log.critical(
                            "Target [ %s ] is unknown. Check the name againt"
                            " the available targets",
                            target,
                        )
                        if not self.return_jobs.get(job_item["job_id"]):
                            self.create_return_jobs(
                                task=job_item["job_id"],
                                job_item=job_item,
                                targets=targets,
                            )
                        self._set_job_status(
                            job_status=self.driver.job_failed,
                            job_id=job_item["job_id"],
                            identity=target.decode(),
                            job_output=(
                                "Target unknown. Available targets {}".format(
                                    list(self.workers.keys())
                                )
                            ),
                            recv_time=time.time(),
                        )

                if not targets:
                    self.log.error("No known targets defined.")
                    continue

                self.log.debug("All targets %s", targets)
                if job_item["verb"] == "QUERY":
                    self.log.debug("Query mode enabled.")
                    # NOTE(cloudnull): QUERY runs across the cluster. The
                    #                  callback tasks are scoped to only
                    #                  the nodes defined within the job
                    #                  execution.
                    job_item["targets"] = [i.decode() for i in targets]
                    targets = self.workers.keys()
                elif job_item.get("run_once", False):
                    self.log.debug("Run once enabled.")
                    targets = [targets[0]]
                    job_item["targets"] = [targets[0].decode()]

                job_id = job_item.get("job_id", utils.get_uuid())
                job_info = self.create_return_jobs(
                    task=job_id, job_item=job_item, targets=targets
                )
                self.log.debug("Processing job [ %s ]", job_item)
                for identity in targets:
                    if job_item["verb"] in ["ADD", "COPY"]:
                        for file_path in job_item["from"]:
                            job_item["file_sha3_224"] = utils.file_sha3_224(
                                file_path=file_path
                            )
                            if job_item["to"].endswith(os.sep):
                                job_item["file_to"] = os.path.join(
                                    job_item["to"],
                                    os.path.basename(file_path),
                                )
                            else:
                                job_item["file_to"] = job_item["to"]

                            if (
                                job_item["file_to"]
                                not in job_info["TRANSFERS"]
                            ):
                                job_info["TRANSFERS"].append(
                                    job_item["file_to"]
                                )

                            self.log.debug(
                                "Queueing file transfer job [ %s ] for"
                                " file_path [ %s ] to identity [ %s ]",
                                job_item["job_id"],
                                file_path,
                                identity.decode(),
                            )
                            self.send_queue.put(
                                dict(
                                    identity=identity,
                                    command=job_item["verb"].encode(),
                                    data=job_item,
                                    info=file_path.encode(),
                                )
                            )
                    else:
                        self.log.debug(
                            "Queuing job [ %s ] for identity [ %s ]",
                            job_item["job_id"],
                            identity.decode(),
                        )
                        self.send_queue.put(
                            dict(
                                identity=identity,
                                command=job_item["verb"].encode(),
                                data=job_item,
                            )
                        )
                else:
                    self.return_jobs[job_id] = job_info

            if sentinel:
                break

    def run_backend(self, sentinel=False):
        """Execute the transfer loop.

        Directord's interaction executor will slow down the poll interval
        when no work is present. This means Directord will ramp-up resource
        utilization when required and become virtually idle when there's
        nothing to do.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 1.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_backend = self.driver.backend_bind()
        poller_time = time.time()
        poller_interval = 128

        while True:
            poller_interval = utils.return_poller_interval(
                poller_time=poller_time,
                poller_interval=poller_interval,
                log=self.log,
            )

            if self.driver.bind_check(
                bind=self.bind_backend, constant=poller_interval
            ):
                poller_interval, poller_time = 128, time.time()
                (
                    identity,
                    msg_id,
                    control,
                    command,
                    data,
                    info,
                    stderr,
                    stdout,
                ) = self.driver.socket_recv(socket=self.bind_backend)
                if control in [
                    self.driver.coordination_notice,
                    self.driver.coordination_ack,
                    self.driver.coordination_failed,
                ]:
                    for _ in range(120):
                        try:
                            self.driver.socket_send(
                                socket=self.bind_backend,
                                identity=info,
                                control=control,
                                command=command,
                                data=data,
                                info=identity,
                                stderr=stderr,
                                stdout=stdout,
                            )
                            break
                        except Exception as e:
                            self.log.debug(
                                "Job [ %s ] connecting to target [ %s ] saw"
                                " exception %s -- retrying",
                                msg_id.decode(),
                                info.decode(),
                                str(e),
                            )
                            time.sleep(0.01)
                    else:
                        try:
                            self.driver.socket_send(
                                socket=self.bind_backend,
                                identity=identity,
                                control=self.driver.coordination_failed,
                                command=command,
                                data=data,
                                info=info,
                                stderr=(
                                    "Failed to connect to coordination node"
                                    " [ {} ] after three attempts.".format(
                                        info.decode()
                                    )
                                ).encode(),
                                stdout=stdout,
                            )
                        except Exception as e:
                            self.log.error(
                                "Job [ %s ] connecting to target [ %s ] saw"
                                " exception %s",
                                msg_id.decode(),
                                info.decode(),
                                str(e),
                            )
                elif control == self.driver.transfer_start:
                    transfer_identity = identity.decode()
                    transfer_job_id = msg_id.decode()
                    transfer_file_path = os.path.abspath(
                        os.path.expanduser(info.decode())
                    )
                    offset = int(command)
                    chunk_size = int(data)
                    self.log.debug(
                        "Identity [ %s ] transfer job [ %s ] processing"
                        " file [ %s ]",
                        transfer_identity,
                        transfer_job_id,
                        transfer_file_path,
                    )
                    if not os.path.isfile(transfer_file_path):
                        self.log.error(
                            "Identity [ %s ] Job [ %s ] File was not found."
                            " File path [ %s ]",
                            transfer_identity,
                            transfer_job_id,
                            transfer_file_path,
                        )
                        self.driver.socket_send(
                            socket=self.bind_backend,
                            identity=transfer_identity.encode(),
                            control=self.driver.job_failed,
                            info="File [ {} ] was not found".format(
                                transfer_file_path
                            ).encode(),
                        )
                    else:
                        self.log.info(
                            "Identity [ %s ] Job [ %s ] file transfer for"
                            " [ %s ] starting",
                            transfer_identity,
                            transfer_job_id,
                            transfer_file_path,
                        )
                        with open(transfer_file_path, "rb") as f:
                            f.seek(offset, os.SEEK_SET)
                            data = f.read(chunk_size)
                            self.driver.socket_send(
                                socket=self.bind_backend,
                                identity=transfer_identity.encode(),
                                control=(
                                    self.driver.transfer_end
                                    if len(data) < chunk_size
                                    else self.driver.job_processing
                                ),
                                data=data,
                            )
                        self.log.info(
                            "Identity [ %s ] Job [ %s ] file transfer for"
                            " [ %s ] blob sent",
                            transfer_identity,
                            transfer_job_id,
                            transfer_file_path,
                        )
                else:
                    self.log.warning(
                        "Unknown transfer job [ %s ] connection received from"
                        " [ %s ], control [ %s ] with"
                        " info [ %s ]",
                        msg_id.decode(),
                        identity.decode(),
                        control.decode(),
                        info.decode(),
                    )

            if sentinel:
                break

    def run_interactions(self, sentinel=False):
        """Execute the interactions loop.

        Directord's interaction executor will slow down the poll interval
        when no work is present. This means Directord will ramp-up resource
        utilization when required and become virtually idle when there's
        nothing to do.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 1.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_job = self.driver.job_bind()
        poller_time = time.time()
        prune_time = time.time()
        poller_interval = 1
        run_jobs_thread = None
        while True:
            if self.terminate_process(process=run_jobs_thread):
                run_jobs_thread = None

            if not self.job_queue.empty():
                if not run_jobs_thread:
                    run_jobs_thread = self.thread(
                        target=self.run_job,
                        name="run_job",
                        daemon=True,
                    )
                    run_jobs_thread.start()
            elif self.send_queue.empty():
                poller_interval = utils.return_poller_interval(
                    poller_time=poller_time,
                    poller_interval=poller_interval,
                    log=self.log,
                )

            while not self.send_queue.empty():
                try:
                    send_item = self.send_queue.get_nowait()
                except Exception:
                    break
                else:
                    self.log.debug(
                        "Sending job [ %s ] sent to [ %s ]",
                        send_item["data"]["job_id"],
                        send_item["identity"].decode(),
                    )
                    send_item["data"] = json.dumps(send_item["data"]).encode()
                    self.driver.socket_send(
                        socket=self.bind_job,
                        **send_item,
                    )

            if self.driver.bind_check(
                bind=self.bind_job, constant=poller_interval
            ):
                (
                    identity,
                    msg_id,
                    control,
                    _,
                    data,
                    info,
                    stderr,
                    stdout,
                ) = self.driver.socket_recv(socket=self.bind_job)
                if control == self.driver.heartbeat_notice:
                    self.log.debug(
                        "Received Heartbeat from [ %s ]",
                        identity.decode(),
                    )
                    expire = self.driver.get_expiry(
                        heartbeat_interval=self.heartbeat_interval,
                    )
                    metadata = {"time": expire}
                    if data:
                        try:
                            loaded_data = json.loads(data.decode())
                        except Exception:
                            pass
                        else:
                            if loaded_data:
                                metadata.update(loaded_data)

                    self.workers[identity.decode()] = metadata
                else:
                    poller_interval, poller_time = 1, time.time()
                    self.log.debug(
                        "Execution job received [ %s ]", msg_id.decode()
                    )
                    node = identity.decode()
                    node_output = info.decode()
                    if stderr:
                        stderr = stderr.decode()
                    if stdout:
                        stdout = stdout.decode()

                    try:
                        data_item = json.loads(data.decode())
                    except Exception:
                        data_item = dict()

                    self._set_job_status(
                        job_status=control,
                        job_id=msg_id.decode(),
                        identity=node,
                        job_output=node_output,
                        job_stdout=stdout,
                        job_stderr=stderr,
                        execution_time=data_item.get("execution_time", 0),
                        return_timestamp=data_item.get("return_timestamp", 0),
                        component_exec_timestamp=data_item.get(
                            "component_exec_timestamp", 0
                        ),
                        recv_time=time.time(),
                    )

                    for new_task in data_item.get("new_tasks", list()):
                        self.log.debug("New task found: %s", new_task)
                        if "targets" in new_task and new_task["targets"]:
                            targets = [i.encode() for i in new_task["targets"]]
                            self.log.debug(
                                "Using existing targets from old job"
                                " specification %s",
                                targets,
                            )
                        else:
                            targets = self.workers.keys()
                            self.log.debug(
                                "Targets undefined in old job specification"
                                " running everwhere"
                            )

                        # NOTE(cloudnull): If the new task identity is set but
                        #                  with a null value, reset the value
                        #                  to that of the known workers.
                        if "identity" in new_task and not new_task["identity"]:
                            self.log.debug("identities reset to all workers")
                            new_task["identity"] = [
                                i.decode() for i in self.workers.keys()
                            ]

                        if "job_id" not in new_task:
                            new_task["job_id"] = utils.get_uuid()

                        self.create_return_jobs(
                            task=new_task["job_id"],
                            job_item=new_task,
                            targets=targets,
                        )

                        for target in targets:
                            self.log.debug(
                                "Queuing callback job [ %s ] for identity"
                                " [ %s ]",
                                new_task["job_id"],
                                target.decode(),
                            )
                            self.send_queue.put(
                                dict(
                                    identity=target,
                                    command=new_task["verb"].encode(),
                                    data=new_task,
                                )
                            )

            if time.time() > prune_time:
                self.workers.prune()
                prune_time = time.time() + 762

            if sentinel:
                break

    def run_socket_server(self, sentinel=False):
        """Start a socket server.

        The socket server is used to broker a connection from the end user
        into the directord sub-system. The socket server will allow for 1
        message of 10M before requiring the client to reconnect.

        All received data is expected to be JSON serialized data. Before
        being added to the queue, a task ID and SHA3_224 SUM is added to the
        content. This is done for tracking and caching purposes. The task
        ID can be defined in the data. If a task ID is not defined one will
        be generated.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        try:
            os.unlink(self.args.socket_path)
        except OSError:
            if os.path.exists(self.args.socket_path):
                raise SystemExit(
                    "Socket path already exists and wasn't able to be"
                    " cleaned up: {}".format(self.args.socket_path)
                )

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(self.args.socket_path)
        self.log.debug("Socket:%s bound", self.args.socket_path)
        os.chmod(self.args.socket_path, 509)
        uid = 0
        group = getattr(self.args, "socket_group", "root")
        try:
            gid = int(group)
        except ValueError:
            gid = grp.getgrnam(group).gr_gid
        os.chown(self.args.socket_path, uid, gid)
        sock.listen(1)
        while True:
            conn, _ = sock.accept()
            with conn:
                data = conn.recv(409600)
                data_decoded = data.decode()
                json_data = json.loads(data_decoded)
                if "manage" in json_data:
                    self.log.debug("Received manage command: %s", json_data)
                    key, value = next(iter(json_data["manage"].items()))
                    if key == "list_nodes":
                        data = list()
                        for k, v in self.workers.items():
                            if v:
                                expiry = v.pop("time") - time.time()
                                v["expiry"] = expiry
                                try:
                                    data.append((k.decode(), v))
                                except AttributeError:
                                    data.append((str(k), v))
                    elif key == "list_jobs":
                        data = [
                            (str(k), v) for k, v in self.return_jobs.items()
                        ]
                    elif key == "job_info":
                        try:
                            data = [(str(value), self.return_jobs[value])]
                        except KeyError:
                            data = []
                    elif key == "purge_nodes":
                        self.workers.empty()
                        data = {"success": True}
                    elif key == "purge_jobs":
                        self.return_jobs.empty()
                        data = {"success": True}
                    else:
                        data = {"failed": True}

                    try:
                        conn.sendall(json.dumps(data).encode())
                    except BrokenPipeError as e:
                        self.log.error(
                            "Encountered a broken pipe while sending manage"
                            " data. Error:%s",
                            str(e),
                        )
                else:
                    json_data["job_id"] = json_data.get(
                        "job_id", utils.get_uuid()
                    )

                    if "parent_id" not in json_data:
                        json_data["parent_id"] = json_data["job_id"]

                    # Returns the message in reverse to show a return. This
                    # will be a standard client return in JSON format under
                    # normal circomstances.
                    if json_data.get("return_raw", False):
                        msg = json_data["job_id"].encode()
                    else:
                        msg = "Job received. Task ID: {}".format(
                            json_data["job_id"]
                        ).encode()

                    try:
                        conn.sendall(msg)
                    except BrokenPipeError as e:
                        self.log.error(
                            "Encountered a broken pipe while sending job"
                            " data. Error:%s",
                            str(e),
                        )
                    else:
                        self.log.debug("Data sent to queue [ %s ]", json_data)
                        self.job_queue.put(json_data)

            if sentinel:
                break

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            (
                self.thread(
                    name="run_socket_server", target=self.run_socket_server
                ),
                True,
            ),
            (
                self.thread(
                    name="run_interactions", target=self.run_interactions
                ),
                False,
            ),
            (
                self.thread(name="run_backend", target=self.run_backend),
                True,
            ),
        ]

        if self.args.run_ui:
            # low import to ensure nothing flask is loading needlessly.
            from directord import ui  # noqa

            ui_obj = ui.UI(
                args=self.args, jobs=self.return_jobs, nodes=self.workers
            )
            threads.append(
                (self.thread(name="ui", target=ui_obj.start_app), True)
            )

        self.run_threads(threads=threads)
