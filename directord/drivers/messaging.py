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

from oslo_config import cfg
import oslo_messaging
from oslo_messaging.rpc import dispatcher
from oslo_messaging.rpc.server import expose


from directord import drivers


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

        self.log.info("Handling heartbeat")
        self.interface.handle_heartbeat(identity=identity, data=data)

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

        self.log.info("Handling job [ %s ] for [ %s ]", job_id, identity)

        if self.mode == "server":
            kwargs = dict(
                identity=identity,
                job_id=job_id,
                control=control,
                data=data,
                info=info,
                stderr=stderr,
                stdout=stdout,
            )
        else:
            kwargs = dict(
                command=command,
                data=data,
                info=info,
            )

        self.interface.handle_job(**kwargs)

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

        client = oslo_messaging.RPCClient(self.transport, target)

        return client.call({}, method, **kwargs)

    def backend_check(self, interval=1, constant=1000):
        """Return True if the backend contains work ready."""

        pass

    def backend_close(self):
        """Close the backend."""

        pass

    def backend_init(self):
        """Initialize the backend."""

        pass

    def backend_recv(self):
        """Receive a message."""

        pass

    def backend_send(self, *args, **kwargs):
        """Send a message over the backend."""

        pass

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

        method = "_heartbeat"
        topic = "directord"

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
            method,
            topic,
            server="directord",
            identity=self.identity,
            data=data,
        )

    def job_check(self, interval=1, constant=1000):
        """Return True if a job contains work ready."""

        pass

    def job_close(self):
        """Stop the server mode."""

        self.log.info("Stopping messaging server")
        if not self.server:
            self.log.info("No server to stop")
        else:
            self.server.stop()
            self.server.wait()

    def job_init(self, sentinel=False):
        """Run in server mode.

        :param sentinel: Breaks the loop
        :type sentinel: Boolean
        """

        if self.mode == "server":
            server_target = "directord"
        else:
            server_target = self.machine_id

        self.server = oslo_messaging.get_rpc_server(
            transport=self.transport,
            target=oslo_messaging.Target(
                topic="directord",
                server=server_target,
            ),
            endpoints=[self],
            executor="threading",
            access_policy=dispatcher.ExplicitRPCAccessPolicy,
        )
        self.log.info("Starting messaging server")
        self.server.start()

    def job_recv(self):
        """Receive a message."""

        pass

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

        method = "_job"
        topic = "directord"

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
            method,
            topic,
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

    def key_generate(self, keys_dir, key_type):
        """Generate certificate."""

        pass
