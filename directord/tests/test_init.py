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

import time
import unittest

from unittest.mock import ANY
from unittest.mock import patch

import directord

from directord import datastores
from directord import logger
from directord import tests


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.log = logger.LogSetup()

        self.uid_patched = unittest.mock.patch("directord.os.getuid")
        self.uid = self.uid_patched.start()

        self.env_patched = unittest.mock.patch("directord.os.path.expanduser")
        self.env = self.env_patched.start()

        self.idr_patched = unittest.mock.patch("directord.os.path.isdir")
        self.idr = self.idr_patched.start()

        self.stat_patched = unittest.mock.patch("directord.os.stat")
        self.stat = self.stat_patched.start()

    def tearDown(self):
        self.uid_patched.stop()
        self.env_patched.stop()
        self.idr_patched.stop()

    def test_logger_max_backup(self):
        self.assertEqual(self.log.max_backup, 5)

    def test_logger_max_size(self):
        self.assertEqual(self.log.max_size, 524288000)

    def test_logger_debug_logging(self):
        self.assertEqual(self.log.debug_logging, False)

    def test_logger_override_backup(self):
        log = logger.LogSetup(max_backup=10)
        self.assertEqual(log.max_backup, 10)

    def test_logger_override_max_backup(self):
        log = logger.LogSetup(max_backup=10)
        self.assertEqual(log.max_backup, 10)

    def test_logger_override_max_size(self):
        log = logger.LogSetup(max_size=10)
        self.assertEqual(log.max_size, 10485760)

    def test_logger_debug_logging_enabled(self):
        log = logger.LogSetup(debug_logging=True)
        self.assertEqual(log.debug_logging, True)

    def test_logger_return_logfile_not_root_new_log_dir(self):
        self.uid.return_value = 99
        self.env.return_value = "/home/TestUser"
        self.idr.return_value = False
        self.stat.return_value = tests.FakeStat(uid=99, gid=99)
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/home/TestUser/test_file")

    def test_logger_return_logfile_root_new_log_dir(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = True
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/other/test_file")

    def test_logger_return_logfile_not_root(self):
        self.uid.return_value = 99
        self.env.return_value = "/home/TestUser"
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(filename="test_file")
        self.assertEqual(logfile, "/home/TestUser/test_file")

    def test_logger_return_logfile_root(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = True
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(filename="test_file")
        self.assertEqual(logfile, "/var/log/test_file")

    def test_logger_return_logfile_root_log_dir_not_found(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = False
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/root/test_file")


class TestProcessor(unittest.TestCase):
    def setUp(self):
        self.log_patched = unittest.mock.patch("directord.logger.getLogger")
        self.log = self.log_patched.start()
        self.processor = directord.Processor()

    def tearDown(self):
        self.log_patched.stop()

    def test_wq_prune_0(self):
        workers = datastores.BaseDocument()
        workers["test"] = 1
        workers.empty()
        self.assertDictEqual(workers, dict())
        self.log.debug.called_once()

    def test_wq_prune_valid(self):
        workers = datastores.BaseDocument()
        workers["valid1"] = {"time": time.time() + 2}
        workers["invalid1"] = {"time": time.time() - 2}
        workers["invalid2"] = {"time": time.time() - 3}
        workers.prune()
        self.assertEqual(len(workers), 1)
        self.assertIn("valid1", workers)
        self.log.debug.called_once()

    def test_wq_empty(self):
        workers = datastores.BaseDocument()
        workers["valid1"] = {"time": time.time() + 2}
        workers["invalid1"] = {"time": time.time() - 2}
        workers["invalid2"] = {"time": time.time() - 3}
        self.assertEqual(len(workers), 3)
        workers.empty()
        self.assertEqual(len(workers), 0)

    def test_read_in_chunks(self):
        chunks = list()
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data="data")
        ) as mock_file:
            with open(mock_file) as f:
                for d in self.processor.read_in_chunks(file_object=f):
                    chunks.append(d)
                    self.log.debug.called_once()
        self.assertListEqual(chunks, ["data"])

    def test_read_in_chunks_set_chunk(self):
        chunks = list()
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data="data")
        ) as mock_file:
            with open(mock_file) as f:
                for d in self.processor.read_in_chunks(
                    file_object=f, chunk_size=1
                ):
                    chunks.append(d)
                    self.log.debug.called_once()
        self.assertListEqual(chunks, ["d", "a", "t", "a"])

    def test_run_threads(self):
        pass


class TestUnixSocket(unittest.TestCase):
    def setUp(self):
        self.socket_patched = unittest.mock.patch("directord.socket.socket")
        self.socket = self.socket_patched.start()

    def tearDown(self):
        self.socket_patched.stop()

    def test_unix_socket(self):
        with directord.UNIXSocketConnect(sock_path="/test.sock") as c:
            c.connect.assert_called_once_with("/test.sock")
        c.close.assert_called_once()
        self.socket.assert_called_once_with(
            directord.socket.AF_UNIX, directord.socket.SOCK_STREAM
        )


class TestDirectordConnect(unittest.TestCase):
    def setUp(self):
        self.dc = directord.DirectordConnect()

    def tearDown(self):
        pass

    def test_from_json(self):
        return_data = self.dc._from_json(b'{"test": "value"}')
        self.assertDictEqual(return_data, {"test": "value"})

    @patch("directord.mixin.Mixin.exec_orchestrations", autospec=True)
    def test_orchestrate(self, mock_exec_orchestrations):
        mock_exec_orchestrations.return_value = [b"XXX", b"YYY"]
        ids = self.dc.orchestrate(orchestrations=[{"test": "jobs"}])
        self.assertEqual(ids, ["XXX", "YYY"])
        mock_exec_orchestrations.assert_called_with(
            ANY, [{"test": "jobs"}], defined_targets=None, return_raw=True
        )

    @patch("directord.mixin.Mixin.exec_orchestrations", autospec=True)
    def test_orchestrate_defined_targets(self, mock_exec_orchestrations):
        mock_exec_orchestrations.return_value = [b"XXX", b"YYY"]
        ids = self.dc.orchestrate(
            orchestrations=[{"test": "jobs"}], defined_targets=["test-node1"]
        )
        self.assertEqual(ids, ["XXX", "YYY"])
        mock_exec_orchestrations.assert_called_with(
            ANY,
            [{"test": "jobs"}],
            defined_targets=["test-node1"],
            return_raw=True,
        )

    @patch("directord.user.Manage.poll_job", autospec=True)
    def test_poll_job(self, mock_poll_job):
        mock_poll_job.return_value = (True, "info")
        status_boolean, info = self.dc.poll(job_id="XXX")
        self.assertEqual(status_boolean, True)
        mock_poll_job.assert_called_with(ANY, job_id="XXX")

    @patch("directord.user.Manage.run", autospec=True)
    def test_purge_nodes(self, mock_run):
        mock_run.return_value = b'{"success": true}'
        self.assertTrue(self.dc.purge_nodes())

    @patch("directord.user.Manage.run", autospec=True)
    def test_purge_jobs(self, mock_run):
        mock_run.return_value = b'{"success": true}'
        self.assertTrue(self.dc.purge_jobs())
