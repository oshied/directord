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

from distutils.util import strtobool
import json
import logging
import os
import pkg_resources
import queue
import time

try:
    from oslo_config import cfg
    import oslo_messaging
    from oslo_messaging.rpc import dispatcher
    from oslo_messaging.rpc.server import expose
    from oslo_messaging import transport
except (ImportError, ModuleNotFoundError):

    def expose(*args, **kwargs):
        """Mock expose."""

        pass


import tenacity

from directord import drivers
from directord import logger
from directord import utils


def parse_args(parser, parser_server, parser_client):
    """Add arguments for this driver to the parser.

    :param parser: Parser
    :type parser: Object
    :param parser_server: SubParser object
    :type parser_server: Object
    :param parser_client: SubParser object
    :type parser_client: Object
    :returns: Object
    """

    messaging_group = parser.add_argument_group("Messaging driver options")
    messaging_group.add_argument(
        "--messaging-ssl",
        help=("Enable messaging driver SSL encryption. Default: %(default)s"),
        metavar="BOOLEAN",
        default=bool(strtobool(os.getenv("DIRECTORD_MESSAGING_SSL", "True"))),
        type=bool,
    )
    messaging_group.add_argument(
        "--messaging-ssl-ca",
        help=("Messaging driver SSL CA file path. Default: %(default)s"),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_MESSAGING_SSL_CA",
                "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem",
            )
        ),
        type=str,
    )
    messaging_group.add_argument(
        "--messaging-ssl-cert",
        help=(
            "Messaging driver SSL certificate file path. "
            "Default: %(default)s"
        ),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_MESSAGING_SSL_CERT",
                "/etc/directord/messaging/ssl/directord.crt",
            )
        ),
        type=str,
    )
    messaging_group.add_argument(
        "--messaging-ssl-key",
        help=("Messaging driver SSL key file path. Default: %(default)s"),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_MESSAGING_SSL_KEY",
                "/etc/directord/messaging/ssl/directord.key",
            )
        ),
        type=str,
    )
    messaging_group.add_argument(
        "--messaging-address",
        help=(
            "IP address or hostname of messaging server (router/broker)."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=str(os.getenv("DIRECTORD_MESSAGING_ADDRESS", "127.0.0.1")),
        type=str,
    )

    return parser


class Driver(drivers.BaseDriver):
    def __init__(
        self,
        args,
        encrypted_traffic_data=None,
        interface=None,
    ):
        """Initialize the Driver.

        :param args: Arguments parsed by argparse.
        :type args: Object
        :param encrypted_traffic: Enable|Disable encrypted traffic.
        :type encrypted_traffic: Boolean
        :param interface: The interface instance (client/server)
        :type interface: Object
        """

        super(Driver, self).__init__(
            args=args,
            encrypted_traffic_data=encrypted_traffic_data,
            interface=interface,
        )
        self.mode = getattr(args, "mode", None)

        self.proto = "amqp"
        self.connection_string = "{proto}://{addr}".format(
            proto=self.proto, addr=self.args.messaging_address
        )

        self.conf = self._rpc_conf()
        self.transport = self._rpc_transport()
        self.server = None
        self.backend_server = None
        self.job_q = queue.Queue()
        self.backend_q = queue.Queue()
        self.send_q = queue.Queue()
        self.process_send_q = None
        self.timeout = 1

    def _rpc_conf(self):
        """Initialize the RPC configuration.

        :returns: Object
        """

        conf = cfg.CONF

        # Load the amqp driver from the oslo.messaging.drivers entrypoint and
        # instantiate an instance. This is just so that we can get the options
        # registered in the conf object.
        for oslo_driver in pkg_resources.iter_entry_points(
            "oslo.messaging.drivers"
        ):
            if oslo_driver.name == "amqp":
                proton_driver = oslo_driver.load()
                proton_driver(conf, transport.TransportURL(conf))
                break

        conf.set_default(
            "ssl_cert_file",
            self.args.messaging_ssl_cert,
            "oslo_messaging_amqp",
        )
        conf.set_default(
            "ssl_key_file",
            self.args.messaging_ssl_key,
            "oslo_messaging_amqp",
        )
        conf.set_default(
            "ssl",
            self.args.messaging_ssl,
            "oslo_messaging_amqp",
        )
        conf.set_default(
            "ssl_ca_file",
            self.args.messaging_ssl_ca,
            "oslo_messaging_amqp",
        )

        conf.transport_url = "{}:5672/".format(self.connection_string)

        return conf

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
    def _heartbeat(self, *args, **kwargs):
        """Handle a heartbeat interaction.

        Because this method is exposed to the RPC server, some named objects
        may be passed through which are unused. To support these extra args
        and kwargs, *args, is accepted but dumped.

        :param identity: Client identity
        :type identity: String
        :param job_id: Job Id
        :type job_id: String
        :param control: Job control character
        :type control: String
        :param data: Heartbeat data
        :type data: Dictionary
        """

        self.log.debug("Handling heartbeat for [ %s ]", kwargs.get("identity"))
        self.job_q.put(
            [
                kwargs.get("identity"),
                kwargs.get("job_id"),
                kwargs.get("control"),
                None,
                kwargs.get("data"),
                None,
                None,
                None,
            ]
        )

    @expose
    def _job(
        self,
        *args,
        **kwargs,
    ):
        """Handle a job interaction.

        Because this method is exposed to the RPC server, some named objects
        may be passed through which are unused. To support these extra args
        and kwargs, *args, is accepted but dumped.

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

        self.log.debug(
            "Handling job [ %s ] for [ %s ]",
            kwargs.get("job_id"),
            kwargs.get("identity"),
        )
        job = [
            kwargs.get("job_id"),
            kwargs.get("control"),
            kwargs.get("command"),
            kwargs.get("data"),
            kwargs.get("info"),
            kwargs.get("stderr"),
            kwargs.get("stdout"),
        ]

        if self.mode == "server":
            job.insert(0, kwargs.get("identity"))

        self.job_q.put(job)

    @expose
    def _backend(
        self,
        *args,
        **kwargs,
    ):
        """Handle a backend interaction.

        Because this method is exposed to the RPC server, some named objects
        may be passed through which are unused. To support these extra args
        and kwargs, *args, is accepted but dumped.

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

        self.log.debug(
            "Handling backend [ %s ] for [ %s ]",
            kwargs.get("job_id"),
            kwargs.get("identity"),
        )
        job = [
            kwargs.get("job_id"),
            kwargs.get("control"),
            kwargs.get("command"),
            kwargs.get("data"),
            kwargs.get("info"),
            kwargs.get("stderr"),
            kwargs.get("stdout"),
        ]

        if self.mode == "server":
            job.insert(0, kwargs.get("identity"))

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
            pool_size = 16
        else:
            server_target = self.machine_id
            pool_size = 1

        if not self.backend_server:
            self.backend_server = self._rpc_server(
                server_target=server_target, topic="directord-backend"
            )
            self.log.info("Starting messaging backend server")
            self.backend_server.start(override_pool_size=pool_size)

        if not self.server:
            self.server = self._rpc_server(
                server_target=server_target, topic="directord"
            )
            self.log.info("Starting messaging server")
            self.server.start(override_pool_size=pool_size)

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
            target = worker.machine_id

            if not worker.machine_id:
                self.log.fatal(
                    "Machine ID for identity [ %s ] not found", identity
                )
                return

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

    def _rpc_transport(self):
        """Returns an rpc transport.

        :returns: Object
        """

        return oslo_messaging.get_rpc_transport(self.conf)

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
        retry=tenacity.retry_if_exception_type(Exception),
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

        client = oslo_messaging.RPCClient(
            self.transport, target, timeout=2, retry=3
        )

        try:
            return client.call({}, method, **kwargs)
        except Exception as e:
            self.log.warn(
                "Failed to send message using topic [ %s ] to server [ %s ]",
                topic,
                server,
            )
            raise e

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
        self, host_uptime=None, agent_uptime=None, version=None, driver=None
    ):
        """Send a heartbeat.

        :param host_uptime: Sender uptime
        :type host_uptime: String
        :param agent_uptime: Sender agent uptime
        :type agent_uptime: String
        :param version: Sender directord version
        :type version: String
        :param version: Driver information
        :type version: String
        """

        job_id = utils.get_uuid()
        self.log.info(
            "Job [ %s ] sending heartbeat from [ %s ] to server",
            job_id,
            self.identity,
        )
        return self._process_send(
            method="_heartbeat",
            topic="directord",
            msg_id=job_id,
            control=self.heartbeat_notice,
            data=json.dumps(
                {
                    "job_id": job_id,
                    "version": version,
                    "host_uptime": host_uptime,
                    "agent_uptime": agent_uptime,
                    "machine_id": self.machine_id,
                    "driver": driver,
                }
            ),
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
