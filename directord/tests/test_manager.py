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
import uuid

from unittest.mock import patch

from directord import manager
from directord import tests


class TestUtils(unittest.TestCase):
    def setUp(self):
        args = tests.FakeArgs()
        self.interface = manager.Interface(args=args)
        self.sockets = list()

    def tearDown(self):
        for socket in self.sockets:
            socket.close()

    def test_get_heartbeat(self):
        with patch("time.time") as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(self.interface.get_heartbeat, 1000000060.0000001)

    def test_get_expiry(self):
        with patch("time.time") as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(self.interface.get_expiry, 1000000180.0000001)

    def test_get_uuid(self):
        uuid1 = self.interface.get_uuid
        uuid.UUID(uuid1, version=4)
        uuid2 = self.interface.get_uuid
        uuid.UUID(uuid2, version=4)
        self.assertNotEqual(uuid1, uuid2)

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    def test_socket_bind_no_auth(self, mock_poller, mock_socket):
        bind = self.interface.socket_bind(
            socket_type=manager.zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)

    @patch("logging.Logger.info", autospec=True)
    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.manager.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_auth(
        self, mock_auth, mock_poller, mock_socket, mock_info_logging
    ):
        setattr(self.interface.args, "shared_key", "test")
        bind = self.interface.socket_bind(
            socket_type=manager.zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)
        self.assertEqual(bind.plain_server, True)
        mock_info_logging.assert_called()

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.manager.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_curve_auth(
        self, mock_auth, mock_poller, mock_socket
    ):
        setattr(self.interface.args, "curve_encryption", True)
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            bind = self.interface.socket_bind(
                socket_type=manager.zmq.ROUTER,
                connection="tcp://127.0.0.1",
                port=9000,
            )
            self.assertIsNotNone(bind.bind)
            self.assertEqual(bind.curve_server, True)

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect(self, mock_info_logging):
        self.interface.curve_keys_exist = False
        bind = self.interface.socket_connect(
            socket_type=manager.zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.linger, 0)
        mock_info_logging.assert_called()

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect_shared_key(self, mock_info_logging):
        self.interface.curve_keys_exist = False
        setattr(self.interface.args, "shared_key", "test-key")
        bind = self.interface.socket_connect(
            socket_type=manager.zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.plain_username, b"admin")
        self.assertEqual(bind.plain_password, b"test-key")
        self.assertEqual(bind.linger, 0)
        mock_info_logging.assert_called()

    @patch("logging.Logger.info", autospec=True)
    def test_socket_connect_curve_auth(self, mock_info_logging):
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            bind = self.interface.socket_connect(
                socket_type=manager.zmq.PULL,
                connection="tcp://test",
                port=1234,
            )
            self.assertEqual(bind.linger, 0)
        mock_info_logging.assert_called()

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket,
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_ident(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket, identity=b"test-identity"
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
                b"\x00",
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_msg_id(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket,
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_control(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket, identity=b"test-identity", control=b"\x01"
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_command(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket,
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_data(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket,
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_info(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket, identity=b"test-identity", info=b"stdout-data"
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_stderr(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket, identity=b"test-identity", stderr=b"stderr"
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
            ]
        )

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_multipart_send_stdout(self, mock_socket):
        self.interface.socket_multipart_send(
            zsocket=mock_socket, identity=b"test-identity", stdout=b"stdout"
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
            ]
        )
