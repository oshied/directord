#   Copyright 2021 Red Hat, Inc.
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
import logging
import multiprocessing
import time

from oslo_config import cfg
import oslo_messaging
from oslo_messaging.rpc import dispatcher
from oslo_messaging.rpc.server import expose

import tenacity

from directord import drivers
from directord import logger


class Driver(drivers.BaseDriver):
    def __init__(
        self,
        args,
        encrypted_traffic_data=None,
        connection_string=None,
        interface=None,
    ):
        """Initialize the Driver.

        :param args: Arguments parsed by argparse.
        :type args: Object
        :param encrypted_traffic: Enable|Disable encrypted traffic.
        :type encrypted_traffic: Boolean
        :param connection_string: Connection string used to provide connection
                                  instructions to the driver.
        :type connection_string: String.
        :param interface: The interface instance (client/server)
        :type interface: Object
        """

        super(Driver, self).__init__(
            args=args,
            encrypted_traffic_data=encrypted_traffic_data,
            connection_string=connection_string,
            interface=interface,
        )
        self.mode = getattr(args, "mode", None)
        self.connection_string = connection_string
        self.conf = cfg.CONF
        self.conf.transport_url = "{}:5672/".format(self.connection_string)
        self.transport = oslo_messaging.get_rpc_transport(self.conf)
        self.server = None
        self.backend_server = None
        self.job_q = multiprocessing.Queue()
        self.backend_q = multiprocessing.Queue()
        self.timeout = 1

    def _check(self, queue, interval=1, constant=1000):
        """Return True if a job contains work ready.

        :param queue: Queueing object.
        :type queue: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Boolean
        """

        self.timeout = interval * (constant * 0.001)
        if queue.empty():
            time.sleep(self.timeout)
            return False
        else:
            return True

    @expose
    def _heartbeat(self, context, identity, data):
        """Handle a heartbeat interaction.

        :param context: RPC Context
        :type context: Dictionary
        :param identity: Client identity
        :type identity: String
        :param data: Heartbeat data
        :type data: Dictionary
        """

        self.log.debug("Handling heartbeat for [ %s ]", identity)
        self.job_q.put(
            [
                identity,
                None,
                self.heartbeat_notice,
                None,
                data,
                None,
                None,
                None,
            ]
        )

    @expose
    def _job(
        self,
        context,
        identity=None,
        job_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Handle a job interaction.

        :param context: RPC Context
        :type context: Dictionary
        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        :param stderr: Job stderr output
        :type stderr: String
        :param stdout: Job stdout output
        :type stdout: String
        """

        self.log.debug("Handling job [ %s ] for [ %s ]", job_id, identity)
        job = [
            job_id,
            control,
            command,
            data,
            info,
            stderr,
            stdout,
        ]

        if self.mode == "server":
            job.insert(0, identity)

        self.job_q.put(job)

    @expose
    def _backend(
        self,
        context,
        identity=None,
        job_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Handle a backend interaction.

        :param context: RPC Context
        :type context: Dictionary
        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        :param stderr: Job stderr output
        :type stderr: String
        :param stdout: Job stdout output
        :type stdout: String
        """

        self.log.debug("Handling backend [ %s ] for [ %s ]", job_id, identity)
        job = [
            job_id,
            control,
            command,
            data,
            info,
            stderr,
            stdout,
        ]

        if self.mode == "server":
            job.insert(0, identity)

        self.backend_q.put(job)

    def _close(self, process_obj):
        """Close the backend.

        :param process_obj: Server process object
        :type process_obj: Object
        """

        self.log.debug("Stopping messaging server")
        if not process_obj:
            self.log.debug("No server to stop")
        else:
            process_obj.stop()
            process_obj.wait()
            self.log.debug("Server to stopped")

    def _init_rpc_servers(self):
        """Initialize the rpc server."""

        if self.mode == "server":
            server_target = "directord"
        else:
            server_target = self.machine_id

        if not self.backend_server:
            self.backend_server = self._rpc_server(
                server_target=server_target, topic="directord-backend"
            )
            self.log.info("Starting messaging backend server")
            self.backend_server.start(override_pool_size=1)

        if not self.server:
            self.server = self._rpc_server(
                server_target=server_target, topic="directord"
            )
            self.log.info("Starting messaging server")
            self.server.start(override_pool_size=1)

    def _process_send(
        self,
        method,
        topic,
        identity=None,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Send a job message.

        :param method: messaging method
        :type method: String
        :param topic: Messaging topic
        :type topic: String
        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        :param stderr: Job stderr output
        :type stderr: String
        :param stdout: Job stdout output
        :type stdout: String
        """

        if not identity:
            target = "directord"
            identity = self.identity
        else:
            worker = self.interface.workers.get(identity)
            target = worker.get("machine_id")

            if not target:
                self.log.fatal(
                    "Machine ID for identity [ %s ] not found", identity
                )

        self._send(
            method=method,
            topic=topic,
            server=target,
            identity=identity,
            job_id=msg_id,
            control=control,
            command=command,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout,
        )

    def _rpc_server(self, server_target, topic):
        """Returns an rpc server object.

        :param server_target: OSLO target object
        :type server_target: Object
        :param topic: Messaging topic
        :type topic: String
        :returns: Object
        """

        return oslo_messaging.get_rpc_server(
            transport=self.transport,
            target=oslo_messaging.Target(
                topic=topic,
                server=server_target,
            ),
            endpoints=[self],
            executor="threading",
            access_policy=dispatcher.ExplicitRPCAccessPolicy,
        )

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(
            oslo_messaging.exceptions.MessagingTimeout
        ),
        wait=tenacity.wait_fixed(1),
        before_sleep=tenacity.before_sleep_log(
            logger.getLogger(name="directord"), logging.WARN
        ),
    )
    def _send(self, method, topic, server="directord", **kwargs):
        """Send a message.

        :param method: Send method type
        :type method: String
        :param topic: Messaging topic
        :type topic: String
        :param method: Server name
        :type method: String
        :param kwargs: Extra named arguments
        :type kwargs: Dictionary
        :returns: Object
        """

        if server:
            target = oslo_messaging.Target(topic=topic, server=server)
        else:
            target = oslo_messaging.Target(topic=topic)

        client = oslo_messaging.RPCClient(self.transport, target, timeout=2)

        return client.call({}, method, **kwargs)

    def backend_check(self, interval=1, constant=1000):
        """Return True if the backend contains work ready.

        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Boolean
        """

        return self._check(
            queue=self.backend_q, interval=interval, constant=constant
        )

    def backend_close(self):
        """Close the backend."""

        self.log.debug(
            "The messaging driver does not initialize a backend connection"
            " so nothing to close"
        )

    def backend_init(self, sentinel=False):
        """Initialize servers.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self.log.debug(
            "The messaging driver does not initialize a backend connection"
            " so nothing to start"
        )

    def backend_recv(self):
        """Receive a message."""

        return self.backend_q.get()

    def backend_send(
        self,
        identity=None,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Send a message over the backend.

        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        :param stderr: Job stderr output
        :type stderr: String
        :param stdout: Job stdout output
        :type stdout: String
        """

        self._process_send(
            method="_backend",
            topic="directord-backend",
            identity=identity,
            msg_id=msg_id,
            control=control,
            command=command,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout,
        )

    def heartbeat_send(
        self, host_uptime=None, agent_uptime=None, version=None
    ):
        """Send a heartbeat.

        :param host_uptime: Sender uptime
        :type host_uptime: String
        :param agent_uptime: Sender agent uptime
        :type agent_uptime: String
        :param version: Sender directord version
        :type version: String
        """

        data = json.dumps(
            {
                "version": version,
                "host_uptime": host_uptime,
                "agent_uptime": agent_uptime,
                "machine_id": self.machine_id,
            }
        )

        self.log.info("Sending heartbeat from [ %s ] to server", self.identity)

        self._send(
            method="_heartbeat",
            topic="directord",
            server="directord",
            identity=self.identity,
            data=data,
        )

    def job_check(self, interval=1, constant=1000):
        """Return True if a job contains work ready.

        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Boolean
        """

        return self._check(
            queue=self.job_q, interval=interval, constant=constant
        )

    def job_close(self):
        """Stop the server mode."""

        self._close(process_obj=self.server)
        self._close(process_obj=self.backend_server)

    def job_init(self, sentinel=False):
        """Initialize servers.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        self._init_rpc_servers()

    def job_recv(self):
        """Receive a message."""

        return self.job_q.get()

    def job_send(
        self,
        identity=None,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Send a job message.

        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param command: Command
        :type command: String
        :param data: Job data
        :type data: Dictionary
        :param info: Job info
        :type info: Dictionary
        :param stderr: Job stderr output
        :type stderr: String
        :param stdout: Job stdout output
        :type stdout: String
        """

        self._process_send(
            method="_job",
            topic="directord",
            identity=identity,
            msg_id=msg_id,
            control=control,
            command=command,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout,
        )

    def key_generate(self, keys_dir, key_type):
        """Generate certificate."""

        pass
