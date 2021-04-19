import unittest
import uuid

from unittest.mock import patch
from unittest.mock import MagicMock

from director import manager

from director import tests


class TestUtils(unittest.TestCase):
    def setUp(self):
        args = tests.FakeArgs()
        self.interface = manager.Interface(args=args)

    def test_get_heartbeat(self):
        with patch('time.time') as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(
                self.interface.get_heartbeat,
                1000000060.0000001
            )

    def test_get_expiry(self):
        with patch('time.time') as p:
            p.return_value = 1000000000.0000001
            self.assertEqual(
                self.interface.get_expiry,
                1000000180.0000001
            )

    def test_get_uuid(self):
        uuid1 = self.interface.get_uuid
        uuid.UUID(uuid1, version=4)
        uuid2 = self.interface.get_uuid
        uuid.UUID(uuid2, version=4)
        self.assertNotEqual(uuid1, uuid2)

    @patch("zmq.backend.Socket", autospec=True)
    @patch("zmq.Poller", autospec=True)
    def test_socket_bind_no_auth(self, socket, poller):
        bind = self.interface.socket_bind(
            socket_type=manager.zmq.ROUTER,
            connection="tcp://127.0.0.1",
            port=9000,
        )
        self.assertIsNotNone(bind.bind)


    def test_socket_bind_shared_auth(self):
        pass

    def test_socket_bind_curve_auth(self):
        pass

    def test_socket_connect(self):
        pass

    def test_run_threads(self):
        pass

    def test_socket_multipart_send(self):
        pass

    def test_socket_multipart_recv(self):
        pass
