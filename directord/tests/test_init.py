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

import queue
import time
import unittest

from unittest import mock
from unittest.mock import ANY
from unittest.mock import patch

import directord

from directord import logger
from directord import tests


COMPONENT_FAILURE_INFO = """Failure - Unknown Component
ERROR:No module named 'directord.components.builtin_notacomponent'
[Errno 2] No such file or directory: '/test/path/share/directord/components/notacomponent.py'
[Errno 2] No such file or directory: '/etc/directord/components/notacomponent.py'
COMMAND:notacomponent
ID:None
PATH:['/test/path/share/directord/components', '/etc/directord/components']"""  # noqa
COMPONENT_VENV_FAILURE_INFO = """Failure - Unknown Component
ERROR:No module named 'directord.components.builtin_notacomponent'
[Errno 2] No such file or directory: '/test/venv-path/share/directord/components/notacomponent.py'
[Errno 2] No such file or directory: '/test/path/share/directord/components/notacomponent.py'
[Errno 2] No such file or directory: '/etc/directord/components/notacomponent.py'
COMMAND:notacomponent
ID:None
PATH:['/test/venv-path/share/directord/components', '/test/path/share/directord/components', '/etc/directord/components']"""  # noqa


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

    def test_get_lock(self):
        with patch("multiprocessing.Lock") as mock_lock:
            self.processor.get_lock()
            mock_lock.assert_called()

    def test_get_queue(self):
        with patch("multiprocessing.Queue") as mock_queue:
            self.processor.get_queue()
            mock_queue.assert_called()

    def test_run_threads(self):
        thread1 = tests.FakeThread()
        thread2 = tests.FakeThread()
        self.processor.run_threads(threads=[(thread1, False), (thread2, True)])
        self.assertFalse(thread1.daemon)
        self.assertTrue(thread2.daemon)

    def test_timeout_error_reraise(self):
        with self.assertRaises(TimeoutError):
            with self.processor.timeout(1, "test-job_id", reraise=True):
                time.sleep(5)

    def test_timeout_error(self):
        with self.processor.timeout(1, "test-job_id"):
            time.sleep(5)

    def test_timeout(self):
        with self.processor.timeout(5, "test-job_id"):
            time.sleep(1)

    def test_raise_timeout(self):
        with self.assertRaises(TimeoutError):
            self.processor.raise_timeout()


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

    @patch("logging.Logger.error", autospec=True)
    def test_unix_socket_error(self, mock_log_error):
        with patch.object(directord, "UNIXSocketConnect") as conn:
            conn.side_effect = PermissionError()
            with self.assertRaises(PermissionError):
                directord.send_data("/test.sock", "test")
        mock_log_error.assert_called()


class TestDirectordConnect(unittest.TestCase):
    def setUp(self):
        self.dc = directord.DirectordConnect()

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
        mock_poll_job.return_value = (True, "info", None, None, None)
        status_boolean, _ = self.dc.poll(job_id="XXX")
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

    @patch("directord.user.Manage.run", autospec=True)
    def test_list_jobs(self, mock_run):
        mock_run.return_value = b"{}"
        self.dc.list_jobs()


class TestDirectordInit(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_plugin_import(self):
        with patch("importlib.import_module", autospec=True) as mock_module:
            directord.plugin_import("notaplugin")
        mock_module.assert_called_once_with("notaplugin", package="directord")

    def test_plugin_import_error(self):
        with self.assertRaises(ModuleNotFoundError):
            directord.plugin_import("notaplugin")

    def test_component_import(self):
        with patch.object(
            directord, "plugin_import", autospec=True
        ) as mock_plugin_import:
            directord.component_import("notaplugin")
        mock_plugin_import.assert_called_once_with(
            plugin=".components.builtin_notaplugin"
        )

    def test_component_import_error(self):
        self.maxDiff = 1000
        with patch.object(
            directord, "plugin_import", autospec=True
        ) as mock_plugin_import:
            mock_plugin_import.side_effect = ImportError(
                "No module named 'directord.components.builtin_notacomponent'"
            )
            with patch("sys.base_prefix", "/test/path"):
                with patch("sys.prefix", "/test/path"):
                    status, transfer, info = directord.component_import(
                        "notacomponent"
                    )
        self.assertEqual(status, False)
        self.assertEqual(
            transfer, "/etc/directord/components/notacomponent.py"
        )
        self.assertEqual(info, COMPONENT_FAILURE_INFO)

    def test_component_import_venv_error(self):
        with patch.object(
            directord, "plugin_import", autospec=True
        ) as mock_plugin_import:
            mock_plugin_import.side_effect = ImportError(
                "No module named 'directord.components.builtin_notacomponent'"
            )
            with patch("sys.base_prefix", "/test/path"):
                with patch("sys.prefix", "/test/venv-path"):
                    status, transfer, info = directord.component_import(
                        "notacomponent"
                    )
        self.assertEqual(status, False)
        self.assertEqual(
            transfer, "/etc/directord/components/notacomponent.py"
        )
        self.assertEqual(info, COMPONENT_VENV_FAILURE_INFO)

    def test_component_import_search(self):
        with patch.object(
            directord, "plugin_import", autospec=True
        ) as mock_plugin_import:
            mock_plugin_import.side_effect = ImportError(
                "No module named 'directord.components.builtin_notacomponent'"
            )
            with patch("sys.base_prefix", "/test/path"):
                with patch("sys.prefix", "/test/path"):
                    with patch(
                        "importlib.util.spec_from_file_location", autospec=True
                    ) as mock_spec_from_file:
                        with patch(
                            "importlib.util.module_from_spec", autospec=True
                        ):
                            directord.component_import("notacomponent")
                    mock_spec_from_file.assert_called_once_with(
                        "directord_user_component_notacomponent",
                        "/test/path/share/directord/components/notacomponent.py",  # noqa
                    )


class TestIndicator(unittest.TestCase):
    def setUp(self):
        self.multi_patched = mock.patch("directord.multiprocessing.Process")
        self.multi = self.multi_patched.start()

    def tearDown(self):
        self.multi_patched.stop()

    def test_spinner_class(self):
        spinner = directord.Spinner()
        self.assertEqual(spinner.run, False)

    def test_spinner_context(self):
        with directord.Spinner(run=True) as indicator:
            self.assertTrue(indicator.run)

    def test_spinner_context_msg(self):
        with directord.Spinner(run=True) as indicator:
            msg = indicator.indicator_msg(msg="test")
            self.assertTrue(indicator.run)
            self.assertIsNone(msg)
