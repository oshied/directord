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

import json
import os
import socket
import struct
import time

import zmq

from directord import manager
from directord import utils


class Server(manager.Interface):
    """Directord server class."""

    def __init__(self, args):
        """Initialize the Server class.

        Sets up the server object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Server, self).__init__(args=args)

    def heartbeat_bind(self):
        """Bind an address to a heartbeat socket and return the socket.

        :returns: Object
        """

        return self.socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.heartbeat_port,
        )

    def job_bind(self):
        """Bind an address to a job socket and return the socket.

        :returns: Object
        """

        return self.socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.job_port,
        )

    def transfer_bind(self):
        """Bind an address to a transfer socket and return the socket.

        :returns: Object
        """

        return self.socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.transfer_port,
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

        self.bind_heatbeat = self.heartbeat_bind()
        heartbeat_at = self.get_heartbeat
        while True:
            idle_time = heartbeat_at + (self.heartbeat_interval * 3)
            socks = dict(self.poller.poll(1000))
            if socks.get(self.bind_heatbeat) == zmq.POLLIN:
                (
                    identity,
                    _,
                    control,
                    _,
                    data,
                    _,
                    _,
                    _,
                ) = self.socket_multipart_recv(zsocket=self.bind_heatbeat)
                if control in [self.heartbeat_ready, self.heartbeat_notice]:
                    self.log.debug(
                        "Received Heartbeat from [ {} ], client online".format(
                            identity.decode()
                        )
                    )
                    expire = self.get_expiry
                    worker_metadata = {"time": expire}
                    try:
                        loaded_data = json.loads(data.decode())
                    except Exception:
                        pass
                    else:
                        worker_metadata.update(loaded_data)

                    self.workers[identity] = worker_metadata
                    heartbeat_at = self.get_heartbeat
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        identity=identity,
                        control=self.heartbeat_notice,
                        info=struct.pack("<f", expire),
                    )
                    self.log.debug(
                        "Sent Heartbeat to [ {} ]".format(identity.decode())
                    )

            # Send heartbeats to idle workers if it's time
            elif time.time() > idle_time and self.workers:
                for worker in list(self.workers.keys()):
                    self.log.warning(
                        "Sending idle worker [ {} ] a heartbeat".format(worker)
                    )
                    self.socket_multipart_send(
                        zsocket=self.bind_heatbeat,
                        identity=worker,
                        control=self.heartbeat_notice,
                        command=b"reset",
                        info=struct.pack("<f", self.get_expiry),
                    )
                    if time.time() > idle_time + 3:
                        self.log.warning(
                            "Removing dead worker {}".format(worker)
                        )
                        self.workers.pop(worker)
            else:
                self.wq_prune(workers=self.workers)

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
        """

        def return_exec_time(started):
            if started:
                return time.time() - started
            else:
                return 0

        # NOTE(cloudnull): This is where we would need to implement a
        #                  callback plugin for the client.
        job_metadata = self.return_jobs.get(job_id)
        if not job_metadata:
            return

        if job_output:
            job_metadata["INFO"][identity] = job_output

        if job_stdout:
            job_metadata["STDOUT"][identity] = job_stdout

        if job_stderr:
            job_metadata["STDERR"][identity] = job_stderr

        job_metadata["PROCESSING"] = job_status.decode()

        _starttime = job_metadata.get("_starttime")
        _createtime = job_metadata.get("_createtime")
        if job_status == self.job_ack:
            if not _createtime:
                job_metadata["_createtime"] = time.time()
            self.log.debug("{} received job {}".format(identity, job_id))
        elif job_status == self.job_processing:
            if not _starttime:
                job_metadata["_starttime"] = time.time()
            self.log.debug("{} is processing {}".format(identity, job_id))
        elif job_status in [self.job_end, self.nullbyte]:
            self.log.debug(
                "{} finished processing {}".format(identity, job_id)
            )
            if "SUCCESS" in job_metadata:
                job_metadata["SUCCESS"].append(identity)
            else:
                job_metadata["SUCCESS"] = [identity]
            job_metadata["EXECUTION_TIME"] = return_exec_time(
                started=_starttime
            )
            job_metadata["TOTAL_ROUNDTRIP_TIME"] = return_exec_time(
                started=_createtime
            )
        elif job_status == self.job_failed:
            if "FAILED" in job_metadata:
                job_metadata["FAILED"].append(identity)
            else:
                job_metadata["FAILED"] = [identity]
            job_metadata["EXECUTION_TIME"] = return_exec_time(
                started=_starttime
            )
            job_metadata["TOTAL_ROUNDTRIP_TIME"] = return_exec_time(
                started=_createtime
            )

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
                self.socket_multipart_send(
                    zsocket=self.bind_transfer,
                    identity=identity,
                    command=verb,
                    data=chunk,
                )
            else:
                self.socket_multipart_send(
                    zsocket=self.bind_transfer,
                    identity=identity,
                    control=self.transfer_end,
                    command=verb,
                )

    def create_return_jobs(self, task, job_item, targets):
        if task not in self.return_jobs:
            job_info = self.return_jobs[task] = {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": [i.decode() for i in targets],
                "VERB": job_item["verb"],
                "TRANSFERS": list(),
                "TASK_SHA1": job_item["task_sha1sum"],
                "JOB_DEFINITION": job_item,
                "PARENT_JOB_ID": job_item.get("parent_id"),
                "_createtime": time.time(),
            }
            return job_info
        else:
            return self.return_jobs[task]

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
            job_item = self.job_queue.get(block=False, timeout=1)
        except Exception:
            self.log.debug(
                "Directord server found nothing to do, cooling down"
                " the poller."
            )
            return 512, time.time()
        else:
            restrict_sha1 = job_item.get("restrict")
            if restrict_sha1:
                if job_item["task_sha1sum"] not in restrict_sha1:
                    self.log.debug(
                        "Job restriction %s is unknown.", restrict_sha1
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
                            "Target {} is in an unknown state.".format(
                                job_target
                            )
                        )
                        return 512, time.time()
            else:
                targets = self.workers.keys()

            if job_item.get("run_once", False) and not run_query:
                self.log.debug("Run once enabled.")
                targets = [targets[0]]

            if run_query:
                job_item["targets"] = [i.decode() for i in targets]

            task = job_item.get("task", utils.get_uuid())
            job_info = self.create_return_jobs(
                task=task, job_item=job_item, targets=targets
            )
            self.log.debug("Sending job:%s", job_item)
            for identity in targets:
                if job_item["verb"] in ["ADD", "COPY"]:
                    for file_path in job_item["from"]:
                        job_item["file_sha1sum"] = utils.file_sha1(
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
                        self.socket_multipart_send(
                            zsocket=self.bind_job,
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
                    self.socket_multipart_send(
                        zsocket=self.bind_job,
                        identity=identity,
                        command=job_item["verb"].encode(),
                        data=json.dumps(job_item).encode(),
                    )

                self.log.debug("Sent job {} to {}".format(task, identity))
            else:
                self.return_jobs[task] = job_info

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

        self.bind_job = self.job_bind()
        self.bind_transfer = self.transfer_bind()
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

            socks = dict(self.poller.poll(poller_interval))

            if socks.get(self.bind_transfer) == zmq.POLLIN:
                poller_interval, poller_time = 128, time.time()

                (
                    identity,
                    msg_id,
                    control,
                    command,
                    _,
                    info,
                    _,
                    _,
                ) = self.socket_multipart_recv(zsocket=self.bind_transfer)
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
                elif control == self.transfer_end:
                    self.log.debug(
                        "Transfer complete for [ %s ]", info.decode()
                    )
                    self._set_job_status(
                        job_status=control,
                        job_id=msg_id.decode(),
                        identity=identity.decode(),
                        job_output=info.decode(),
                    )

            elif socks.get(self.bind_job) == zmq.POLLIN:
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
                ) = self.socket_multipart_recv(zsocket=self.bind_job)
                node = identity.decode()
                node_output = info.decode()
                if stderr:
                    stderr = stderr.decode()
                if stdout:
                    stdout = stdout.decode()
                self._set_job_status(
                    job_status=control,
                    job_id=msg_id.decode(),
                    identity=node,
                    job_output=node_output,
                    job_stdout=stdout,
                    job_stderr=stderr,
                )
                if command == b"QUERY":
                    try:
                        data_item = json.loads(data.decode())
                    except Exception:
                        data_item = dict()
                    # NOTE(cloudnull): When a command return is "QUERY" an ARG
                    #                  is resent to all known workers.
                    try:
                        query_value = json.loads(node_output)
                    except Exception as e:
                        self.log.error(
                            "Query value failed to load, VALUE:%s, ERROR:%s",
                            node_output,
                            str(e),
                        )
                    else:
                        if query_value and data_item:
                            targets = self.workers.keys()
                            task = data_item["task"] = utils.get_uuid()
                            data_item["skip_cache"] = True
                            data_item["verb"] = "ARG"
                            data_item["args"] = {
                                "query": {
                                    node: {data_item.pop("query"): query_value}
                                }
                            }
                            data_item.pop("task_sha1sum", None)
                            data_item["task_sha1sum"] = utils.object_sha1(
                                data_item
                            )
                            self.create_return_jobs(
                                task=task, job_item=data_item, targets=targets
                            )
                            self.log.debug(
                                "Runing query against with DATA: %s", data_item
                            )
                            for target in targets:
                                self.log.debug(
                                    "Runing query ARG update against"
                                    " TARGET: %s",
                                    target.decode(),
                                )
                                self.socket_multipart_send(
                                    zsocket=self.bind_job,
                                    identity=target,
                                    command=data_item["verb"].encode(),
                                    data=json.dumps(data_item).encode(),
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
        being added to the queue, a task ID and SHA1 SUM is added to the
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
                            data.append((key.decode(), value))

                    elif manage == "list-jobs":
                        data = [
                            (str(k), v) for k, v in self.return_jobs.items()
                        ]
                    elif manage == "purge-nodes":
                        self.wq_empty(workers=self.workers)
                        data = {"success": True}
                    elif manage == "purge-jobs":
                        self.wq_empty(workers=self.return_jobs)
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
                    json_data["task"] = json_data.get("task", utils.get_uuid())
                    if "parent_id" not in json_data:
                        json_data["parent_id"] = json_data["task"]

                    # Returns the message in reverse to show a return. This
                    # will be a standard client return in JSON format under
                    # normal circomstances.
                    if json_data.get("return_raw", False):
                        msg = json_data["task"].encode()
                    else:
                        msg = "Job received. Task ID: {}".format(
                            json_data["task"]
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
                        self.log.debug(
                            "Data sent to queue, {}".format(json_data)
                        )
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
            self.thread(target=self.run_socket_server),
            self.thread(target=self.run_heartbeat),
            self.thread(target=self.run_interactions),
        ]

        if self.args.run_ui:
            # low import to ensure nothing flask is loading needlessly.
            from directord import ui  # noqa

            ui_obj = ui.UI(
                args=self.args, jobs=self.return_jobs, nodes=self.workers
            )
            threads.append(self.thread(target=ui_obj.start_app))

        self.run_threads(threads=threads)
