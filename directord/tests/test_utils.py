import unittest

from unittest.mock import patch

from directord import tests
from directord import utils


class TestUtils(unittest.TestCase):
    @patch("directord.utils.subprocess.Popen")
    def test_run_command_success(self, popen):
        popen.return_value = tests.FakePopen()
        output, outcome = utils.run_command(command="test_command")
        self.assertEqual(output, "stdout")
        self.assertEqual(outcome, True)

    @patch("directord.utils.subprocess.Popen")
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

    def test_merge_dict(self):
        a = {
            "dict": {"a": "test", "b": {"int1": 1}},
            "list": ["a"],
            "str": "a",
            "int": 1,
        }
        b = {
            "dict": {"b": {"int2": 2}, "c": "test2"},
            "list": ["b"],
            "key": "value",
        }
        merge = {
            "dict": {"a": "test", "b": {"int1": 1, "int2": 2}, "c": "test2"},
            "int": 1,
            "key": "value",
            "list": ["a", "b"],
            "str": "a",
        }
        new = utils.merge_dict(base=a, new=b)
        self.assertEqual(new, merge)

    def test_ctx_mgr_clientstatus_enter_exit(self):
        ctx = unittest.mock.MagicMock()
        socket = unittest.mock.MagicMock()
        with utils.ClientStatus(
            socket=socket,
            job_id=b"test-id",
            command=b"test",
            ctx=ctx,
        ) as c:
            assert c.job_id == b"test-id"

        ctx.socket_multipart_send.assert_called_with(
            zsocket=socket,
            msg_id=b"test-id",
            command=b"test",
            control=unittest.mock.ANY,
            data=unittest.mock.ANY,
            info=unittest.mock.ANY,
        )

    def test_ctx_mgr_clientstatus_start_processing(self):
        ctx = unittest.mock.MagicMock()
        socket = unittest.mock.MagicMock()
        with utils.ClientStatus(
            socket=socket, job_id=b"test-id-start", command=b"test", ctx=ctx
        ) as c:
            c.start_processing()
            ctx.socket_multipart_send.assert_called_with(
                zsocket=socket,
                msg_id=b"test-id-start",
                control=unittest.mock.ANY,
            )

        ctx.socket_multipart_send.assert_called_with(
            zsocket=socket,
            msg_id=b"test-id-start",
            command=b"test",
            control=unittest.mock.ANY,
            data=unittest.mock.ANY,
            info=unittest.mock.ANY,
        )

    @patch("directord.utils.paramiko.RSAKey", autospec=True)
    @patch("directord.utils.paramiko.SSHClient", autospec=True)
    def test_paramikoconnect(self, mock_sshclient, mock_rsakey):
        with utils.ParamikoConnect(
            host="test", username="testuser", port=22, key_file="/test/key"
        ) as p:
            ssh, _ = p
            self.assertEqual(ssh, mock_sshclient())
            ssh.connect.assert_called_once_with(
                allow_agent=True,
                hostname="test",
                pkey=unittest.mock.ANY,
                port=22,
                username="testuser",
            )
            ssh.get_transport.assert_called_once_with()
        ssh.close.assert_called_once_with()
