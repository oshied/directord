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

    @patch("time.time", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    def test_run_heartbeat_idle_workers(self, mock_log_warning, mock_time):
        self.mock_driver.bind_check.side_effect = [False, True]
        self.mock_driver.get_heartbeat.return_value = 1
        self.server.workers.update({b"test-node": 10000})
        mock_time.side_effect = [9000, 10000]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.server.run_heartbeat(sentinel=True)
        mock_log_warning.assert_called()
        self.mock_driver.socket_send.assert_called_with(
            socket=ANY,
            identity=b"test-node",
            control=b"\x05",
            command=b"reset",
            info=b"\x00\x00\x80?",
        )
        self.mock_driver.heartbeat_bind.assert_called()

    def test__set_job_status(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x06",
                "STDERR": {},
                "STDOUT": {},
                "TASK_SHA256": "YYY",
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    def test__set_job_status_stdout(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x06",
                "STDERR": {},
                "STDOUT": {"test-node": "stdout"},
                "TASK_SHA256": "YYY",
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    def test__set_job_status_stderr(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x06",
                "STDERR": {"test-node": "stderr"},
                "STDOUT": {},
                "TASK_SHA256": "YYY",
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    def test__set_job_processing(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x16",
                "STDERR": {},
                "STDOUT": {},
                "TASK_SHA256": "YYY",
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
                "_starttime": ANY,
            },
        )

    def test__set_job_end(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "EXECUTION_TIME": 0,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x04",
                "STDERR": {},
                "STDOUT": {},
                "SUCCESS": ["test-node"],
                "TASK_SHA256": "YYY",
                "TOTAL_ROUNDTRIP_TIME": ANY,
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    def test__set_job_null(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "EXECUTION_TIME": 0,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x00",
                "STDERR": {},
                "STDOUT": {},
                "SUCCESS": ["test-node"],
                "TASK_SHA256": "YYY",
                "TOTAL_ROUNDTRIP_TIME": ANY,
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    def test__set_job_failed(self):
        self.server.return_jobs = {
            "XXX": {
                "ACCEPTED": True,
                "INFO": dict(),
                "STDOUT": dict(),
                "STDERR": dict(),
                "NODES": ["test-node"],
                "VERB": "RUN",
                "TRANSFERS": list(),
                "TASK_SHA256": "YYY",
                "JOB_DEFINITION": {},
                "PARENT_JOB_ID": "ZZZ",
                "_createtime": 1,
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
                "EXECUTION_TIME": 0,
                "INFO": {"test-node": "output"},
                "JOB_DEFINITION": {},
                "NODES": ["test-node"],
                "PARENT_JOB_ID": "ZZZ",
                "PROCESSING": "\x15",
                "STDERR": {},
                "STDOUT": {},
                "FAILED": ["test-node"],
                "TASK_SHA256": "YYY",
                "TOTAL_ROUNDTRIP_TIME": ANY,
                "TRANSFERS": [],
                "VERB": "RUN",
                "_createtime": 1,
            },
        )

    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_transfer(self, mock_log_info, mock_isfile):
        self.server.bind_transfer = MagicMock()
        mock_isfile.return_value = True
        m = unittest.mock.mock_open(read_data="test data")
        with patch("builtins.open", m):
            self.server._run_transfer(
                identity="test-node", verb=b"ADD", file_path="/test/file1"
            )
        self.mock_driver.socket_send.assert_called()
        mock_log_info.assert_called()

    def test_create_return_jobs(self):
        self.server.return_jobs = datastores.BaseDocument()
        status = self.server.create_return_jobs(
            task="XXX",
            job_item={
                "verb": "TEST",
                "task_sha256sum": "YYY",
                "parent_id": "ZZZ",
            },
            targets=[b"test-node1", b"test-node2"],
        )
        self.assertDictEqual(
            status,
            {
                "ACCEPTED": True,
                "INFO": {},
                "JOB_DEFINITION": {
                    "parent_id": "ZZZ",
                    "task_sha256sum": "YYY",
                    "verb": "TEST",
                },
                "NODES": ["test-node1", "test-node2"],
                "PARENT_JOB_ID": "ZZZ",
                "STDERR": {},
                "STDOUT": {},
                "TASK_SHA256": "YYY",
                "TRANSFERS": [],
                "VERB": "TEST",
                "_createtime": ANY,
            },
        )

    def test_create_return_jobs_exists(self):
        self.server.return_jobs = datastores.BaseDocument()
        self.server.return_jobs["XXX"] = {"exists": True}
        status = self.server.create_return_jobs(
            task="XXX",
            job_item={
                "verb": "TEST",
                "task_sha256sum": "YYY",
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
        return_int, _ = self.server.run_job()
        self.assertEqual(return_int, 512)
        mock_log_debug.assert_called()

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_job_restricted_null(self, mock_log_debug, mock_queue):
        mock_queue.get.side_effect = [
            {
                "verb": "RUN",
                "restrict": "12345",
                "task_sha256sum": "YYY",
                "targets": ["test-node1", "test-node2"],
                "task": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        return_int, _ = self.server.run_job()
        self.assertEqual(return_int, 512)
        mock_log_debug.assert_called()

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.critical", autospec=True)
    def test_run_job_run_node_fail(self, mock_log_critical, mock_queue):
        mock_queue.get.side_effect = [
            {
                "verb": "RUN",
                "task_sha256sum": "YYY",
                "targets": ["test-node1", "test-node2"],
                "task": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        return_int, _ = self.server.run_job()
        self.assertEqual(return_int, 512)
        mock_log_critical.assert_called()

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_job_run(self, mock_log_debug, mock_queue):
        self.server.bind_job = MagicMock()
        mock_queue.get.side_effect = [
            {
                "verb": "RUN",
                "task_sha256sum": "YYY",
                "targets": ["test-node1", "test-node2"],
                "task": "XXX",
            }
        ]
        self.server.job_queue = mock_queue
        self.server.workers = {b"test-node1": 12345, b"test-node2": 12345}
        return_int, _ = self.server.run_job()
        self.assertEqual(return_int, 128)
        mock_log_debug.assert_called()
        self.mock_driver.socket_send.assert_called()

    @patch("time.time", autospec=True)
    def test_run_interactions(self, mock_time):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                None,
                None,
                None,
            )
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)

    @patch("time.time", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test_run_interactions_idle(self, mock_log_info, mock_time):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                None,
                None,
                None,
            )
        ]
        mock_time.side_effect = [1, 66, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_log_info.assert_called_with(
            ANY, "Directord server entering idle state."
        )

    @patch("time.time", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test_run_interactions_ramp(self, mock_log_info, mock_time):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                None,
                None,
                None,
                None,
                None,
                None,
            )
        ]
        mock_time.side_effect = [1, 34, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_log_info.assert_called_with(ANY, "Directord server ramping down.")

    @patch("directord.server.Server._run_transfer", autospec=True)
    @patch("time.time", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_interactions_run_transfer(
        self,
        mock_log_debug,
        mock_time,
        mock_run_transfer,
    ):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.transfer_start,
                b"transfer",
                None,
                b"/test/file1",
                None,
                None,
            )
        ]
        self.mock_driver.transfer_bind.return_value = MagicMock()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_log_debug.assert_called()
        mock_run_transfer.assert_called_with(
            ANY, identity=b"test-node", verb=b"ADD", file_path="/test/file1"
        )

    @patch("directord.server.Server._set_job_status", autospec=True)
    @patch("time.time", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_interactions_transfer_complete(
        self,
        mock_log_debug,
        mock_time,
        mock_set_job_status,
    ):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.transfer_end,
                None,
                None,
                b"/test/file1",
                None,
                None,
            )
        ]
        self.mock_driver.transfer_bind.return_value = MagicMock()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_log_debug.assert_called()
        mock_set_job_status.assert_called_with(
            ANY,
            job_status=b"\x03",
            job_id="XXX",
            identity="test-node",
            job_output="/test/file1",
        )

    @patch("directord.server.Server._set_job_status", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_interactions_set_status(
        self,
        mock_time,
        mock_set_job_status,
    ):
        self.mock_driver.bind_check.side_effect = [False, True]
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.job_end,
                b"RUN",
                b"{}",
                b"info",
                None,
                None,
            )
        ]
        self.mock_driver.job_bind.return_value = MagicMock()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_set_job_status.assert_called_with(
            ANY,
            job_status=b"\x04",
            job_id="XXX",
            identity="test-node",
            job_output="info",
            job_stdout=None,
            job_stderr=None,
        )

    @patch("directord.server.Server._set_job_status", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_interactions_run_query(
        self,
        mock_time,
        mock_set_job_status,
    ):
        self.mock_driver.bind_check.side_effect = [False, True]
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                b"XXX",
                self.server.driver.job_end,
                b"QUERY",
                json.dumps(
                    {
                        "verb": "RUN",
                        "restrict": "12345",
                        "task_sha256sum": "YYY",
                        "targets": ["test-node1", "test-node2"],
                        "task": "XXX",
                        "query": "key",
                    }
                ).encode(),
                b'{"key": "value"}',
                None,
                None,
            )
        ]
        self.mock_driver.job_bind.return_value = MagicMock()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.server.run_interactions(sentinel=True)
        mock_set_job_status.assert_called_with(
            ANY,
            job_status=b"\x04",
            job_id="XXX",
            identity="test-node",
            job_output='{"key": "value"}',
            job_stdout=None,
            job_stderr=None,
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
        conn.recv.return_value = json.dumps({"manage": "list-nodes"}).encode()
        conn.sendall = MagicMock()
        socket.accept.return_value = [conn, MagicMock()]
        self.server.workers = {
            b"test-node1": {"time": 12345, "version": "x.x.x"},
            b"test-node2": {"time": 12345, "version": "x.x.x"},
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
        conn.recv.return_value = json.dumps({"manage": "list-jobs"}).encode()
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
        conn.recv.return_value = json.dumps({"manage": "purge-nodes"}).encode()
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
        conn.recv.return_value = json.dumps({"manage": "purge-jobs"}).encode()
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
                "task_sha256sum": "YYY",
                "targets": ["test-node1", "test-node2"],
                "task": "XXX",
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
                "task_sha256sum": "YYY",
                "targets": ["test-node1", "test-node2"],
                "task": "XXX",
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
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY, ANY])

    @patch("directord.server.Server.run_threads", autospec=True)
    def test_worker_run_ui(self, mock_run_threads):
        try:
            setattr(self.args, "run_ui", True)
            self.server.worker_run()
        finally:
            self.args = tests.FakeArgs()
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY, ANY, ANY])

    @patch("time.time", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat_ready(self, mock_log_debug, mock_time):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_ready,
                None,
                None,
                b"x.x.x",
                None,
                None,
            )
        ]
        mock_time.side_effect = [1, 1000, 3000]
        self.server.run_heartbeat(sentinel=True)
        mock_log_debug.assert_called()
        self.assertIn(b"test-node", self.server.workers)

    @patch("time.time", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat_notice(self, mock_log_debug, mock_time):
        self.mock_driver.socket_recv.side_effect = [
            (
                b"test-node",
                None,
                self.mock_driver.heartbeat_notice,
                None,
                None,
                b"x.x.x",
                None,
                None,
            )
        ]
        mock_time.side_effect = [1, 1000, 3000]
        self.server.run_heartbeat(sentinel=True)
        mock_log_debug.assert_called()
        self.assertIn(b"test-node", self.server.workers)
