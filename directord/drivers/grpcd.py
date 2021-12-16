#   Copyright Alex Schultz <aschultz@redhat.com>. All Rights Reserved.
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

from concurrent import futures
from distutils.util import strtobool
import json
import os
import queue
import random
import threading
import time
import uuid

try:
    import grpc
    from directord.drivers.generated import msg_pb2
    from directord.drivers.generated import msg_pb2_grpc
    from directord.drivers.generated.msg_pb2_grpc import (
        MessageServiceServicer as grpc_MessageServiceServicer,
    )
except (ImportError, ModuleNotFoundError):
    grpc_MessageServiceServicer = object
    pass

from directord import drivers
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

    group = parser.add_argument_group("gRPC driver options")
    group.add_argument(
        "--grpc-port",
        type=int,
        default=os.getenv("DIRECTORD_GRPC_PORT", 5558),
        metavar="INTEGER",
        help=("gRPC Port. Default %(default)s."),
    )
    group.add_argument(
        "--grpc-server-address",
        help=(
            "gRPC Domain or IP address of the Directord server."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_GRPC_SERVER_ADDRESS", "127.0.0.1"),
    )
    group.add_argument(
        "--grpc-disable-compression",
        metavar="BOOLEAN",
        default=bool(
            strtobool(os.getenv("DIRECTORD_GRPC_DISABLE_COMPRESSION", "False"))
        ),
        help=("Disable compression between client and server."),
        type=bool,
    )

    server_group = parser_server.add_argument_group(
        "gRPC Server driver options"
    )
    server_group.add_argument(
        "--grpc-bind-address",
        help=(
            "gRPC IP Address to bind a Directord Server."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_GRPC_BIND_ADDRESS", "0.0.0.0"),
    )
    server_group.add_argument(
        "--grpc-server-workers",
        type=int,
        default=os.getenv("DIRECTORD_GRPC_SERVER_WORKERS", 4),
        metavar="INTEGER",
        help=("Number of gRPC server workers. Default: %(default)s"),
    )
    auth_group = parser.add_argument_group("gRPC driver auth options")
    auth_group.add_argument(
        "--grpc-ssl",
        help=("Enable gRPC driver SSL encryption. Default: %(default)s"),
        metavar="BOOLEAN",
        default=bool(strtobool(os.getenv("DIRECTORD_GRPC_SSL", "False"))),
        type=bool,
    )
    auth_group.add_argument(
        "--grpc-ssl-ca",
        help=("gRPC driver SSL CA file path. Default: %(default)s"),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_GRPC_SSL_CA",
                "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem",
            )
        ),
        type=str,
    )
    auth_group.add_argument(
        "--grpc-ssl-cert",
        help=(
            "gRPC driver SSL certificate file path. " "Default: %(default)s"
        ),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_GRPC_SSL_CERT",
                "/etc/directord/grpc/ssl/directord.crt",
            )
        ),
        type=str,
    )
    auth_group.add_argument(
        "--grpc-ssl-key",
        help=("gRPC driver SSL key file path. Default: %(default)s"),
        metavar="STRING",
        default=str(
            os.getenv(
                "DIRECTORD_GRPC_SSL_KEY",
                "/etc/directord/grpc/ssl/directord.key",
            )
        ),
        type=str,
    )
    auth_group.add_argument(
        "--grpc-ssl-client-auth",
        help=("Require ssl client auth. Default: %(default)s"),
        metavar="BOOLEAN",
        default=bool(
            strtobool(os.getenv("DIRECTORD_GRPC_SSL_CLIENT_AUTH", "False"))
        ),
        type=bool,
    )

    return parser


class QueueBase:
    """Base queue."""

    _instance = None

    def __init__(self):
        """Init."""
        raise RuntimeError("Use instance()")

    def _setup(self):
        """Setup queue data."""
        self._data_queue = {}
        self._lock = threading.Lock()

    @classmethod
    def instance(cls):
        """Get queue instance."""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance._setup()
        return cls._instance

    def get_lock(self):
        """Get object lock."""
        return self._lock

    def add_queue(self, target, data):
        """Add data to target queue.

        :param target: String. queue target
        :param data: Object. queue data
        """
        with self.get_lock():
            if target not in self._data_queue:
                self._data_queue[target] = queue.Queue()
        self._data_queue[target].put(data)

    def get_from_queue(self, target):
        """Get data from top of queue.

        This returns a single data item from the queue.

        :param target: queue target
        :type target: string
        :returns: Object
        """

        with self.get_lock():
            if (
                target not in self._data_queue
                or self._data_queue[target].empty()
            ):
                return None
        return self._data_queue[target].get()

    def check_queue(self, target):
        """Check if target has data in queue.

        :param target: queue target key
        :type target: string
        :returns: boolean
        """
        with self.get_lock():
            if target not in self._data_queue:
                return False
        return not self._data_queue[target].empty()

    def get_stats(self):
        """Return queue stats."""
        stats = {}
        with self.get_lock():
            stats["targets"] = list(self._data_queue)
        return stats

    def purge_queue(self):
        """Empty queue."""
        with self.get_lock():
            self._data_queue = {}
        return True


class MessageQueue(QueueBase):
    """Message queue instance."""

    _instance = None


class JobQueue(QueueBase):
    """Job queue instance."""

    _instance = None


class MessageServiceServicer(grpc_MessageServiceServicer):
    def __init__(self, logger):
        self.log = logger

    def GetMessage(self, request, context):
        """Gets a message.

        gRPC calls this method when clients call the GetMessage rpc (method).
        :param request: The incoming request.
        :type request: GetMessageRequest
        :param context: The gRPC connection context.
        :returns: MessageResponse
        """
        target = request.target
        req_id = request.req_id
        # self.log.debug("%s | -> GetMessage Request: %s", req_id, request)

        q = MessageQueue.instance()
        status = True
        job_data = q.get_from_queue(target)

        if not job_data:
            self.log.debug("%s | ! No messages for %s", req_id, target)
            status = False
            job_data = None

        response = msg_pb2.MessageResponse(
            req_id=req_id, status=status, target=target, data=job_data
        )
        # self.log.debug("%s | <- GetMessage Response: %s", req_id, response)
        return response

    def GetJob(self, request, context):
        """Gets a message.

        gRPC calls this method when clients call the GetMessage rpc (method).
        :param request: The incoming request
        :type request: GetJobRequest
        :param context: The gRPC connection context.
        :returns: JobResponse
        """
        target = request.target
        req_id = request.req_id
        # self.log.debug("%s | -> GetJob Request: %s", req_id, request)

        q = JobQueue.instance()
        status = True
        job_data = q.get_from_queue(target)

        if not job_data:
            self.log.debug("%s | ! No jobs for %s", req_id, target)
            status = False
            job_data = None

        response = msg_pb2.JobResponse(
            req_id=req_id, status=status, target=target, data=job_data
        )
        # self.log.debug("%s | <- GetJob Response: %s", req_id, response)
        return response

    def PutMessage(self, request, context):
        """Put a message.

        gRPC calls this method when clients call the PutMessage rpc (method).
        :param request: The incoming request
        :type request: PutMessageRequest
        :param context: The gRPC connection context.
        :returns: Status
        """
        target = request.target
        req_id = request.req_id
        msg = request.data

        # self.log.debug("%s | -> PutMessage Request: %s", req_id, request)
        q = MessageQueue.instance()
        q.add_queue(target, msg)
        self.log.debug("%s | + We added message to queue (%s)", req_id, target)

        status = msg_pb2.Status(req_id=req_id, result=True)
        # self.log.debug("%s | <- PutMessage Response: %s", req_id, status)
        return status

    def PutJob(self, request, context):
        """Put a message.

        gRPC calls this method when clients call the PutJob rpc (method).
        :param request: The incoming request.
        :type request: PutJobRequest
        :param context: The gRPC connection context.
        :returns: Status
        """
        target = request.target
        req_id = request.req_id
        msg = request.data

        # self.log.debug("%s | -> PutJob Request: %s", req_id, request)
        q = JobQueue.instance()
        q.add_queue(target, msg)
        self.log.debug("%s | + We added job to queue (%s)", req_id, target)

        status = msg_pb2.Status(req_id=req_id, result=True)
        # self.log.debug("%s | <- PutJob Response: %s", req_id, status)
        return status

    def MessageCheck(self, request, context):
        """Check if messages in queue."""
        # self.log.debug(
        #     "%s | -> Message Check: %s", request.req_id, request.target
        # )
        return msg_pb2.CheckResponse(
            req_id=request.req_id,
            target=request.target,
            has_data=MessageQueue.instance().check_queue(request.target),
        )

    def JobCheck(self, request, context):
        """Check if jobs in queue."""
        # self.log.debug(
        #     "%s | -> Job Check: %s", request.req_id, request.target
        # )
        return msg_pb2.CheckResponse(
            target=request.target,
            has_data=JobQueue.instance().check_queue(request.target),
        )

    def PurgeQueues(self, request, context):
        """Nuke queues."""
        self.log.warning(
            "%s | Purging message and job queues.", request.req_id
        )
        MessageQueue.instance().purge_queue()
        JobQueue.instance().purge_queue()
        # print("++ purging queue")
        status = msg_pb2.Status(req_id=request.req_id, result=True)
        # print(f"<- Response: {status}")
        return status


class MessageServiceClient:
    """Service Client."""

    _instance = None
    log = None
    server_address = None
    server_port = None
    channel = None
    stub = None
    compression = None
    ssl_ca = None
    ssl_cert = None
    ssl_key = None

    def __init__(self):
        """Init."""
        raise RuntimeError("Use instance()")

    @classmethod
    def instance(
        cls,
        logger,
        server_address,
        server_port,
        secure=False,
        compression=True,
        ssl_ca=None,
        ssl_cert=None,
        ssl_key=None,
    ):
        """Get client instance."""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.log = logger
            cls._instance._setup(
                server_address,
                server_port,
                secure,
                compression,
                ssl_ca,
                ssl_cert,
                ssl_key,
            )
        return cls._instance

    def _setup(
        self,
        server_address,
        server_port,
        secure=False,
        compression=True,
        ssl_ca=None,
        ssl_cert=None,
        ssl_key=None,
    ):
        """Initializer.

        Creates a gRPC channel for connecting to the server.
        Adds the channel to the generated client stub.
        """
        self.server_address = server_address
        self.server_port = server_port
        self.secure = secure
        self.channel = None
        self.stub = None
        self.compression = compression
        self.ssl_ca = ssl_ca
        self.ssl_cert = ssl_cert
        self.ssl_key = ssl_key
        self.connect()

    def connect(self):
        """Connect to channel."""
        wait_for_channel = threading.Event()

        def wait_for_connection(connectivity):
            self.log.debug("grpc wait_for_connection: %s", connectivity)
            if connectivity in [grpc.ChannelConnectivity.READY]:
                wait_for_channel.set()

        compression_type = grpc.Compression.Gzip
        if not self.compression:
            compression_type = grpc.Compression.NoCompression

        if self.secure:
            ssl_cert = None
            ssl_key = None
            if not os.path.exists(self.ssl_ca):
                raise Exception(
                    "SSL is enabled but CA file does not exist "
                    f"({self.ssl_ca})"
                )
            with open(self.ssl_ca, "rb") as ca_file:
                ca_cert = ca_file.read()

            if (
                not self.ssl_cert
                or not os.path.exists(self.ssl_cert)
                or not self.ssl_key
                or not os.path.exists(self.ssl_key)
            ):
                self.log.warning(
                    "Client SSL Cert or Key do not exist. "
                    "Skipping configuration"
                )
            else:
                with open(self.ssl_cert, "rb") as cert_file:
                    ssl_cert = cert_file.read()
                with open(self.ssl_key, "rb") as key_file:
                    ssl_key = key_file.read()

            credentials = grpc.ssl_channel_credentials(
                ca_cert, ssl_key, ssl_cert
            )
            self.log.info("grpc client IS using SSL")
            self.channel = grpc.secure_channel(
                f"{self.server_address}:{self.server_port}",
                credentials=credentials,
                compression=compression_type,
            )

        else:
            self.log.info("grpc client IS NOT using SSL")
            self.channel = grpc.insecure_channel(
                f"{self.server_address}:{self.server_port}",
                compression=compression_type,
            )
        self.channel.subscribe(wait_for_connection, try_to_connect=True)
        self.stub = msg_pb2_grpc.MessageServiceStub(self.channel)
        self.log.debug("Waiting for channel connectivity...")
        wait_for_channel.wait()
        self.log.debug("Channel ready...")

    def close(self):
        """Close channels."""
        if self.channel:
            self.channel.close()
            self.channel = None
        self.stub = None

    def get_message(self, target):
        """Gets a message for a target.

        :param target: The resource target of a message.
        :returns: Tuple; (target, data)
        """
        if not self.stub:
            raise Exception("Message request after close")

        request = msg_pb2.GetMessageRequest(
            req_id=str(uuid.uuid1()), target=target
        )

        try:
            response = self.stub.GetMessage(request)
            # self.log.debug("%s | get_message: Request OK.", request.req_id)
            if response.status:
                self.log.debug(
                    "%s | get_message: Message fetched.", request.req_id
                )
                # print(response)
                return response.target, response.data
            else:
                self.log.debug(
                    "%s | get_message: No message found.", request.req_id
                )
                # print(response)
                return target, None
        except grpc.RpcError as err:
            self.log.error(
                "%s | get_message: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
            raise

    def get_job(self, target):
        """Gets a job for a target.

        :param target: The resource target of a job.
        :returns: Tuple; (target, data)
        """
        if not self.stub:
            raise Exception("Job request after close")

        request = msg_pb2.GetJobRequest(
            req_id=str(uuid.uuid1()), target=target
        )

        try:
            response = self.stub.GetJob(request)
            # self.log.debug("%s | get_job: Request OK.", request.req_id)
            if response.status:
                self.log.debug("%s | get_job: Job fetched.", request.req_id)
                # print(response)
                return response.target, response.data
            else:
                self.log.debug("%s | get_job: No job found.", request.req_id)
                # print(response)
                return target, None
        except grpc.RpcError as err:
            self.log.error(
                "%s | get_job: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
            raise

    def put_message(
        self,
        target,
        identity,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Put a message in queue.

        :param identity: The resource target of a message.
        :param msg_id: The id of a msg.
        :param control: The control char of the msg
        :param command: The msg commnd
        :param data: The msg data
        :param info: The msg info
        :param stderr: The msg stderr
        :param stdout: The msg stdout.
        :returns: Boolean
        """
        if not self.stub:
            raise Exception("Message request after close")
        message = msg_pb2.MessageData(
            identity=identity,
            msg_id=msg_id,
            control=control,
            command=command,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout,
        )
        request = msg_pb2.PutMessageRequest(
            req_id=str(uuid.uuid1()), target=target, data=message
        )
        # self.log.debug(
        #     "%s | put_message: request %s", request.req_id, request
        # )

        try:
            response = self.stub.PutMessage(request)
            self.log.debug(
                "%s | put_message: Message submitted, %s",
                request.req_id,
                message.msg_id,
            )
            # print(response)
            return response.result
        except grpc.RpcError as err:
            self.log.error(
                "%s | put_message: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
        return False

    def put_job(
        self,
        target,
        identity,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Put a job in queue.

        :param identity: The resource target of a job.
        :param msg_id: The id of a msg.
        :param control: The control char of the msg
        :param command: The msg commnd
        :param data: The msg data
        :param info: The msg info
        :param stderr: The msg stderr
        :param stdout: The msg stdout.
        :returns: Boolean
        """
        if not self.stub:
            raise Exception("Job request after close")
        job = msg_pb2.MessageData(
            identity=identity,
            msg_id=msg_id,
            control=control,
            command=command,
            data=data,
            info=info,
            stderr=stderr,
            stdout=stdout,
        )
        request = msg_pb2.PutJobRequest(
            req_id=str(uuid.uuid1()), target=target, data=job
        )
        # self.log.debug("%s | put_job: request %s", request.req_id, request)

        try:
            response = self.stub.PutJob(request)
            self.log.debug(
                "%s | put_job: Job submitted, %s",
                request.req_id,
                job.msg_id,
            )
            # print(response)
            return response.result
        except grpc.RpcError as err:
            self.log.error(
                "%s | put_job: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
        return False

    def message_check(self, target):
        """Check if messages are in queue."""
        if not self.stub:
            raise Exception("Job request after close")
        request = msg_pb2.CheckRequest(req_id=str(uuid.uuid1()), target=target)
        try:
            response = self.stub.MessageCheck(request)
            # self.log.debug("message_check: %s", response.has_data)
            return response.has_data
        except grpc.RpcError as err:
            self.log.error(
                "%s | message_check: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
        return False

    def job_check(self, target):
        """Check if jobs are in queue."""
        if not self.stub:
            raise Exception("Job request after close")
        request = msg_pb2.CheckRequest(req_id=str(uuid.uuid1()), target=target)
        try:
            response = self.stub.JobCheck(request)
            # self.log.debug("job_check: %s", response.has_data)
            return response.has_data
        except grpc.RpcError as err:
            self.log.error(
                "%s | job_check: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
        return False

    def purge_queues(self):
        """Empty queues."""
        if not self.stub:
            raise Exception("Message request after close")
        request = msg_pb2.BasicRequest(req_id=str(uuid.uuid1()), verbose=False)
        try:
            response = self.stub.PurgeQueues(request)
            self.log.warning("%s | Queue purged", request.req_id)
            return response.status
        except grpc.RpcError as err:
            self.log.error(
                "%s | purge_queue: %s, %s, %s",
                request.req_id,
                err.code().name,
                err.code().value,
                err.details(),
            )  # pylint: disable=no-member
            self.log.error(err)
            raise


class MessageServiceServer:
    """Base queue."""

    _instance = None
    _server = None
    log = None

    def __init__(self):
        """Init."""
        raise RuntimeError("Use instance()")

    def _setup(
        self,
        address,
        port,
        secure,
        workers,
        compression=True,
        ssl_ca=None,
        ssl_cert=None,
        ssl_key=None,
        ssl_auth=False,
    ):
        """Setup data data."""
        if self._server:
            self.log.debug("Backend already configured, ignoring bind")
            return
        compression_type = grpc.Compression.Gzip
        if not compression:
            compression_type = grpc.Compression.NoCompression

        self._server = grpc.server(
            futures.ThreadPoolExecutor(max_workers=workers),
            compression=compression_type,
        )
        # add grpc servicer(s)
        msg_pb2_grpc.add_MessageServiceServicer_to_server(
            MessageServiceServicer(self.log), self._server
        )

        if secure:
            # handle cert/key
            key_pairs = []
            if not ssl_cert or not os.path.exists(ssl_cert):
                raise Exception(
                    f"Configured SSL Cert {ssl_cert} does not exist."
                )
            if not ssl_key or not os.path.exists(ssl_key):
                raise Exception(
                    f"Configured SSL Key {ssl_key} does not exist."
                )
            with open(ssl_cert, "rb") as cert_data:
                ssl_cert_data = cert_data.read()
            with open(ssl_key, "rb") as key_data:
                ssl_key_data = key_data.read()
            key_pairs.append((ssl_key_data, ssl_cert_data))
            # handle ca
            if not ssl_ca or not os.path.exists(ssl_ca):
                raise Exception(f"Configured SSL CA {ssl_ca} does not exist.")
            with open(ssl_ca, "rb") as ca_data:
                ssl_ca_data = ca_data.read()

            server_credentials = grpc.ssl_server_credentials(
                key_pairs, ssl_ca_data, ssl_auth
            )

            self.log.info("grpc server IS using SSL")
            self._server.add_secure_port(
                f"{address}:{port}", server_credentials
            )
        else:
            self.log.info("grpc server IS NOT using SSL")
            self._server.add_insecure_port(f"{address}:{port}")
        self._server.start()
        self.log.info("Started Message Service Server (%s:%s)", address, port)

    @classmethod
    def instance(
        cls,
        logger,
        address,
        port,
        secure=False,
        workers=4,
        compression=True,
        ssl_ca=None,
        ssl_cert=None,
        ssl_key=None,
        ssl_auth=False,
    ):
        """Get queue instance."""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.log = logger
            cls._instance._setup(
                address,
                port,
                secure,
                workers,
                compression,
                ssl_ca,
                ssl_cert,
                ssl_key,
                ssl_auth,
            )
        return cls._instance

    def stop(self, grace=None):
        """Stop the server."""
        if self._server:
            self.log.info("Stopping Message Service Server")
            self._server.stop(grace=grace)
        self._server = None


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

        self._client = None
        self._server = None
        # Use a special identity for all message destined for directord server.
        # In this case we use DIRECTORD_SERVER because that's not a valid
        # hostname so it shouldn't be possible to end up with a duplicate
        # target that masks the server.
        self._server_identity = "DIRECTORD_SERVER"

        self.args = args
        self.encrypted_traffic_data = encrypted_traffic_data

        self.mode = getattr(self.args, "mode", None)
        self.grpc_port = self.args.grpc_port
        self.server_address = self.args.grpc_server_address
        if self.mode == "server":
            self.bind_address = self.args.grpc_bind_address
        else:
            self.bind_address = "0.0.0.0"

        # TODO(mwhahaha): fix encryption?
        self.encrypted_traffic_data = False

        super(Driver, self).__init__(
            args=args,
            encrypted_traffic_data=self.encrypted_traffic_data,
            interface=interface,
        )
        # override identity because server identity is static to get messages
        # back to it
        if self.mode == "server":
            self.identity = self._server_identity

    def __copy__(self):
        """Return a new copy of the driver."""
        drv = Driver(
            args=self.args,
            encrypted_traffic_data=self.encrypted_traffic_data,
            interface=self.interface,
        )
        # init backend(s)
        drv.job_init()
        return drv

    def backend_recv(self, nonblocking=False):
        """Receive a transfer message.

        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        :returns: Tuple
        """
        while not self.backend_check():
            self.log.debug("No messages ready, waiting...")
        target, data = self._client.get_message(self.identity)
        return_msg = [
            data.msg_id,
            data.control,
            data.command,
            data.data or "{}",  # data is expected to be jsonable
            data.info,
            data.stderr,
            data.stdout,
        ]
        if self.mode == "server":
            return_msg.insert(0, data.identity)
        return return_msg

    def _grpc_init(self):
        """Initialize server and client."""
        if self.mode == "server" and not self._server:
            self._server = MessageServiceServer.instance(
                self.log,
                self.bind_address,
                self.grpc_port,
                self.args.grpc_ssl,
                self.args.grpc_server_workers,
                not self.args.grpc_disable_compression,
                self.args.grpc_ssl_ca,
                self.args.grpc_ssl_cert,
                self.args.grpc_ssl_key,
                self.args.grpc_ssl_client_auth,
            )
        # start connection to server
        if not self._client:
            self._client = MessageServiceClient.instance(
                self.log,
                self.server_address,
                self.grpc_port,
                self.args.grpc_ssl,
                not self.args.grpc_disable_compression,
                self.args.grpc_ssl_ca,
                self.args.grpc_ssl_cert,
                self.args.grpc_ssl_key,
            )
            self.log.info(
                "Started Message Service client (%s:%s)",
                self.server_address,
                self.grpc_port,
            )

    def backend_init(self):
        """Initialize the backend socket.

        For server mode, this is a bound local socket.
        For client mode, it is a connection to the server socket.

        :returns: Object
        """
        try:
            self._grpc_init()
        except Exception as e:
            self.log.error(
                "Unable to initialize backend. And Exception was raised. %s", e
            )
            raise

    def backend_close(self):
        """Close the backend connection."""
        self.log.debug(
            "The grpcd driver does not initialize a different backend "
            "connection. Nothing to close."
        )

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
        if self._client.message_check(self.identity):
            return True
        # limit checks to 5 per second and add some jitter
        self.timeout = (
            max(interval * (constant * 0.001), 0.5)
            + random.randrange(0, 1000) / 10000
        )
        time.sleep(self.timeout)
        return False

    def backend_send(self, *args, **kwargs):
        """Send a job message.

        * All args and kwargs are passed through to the socket send.

        :returns: Object
        """
        # target defaults to server if identity not specified
        identity = kwargs.get("identity", self.identity)
        target = kwargs.get(
            "target", kwargs.get("identity", self._server_identity)
        )
        try:
            self._client.put_message(
                target=target,
                identity=identity,
                msg_id=kwargs.get("msg_id"),
                control=kwargs.get("control"),
                command=kwargs.get("command"),
                data=kwargs.get("data"),
                info=kwargs.get("info"),
                stderr=kwargs.get("stderr"),
                stdout=kwargs.get("stdout"),
            )
        except Exception as e:
            self.log.error("Error putting message, %s", e)
            raise
        return True

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
            target=self._server_identity,
            identity=self.identity,
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
        # target defaults to server if identity not specified
        identity = kwargs.get("identity", self.identity)
        target = kwargs.get(
            "target", kwargs.get("identity", self._server_identity)
        )
        try:
            self._client.put_job(
                target=target,
                identity=identity,
                msg_id=kwargs.get("msg_id"),
                control=kwargs.get("control"),
                command=kwargs.get("command"),
                data=kwargs.get("data"),
                info=kwargs.get("info"),
                stderr=kwargs.get("stderr"),
                stdout=kwargs.get("stdout"),
            )
        except Exception as e:
            self.log.error("Error putting message, %s", e)
            raise
        return True

    def job_recv(self, nonblocking=False):
        """Receive a transfer message.

        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        :returns: Tuple
        """

        while not self.job_check():
            self.log.debug("No jobs ready, waiting...")
        target, data = self._client.get_job(self.identity)
        return_msg = [
            data.msg_id,
            data.control,
            data.command,
            data.data or "{}",  # data is expected to be jsonable
            data.info,
            data.stderr,
            data.stdout,
        ]
        if self.mode == "server":
            return_msg.insert(0, data.identity)
        return return_msg

    def job_init(self):
        """Initialize the job socket.

        For server mode, this is a bound local socket.
        For client mode, it is a connection to the server socket.

        :returns: Object
        """
        try:
            self._grpc_init()
        except Exception as e:
            self.log.error(
                (
                    "Unable to initialize jobs backend. And Exception was "
                    "raised. %s"
                ),
                e,
            )
            raise

    def job_close(self):
        """Close the job socket."""
        self.log.debug(
            "The grpcd driver shares a single client between all threads, "
            "skipping close."
        )

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
        if self._client.job_check(self.identity):
            return True
        # limit checks to 5 per second and add some jitter
        self.timeout = (
            max(interval * (constant * 0.001), 0.5)
            + random.randrange(0, 1000) / 10000
        )
        time.sleep(self.timeout)
        return False
