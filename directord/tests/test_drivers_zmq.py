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
from unittest.mock import call
from unittest.mock import patch

import zmq

from directord import tests
from directord.drivers import zmq as zmq_driver


class TestDriverZMQSharedAuth(tests.TestBase):
    def setUp(self):
        super().setUp()
        with patch("zmq.Context"):
            self.driver = zmq_driver.Driver(args=tests.FakeArgs)
        self.driver.encrypted_traffic = True
        self.driver.secret_keys_dir = "test/key"
        self.driver.public_keys_dir = "test/key"

    def tearDown(self):
        super().tearDown()
        self.driver.shutdown()

    def test_get_lock(self):
        with patch("multiprocessing.Lock") as mock_lock:
            self.driver.get_lock()
            mock_lock.assert_called()

    def test_socket_connect_curve_auth(self):
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = True
                bind = self.driver._socket_connect(
                    socket_type=zmq.PULL,
                    connection="tcp://test",
                    port=1234,
                )
            self.assertEqual(bind.linger, 60)

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.drivers.zmq.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_curve_auth(
        self, mock_auth, mock_poller, mock_socket
    ):
        m = unittest.mock.mock_open(read_data=tests.MOCK_CURVE_KEY.encode())
        with patch("builtins.open", m):
            setattr(self.driver.args, "zmq_curve_encryption", True)
            setattr(self.driver.args, "zmq_shared_key", None)
            with patch("os.path.exists") as mock_exists:
                mock_exists.return_value = True
                bind = self.driver._socket_bind(
                    socket_type=zmq.ROUTER,
                    connection="tcp://127.0.0.1",
                    port=9000,
                )
            self.assertIsNotNone(bind.bind)
            self.assertEqual(bind.curve_server, True)


class TestDriverZMQ(tests.TestBase):
    def setUp(self):
        super().setUp()
        with patch("zmq.Context"):
            self.driver = zmq_driver.Driver(args=tests.FakeArgs)

    def tearDown(self):
        super().tearDown()
        self.driver.shutdown()

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    def test_socket_bind_no_auth(self, mock_poller, mock_socket):
        bind = self.driver._socket_bind(
            socket_type=zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    @patch("directord.drivers.zmq.ThreadAuthenticator", autospec=True)
    def test_socket_bind_shared_auth(
        self, mock_auth, mock_poller, mock_socket
    ):
        setattr(self.driver.args, "zmq_shared_key", "test")
        bind = self.driver._socket_bind(
            socket_type=zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)
        self.assertEqual(bind.plain_server, True)

    def test_socket_connect_shared_key(self):
        self.driver.encrypted_traffic = False
        setattr(self.driver.args, "zmq_shared_key", "test-key")
        bind = self.driver._socket_connect(
            socket_type=zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.plain_username, b"admin")
        self.assertEqual(bind.plain_password, b"test-key")
        self.assertEqual(bind.linger, 60)

    def test_socket_connect(self):
        bind = self.driver._socket_connect(
            socket_type=zmq.PULL,
            connection="tcp://test",
            port=1234,
        )
        self.assertEqual(bind.linger, 60)

    @patch("zmq.sugar.socket.Socket", autospec=True)
    def test_socket_send(self, mock_socket):
        self.driver._socket_send(
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
        self.driver._socket_send(socket=mock_socket, identity=b"test-identity")
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
        self.driver._socket_send(
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
    def test_job_bind(self, mock_socket_bind):
        self.driver._job_bind()
        mock_socket_bind.assert_called_with(
            ANY,
            socket_type=zmq.ROUTER,
            connection="tcp://localhost",
            port=5555,
        )

    @patch("directord.drivers.zmq.Driver._socket_bind", autospec=True)
    def test_backend_bind(self, mock_socket_bind):
        self.driver._backend_bind()
        mock_socket_bind.assert_called_with(
            ANY,
            socket_type=zmq.ROUTER,
            connection="tcp://localhost",
            port=5556,
        )

    def test_get_expiry(self):
        with patch("time.time") as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(
                self.driver.get_expiry(heartbeat_interval=60, interval=3),
                1000000180.0000001,
            )

    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    def test_job_connect(self, mock_socket_connect):
        self.driver._job_connect()
        mock_socket_connect.assert_called()

    @patch("directord.drivers.zmq.Driver._socket_connect", autospec=True)
    def test_backend_connect(self, mock_socket_connect):
        self.driver._backend_connect()
        mock_socket_connect.assert_called()

    def test_zmq_mode_client(self):
        client_args = tests.FakeArgs()
        client_args.mode = "client"
        with patch("zmq.Context"):
            driver = zmq_driver.Driver(args=client_args)
        try:
            self.assertEqual(driver.bind_address, "localhost")
        finally:
            driver.shutdown()

    def test_zmq_mode_server(self):
        server_args = tests.FakeArgs()
        server_args.mode = "server"
        with patch("zmq.Context"):
            driver = zmq_driver.Driver(args=server_args)
        try:
            self.assertEqual(driver.bind_address, "10.1.10.1")
        finally:
            driver.shutdown()

    def test_key_generate(self):
        with patch("io.open", create=True):
            self.driver._key_generate("foo", "bar")

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_null(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one", "item-two"]
        self.driver._move_certificates(directory="/test/path")
        mock_rename.assert_not_called()

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_normal(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.driver._move_certificates(directory="/test/path")
        mock_rename.assert_called_with(
            "/test/path/item-two.key", "/test/path/item-two.key"
        )

        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/test/path/item-one.key"),
                call("/test/path/item-two.key", "/test/path/item-two.key"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_backup(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.driver._move_certificates(directory="/test/path", backup=True)
        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/test/path/item-one.key.bak"),
                call("/test/path/item-two.key", "/test/path/item-two.key.bak"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_target_directory(
        self, mock_listdir, mock_rename
    ):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.driver._move_certificates(
            directory="/test/path", target_directory="/new/test/path"
        )
        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/new/test/path/item-one.key"),
                call("/test/path/item-two.key", "/new/test/path/item-two.key"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_normal_selective(
        self, mock_listdir, mock_rename
    ):
        mock_listdir.return_value = ["item-one.test", "item-two.key"]
        self.driver._move_certificates(directory="/test/path", suffix=".test")
        mock_rename.assert_called_once_with(
            "/test/path/item-one.test", "/test/path/item-one.test"
        )

    @patch("os.makedirs", autospec=True)
    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_generate_certificates(
        self, mock_listdir, mock_rename, mock_makedirs
    ):
        mock_listdir.return_value = ["item-one.test", "item-two.key"]
        with patch("io.open", create=True):
            self.driver._generate_certificates()

        mock_makedirs.assert_has_calls(
            [
                call("/etc/directord/certificates", exist_ok=True),
                call("/etc/directord/public_keys", exist_ok=True),
                call("/etc/directord/private_keys", exist_ok=True),
            ]
        )
