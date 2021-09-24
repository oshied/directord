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
import unittest

from unittest.mock import ANY
from unittest.mock import MagicMock
from unittest.mock import patch

from directord import datastores
from directord import server
from directord import tests


class TestServer(tests.TestDriverBase):
    def setUp(self):
        super(TestServer, self).setUp()
        self.args = tests.FakeArgs()
        self.server = server.Server(args=self.args)
        self.server.workers = datastores.BaseDocument()
        self.server.return_jobs = datastores.BaseDocument()
        self.server.driver = self.mock_driver

    def test__set_job_status(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x06"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_ack,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {},
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x06"},
            },
        )

    def test__set_job_status_stdout(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": dict(),
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_ack,
            job_id="XXX",
            identity="test-node",
            job_output="output",
            job_stdout="stdout",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {"test-node": "stdout"},
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x06"},
            },
        )

    def test__set_job_status_stderr(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x04"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_ack,
            job_id="XXX",
            identity="test-node",
            job_output="output",
            job_stderr="stderr",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {"test-node": "stderr"},
                "STDOUT": {},
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x06"},
            },
        )

    def test__set_job_processing(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_processing,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x16",
                "STDERR": {},
                "STDOUT": {},
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
            },
        )

    def test__set_job_end(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x04"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_end,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {},
                "SUCCESS": ["test-node"],
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x04"},
            },
        )

    def test__set_job_null(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x00"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.nullbyte,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {},
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x00"},
            },
        )

    def test__set_job_failed(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "_nodes": ["test-node"],
                "VERB": "RUN",
                "JOB_SHA3_224": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x15"},
            }
        }
        self.server._set_job_status(
            job_status=self.server.driver.job_failed,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )

        self.assertDictEqual(
            self.server.return_jobs["XXX"],
            {
                "ACCEPTED": True,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "_nodes": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {},
                "FAILED": ["test-node"],
                "JOB_SHA3_224": "YYY",
                "VERB": "RUN",
                "_createtime": 1,
                "_lasttime": ANY,
                "_processing": {"test-node": "\x15"},
            },
        )

    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test_run_backend(self, mock_log_info, mock_isfile):
        self.mock_driver.backend_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.transfer_start,
                b"1",
                b"1",
                b"/fake/file",
                None,
                None,
            )
        ]
        self.server.bind_backend = MagicMock()
        mock_isfile.return_value = True
        m = unittest.mock.mock_open(read_data=b"test data")
        with patch("builtins.open", m):
            self.server.run_backend(sentinel=True)
        self.mock_driver.backend_send.assert_called()
        mock_log_info.assert_called()

    def test_create_return_jobs(self):
        self.server.return_jobs = datastores.BaseDocument()
        status = self.server.create_return_jobs(
            task="XXX",
            job_item={
                "verb": "TEST",
                "job_sha3_224": "YYY",
                "parent_id": "ZZZ",
            },
            targets=["test-node1", "test-node2"],
        )
        self.assertDictEqual(
            status,
            {
                "ACCEPTED": True,
                "INFO": {},
                "JOB_DEFINITION": {
                    "parent_id": "ZZZ",
                    "job_sha3_224": "YYY",
                    "verb": "TEST",
                },
                "_nodes": ["test-node1", "test-node2"],
                "PARENT_JOB_ID": "ZZZ",
                "STDERR": {},
                "STDOUT": {},
                "JOB_SHA3_224": "YYY",
                "VERB": "TEST",
                "_createtime": ANY,
                "_processing": ANY,
                "_executiontime": ANY,
                "_roundtripltime": ANY,
            },
        )

    def test_create_return_jobs_exists(self):
        self.server.return_jobs = datastores.BaseDocument()
        self.server.return_jobs["XXX"] = {"exists": True}
        status = self.server.create_return_jobs(
            task="XXX",
            job_item={
                "verb": "TEST",
                "job_sha3_224": "YYY",
                "parent_id": "ZZZ",
            },
            targets=[b"test-node1", b"test-node2"],
        )
        self.assertDictEqual(
            status,
            {"exists": True},
        )

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_job(self, mock_log_debug, mock_queue):
        mock_queue.return_value = MagicMock()
        self.server.job_queue = mock_queue
        self.server.run_job(sentinel=True)

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_job_restricted_null(self, mock_log_debug, mock_queue):
        mock_queue.get_nowait.side_effect = [
            {
                "verb": "RUN",
                "restrict": "12345",
                "job_sha3_224": "YYY",
                "targets": ["test-node1", "test-node2"],
                "job_id": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        self.server.run_job(sentinel=True)

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.critical", autospec=True)
    def test_run_job_run_node_fail(self, mock_log_critical, mock_queue):
        mock_queue.get_nowait.side_effect = [
            {
                "verb": "RUN",
                "job_sha3_224": "YYY",
                "targets": ["test-node1", "test-node2"],
                "job_id": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        self.server.run_job(sentinel=True)

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_job_run(self, mock_log_debug, mock_queue):
        mock_queue.get_nowait.side_effect = [
            {
                "verb": "RUN",
                "job_sha3_224": "YYY",
                "targets": ["test-node1", "test-node2"],
                "job_id": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        self.server.workers = {b"test-node1": 12345, b"test-node2": 12345}
        self.server.run_job(sentinel=True)

    @patch("time.time", autospec=True)
    def test_run_interactions(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                b"info",
                None,
                None,
            ),
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                b"{}",
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)

    @patch("time.time", autospec=True)
    def test_run_interactions_idle(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                b"info",
                None,
                None,
            ),
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                b"{}",
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 66, 1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)

    @patch("time.time", autospec=True)
    def test_run_interactions_ramp(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                b"info",
                None,
                None,
            ),
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                b"{}",
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 34, 1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)

    @patch("time.time", autospec=True)
    def test_run_interactions_run_backend(
        self,
        mock_time,
    ):
        self.mock_driver.job_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.transfer_start,
                b"transfer",
                None,
                b"/test/file1",
                None,
                None,
            ),
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                b"{}",
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)

    @patch("directord.server.Server._set_job_status", autospec=True)
    @patch("time.time", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_interactions_transfer_complete(
        self,
        mock_log_debug,
        mock_time,
        mock_set_job_status,
    ):
        self.mock_driver.job_recv.side_effect = [
            (
                "test-node",
                "XXX",
                self.server.driver.transfer_end,
                None,
                None,
                "/test/file1",
                None,
                None,
            ),
            (
                "test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                "{}",
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_log_debug.assert_called()
        mock_set_job_status.assert_called_with(
            ANY,
            job_status=self.server.driver.transfer_end,
            job_id="XXX",
            identity="test-node",
            job_output="/test/file1",
            job_stdout=None,
            job_stderr=None,
            execution_time=0,
            return_timestamp=0,
            component_exec_timestamp=0,
            recv_time=1,
        )

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps({}).encode()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("time.time", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_manage_list_nodes(
        self, mock_socket, mock_unlink, mock_time, mock_chmod, mock_chown
    ):
        mock_time.return_value = 1
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {"manage": {"list_nodes": None}}
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.workers = {
            "test-node1": {"time": 12345, "version": "x.x.x"},
            "test-node2": {"time": 12345, "version": "x.x.x"},
        }
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        conn.sendall.assert_called_with(
            json.dumps(
                [
                    ["test-node1", {"version": "x.x.x", "expiry": 12344}],
                    ["test-node2", {"version": "x.x.x", "expiry": 12344}],
                ]
            ).encode()
        )
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_manage_list_jobs(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {"manage": {"list_jobs": None}}
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.return_jobs = {"k": {"v": "test"}}
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        conn.sendall.assert_called_with(b'[["k", {"v": "test"}]]')
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_manage_purge_nodes(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {"manage": {"purge_nodes": None}}
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        workers = self.server.workers = datastores.BaseDocument()
        workers[b"test-node1"] = {"version": "x.x.x", "expiry": 12344}
        workers[b"test-node2"] = {"version": "x.x.x", "expiry": 12344}
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.workers, {})
        conn.sendall.assert_called_with(b'{"success": true}')
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_manage_purge_jobs(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {"manage": {"purge_jobs": None}}
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        return_jobs = self.server.return_jobs = datastores.BaseDocument()
        return_jobs["k"] = {"v": "test"}
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.return_jobs, {})
        conn.sendall.assert_called_with(b'{"success": true}')
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_run(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {
                "verb": "RUN",
                "restrict": "12345",
                "job_sha3_224": "YYY",
                "targets": ["test-node1", "test-node2"],
                "job_id": "XXX",
                "query": "key",
            }
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.return_jobs, {})
        conn.sendall.assert_called_with(b"Job received. Task ID: XXX")
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("os.unlink", autospec=True)
    @patch("socket.socket", autospec=True)
    def test_run_socket_server_run_raw(
        self, mock_socket, mock_unlink, mock_chmod, mock_chown
    ):
        socket = mock_socket.return_value = MagicMock()
        conn = MagicMock()
        conn.recv.return_value = json.dumps(
            {
                "verb": "RUN",
                "restrict": "12345",
                "job_sha3_224": "YYY",
                "targets": ["test-node1", "test-node2"],
                "job_id": "XXX",
                "return_raw": True,
            }
        ).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.run_socket_server(sentinel=True)
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.return_jobs, {})
        conn.sendall.assert_called_with(b"XXX")
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("directord.server.Server.run_threads", autospec=True)
    def test_worker_run(self, mock_run_threads):
        try:
            setattr(self.args, "run_ui", False)
            self.server.worker_run()
        finally:
            self.args = tests.FakeArgs()
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY, ANY, ANY])

    @patch("directord.server.Server.run_threads", autospec=True)
    def test_worker_run_ui(self, mock_run_threads):
        try:
            setattr(self.args, "run_ui", True)
            self.server.worker_run()
        finally:
            self.args = tests.FakeArgs()
        mock_run_threads.assert_called_with(
            ANY, threads=[ANY, ANY, ANY, ANY, ANY]
        )
