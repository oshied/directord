import socket
import time

import zmq

import director


class Interface(director.Processor):
    """The Interface class.

    This class defines everything required to connect to or from a given
    server.
    """

    def __init__(self, args):
        """Initialize the interface class.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Interface, self).__init__()

        self.args = args

        if self.args.mode == "client":
            self.bind_address = self.args.server_address
        elif self.args.mode == "server":
            self.bind_address = self.args.bind_address
        else:
            self.bind_address = "*"

        self.proto = "tcp"
        self.connection_string = "{proto}://{addr}".format(
            proto=self.proto, addr=self.bind_address
        )

        self.identity = socket.gethostname()

        self.heartbeat_liveness = 3
        self.heartbeat_interval = 1

        self.nullbyte = b"\000"  # Signals null
        self.heartbeat_ready = b"\001"  # Signals worker is ready
        self.heartbeat_notice = b"\005"  # Signals worker heartbeat
        self.job_ack = b"\006"  # Signals job started
        self.job_end = b"\004"  # Signals job ended
        self.job_processing = b"\026"  # Signals job running
        self.job_failed = b"\025"  # Signals job failed
        self.transfer_start = b"\002"  # Signals start file transfer
        self.transfer_end = b"\003"  # Signals start file transfer

        self.ctx = zmq.Context()
        self.poller = zmq.Poller()

    @property
    def get_heartbeat(self):
        """Return a new hearbeat interval time."""

        return time.time() + self.args.heartbeat_interval

    @property
    def get_expiry(self):
        """Return a new expiry time."""

        return time.time() + self.heartbeat_interval * self.heartbeat_liveness

    def socket_bind(
        self, socket_type, connection, port, poller_type=zmq.POLLIN
    ):
        """Return a socket object which has been bound to a given address.

        When the socket_type is not PUB or PUSH, the bound socket will also be
        registered with self.poller as defined within the Interface class.

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

        bind = self.ctx.socket(socket_type)
        bind.bind(
            "{connection}:{port}".format(
                connection=connection,
                port=port,
            )
        )

        if socket_type not in [zmq.PUB]:
            self.poller.register(bind, poller_type)

        return bind

    def socket_connect(
        self,
        socket_type,
        connection,
        port,
        poller_type=zmq.POLLIN,
        send_ready=True,
    ):
        """Return a socket object which has been bound to a given address.

        When send_ready is set True and the socket_type is not SUB or PULL,
        the bound socket will send a single SOH ready message.

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
        :param poller_type: Set the Socket type, typically defined using a ZMQ
                            constant.
        :type poller_type: Integer
        :returns: Object
        """

        bind = self.ctx.socket(socket_type)
        if socket_type == zmq.SUB:
            bind.setsockopt_string(zmq.SUBSCRIBE, self.identity)
        else:
            bind.setsockopt_string(zmq.IDENTITY, self.identity)
        bind.linger = 0
        self.poller.register(bind, poller_type)
        bind.connect(
            "{connection}:{port}".format(
                connection=connection,
                port=port,
            )
        )

        if send_ready and socket_type not in [zmq.SUB, zmq.PULL]:
            bind.send(self.heartbeat_ready)

        return bind

    def run_threads(self, threads):
        """Execute process objects from an array.

        The array of threads are processed and started in a "daemon" mode.
        Once started the thread object is added into a cleanup array which
        is then joined.

        :param threads: An array of Process objects.
        :type threads: List
        """

        cleanup_threads = list()
        for t in threads:
            t.daemon = True
            t.start()
            cleanup_threads.append(t)

        for t in cleanup_threads:
            t.join()
