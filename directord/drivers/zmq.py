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
import logging
import multiprocessing
from multiprocessing import queues as mqs
import os
import time

import tenacity

try:
    import zmq
    import zmq.auth as zmq_auth
    from zmq.auth.thread import ThreadAuthenticator
except (ImportError, ModuleNotFoundError):
    pass

from directord import drivers
from directord import iodict
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

    group = parser.add_argument_group("ZMQ driver options")
    group.add_argument(
        "--zmq-highwater-mark",
        type=int,
        default=os.getenv("DIRECTORD_ZMQ_HIGHWATER_MARK", 1024),
        metavar="INTEGER",
        help=("Set the ZMQ highwater mark. Default %(default)s."),
    )
    server_group = parser_server.add_argument_group(
        "ZMQ Server driver options"
    )
    server_group.add_argument(
        "--zmq-generate-keys",
        action="store_true",
        help="Generate encryption keys for Curve authentication.",
    )
    server_group.add_argument(
        "--zmq-bind-address",
        help=(
            "ZMQ IP Address to bind a Directord Server."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_ZMQ_BIND_ADDRESS", "*"),
    )
    client_group = parser_client.add_argument_group(
        "ZMQ Client driver options"
    )
    client_group.add_argument(
        "--zmq-server-address",
        help=(
            "ZMQ Domain or IP address of the Directord server."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_ZMQ_SERVER_ADDRESS", "127.0.0.1"),
    )
    auth_group = group.add_mutually_exclusive_group()
    auth_group.add_argument(
        "--zmq-shared-key",
        help="Shared key used for server client authentication.",
        metavar="STRING",
        default=os.getenv("DIRECTORD_ZMQ_SHARED_KEY", None),
    )
    auth_group.add_argument(
        "--zmq-curve-encryption",
        action="store_true",
        help=(
            "Server and client will connect using Curve authentication"
            " and encryption. Enabling this option assumes keys have been"
            " generated. see `--zmq-generate-keys` for more."
        ),
    )

    return parser


class _FlushQueue(mqs.Queue, iodict.FlushQueue):
    """Flush queue capability helper class."""

    def __init__(self, path, lock, semaphore):
        super().__init__(ctx=multiprocessing.get_context())
        self.path = path
        self.lock = lock
        self.semaphore = semaphore


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

        self.thread_processor = multiprocessing.Process
        self.event = multiprocessing.Event()
        self.semaphore = multiprocessing.Semaphore
        self.flushqueue = _FlushQueue
        self.args = args
        if getattr(self.args, "zmq_generate_keys", False) is True:
            self._generate_certificates()
            print("New certificates generated")
            raise SystemExit(0)

        self.encrypted_traffic_data = encrypted_traffic_data

        mode = getattr(self.args, "mode", None)
        if mode == "client":
            self.bind_address = self.args.zmq_server_address
        elif mode == "server":
            self.bind_address = self.args.zmq_bind_address
        else:
            self.bind_address = "*"
        self.proto = "tcp"
        self.connection_string = "{proto}://{addr}".format(
            proto=self.proto, addr=self.bind_address
        )

        if self.encrypted_traffic_data:
            self.encrypted_traffic = self.encrypted_traffic_data.get("enabled")
            self.secret_keys_dir = self.encrypted_traffic_data.get(
                "secret_keys_dir"
            )
            self.public_keys_dir = self.encrypted_traffic_data.get(
                "public_keys_dir"
            )
        else:
            self.encrypted_traffic = False
            self.secret_keys_dir = None
            self.public_keys_dir = None

        self._context = zmq.Context()
        self.ctx = self._context.instance()
        self.poller = zmq.Poller()
        self.interface = interface
        super(Driver, self).__init__(
            args=args,
            encrypted_traffic_data=self.encrypted_traffic_data,
            interface=interface,
        )
        self.bind_job = None
        self.bind_backend = None
        self.hwm = getattr(self.args, "zmq_highwater_mark", 1024)

    def __copy__(self):
        """Return a new copy of the driver."""

        return Driver(
            args=self.args,
            encrypted_traffic_data=self.encrypted_traffic_data,
            interface=self.interface,
        )

    def _backend_bind(self):
        """Bind an address to a backend socket and return the socket.

        :returns: Object
        """

        bind = self._socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.backend_port,
        )
        bind.set_hwm(self.hwm)
        self.log.debug(
            "Identity [ %s ] backend connect hwm state [ %s ]",
            self.identity,
            bind.get_hwm(),
        )
        return bind

    def _backend_connect(self):
        """Connect to a backend socket and return the socket.

        :returns: Object
        """

        self.log.debug("Establishing backend connection.")
        bind = self._socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.backend_port,
        )
        bind.set_hwm(self.hwm)
        self.log.debug(
            "Identity [ %s ] backend connect hwm state [ %s ]",
            self.identity,
            bind.get_hwm(),
        )
        return bind

    def _bind_check(self, bind, interval=1, constant=1000):
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

        socks = dict(self.poller.poll(interval * constant))
        if socks.get(bind) == zmq.POLLIN:
            return True
        else:
            return False

    def _close(self, socket):
        if socket is None:
            return

        try:
            socket.close(linger=2)
            close_time = time.time()
            while not socket.closed:
                if time.time() - close_time > 60:
                    raise TimeoutError(
                        "Job [ {} ] failed to close transfer socket".format(
                            self.job_id
                        )
                    )
                else:
                    socket.close(linger=2)
                    time.sleep(1)
        except Exception as e:
            self.log.error(
                "Ran into an exception while closing the socket %s",
                str(e),
            )
        else:
            self.log.debug("Backend socket closed")

    def _generate_certificates(self, base_dir="/etc/directord"):
        """Generate client and server CURVE certificate files.

        :param base_dir: Directord configuration path.
        :type base_dir: String
        """

        keys_dir = os.path.join(base_dir, "certificates")
        public_keys_dir = os.path.join(base_dir, "public_keys")
        secret_keys_dir = os.path.join(base_dir, "private_keys")

        for item in [keys_dir, public_keys_dir, secret_keys_dir]:
            os.makedirs(item, exist_ok=True)

        # Run certificate backup
        self._move_certificates(directory=public_keys_dir, backup=True)
        self._move_certificates(
            directory=secret_keys_dir, backup=True, suffix=".key_secret"
        )

        # create new keys in certificates dir
        for item in ["server", "client"]:
            self._key_generate(keys_dir=keys_dir, key_type=item)

        # Move generated certificates in place
        self._move_certificates(
            directory=keys_dir,
            target_directory=public_keys_dir,
            suffix=".key",
        )
        self._move_certificates(
            directory=keys_dir,
            target_directory=secret_keys_dir,
            suffix=".key_secret",
        )

    def _job_bind(self):
        """Bind an address to a job socket and return the socket.

        :returns: Object
        """

        return self._socket_bind(
            socket_type=zmq.ROUTER,
            connection=self.connection_string,
            port=self.args.job_port,
        )

    def _job_connect(self):
        """Connect to a job socket and return the socket.

        :returns: Object
        """

        self.log.debug("Establishing Job connection.")
        return self._socket_connect(
            socket_type=zmq.DEALER,
            connection=self.connection_string,
            port=self.args.job_port,
        )

    def _key_generate(self, keys_dir, key_type):
        """Generate certificate.

        :param keys_dir: Full Directory path where a given key will be stored.
        :type keys_dir: String
        :param key_type: Key type to be generated.
        :type key_type: String
        """

        zmq_auth.create_certificates(keys_dir, key_type)

    @staticmethod
    def _move_certificates(
        directory, target_directory=None, backup=False, suffix=".key"
    ):
        """Move certificates when required.

        :param directory: Set the origin path.
        :type directory: String
        :param target_directory: Set the target path.
        :type target_directory: String
        :param backup: Enable file backup before moving.
        :type backup:  Boolean
        :param suffix: Set the search suffix
        :type suffix: String
        """

        for item in os.listdir(directory):
            if backup:
                target_file = "{}.bak".format(os.path.basename(item))
            else:
                target_file = os.path.basename(item)

            if item.endswith(suffix):
                os.rename(
                    os.path.join(directory, item),
                    os.path.join(target_directory or directory, target_file),
                )

    def _socket_bind(self, socket_type, connection, port, poller_type=None):
        """Return a socket object which has been bound to a given address.

        When the socket_type is not PUB or PUSH, the bound socket will also be
        registered with self.poller as defined within the Interface
        class.

        :param socket_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type socket_type: Integer
        :param connection: Set the Address information used for the bound
                           socket.
        :type connection: String
        :param port: Define the port which the socket will be bound to.
        :type port: Integer
        :param poller_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type poller_type: Integer
        :returns: Object
        """

        if poller_type is None:
            poller_type = zmq.POLLIN

        bind = self._socket_context(socket_type=socket_type)
        auth_enabled = (
            self.args.zmq_shared_key or self.args.zmq_curve_encryption
        )

        if auth_enabled:
            self.auth = ThreadAuthenticator(self.ctx, log=self.log)
            self.auth.start()
            self.auth.allow()

            if self.args.zmq_shared_key:
                # Enables basic auth
                self.auth.configure_plain(
                    domain="*", passwords={"admin": self.args.zmq_shared_key}
                )
                bind.plain_server = True  # Enable shared key authentication
                self.log.info("Shared key authentication enabled.")
            elif self.args.zmq_curve_encryption:
                server_secret_file = os.path.join(
                    self.secret_keys_dir, "server.key_secret"
                )
                for item in [
                    self.public_keys_dir,
                    self.secret_keys_dir,
                    server_secret_file,
                ]:
                    if not os.path.exists(item):
                        raise SystemExit(
                            "The required path [ {} ] does not exist. Have"
                            " you generated your keys?".format(item)
                        )
                self.auth.configure_curve(
                    domain="*", location=self.public_keys_dir
                )
                try:
                    server_public, server_secret = zmq_auth.load_certificate(
                        server_secret_file
                    )
                except OSError as e:
                    self.log.error(
                        "Failed to load certificates: %s, Configuration: %s",
                        str(e),
                        vars(self.args),
                    )
                    raise SystemExit("Failed to load certificates")
                else:
                    bind.curve_secretkey = server_secret
                    bind.curve_publickey = server_public
                    bind.curve_server = True  # Enable curve authentication
        bind.bind(
            "{connection}:{port}".format(
                connection=connection,
                port=port,
            )
        )

        if socket_type not in [zmq.PUB]:
            self.poller.register(bind, poller_type)

        return bind

    def _socket_connect(self, socket_type, connection, port, poller_type=None):
        """Return a socket object which has been bound to a given address.

        > A connection back to the server will wait 10 seconds for an ack
          before going into a retry loop. This is done to forcefully cycle
          the connection object to reset.

        :param socket_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type socket_type: Integer
        :param connection: Set the Address information used for the bound
                           socket.
        :type connection: String
        :param port: Define the port which the socket will be bound to.
        :type port: Integer
        :param poller_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type poller_type: Integer
        :returns: Object
        """

        if poller_type is None:
            poller_type = zmq.POLLIN

        bind = self._socket_context(socket_type=socket_type)

        if self.args.zmq_shared_key:
            bind.plain_username = b"admin"  # User is hard coded.
            bind.plain_password = self.args.zmq_shared_key.encode()
            self.log.info("Shared key authentication enabled.")
        elif self.args.zmq_curve_encryption:
            client_secret_file = os.path.join(
                self.secret_keys_dir, "client.key_secret"
            )
            server_public_file = os.path.join(
                self.public_keys_dir, "server.key"
            )
            for item in [
                self.public_keys_dir,
                self.secret_keys_dir,
                client_secret_file,
                server_public_file,
            ]:
                if not os.path.exists(item):
                    raise SystemExit(
                        "The required path [ {} ] does not exist. Have"
                        " you generated your keys?".format(item)
                    )
            try:
                client_public, client_secret = zmq_auth.load_certificate(
                    client_secret_file
                )
                server_public, _ = zmq_auth.load_certificate(
                    server_public_file
                )
            except OSError as e:
                self.log.error(
                    "Error while loading certificates: %s. Configuration: %s",
                    str(e),
                    vars(self.args),
                )
                raise SystemExit("Failed to load keys.")
            else:
                bind.curve_secretkey = client_secret
                bind.curve_publickey = client_public
                bind.curve_serverkey = server_public

        if socket_type == zmq.SUB:
            bind.setsockopt_string(zmq.SUBSCRIBE, self.identity)
        else:
            bind.setsockopt_string(zmq.IDENTITY, self.identity)

        self.poller.register(bind, poller_type)
        bind.connect(
            "{connection}:{port}".format(
                connection=connection,
                port=port,
            )
        )

        self.log.info("Socket connected to [ %s ].", connection)
        return bind

    def _socket_context(self, socket_type):
        """Create socket context and return a bind object.

        :param socket_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type socket_type: Integer
        :returns: Object
        """

        bind = self.ctx.socket(socket_type)
        bind.linger = getattr(self.args, "heartbeat_interval", 60)
        hwm = int(self.hwm * 4)
        try:
            bind.sndhwm = bind.rcvhwm = hwm
        except AttributeError:
            bind.hwm = hwm

        bind.set_hwm(hwm)
        bind.setsockopt(zmq.SNDHWM, hwm)
        bind.setsockopt(zmq.RCVHWM, hwm)
        if socket_type == zmq.ROUTER:
            bind.setsockopt(zmq.ROUTER_MANDATORY, 1)

        return bind

    @staticmethod
    def _socket_recv(socket, nonblocking=False):
        """Receive a message over a ZM0 socket.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message parts are byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        """

        if nonblocking:
            flags = zmq.NOBLOCK
        else:
            flags = 0

        return socket.recv_multipart(flags=flags)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(Exception),
        wait=tenacity.wait_fixed(5),
        before_sleep=tenacity.before_sleep_log(
            logger.getLogger(name="directord"), logging.WARN
        ),
    )
    def _socket_send(
        self,
        socket,
        identity=None,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
        nonblocking=False,
    ):
        """Send a message over a ZM0 socket.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message information is assumed to be byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param identity: Target where message will be sent.
        :type identity: Bytes
        :param msg_id: ID information for a given message. If no ID is
                       provided a UUID will be generated.
        :type msg_id: Bytes
        :param control: ASCII control charaters.
        :type control: Bytes
        :param command: Command definition for a given message.
        :type command: Bytes
        :param data: Encoded data that will be transmitted.
        :type data: Bytes
        :param info: Encoded information that will be transmitted.
        :type info: Bytes
        :param stderr: Encoded error information from a command.
        :type stderr: Bytes
        :param stdout: Encoded output information from a command.
        :type stdout: Bytes
        :param nonblocking: Enable non-blocking send.
        :type nonblocking: Boolean
        :returns: Object
        """

        def _encoder(item):
            try:
                return item.encode()
            except AttributeError:
                return item

        if not msg_id:
            msg_id = utils.get_uuid()

        if not control:
            control = self.nullbyte

        if not command:
            command = self.nullbyte

        if not data:
            data = self.nullbyte

        if not info:
            info = self.nullbyte

        if not stderr:
            stderr = self.nullbyte

        if not stdout:
            stdout = self.nullbyte

        message_parts = [msg_id, control, command, data, info, stderr, stdout]

        if identity:
            message_parts.insert(0, identity)

        message_parts = [_encoder(i) for i in message_parts]

        if nonblocking:
            flags = zmq.NOBLOCK
        else:
            flags = 0

        try:
            return socket.send_multipart(message_parts, flags=flags)
        except Exception as e:
            self.log.warn("Failed to send message to [ %s ]", identity)
            raise e

    def _recv(self, socket, nonblocking=False):
        """Receive message.

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        :returns: Tuple
        """

        recv_obj = self._socket_recv(socket=socket, nonblocking=nonblocking)
        return tuple([i.decode() for i in recv_obj])

    def backend_recv(self, nonblocking=False):
        """Receive a transfer message.

        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        :returns: Tuple
        """

        return self._recv(socket=self.bind_backend, nonblocking=nonblocking)

    def backend_init(self):
        """Initialize the backend socket.

        For server mode, this is a bound local socket.
        For client mode, it is a connection to the server socket.

        :returns: Object
        """

        if self.args.mode == "server":
            self.bind_backend = self._backend_bind()
        else:
            self.bind_backend = self._backend_connect()

    def backend_close(self):
        """Close the backend socket."""

        self._close(socket=self.bind_backend)

    def backend_check(self, interval=1, constant=1000):
        """Return True if the backend contains work ready.

        :param bind: A given Socket bind to identify.
        :type bind: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Object
        """

        return self._bind_check(
            bind=self.bind_backend, interval=interval, constant=constant
        )

    def backend_send(self, *args, **kwargs):
        """Send a job message.

        * All args and kwargs are passed through to the socket send.

        :returns: Object
        """

        kwargs["socket"] = self.bind_backend
        return self._socket_send(*args, **kwargs)

    @staticmethod
    def get_lock():
        """Returns a thread lock."""

        return multiprocessing.Lock()

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

        return self.job_send(
            control=self.heartbeat_notice,
            msg_id=job_id,
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

    def job_send(self, *args, **kwargs):
        """Send a job message.

        * All args and kwargs are passed through to the socket send.

        :returns: Object
        """

        kwargs["socket"] = self.bind_job
        return self._socket_send(*args, **kwargs)

    def job_recv(self, nonblocking=False):
        """Receive a transfer message.

        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        :returns: Tuple
        """

        return self._recv(socket=self.bind_job, nonblocking=nonblocking)

    def job_init(self):
        """Initialize the job socket.

        For server mode, this is a bound local socket.
        For client mode, it is a connection to the server socket.

        :returns: Object
        """

        if self.args.mode == "server":
            self.bind_job = self._job_bind()
        else:
            self.bind_job = self._job_connect()

    def job_close(self):
        """Close the job socket."""

        self._close(socket=self.bind_job)

    def job_check(self, interval=1, constant=1000):
        """Return True if a job contains work ready.

        :param bind: A given Socket bind to identify.
        :type bind: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Object
        """

        return self._bind_check(
            bind=self.bind_job, interval=interval, constant=constant
        )

    def shutdown(self):
        """Shutdown the driver."""

        if hasattr(self.ctx, "close"):
            self.ctx.close()

        if hasattr(self._context, "close"):
            self._context.close()

        self.job_close()
        self.backend_close()
