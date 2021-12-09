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

import unittest

import unittest.mock as mock

from directord import tests
from directord.drivers import grpcd

try:
    import grpc

    GRPC_UNAVAILABLE = False
except (ImportError, ModuleNotFoundError):
    GRPC_UNAVAILABLE = True


class TestDriverGrpcdServerMode(unittest.TestCase):
    def setUp(self):
        args = tests.FakeArgs()
        args.mode = "server"
        self.driver = grpcd.Driver(args=args)
        self.client_mock = mock.MagicMock()
        self.driver._client = self.client_mock
        self.server_mock = mock.MagicMock()
        self.driver._server = self.server_mock

    def tearDown(self):
        pass

    @mock.patch("directord.drivers.grpcd.MessageServiceClient.instance")
    @mock.patch("directord.drivers.grpcd.MessageServiceServer.instance")
    def test_grpc_init(self, mock_server_inst, mock_client_inst):
        """Test backend startup."""
        mock_client = mock.MagicMock()
        mock_server = mock.MagicMock()
        mock_server_inst.return_value = mock_server
        mock_client_inst.return_value = mock_client

        self.driver._server = None
        self.driver._client = None

        self.driver._grpc_init()
        self.assertEqual(self.driver._server, mock_server)
        self.assertEqual(self.driver._client, mock_client)

        mock_server_inst.assert_called_once_with(
            self.driver.log,
            "0.0.0.0",
            5558,
            False,
            4,
            True,
            "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem",
            "/etc/directord/grpc/ssl/directord.crt",
            "/etc/directord/grpc/ssl/directord.key",
            False,
        )
        mock_client_inst.assert_called_once_with(
            self.driver.log,
            "127.0.0.1",
            5558,
            False,
            True,
            "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem",
            "/etc/directord/grpc/ssl/directord.crt",
            "/etc/directord/grpc/ssl/directord.key",
        )

    def test_backend_init(self):
        """Test backend init."""
        mock_grpc_init = mock.MagicMock()
        self.driver._grpc_init = mock_grpc_init
        self.driver.backend_init()
        mock_grpc_init.assert_called_once_with()

        mock_grpc_init.side_effect = Exception("foo")
        self.assertRaises(Exception, self.driver.backend_init)

    def test_job_init(self):
        """Test job init."""
        mock_grpc_init = mock.MagicMock()
        self.driver._grpc_init = mock_grpc_init
        self.driver.job_init()
        mock_grpc_init.assert_called_once_with()

        mock_grpc_init.side_effect = Exception("foo")
        self.assertRaises(Exception, self.driver.job_init)

    def test_backend_recv(self):
        """Test backend recv."""
        mock_backend_check = mock.MagicMock()
        mock_backend_check.return_value = True
        mock_data = mock.Mock()
        mock_data.identity = "identity"
        mock_data.msg_id = "msg_id"
        mock_data.control = "control"
        mock_data.command = "command"
        mock_data.data = "{}"
        mock_data.info = "info"
        mock_data.stdout = "stdout"
        mock_data.stderr = "stderr"

        self.driver._client.get_message.return_value = ("target", mock_data)

        self.driver.backend_check = mock_backend_check

        data = self.driver.backend_recv()

        self.assertEqual(
            data,
            [
                "identity",
                "msg_id",
                "control",
                "command",
                "{}",
                "info",
                "stderr",
                "stdout",
            ],
        )

    def test_job_recv(self):
        """Test job recv."""
        mock_job_check = mock.MagicMock()
        mock_job_check.return_value = True
        mock_data = mock.Mock()
        mock_data.identity = "identity"
        mock_data.msg_id = "msg_id"
        mock_data.control = "control"
        mock_data.command = "command"
        mock_data.data = "{}"
        mock_data.info = "info"
        mock_data.stdout = "stdout"
        mock_data.stderr = "stderr"

        self.driver._client.get_job.return_value = ("target", mock_data)

        self.driver.job_check = mock_job_check

        data = self.driver.job_recv()

        self.assertEqual(
            data,
            [
                "identity",
                "msg_id",
                "control",
                "command",
                "{}",
                "info",
                "stderr",
                "stdout",
            ],
        )

    def test_backend_send(self):
        """Test backend send."""
        mock_put = mock.MagicMock()
        self.driver._client.put_message = mock_put
        self.assertTrue(
            self.driver.backend_send(
                target="foo",
                identity="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )

        mock_put.assert_called_once_with(
            target="foo",
            identity="bar",
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        self.assertTrue(
            self.driver.backend_send(
                identity="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )
        mock_put.assert_called_once_with(
            target="bar",
            identity="bar",
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        self.assertTrue(
            self.driver.backend_send(
                target="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )
        mock_put.assert_called_once_with(
            target="bar",
            identity=self.driver._server_identity,
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        mock_put.side_effect = Exception("err")
        self.assertRaises(Exception, self.driver.backend_send)

    def test_job_send(self):
        """Test job send."""
        mock_put = mock.MagicMock()
        self.driver._client.put_job = mock_put
        self.assertTrue(
            self.driver.job_send(
                target="foo",
                identity="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )

        mock_put.assert_called_once_with(
            target="foo",
            identity="bar",
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        self.assertTrue(
            self.driver.job_send(
                identity="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )
        mock_put.assert_called_once_with(
            target="bar",
            identity="bar",
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        self.assertTrue(
            self.driver.job_send(
                target="bar",
                msg_id="msg_id",
                control="control",
                command="command",
                data="data",
                info="info",
            )
        )
        mock_put.assert_called_once_with(
            target="bar",
            identity=self.driver._server_identity,
            msg_id="msg_id",
            control="control",
            command="command",
            data="data",
            info="info",
            stderr=None,
            stdout=None,
        )

        mock_put.reset_mock()
        mock_put.side_effect = Exception("err")
        self.assertRaises(Exception, self.driver.job_send)

    @mock.patch("time.sleep")
    def test_backend_check(self, mock_sleep):
        """Test backend check function."""
        self.driver._client.message_check.return_value = True
        self.assertTrue(self.driver.backend_check())
        mock_sleep.assert_not_called()

        self.driver._client.message_check.return_value = False
        self.assertFalse(self.driver.backend_check())
        mock_sleep.assert_called_once_with(self.driver.timeout)

    @mock.patch("time.sleep")
    def test_job_check(self, mock_sleep):
        """Test job check function."""
        self.driver._client.job_check.return_value = True
        self.assertTrue(self.driver.job_check())
        mock_sleep.assert_not_called()

        self.driver._client.job_check.return_value = False
        self.assertFalse(self.driver.job_check())
        mock_sleep.assert_called_once_with(self.driver.timeout)

    @mock.patch("directord.utils.get_uuid", return_value="uuid")
    def test_hearbeat_send(self, mock_uuid):
        mock_job_send = mock.MagicMock()
        self.driver.job_send = mock_job_send
        self.driver.machine_id = "machine_id"
        self.driver.heartbeat_send(1, 1, 1, "grpcd")
        mock_job_send.assert_called_once_with(
            target="DIRECTORD_SERVER",
            identity="DIRECTORD_SERVER",
            control="\x05",
            msg_id="uuid",
            data=(
                '{"job_id": "uuid", "version": 1, "host_uptime": 1, '
                '"agent_uptime": 1, "machine_id": "machine_id", '
                '"driver": "grpcd"}'
            ),
        )

    def test_backend_close(self):
        """Test backend close"""
        mock_log = mock.MagicMock()
        self.driver.log = mock_log
        self.driver.backend_close()
        mock_log.debug.assert_called_once_with(
            "The grpcd driver does not initialize a different backend "
            "connection. Nothing to close."
        )

    def test_job_close(self):
        """Test job close"""
        mock_log = mock.MagicMock()
        self.driver.log = mock_log
        self.driver.job_close()
        mock_log.debug.assert_called_once_with(
            "The grpcd driver shares a single client between all threads, "
            "skipping close."
        )

    def test_key_generate(self):
        """Test key generate."""
        # does nothing
        self.driver.key_generate("foo", "bar")


class TestDriverGrpcdClientMode(unittest.TestCase):
    def setUp(self):
        args = tests.FakeArgs()
        args.mode = "client"
        self.driver = grpcd.Driver(args=args)
        self.driver = grpcd.Driver(args=args)
        self.client_mock = mock.MagicMock()
        self.driver._client = self.client_mock

    def tearDown(self):
        pass

    @mock.patch("directord.drivers.grpcd.MessageServiceClient.instance")
    def test_grpc_init(self, mock_client_inst):
        """Test backend startup."""
        mock_client = mock.MagicMock()
        mock_client_inst.return_value = mock_client

        self.driver._client = None

        self.driver._grpc_init()
        self.assertEqual(self.driver._server, None)
        self.assertEqual(self.driver._client, mock_client)

        mock_client_inst.assert_called_once_with(
            self.driver.log,
            "127.0.0.1",
            5558,
            False,
            True,
            "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem",
            "/etc/directord/grpc/ssl/directord.crt",
            "/etc/directord/grpc/ssl/directord.key",
        )

    def test_backend_recv(self):
        """Test backend recv."""
        mock_backend_check = mock.MagicMock()
        mock_backend_check.side_effect = [False, True]
        mock_data = mock.Mock()
        mock_data.identity = "identity"
        mock_data.msg_id = "msg_id"
        mock_data.control = "control"
        mock_data.command = "command"
        mock_data.data = "{}"
        mock_data.info = "info"
        mock_data.stdout = "stdout"
        mock_data.stderr = "stderr"

        self.driver._client.get_message.return_value = ("target", mock_data)

        self.driver.backend_check = mock_backend_check

        data = self.driver.backend_recv()

        self.assertEqual(
            data,
            ["msg_id", "control", "command", "{}", "info", "stderr", "stdout"],
        )

    def test_job_recv(self):
        """Test job recv."""
        mock_job_check = mock.MagicMock()
        mock_job_check.side_effect = [False, True]
        mock_data = mock.Mock()
        mock_data.identity = "identity"
        mock_data.msg_id = "msg_id"
        mock_data.control = "control"
        mock_data.command = "command"
        mock_data.data = "{}"
        mock_data.info = "info"
        mock_data.stdout = "stdout"
        mock_data.stderr = "stderr"

        self.driver._client.get_job.return_value = ("target", mock_data)

        self.driver.job_check = mock_job_check

        data = self.driver.job_recv()

        self.assertEqual(
            data,
            [
                "msg_id",
                "control",
                "command",
                "{}",
                "info",
                "stderr",
                "stdout",
            ],
        )

    @mock.patch("directord.utils.get_uuid", return_value="uuid")
    def test_hearbeat_send(self, mock_uuid):
        mock_job_send = mock.MagicMock()
        self.driver.job_send = mock_job_send
        self.driver.machine_id = "machine_id"
        self.driver.heartbeat_send(1, 1, 1, "grpcd")
        mock_job_send.assert_called_once_with(
            target="DIRECTORD_SERVER",
            identity="test-node",
            control="\x05",
            msg_id="uuid",
            data=(
                '{"job_id": "uuid", "version": 1, "host_uptime": 1, '
                '"agent_uptime": 1, "machine_id": "machine_id", '
                '"driver": "grpcd"}'
            ),
        )


class TestGrpcQueueBase(unittest.TestCase):
    """Test queue base."""

    def setUp(self):
        grpcd.QueueBase._instance = None
        self.queue = grpcd.QueueBase.instance()

    def tearDown(self):
        grpcd.QueueBase._instance = None

    def test_instance(self):
        """Test instance setup."""
        self.assertEqual(self.queue._data_queue, {})

    def test_children_queues(self):
        """Test queue subsclasses."""
        msg_q = grpcd.MessageQueue.instance()
        job_q = grpcd.JobQueue.instance()
        self.assertNotEqual(msg_q, job_q)

    def test_add(self):
        """Test queue add."""
        self.queue.add_queue("foo", "bar")
        self.assertEqual(self.queue._data_queue.get("foo").get(), "bar")

    def test_get(self):
        """Test queue get."""
        self.assertEqual(self.queue.get_from_queue("bar"), None)
        self.queue.add_queue("foo", "bar")
        self.assertEqual(self.queue.get_from_queue("foo"), "bar")

    def test_check(self):
        """Test queue check."""
        self.assertFalse(self.queue.check_queue("foo"))
        self.queue.add_queue("foo", "bar")
        self.assertTrue(self.queue.check_queue("foo"))
        self.queue.get_from_queue("foo")
        self.assertFalse(self.queue.check_queue("foo"))

    def test_stats(self):
        """Test queue stats."""
        self.assertEqual(self.queue.get_stats(), {"targets": []})
        self.queue.add_queue("foo", "bar")
        self.assertEqual(self.queue.get_stats(), {"targets": ["foo"]})

    def test_purge(self):
        """Test queue purge."""
        self.queue.add_queue("foo", "bar")
        self.queue.purge_queue()
        self.assertEqual(self.queue._data_queue, {})


@unittest.skipIf(GRPC_UNAVAILABLE, "grpc library unavailable")
class TestGrpcServer(unittest.TestCase):
    """Test grpc server logic."""

    @mock.patch("directord.drivers.grpcd.MessageServiceServer._setup")
    def test_instance(self, mock_setup):
        mock_log = mock.MagicMock()
        grpcd.MessageServiceServer._instance = None
        obj = grpcd.MessageServiceServer.instance(
            mock_log,
            "localhost",
            5558,
            secure=True,
            workers=8,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
            ssl_auth=True,
        )
        self.assertEqual(obj.log, mock_log)
        mock_setup.assert_called_once_with(
            "localhost",
            5558,
            True,
            8,
            False,
            "ssl_ca",
            "ssl_cert",
            "ssl_key",
            True,
        )

    @mock.patch("concurrent.futures.ThreadPoolExecutor")
    @mock.patch("grpc.server")
    def test_setup(self, mock_server, mock_thread_pool):
        mock_log = mock.MagicMock()
        grpcd.MessageServiceServer._instance = None
        obj = grpcd.MessageServiceServer.instance(
            mock_log,
            "localhost",
            5558,
            secure=False,
            compression=False,
        )
        self.assertEqual(obj.log, mock_log)
        mock_thread_pool.assert_called_once_with(max_workers=4)
        mock_server.assert_called_once_with(
            mock_thread_pool.return_value,
            compression=grpc.Compression.NoCompression,
        )
        mock_server.return_value.add_insecure_port.assert_called_once_with(
            "localhost:5558"
        )
        mock_server.return_value.start.assert_called_once_with()

    @mock.patch(
        "directord.drivers.generated.msg_pb2_grpc.add_MessageServiceServicer_to_server"
    )
    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="data")
    @mock.patch("grpc.ssl_server_credentials")
    @mock.patch("os.path.exists")
    @mock.patch("concurrent.futures.ThreadPoolExecutor")
    @mock.patch("grpc.server")
    def test_setup_ssl(
        self,
        mock_server,
        mock_thread_pool,
        mock_exists,
        mock_ssl_creds,
        mock_open,
        mock_add,
    ):
        mock_log = mock.MagicMock()
        mock_exists.side_effect = [True, True, True]
        grpcd.MessageServiceServer._instance = None
        obj = grpcd.MessageServiceServer.instance(
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=True,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
            ssl_auth=True,
        )
        self.assertEqual(obj.log, mock_log)
        mock_thread_pool.assert_called_once_with(max_workers=4)
        mock_server.assert_called_once_with(
            mock_thread_pool.return_value,
            compression=grpc.Compression.Gzip,
        )
        mock_ssl_creds.assert_called_once_with(
            [("data", "data")], "data", True
        )
        mock_server.return_value.add_secure_port.assert_called_once_with(
            "localhost:5558", mock_ssl_creds.return_value
        )
        mock_server.return_value.start.assert_called_once_with()

        # missing ssl cert
        mock_exists.side_effect = [False]
        grpcd.MessageServiceServer._instance = None
        self.assertRaises(
            Exception,
            grpcd.MessageServiceServer.instance,
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
            ssl_auth=True,
        )

        # missing ssl key
        mock_exists.side_effect = [True, False]
        grpcd.MessageServiceServer._instance = None
        self.assertRaises(
            Exception,
            grpcd.MessageServiceServer.instance,
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
            ssl_auth=True,
        )

        # missing ssl ca
        mock_exists.side_effect = [True, True, False]
        grpcd.MessageServiceServer._instance = None
        self.assertRaises(
            Exception,
            grpcd.MessageServiceServer.instance,
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
            ssl_auth=True,
        )

    @mock.patch("directord.drivers.grpcd.MessageServiceServer._setup")
    def test_stop(self, mock_setup):
        mock_log = mock.MagicMock()
        grpcd.MessageServiceServer._instance = None
        obj = grpcd.MessageServiceServer.instance(mock_log, "localhost", 5558)
        mock_server = mock.MagicMock()
        obj._server = mock_server
        obj.stop()
        mock_server.stop.assert_called_once_with(grace=None)
        self.assertEqual(obj._server, None)


@unittest.skipIf(GRPC_UNAVAILABLE, "grpc library unavailable")
class TestGrpcClient(unittest.TestCase):
    """Test grpc client logic."""

    @mock.patch("directord.drivers.grpcd.MessageServiceClient.connect")
    def test_instance(self, mock_connect):
        mock_log = mock.MagicMock()
        grpcd.MessageServiceClient._instance = None
        obj = grpcd.MessageServiceClient.instance(
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
        )
        mock_connect.assert_called_once_with()
        self.assertEqual(obj.server_address, "localhost")
        self.assertEqual(obj.server_port, 5558)
        self.assertEqual(obj.secure, True)
        self.assertEqual(obj.compression, False)
        self.assertEqual(obj.ssl_ca, "ssl_ca")
        self.assertEqual(obj.ssl_cert, "ssl_cert")
        self.assertEqual(obj.ssl_key, "ssl_key")

    @mock.patch("threading.Event")
    @mock.patch("directord.drivers.generated.msg_pb2_grpc.MessageServiceStub")
    @mock.patch("grpc.insecure_channel")
    def test_connect(self, mock_channel, mock_stub, mock_wait):
        mock_log = mock.MagicMock()
        mock_channel_obj = mock.MagicMock()
        mock_channel.return_value = mock_channel_obj
        grpcd.MessageServiceClient._instance = None
        grpcd.MessageServiceClient.instance(mock_log, "localhost", 5558)
        mock_channel.assert_called_once_with(
            "localhost:5558", compression=grpc.Compression.Gzip
        )
        mock_channel_obj.subscribe.assert_called_once_with(
            mock.ANY, try_to_connect=True
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="data")
    @mock.patch("os.path.exists")
    @mock.patch("threading.Event")
    @mock.patch("directord.drivers.generated.msg_pb2_grpc.MessageServiceStub")
    @mock.patch("grpc.ssl_channel_credentials")
    @mock.patch("grpc.secure_channel")
    def test_connect_secure(
        self,
        mock_channel,
        mock_creds,
        mock_stub,
        mock_wait,
        mock_exists,
        mock_open,
    ):
        mock_log = mock.MagicMock()
        mock_channel_obj = mock.MagicMock()
        mock_channel.return_value = mock_channel_obj
        mock_exists.return_value = True
        grpcd.MessageServiceClient._instance = None
        obj = grpcd.MessageServiceClient.instance(
            mock_log,
            "localhost",
            5558,
            secure=True,
            compression=False,
            ssl_ca="ssl_ca",
            ssl_cert="ssl_cert",
            ssl_key="ssl_key",
        )
        mock_creds.assert_called_once_with("data", "data", "data")
        mock_channel.assert_called_once_with(
            "localhost:5558",
            credentials=mock_creds.return_value,
            compression=grpc.Compression.NoCompression,
        )
        mock_channel_obj.subscribe.assert_called_once_with(
            mock.ANY, try_to_connect=True
        )

        # missing CA
        mock_exists.return_value = False
        self.assertRaises(Exception, obj.connect)

        # No client auth due to missing cert bits
        mock_exists.side_effect = [True, False]
        mock_creds.reset_mock()
        obj.connect()
        mock_creds.assert_called_once_with("data", None, None)

        mock_exists.side_effect = [True, True, False]
        mock_creds.reset_mock()
        obj.connect()
        mock_creds.assert_called_once_with("data", None, None)

        mock_exists.side_effect = [True, True, True]
        mock_creds.reset_mock()
        obj.ssl_key = None
        obj.ssl_cert = "ssl_cert"
        obj.connect()
        mock_creds.assert_called_once_with("data", None, None)

        mock_exists.side_effect = [True, True, True]
        mock_creds.reset_mock()
        obj.ssl_key = "ssl_key"
        obj.ssl_cert = None
        obj.connect()
        mock_creds.assert_called_once_with("data", None, None)

    @mock.patch("directord.drivers.grpcd.MessageServiceClient._setup")
    def test_close(self, mock_setup):
        mock_log = mock.MagicMock()
        grpcd.MessageServiceClient._instance = None
        obj = grpcd.MessageServiceClient.instance(mock_log, "localhost", 5558)
        mock_setup.assert_called_once_with(
            "localhost", 5558, False, True, None, None, None
        )

        mock_channel = mock.MagicMock()
        obj.channel = mock_channel
        obj.stub = True
        obj.close()
        self.assertEqual(obj.channel, None)
        self.assertEqual(obj.stub, None)
