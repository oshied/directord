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
import subprocess
import time
import multiprocessing

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
        self.conf.transport_url = "amqp://{}:5672//".format(
            self.interface.bind_address
        )
        self.transport = oslo_messaging.get_rpc_transport(self.conf)

        # TODO(cloudnull): Start the qrouterd process when in server mode.
        #                  This should be removed once we're confident with
        #                  the driver capability in favor of requirement docs.
        self._driver_server = multiprocessing.Process(
            target=self._run, daemon=True
        )
        self._driver_server.start()

    def _run(self):
        """Run in server mode."""

        if self.mode == "server":
            self.qdrouterd()
            server_target = "directord"
        else:
            server_target = self.interface.uuid

        target = oslo_messaging.Target(topic="directord", server=server_target)
        endpoints = [self]
        server = oslo_messaging.get_rpc_server(
            self.transport,
            target,
            endpoints,
            executor="threading",
            access_policy=dispatcher.ExplicitRPCAccessPolicy,
        )
        self.log.info("Starting messaging server.")
        server.start()
        while True:
            time.sleep(1)

    def qdrouterd(self):
        """Start the qdrouterd process as a daemon."""

        self.log.info("Starting qdrouterd.")
        subprocess.run(["qdrouterd", "-d"], check=True)

    def send(self, method, topic, server="directord", **kwargs):
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

    def heartbeat_send(
        self, identity=None, host_uptime=None, agent_uptime=None, version=None
    ):
        """Send a heartbeat.

        :param identity: Sender identity (uuid)
        :type identity: String
        :param host_uptime: Sender uptime
        :type host_uptime: String
        :param agent_uptime: Sender agent uptime
        :type agent_uptime: String
        :param version: Sender directord version
        :type version: String
        """

        method = "heartbeat"
        topic = "directord"

        data = json.dumps(
            {
                "version": version,
                "host_uptime": host_uptime,
                "agent_uptime": agent_uptime,
            }
        )

        if not identity:
            identity = self.identity

        self.log.info("Sending heartbeat from {} to server".format(identity))

        self.send(
            method, topic, server="directord", identity=identity, data=data
        )

    @expose
    def heartbeat(self, context, identity, data):
        self.log.info("Handling heartbeat")
        self.interface.handle_heartbeat(identity, data)
