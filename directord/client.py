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

from directord import components
import json
import os
import struct
import time

import diskcache
import zmq

import directord
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

    def run_heartbeat(self, sentinel=False):
        """Execute the heartbeat loop.

        If the heartbeat loop detects a problem, the connection will be
        reset using a backoff, with a max wait of up to 32 seconds.

        This loop tracks heartbeat messages and should the heartbeat
        interval take longer than the expire time, and fail more than 5
        times the connection will be reset after a failure cooldown.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
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
                    _,
                    _,
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

            if sentinel:
                break

    def _job_executor(
        self,
        conn,
        cache,
        info,
        job,
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

        self.log.debug("Running component:%s", command.decode())

        if cached:
            # TODO(cloudnull): Figure out how to skip cache when file
            #                  transfering.
            self.log.info("Cache hit on {}, task skipped.".format(job_sha1))
            conn.info = b"job skipped"
            conn.job_state = self.job_end
            return None, None, None

        component_kwargs = dict(conn=conn, cache=cache, job=job)

        if command in [b"ARG", b"ENV"]:
            component_name = b"cache"
            component_kwargs["command"] = command
        elif command in [b"ADD", b"COPY"]:
            component_name = b"transfer"
            component_kwargs["source_file"] = info
            component_kwargs["job_id"] = job_id
        else:
            component_name = command

        success, _, component = directord.component_import(
            component=component_name.decode().lower(),
            job_id=job_id,
        )
        if not success:
            self.log.warning(component)
            return None, None, success

        return component.client(**component_kwargs)

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

        self.bind_job = self.job_connect()
        self.bind_transfer = self.transfer_connect()
        poller_time = time.time()
        poller_interval = 128
        cache_check_time = time.time()

        # Ensure that the cache path exists before executing.
        os.makedirs(self.args.cache_path, exist_ok=True)
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

            base_component = components.ComponentBase()
            if self.bind_job in dict(self.poller.poll(poller_interval)):
                with diskcache.Cache(
                    self.args.cache_path, tag_index=True
                ) as cache:
                    poller_interval, poller_time = 128, time.time()
                    (
                        _,
                        _,
                        command,
                        data,
                        info,
                        _,
                        _,
                    ) = self.socket_multipart_recv(zsocket=self.bind_job)
                    job = json.loads(data.decode())
                    job_id = job.get("task", utils.get_uuid())
                    job_sha1 = job.get("task_sha1sum", utils.object_sha1(job))
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

                    with utils.ClientStatus(
                        socket=self.bind_job,
                        job_id=job_id.encode(),
                        command=command,
                        ctx=self,
                    ) as c:
                        if cache.get(job_parent_id) is False:
                            self.log.error(
                                "Parent failure {} skipping {}".format(
                                    job_parent_id, job_id
                                )
                            )
                            status = (
                                "Job [ {} ] was not allowed to run because"
                                " there was a failure under this partent ID"
                                " [ {} ]".format(job_id, job_parent_id)
                            )

                            self.log.error(status)
                            c.info = status.encode()
                            c.job_state = self.job_failed

                            if sentinel:
                                break
                            else:
                                continue

                        with self.timeout(
                            time=job.get("timeout", 600), job_id=job_id
                        ):
                            stdout, stderr, outcome = self._job_executor(
                                conn=c,
                                cache=cache,
                                info=info,
                                job=job,
                                job_id=job_id,
                                job_sha1=job_sha1,
                                cached=cache_hit,
                                command=command,
                            )

                        if stdout:
                            stdout = stdout.strip()
                            if not isinstance(stdout, bytes):
                                stdout = stdout.encode()
                            c.stdout = stdout
                            self.log.info(stdout)

                        if stderr:
                            stderr = stderr.strip()
                            if not isinstance(stderr, bytes):
                                stderr = stderr.encode()
                            c.stderr = stderr
                            self.log.error(stderr)

                        if command == b"QUERY":
                            c.data = json.dumps(job).encode()
                            if stdout:
                                c.info = stdout

                        if outcome is False:
                            state = c.job_state = self.job_failed
                            self.log.error("Job failed {}".format(job_id))
                            if job_parent_id:
                                base_component.set_cache(
                                    cache=cache,
                                    key=job_parent_id,
                                    value=False,
                                    tag="parents",
                                )
                        elif outcome is True:
                            state = c.job_state = self.job_end
                            self.log.info("Job complete {}".format(job_id))
                            if job_parent_id:
                                base_component.set_cache(
                                    cache=cache,
                                    key=job_parent_id,
                                    value=True,
                                    tag="parents",
                                )
                        else:
                            state = self.nullbyte

                    base_component.set_cache(
                        cache=cache,
                        key=job_sha1,
                        value=state,
                        tag="jobs",
                    )

            if sentinel:
                break

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
