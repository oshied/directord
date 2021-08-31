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

import socket
import subprocess
import time

from oslo_config import cfg
import oslo_messaging
from oslo_messaging.rpc import dispatcher
from oslo_messaging.rpc.server import expose

import directord
from directord import drivers
from directord import utils


class Driver(drivers.BaseDriver):

    def __init__(self, interface, args, encrypted_traffic_data,
                 connection_string):
        super(Driver, self).__init__(
            interface=interface,
            args=args,
            encrypted_traffic_data=encrypted_traffic_data,
            connection_string=connection_string,
        )
        self.mode = getattr(args, "mode", None)
        # A reference to the interface object (either the Client or Server)
        self.interface = interface
        self.connection_string = connection_string
        self.conf = cfg.CONF
        self.conf.transport_url = 'amqp://{}:5672//'.format(
            self.interface.bind_address)
        self.transport = oslo_messaging.get_rpc_transport(self.conf)

    def run(self):
        if self.mode == "server":
            self.qdrouterd()
            server = socket.gethostbyaddr(self.interface.bind_address)[0]
        else:
            server = self.interface.uuid

        target = oslo_messaging.Target(
            topic='directord', server=server)
        endpoints = [self]
        server = oslo_messaging.get_rpc_server(
            self.transport, target, endpoints, executor='threading',
            access_policy=dispatcher.ExplicitRPCAccessPolicy)
        self.log.info("Starting messaging server.")
        server.start()
        while True:
            time.sleep(1)

    def qdrouterd(self):
        self.log.info("Starting qdrouterd.")
        subprocess.run(['qdrouterd', '-d'], check=True)

    def send(self, method, topic, server=None, **kwargs):
        if server:
            target = oslo_messaging.Target(topic=topic, server=server)
        else:
            target = oslo_messaging.Target(topic=topic)

        client = oslo_messaging.RPCClient(self.transport, target)
        return client.call({}, method, **kwargs)

    @expose
    def heartbeat(self, context, identity, control, uptime,
                  expire, source_uuid, reset, version):
        self.log.info("Handling heartbeat")
        if self.args.mode == 'client':
            self.interface.handle_heartbeat(heartbeat_at=expire, reset=reset,
                                            source_uuid=source_uuid)
        else:
            self.interface.handle_heartbeat(
                identity, control, uptime, version, source_uuid)

    @expose
    def job(self, context, identity, msg_id, control, command, data, info,
            stderr, stdout):
        self.log.debug("Handling job {}".format(msg_id))
        if self.args.mode == "client":
            self.log.debug("Handling job as client {}".format(msg_id))
            with utils.get_diskcache(self.args.cache_path) as cache:
                self.interface.handle_job(cache, command, data, info)
        else:
            self.log.debug("Handling job as server {}".format(msg_id))
            self.interface.handle_job(
                identity, msg_id, control, command, data, info,
                stderr, stdout)

    @expose
    def job_server_ack(self, job_id):
        self.log.info("Handling job ack")
        self.interface.handle_job_ack(job_id)

    def heartbeat_check(self, heartbeat_interval):
        """Check if the driver is ready to respond to a heartbeat request
        or send a new heartbeat.

        :param heartbeat_interval: heartbeat interval in seconds
        :type heartbeat_interval: Integer
        :returns: Boolean
        """
        time.sleep(heartbeat_interval)
        return False

    def heartbeat_send(self, identity=None, uptime=None, expire=None,
                       source_uuid=None, reset=False):
        method = 'heartbeat'
        topic = 'directord'

        if self.args.mode == 'server':
            server = self.interface.workers[identity]['uuid']
        else:
            server = socket.gethostbyaddr(self.interface.bind_address)[0]

        if not identity:
            identity = self.identity
        return self.send(
            method, topic, server,
            identity=identity,
            control=self.heartbeat_notice,
            uptime=None, expire=None, reset=False,
            source_uuid=source_uuid,
            version=directord.__version__)

    def job_send(self, identity=None, msg_id=None, control=None, command=None,
                 data=None, info=None, stderr=None, stdout=None):
        method = 'job'
        topic = 'directord'

        if self.args.mode == 'server':
            server = self.interface.workers[identity]['uuid']
        else:
            server = socket.gethostbyaddr(self.interface.bind_address)[0]

        if data:
            verb = data.get("verb", None)
        else:
            verb = None

        self.log.debug("Sending Job {} to {}".format(data, server))
        return self.send(
            method, topic, server,
            identity=identity,
            msg_id=msg_id,
            control=control,
            command=verb,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout)

    def job_check(self, constant):
        """Check if the driver is ready to respond to a job request

        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Boolean
        """

        time.sleep(constant/1000)
        return False

    def job_client_ack(self, job_id):
        """Ack a job request. Client->Server"""

        self.job_send(msg_id=job_id, control=self.job_ack)

    def job_connect(self):
        """Connect to a job socket and return the socket.

        :returns: Object
        """

        pass

    def transfer_connect(self):
        """Connect to a transfer socket and return the socket.

        :returns: Object
        """

        pass

    def heartbeat_connect(self):
        """Connect to a heartbeat socket and return the socket.

        :returns: Object
        """

        pass

    def heartbeat_bind(self):
        """Bind an address to a heartbeat socket and return the socket.

        :returns: Object
        """

        pass

    def job_bind(self):
        """Bind an address to a job socket and return the socket.

        :returns: Object
        """

        pass

    def transfer_bind(self):
        """Bind an address to a transfer socket and return the socket.

        :returns: Object
        """

        pass

    def bind_check(self, bind, interval=1, constant=1000):
        """Return True if a bind type contains work ready.

        :param bind: A given Socket bind to identify.
        :type bind: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Object
        """

        pass

    def key_generate(self, keys_dir, key_type):
        """Generate certificate.

        :param keys_dir: Full Directory path where a given key will be stored.
        :type keys_dir: String
        :param key_type: Key type to be generated.
        :type key_type: String
        """

        pass
