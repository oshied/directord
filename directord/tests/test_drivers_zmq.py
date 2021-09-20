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

import unittest

from unittest.mock import ANY
from unittest.mock import patch

import zmq

from directord import tests
from directord.drivers import zmq as zmq_driver


class TestDriverZMQSharedAuth(unittest.TestCase):
    def setUp(self):
        self.driver = zmq_driver.Driver(
            args=tests.FakeArgs, connection_string="tcp://localhost"
        )
        self.driver.encrypted_traffic = True
        self.driver.secret_keys_dir = "test/key"
        self.driver.public_keys_dir = "test/key"

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect_curve_auth(self, mock_info_logging):
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = True
                bind = self.driver._socket_connect(
                    socket_type=zmq.PULL,
                    connection="tcp://test",
                    port=1234,
                )
            self.assertEqual(bind.linger, -1)
        mock_info_logging.assert_called()

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.drivers.zmq.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_curve_auth(
        self, mock_auth, mock_poller, mock_socket
    ):
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            setattr(self.driver.args, "curve_encryption", True)
            setattr(self.driver.args, "shared_key", None)
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = True
                bind = self.driver._socket_bind(
                    socket_type=zmq.ROUTER,
                    connection="tcp://127.0.0.1",
                    port=9000,
                )
            self.assertIsNotNone(bind.bind)
            self.assertEqual(bind.curve_server, True)


class TestDriverZMQ(unittest.TestCase):
    def setUp(self):
        self.driver = zmq_driver.Driver(
            args=tests.FakeArgs, connection_string="tcp://localhost"
        )

    def tearDown(self):
        pass

    @patch("zmq.Poller.unregister", autospec=True)
    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_reset_heartbeat(
        self, mock_log_debug, mock_socket_connect, mock_poller
    ):
        bind_heatbeat = self.driver.heartbeat_connect()
        self.driver.heartbeat_reset(bind_heatbeat=bind_heatbeat)
        mock_poller.assert_called()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    def test_socket_bind_no_auth(self, mock_poller, mock_socket):
        bind = self.driver._socket_bind(
            socket_type=zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)

    @patch("logging.Logger.info", autospec=True)
    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.drivers.zmq.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_auth(
        self, mock_auth, mock_poller, mock_socket, mock_info_logging
    ):
        setattr(self.driver.args, "shared_key", "test")
        bind = self.driver._socket_bind(
            socket_type=zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)
        self.assertEqual(bind.plain_server, True)
        mock_info_logging.assert_called()

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect_shared_key(self, mock_info_logging):
        self.driver.encrypted_traffic = False
        setattr(self.driver.args, "shared_key", "test-key")
        bind = self.driver._socket_connect(
            socket_type=zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.plain_username, b"admin")
        self.assertEqual(bind.plain_password, b"test-key")
        self.assertEqual(bind.linger, -1)
        mock_info_logging.assert_called()

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect(self, mock_info_logging):
        bind = self.driver._socket_connect(
            socket_type=zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.linger, -1)
        mock_info_logging.assert_called()

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket,
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_ident(self, mock_socket):
        self.driver.socket_send(socket=mock_socket, identity=b"test-identity")
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_msg_id(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket,
            identity=b"test-identity",
            msg_id=b"testing_id",
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                b"testing_id",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_control(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket, identity=b"test-identity", control=b"\x01"
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x01",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_command(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket,
            identity=b"test-identity",
            command=b"test-command",
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"test-command",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_data(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket,
            identity=b"test-identity",
            data=b'{"test": "json"}',
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b'{"test": "json"}',
                b"\x00",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_info(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket, identity=b"test-identity", info=b"stdout-data"
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b"\x00",
                b"stdout-data",
                b"\x00",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_stderr(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket, identity=b"test-identity", stderr=b"stderr"
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"stderr",
                b"\x00",
            ],
            flags=0,
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send_stdout(self, mock_socket):
        self.driver.socket_send(
            socket=mock_socket, identity=b"test-identity", stdout=b"stdout"
        )
        mock_socket.send_multipart.assert_called_once_with(
            [
                b"test-identity",
                unittest.mock.ANY,
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"\x00",
                b"stdout",
            ],
            flags=0,
        )

    @patch("directord.drivers.zmq.Driver._socket_bind", autospec=True)
    def test_heartbeat_bind(self, mock_socket_bind):
        self.driver.heartbeat_bind()
        mock_socket_bind.assert_called_with(
            ANY,
            socket_type=zmq.ROUTER,
            connection="tcp://localhost",
            port=5557,
        )

    @patch("directord.drivers.zmq.Driver._socket_bind", autospec=True)
    def test_job_bind(self, mock_socket_bind):
        self.driver.job_bind()
        mock_socket_bind.assert_called_with(
            ANY,
            socket_type=zmq.ROUTER,
            connection="tcp://localhost",
            port=5555,
        )

    @patch("directord.drivers.zmq.Driver._socket_bind", autospec=True)
    def test_backend_bind(self, mock_socket_bind):
        self.driver.backend_bind()
        mock_socket_bind.assert_called_with(
            ANY,
            socket_type=zmq.ROUTER,
            connection="tcp://localhost",
            port=5556,
        )

    def test_get_heartbeat(self):
        with patch("time.time") as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(
                self.driver.get_heartbeat(
                    interval=tests.FakeArgs.heartbeat_interval
                ),
                1000000060.0000001,
            )

    def test_get_expiry(self):
        with patch("time.time") as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(
                self.driver.get_expiry(heartbeat_interval=60, interval=3),
                1000000180.0000001,
            )

    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_job_connect(self, mock_log_debug, mock_socket_connect):
        self.driver.job_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_backend_connect(self, mock_log_debug, mock_socket_connect):
        self.driver.backend_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_heartbeat_connect(self, mock_log_debug, mock_socket_connect):
        self.driver.heartbeat_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()
