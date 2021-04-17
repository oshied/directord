import unittest

from unittest.mock import patch

from director import tests
from director import utils


class TestUtils(unittest.TestCase):
    @patch("director.utils.subprocess.Popen")
    def test_run_command_success(self, popen):
        popen.return_value = tests.FakePopen()
        output, outcome = utils.run_command(command="test_command")
        self.assertEqual(output, "stdout")
        self.assertEqual(outcome, True)

    @patch("director.utils.subprocess.Popen")
    def test_run_command_fail(self, popen):
        popen.return_value = tests.FakePopen(return_code=1)
        output, outcome = utils.run_command(command="test_command")
        self.assertEqual(output, "stderr")
        self.assertEqual(outcome, False)

    def test_dump_yaml(self):
        m = unittest.mock.mock_open()
        with patch("builtins.open", m):
            file_path = utils.dump_yaml(
                file_path="/test.yaml", data={"test": "data"}
            )
        m.assert_called_once_with("/test.yaml", "w")
        assert file_path == "/test.yaml"

    def test_ctx_mgr_clientstatus_enter_exit(self):
        ctx = unittest.mock.MagicMock()
        socket = unittest.mock.MagicMock()
        with utils.ClientStatus(
            socket=socket, job_id=b"test-id", ctx=ctx
        ) as c:
            assert c.job_id == b"test-id"

        ctx.socket_multipart_send.assert_called_once_with(
            zsocket=socket,
            msg_id=b"test-id",
            control=unittest.mock.ANY,
            info=unittest.mock.ANY,
        )

    def test_ctx_mgr_clientstatus_start_processing(self):
        ctx = unittest.mock.MagicMock()
        socket = unittest.mock.MagicMock()
        with utils.ClientStatus(
            socket=socket, job_id=b"test-id-start", ctx=ctx
        ) as c:
            c.start_processing()
            ctx.socket_multipart_send.assert_called_once_with(
                zsocket=socket,
                msg_id=b"test-id-start",
                control=unittest.mock.ANY,
            )

        ctx.socket_multipart_send.assert_called_with(
            zsocket=socket,
            msg_id=b"test-id-start",
            control=unittest.mock.ANY,
            info=unittest.mock.ANY,
        )
