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

import grp
import json
import multiprocessing
import os
import socket
import struct
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
        self.bind_heatbeat = None
        datastore = getattr(self.args, "datastore", None)
        if not datastore:
            self.log.info("Connecting to internal datastore")
            directord.plugin_import(plugin=".datastores.internal")
            manager = multiprocessing.Manager()
            self.workers = manager.document()
            self.return_jobs = manager.document()
        else:
            url = urlparse.urlparse(datastore)
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

    def run_heartbeat(self, sentinel=False):
        """Execute the heartbeat loop.

        If the heartbeat loop detects a problem, the server will send a
        heartbeat probe to the client to ensure that it is alive. At the
        end of the loop workers without a valid heartbeat will be pruned
        from the available pool.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_heatbeat = self.driver.heartbeat_bind()
        heartbeat_at = self.driver.get_heartbeat(
            interval=self.heartbeat_interval
        )
        while True:
            idle_time = heartbeat_at + (self.heartbeat_interval * 3)
            if self.bind_heatbeat and self.driver.bind_check(
                bind=self.bind_heatbeat
            ):
                (
                    identity,
                    _,
                    control,
                    _,
                    data,
                    _,
                    _,
                    _,
                ) = self.driver.socket_recv(socket=self.bind_heatbeat)
                if control in [
                    self.driver.heartbeat_ready,
                    self.driver.heartbeat_notice,
                ]:
                    self.log.debug(
                        "Received Heartbeat from [ %s ], client online",
                        identity.decode(),
                    )
                    expire = self.driver.get_expiry(
                        heartbeat_interval=self.heartbeat_interval,
                        interval=self.heartbeat_liveness,
                    )
                    worker_metadata = {"time": expire}
                    try:
                        loaded_data = json.loads(data.decode())
                    except Exception:
                        pass
                    else:
                        worker_metadata.update(loaded_data)

                    self.workers[identity] = worker_metadata
                    heartbeat_at = self.driver.get_heartbeat(
                        interval=self.heartbeat_interval
                    )
                    self.driver.socket_send(
                        socket=self.bind_heatbeat,
                        identity=identity,
                        control=self.driver.heartbeat_notice,
                        info=struct.pack("<f", expire),
                    )
                    self.log.debug(
                        "Sent Heartbeat to [ %s ]", identity.decode()
                    )

            # Send heartbeats to idle workers if it's time
            elif time.time() > idle_time:
                for worker in list(self.workers.keys()):
                    self.log.warning(
                        "Sending idle worker [ %s ] a heartbeat", worker
                    )
                    self.driver.socket_send(
                        socket=self.bind_heatbeat,
                        identity=worker,
                        control=self.driver.heartbeat_notice,
                        command=b"reset",
                        info=struct.pack(
                            "<f",
                            self.driver.get_expiry(
                                heartbeat_interval=self.heartbeat_interval,
                                interval=self.heartbeat_liveness,
                            ),
                        ),
                    )
                    if time.time() > idle_time + 3:
                        self.log.warning("Removing dead worker %s", worker)
                        self.workers.pop(worker)
            else:
                self.log.debug("Items after prune %s", self.workers.prune())

            if sentinel:
                break

    def _set_job_status(
        self,
        job_status,
        job_id,
        identity,
        job_output,
        job_stdout=None,
        job_stderr=None,
        execution_time=0,
        recv_time=0,
    ):
        """Set job status.

        This will update the manager object for job tracking, allowing the
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
        :param recv_time: Time a task return was received.
        :type recv_tim: Float
        """

        job_metadata = self.return_jobs.get(job_id)
        if not job_metadata:
            return

        if job_output:
            job_metadata["INFO"][identity] = job_output

        if job_stdout:
            job_metadata["STDOUT"][identity] = job_stdout

        if job_stderr:
            job_metadata["STDERR"][identity] = job_stderr

        self.log.debug("current job [ %s ] state [ %s ]", job_id, job_status)
        job_metadata["PROCESSING"] = job_status.decode()

        _createtime = job_metadata.get("_createtime")
        if not _createtime:
            _createtime = job_metadata["_createtime"] = time.time()

        if job_status == self.driver.job_ack:
            self.log.debug("%s received job %s", identity, job_id)
        elif job_status == self.driver.job_processing:
            self.log.debug("%s is processing %s", identity, job_id)
        elif job_status in [self.driver.job_end, self.driver.nullbyte]:
            self.log.debug("%s finished processing %s", identity, job_id)
            if "SUCCESS" in job_metadata:
                job_metadata["SUCCESS"].append(identity)
            else:
                job_metadata["SUCCESS"] = [identity]
            job_metadata["EXECUTION_TIME"] = float(execution_time)
            job_metadata["ROUNDTRIP_TIME"] = recv_time - _createtime
        elif job_status == self.driver.job_failed:
            if "FAILED" in job_metadata:
                job_metadata["FAILED"].append(identity)
            else:
                job_metadata["FAILED"] = [identity]
            job_metadata["EXECUTION_TIME"] = float(execution_time)
            job_metadata["ROUNDTRIP_TIME"] = recv_time - _createtime

        self.return_jobs[job_id] = job_metadata

    def _run_transfer(self, identity, verb, file_path):
        """Run file transfer job.

        The transfer process will transfer all files from a given meta data
        set using strict identity targetting.

        When a file is initiated all chunks will be sent over the wire.

        :param identity: Node name
        :type identity: String
        :param verb: Action taken
        :type verb: Bytes
        :param file_path: Path of file to transfer.
        :type file_path: String
        """

        self.log.debug("Processing file [ %s ]", file_path)
        if not os.path.isfile(file_path):
            self.log.error("File was not found. File path:%s", file_path)
            return

        self.log.info("File transfer for [ %s ] starting", file_path)
        with open(file_path, "rb") as f:
            for chunk in self.read_in_chunks(file_object=f):
                self.driver.socket_send(
                    socket=self.bind_transfer,
                    identity=identity,
                    command=verb,
                    data=chunk,
                )
            else:
                self.driver.socket_send(
                    socket=self.bind_transfer,
                    identity=identity,
                    control=self.driver.transfer_end,
                    command=verb,
                )

    def create_return_jobs(self, task, job_item, targets):
        return self.return_jobs.set(
            task,
            {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": [i.decode() for i in targets],
                "VERB": job_item["verb"],
                "TRANSFERS": list(),
                "JOB_SHA3_224": job_item["job_sha3_224"],
                "JOB_DEFINITION": job_item,
                "PARENT_JOB_ID": job_item.get("parent_id"),
                "_createtime": time.time(),
            },
        )

    def run_job(self):
        """Run a job interaction

        As the job loop executes it will interrogate the job item as returned
        from the queue. If the item contains a "targets" definition the
        job loop will only send the message to the given targets, assuming the
        target is known within the workers object, otherwise all targets will
        receive the message. If a defined target is not found within the
        workers object no job will be executed.

        :returns: Tuple
        """

        try:
            job_item = self.job_queue.get_nowait()
        except Exception:
            self.log.debug(
                "Directord server found nothing to do, cooling down"
                " the poller."
            )
            return 512, time.time()
        else:
            restrict_sha3_224 = job_item.get("restrict")
            if restrict_sha3_224:
                if job_item["job_sha3_224"] not in restrict_sha3_224:
                    self.log.debug(
                        "Job restriction %s is unknown.", restrict_sha3_224
                    )
                    return 512, time.time()

            job_targets = job_item.pop("targets", list())
            # NOTE(cloudnull): We run on all targets if query is used.
            run_query = job_item["verb"] == "QUERY"

            if job_targets and not run_query:
                targets = list()
                for job_target in job_targets:
                    job_target = job_target.encode()
                    if job_target in self.workers:
                        targets.append(job_target)
                    else:
                        self.log.critical(
                            "Target %s is in an unknown state.", job_target
                        )
                        return 512, time.time()
            else:
                targets = self.workers.keys()

            if job_item.get("run_once", False) and not run_query:
                self.log.debug("Run once enabled.")
                targets = [targets[0]]

            if run_query:
                job_item["targets"] = [i.decode() for i in targets]

            job_id = job_item.get("job_id", utils.get_uuid())
            job_info = self.create_return_jobs(
                task=job_id, job_item=job_item, targets=targets
            )
            self.log.debug("Sending job:%s", job_item)
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

                        if job_item["file_to"] not in job_info["TRANSFERS"]:
                            job_info["TRANSFERS"].append(job_item["file_to"])

                        self.log.debug(
                            "Sending file transfer message for"
                            " file_path:%s to identity:%s",
                            file_path,
                            identity.decode(),
                        )
                        self.driver.socket_send(
                            socket=self.bind_job,
                            identity=identity,
                            command=job_item["verb"].encode(),
                            data=json.dumps(job_item).encode(),
                            info=file_path.encode(),
                        )
                else:
                    self.log.debug(
                        "Sending job message for job:%s to identity:%s",
                        job_item["verb"].encode(),
                        identity.decode(),
                    )
                    self.driver.socket_send(
                        socket=self.bind_job,
                        identity=identity,
                        command=job_item["verb"].encode(),
                        data=json.dumps(job_item).encode(),
                    )

                self.log.debug("Sent job %s to %s", job_id, identity)
            else:
                self.return_jobs[job_id] = job_info

        return 128, time.time()

    def run_interactions(self, sentinel=False):
        """Execute the interactions loop.

        Directord's interaction executor will slow down the poll interval
        when no work is present. This means Directord will ramp-up resource
        utilization when required and become virtually idle when there's
        nothing to do.

        * Initial poll interval is 1024, maxing out at 2048. When work is
          present, the poll interval is 128.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.bind_job = self.driver.job_bind()
        self.bind_transfer = self.driver.transfer_bind()
        poller_time = time.time()
        poller_interval = 128

        while True:
            current_time = time.time()
            if current_time > poller_time + 64:
                if poller_interval != 2048:
                    self.log.info("Directord server entering idle state.")
                poller_interval = 2048
            elif current_time > poller_time + 32:
                if poller_interval != 1024:
                    self.log.info("Directord server ramping down.")
                poller_interval = 1024

            if self.driver.bind_check(
                bind=self.bind_transfer, constant=poller_interval
            ):
                poller_interval, poller_time = 64, time.time()

                (
                    identity,
                    msg_id,
                    control,
                    command,
                    _,
                    info,
                    _,
                    _,
                ) = self.driver.socket_recv(socket=self.bind_transfer)
                if command == b"transfer":
                    transfer_obj = info.decode()
                    self.log.debug(
                        "Executing transfer for [ %s ]", transfer_obj
                    )
                    self._run_transfer(
                        identity=identity,
                        verb=b"ADD",
                        file_path=os.path.abspath(
                            os.path.expanduser(transfer_obj)
                        ),
                    )
                elif control == self.driver.transfer_end:
                    self.log.debug(
                        "Transfer complete for [ %s ]", info.decode()
                    )
                    self._set_job_status(
                        job_status=control,
                        job_id=msg_id.decode(),
                        identity=identity.decode(),
                        job_output=info.decode(),
                    )
            elif self.driver.bind_check(
                bind=self.bind_job, constant=poller_interval
            ):
                poller_interval, poller_time = 64, time.time()
                (
                    identity,
                    msg_id,
                    control,
                    command,
                    data,
                    info,
                    stderr,
                    stdout,
                ) = self.driver.socket_recv(socket=self.bind_job)
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
                    recv_time=time.time(),
                )

                for new_task in data_item.get("new_tasks", list()):
                    self.log.debug("New task found: %s", new_task)
                    if "targets" in new_task:
                        targets = [i.encode() for i in new_task["targets"]]
                    else:
                        targets = self.workers.keys()

                    if "job_id" not in new_task:
                        new_task["job_id"] = utils.get_uuid()

                    self.create_return_jobs(
                        task=new_task["job_id"],
                        job_item=new_task,
                        targets=targets,
                    )

                    for target in targets:
                        self.log.debug(
                            "Runing job %s against TARGET: %s",
                            new_task["job_id"],
                            target.decode(),
                        )
                        self.driver.socket_send(
                            socket=self.bind_job,
                            identity=target,
                            command=new_task["verb"].encode(),
                            data=json.dumps(new_task).encode(),
                        )

            elif self.workers:
                poller_interval, poller_time = self.run_job()

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
                    manage = json_data["manage"]
                    if manage == "list-nodes":
                        data = list()
                        for key, value in self.workers.items():
                            expiry = value.pop("time") - time.time()
                            value["expiry"] = expiry
                            try:
                                data.append((key.decode(), value))
                            except AttributeError:
                                data.append((str(key), value))
                    elif manage == "list-jobs":
                        data = [
                            (str(k), v) for k, v in self.return_jobs.items()
                        ]
                    elif manage == "purge-nodes":
                        self.workers.empty()
                        data = {"success": True}
                    elif manage == "purge-jobs":
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
                        self.log.debug("Data sent to queue, %s", json_data)
                    finally:
                        self.job_queue.put(json_data)
            if sentinel:
                break

    def worker_run(self):
        """Run all work related threads.

        Threads are gathered into a list of process objects then fed into the
        run_threads method where their execution will be managed.
        """

        threads = [
            (self.thread(target=self.run_socket_server), True),
            (self.thread(target=self.run_heartbeat), True),
            (self.thread(target=self.run_interactions), True),
        ]

        if self.args.run_ui:
            # low import to ensure nothing flask is loading needlessly.
            from directord import ui  # noqa

            ui_obj = ui.UI(
                args=self.args, jobs=self.return_jobs, nodes=self.workers
            )
            threads.append((self.thread(target=ui_obj.start_app), True))

        self.run_threads(threads=threads)
