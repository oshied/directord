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
import time

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

    def run(self, sentinel=False):
        """Run in server mode."""

        server = oslo_messaging.get_rpc_server(
            transport=self.transport,
            target=oslo_messaging.Target(
                topic="directord", server="directord"
            ),
            endpoints=[self],
            executor="threading",
            access_policy=dispatcher.ExplicitRPCAccessPolicy,
        )
        self.log.info("Starting messaging server")
        server.start()
        while not sentinel:
            time.sleep(1)
        server.stop()
        server.wait()

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

        method = "heartbeat"
        topic = "directord"

        data = json.dumps(
            {
                "version": version,
                "host_uptime": host_uptime,
                "agent_uptime": agent_uptime,
                "machine_id": self.machine_id,
            }
        )

        self.log.info(
            "Sending heartbeat from {} to server".format(self.identity)
        )

        self.send(
            method,
            topic,
            server="directord",
            identity=self.identity,
            data=data,
        )

    @expose
    def heartbeat(self, context, identity, data):
        self.log.info("Handling heartbeat")
        self.interface.handle_heartbeat(identity, data)
