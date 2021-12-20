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
from directord.datastores import memory  # noqa
from directord import models
from directord import server
from directord import tests


class TestServer(tests.TestDriverBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        with patch("directord.plugin_import", autospec=True):
            self.server = server.Server(args=self.args)
        self.server.workers = datastores.BaseDocument()
        self.server.return_jobs = datastores.BaseDocument()
        self.server.driver = self.mock_driver
        self.job_item = {
            "job_id": "XXX",
            "job_sha3_224": "YYY",
            "parent_id": "ZZZ",
            "verb": "TEST",
        }
        self.server.create_return_jobs(
            task="XXX", job_item=self.job_item, targets=["test-node"]
        )

    def test__set_job_status(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_processing,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x16",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_status_stdout(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_processing,
            job_id="XXX",
            identity="test-node",
            job_output="output",
            job_stdout="stdout",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x16",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {"test-node": "stdout"},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_status_stderr(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_processing,
            job_id="XXX",
            identity="test-node",
            job_output="output",
            job_stderr="stderr",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x16",
                "RETURN_TIMESTAMP": None,
                "STDERR": {"test-node": "stderr"},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_processing(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_processing,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x16"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x16",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_end(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_end,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x04"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x04",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_null(self):
        self.server._set_job_status(
            job_status=self.server.driver.nullbyte,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x00"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x04",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    def test__set_job_failed(self):
        self.server._set_job_status(
            job_status=self.server.driver.job_failed,
            job_id="XXX",
            identity="test-node",
            job_output="output",
        )
        self.assertDictEqual(
            self.server.return_jobs["XXX"].__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x15"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {"test-node": "output"},
                "PROCESSING": "\x04",
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
                "ROUNDTRIP_TIME": "0.00000000",
                "EXECUTION_TIME": "0.00000000",
            },
        )

    @patch("os.path.isfile", autospec=True)
    def test_run_backend(self, mock_isfile):
        self.mock_driver.backend_check.side_effect = [True, True, False]
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
            ),
            (
                b"test-node",
                b"XXX",
                self.server.driver.transfer_end,
                b"1",
                b"1",
                b"/fake/file",
                None,
                None,
            ),
        ]
        self.server.bind_backend = MagicMock()
        mock_isfile.return_value = True
        m = unittest.mock.mock_open(read_data=b"test data")
        with patch("builtins.open", m):
            self.server.run_backend()
        self.mock_driver.backend_send.assert_called()

    def test_create_return_jobs(self):
        status = self.server.create_return_jobs(
            task="XXX",
            job_item=self.job_item,
            targets=["test-node1", "test-node2"],
        )
        self.assertDictEqual(
            status.__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node": 0},
                "_lasttime": ANY,
                "_processing": {"test-node": "\x00"},
                "_roundtripltime": {"test-node": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "YYY",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "ZZZ",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {},
                "PROCESSING": None,
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
            },
        )

    def test_create_return_jobs_named(self):
        self.server.return_jobs = datastores.BaseDocument()
        job_item = self.job_item.copy()
        job_item["parent_name"] = "test parent name"
        job_item["job_name"] = "test job name"
        status = self.server.create_return_jobs(
            task="XXX",
            job_item=job_item,
            targets=["test-node1", "test-node2"],
        )
        self.assertDictEqual(
            status.__dict__,
            {
                "_createtime": ANY,
                "_executiontime": {"test-node1": 0, "test-node2": 0},
                "_lasttime": ANY,
                "_processing": {"test-node1": "\x00", "test-node2": "\x00"},
                "_roundtripltime": {"test-node1": 0, "test-node2": 0},
                "job_id": "XXX",
                "JOB_DEFINITION": ANY,
                "JOB_SHA3_224": "YYY",
                "JOB_NAME": "test job name",
                "PARENT_JOB_ID": "ZZZ",
                "PARENT_JOB_NAME": "test parent name",
                "VERB": "TEST",
                "COMPONENT_TIMESTAMP": None,
                "INFO": {},
                "PROCESSING": None,
                "RETURN_TIMESTAMP": None,
                "STDERR": {},
                "STDOUT": {},
            },
        )

    def test_create_return_jobs_exists(self):
        self.server.return_jobs = datastores.BaseDocument()
        self.server.return_jobs["XXX"] = {"exists": True}
        status = self.server.create_return_jobs(
            task="XXX",
            job_item=self.job_item,
            targets=[b"test-node1", b"test-node2"],
        )
        self.assertDictEqual(
            status,
            {"exists": True},
        )

    def test_run_job(self):
        q = tests.MockQueue()
        self.server.job_queue = q
        self.server.run_job()

    def test_run_job_restricted_null(self):
        q = tests.MockQueue()
        with patch.object(q, "get_nowait", autospec=True) as mock_queue:
            mock_queue.side_effect = [
                {
                    "verb": "RUN",
                    "restrict": "12345",
                    "job_sha3_224": "YYY",
                    "targets": ["test-node1", "test-node2"],
                    "job_id": "XXX",
                }
            ]
            self.server.job_queue = q
            self.server.run_job()

    def test_run_job_run_node_fail(self):
        q = tests.MockQueue()
        with patch.object(q, "get_nowait", autospec=True) as mock_queue:
            mock_queue.side_effect = [
                {
                    "verb": "RUN",
                    "job_sha3_224": "YYY",
                    "targets": ["test-node1", "test-node2"],
                    "job_id": "XXX",
                }
            ]
            self.server.job_queue = q
            self.server.run_job()

    def test_run_job_run(self):
        q = tests.MockQueue()
        with patch.object(q, "get_nowait", autospec=True) as mock_queue:
            mock_queue.side_effect = [
                {
                    "verb": "RUN",
                    "job_sha3_224": "YYY",
                    "targets": ["test-node1", "test-node2"],
                    "job_id": "XXX",
                }
            ]
            self.server.job_queue = q
            for i in ["test-node1", "test-node2"]:
                w = models.Worker(identity=i)
                w.version = "x.x.x"
                w.expire_time = 12345
                self.server.workers[w.identity] = w
            self.server.run_job()

    @patch("time.time", autospec=True)
    def test_run_interactions(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                "test-node",
                "XXX",
                None,
                None,
                None,
                "info",
                None,
                None,
            ),
            (
                "test-node",
                "YYY",
                self.mock_driver.heartbeat_notice,
                None,
                json.dumps({"job_id": "YYY"}),
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "job_check") as mock_job_check:
            mock_job_check.side_effect = [True, True, False]
            self.server.run_interactions()

    @patch("time.time", autospec=True)
    def test_run_interactions_idle(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                "test-node",
                "XXX",
                None,
                None,
                None,
                "info",
                None,
                None,
            ),
            (
                "test-node",
                "YYY",
                self.mock_driver.heartbeat_notice,
                None,
                json.dumps({"job_id": "YYY"}),
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 66, 1, 1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "job_check") as mock_job_check:
            mock_job_check.side_effect = [True, True, False]
            self.server.run_interactions()

    @patch("time.time", autospec=True)
    def test_run_interactions_ramp(self, mock_time):
        self.mock_driver.job_recv.side_effect = [
            (
                "test-node",
                "XXX",
                None,
                None,
                None,
                "info",
                None,
                None,
            ),
            (
                "test-node",
                "YYY",
                self.mock_driver.heartbeat_notice,
                None,
                json.dumps({"job_id": "YYY"}),
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 34, 1, 1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "job_check") as mock_job_check:
            mock_job_check.side_effect = [True, True, False]
            self.server.run_interactions()

    @patch("time.time", autospec=True)
    def test_run_interactions_run_backend(
        self,
        mock_time,
    ):
        self.mock_driver.job_recv.side_effect = [
            (
                "test-node",
                "XXX",
                self.server.driver.transfer_start,
                "transfer",
                None,
                "/test/file1",
                None,
                None,
            ),
            (
                "test-node",
                "YYY",
                self.mock_driver.heartbeat_notice,
                None,
                json.dumps({"job_id": "YYY"}),
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "job_check") as mock_job_check:
            mock_job_check.side_effect = [True, True, False]
            self.server.run_interactions()

    @patch("directord.server.Server._set_job_status", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_interactions_transfer_complete(
        self,
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
                "YYY",
                self.mock_driver.heartbeat_notice,
                None,
                json.dumps({"job_id": "YYY"}),
                None,
                None,
                None,
            ),
        ]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "job_check") as mock_job_check:
            mock_job_check.side_effect = [True, True, False]
            self.server.run_interactions()
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
        self.server.run_socket_server()
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
        for i in ["test-node1", "test-node2"]:
            w = models.Worker(identity=i)
            w.version = "x.x.x"
            w.expire_time = 12345
            self.server.workers[w.identity] = w
        with patch("time.time", autospec=True) as mock_time:
            mock_time.return_value = 0
            self.server.run_socket_server()
        mock_unlink.assert_called_with(self.args.socket_path)
        conn.sendall.assert_called_with(
            json.dumps(
                [
                    [
                        "test-node1",
                        {
                            "identity": "test-node1",
                            "active": True,
                            "expire_time": 12345,
                            "machine_id": None,
                            "version": "x.x.x",
                            "host_uptime": None,
                            "agent_uptime": None,
                            "driver": None,
                            "expiry": 12345,
                        },
                    ],
                    [
                        "test-node2",
                        {
                            "identity": "test-node2",
                            "active": True,
                            "expire_time": 12345,
                            "machine_id": None,
                            "version": "x.x.x",
                            "host_uptime": None,
                            "agent_uptime": None,
                            "driver": None,
                            "expiry": 12345,
                        },
                    ],
                ]
            ).encode()
        )
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
        self.server.workers = datastores.BaseDocument()
        for i in ["test-node1", "test-node2"]:
            w = models.Worker(identity=i)
            w.version = "x.x.x"
            w.expire_time = 0
            self.server.workers[w.identity] = w
        self.server.run_socket_server()
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
        self.server.run_socket_server()
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
        self.server.run_socket_server()
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.return_jobs, {"XXX": ANY})
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
        self.server.run_socket_server()
        mock_unlink.assert_called_with(self.args.socket_path)
        self.assertDictEqual(self.server.return_jobs, {"XXX": ANY})
        conn.sendall.assert_called_with(b"XXX")
        mock_chmod.assert_called()
        mock_chown.assert_called()

    @patch("directord.server.Server.run_threads", autospec=True)
    def test_worker_run(self, mock_run_threads):
        try:
            self.server.worker_run()
        finally:
            self.args = tests.FakeArgs()
        mock_run_threads.assert_called_with(
            ANY, threads=[ANY, ANY, ANY], stop_event=ANY
        )
