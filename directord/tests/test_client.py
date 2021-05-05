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

from directord import client
from directord import tests


class TestClient(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.client = client.Client(args=self.args)

    def tearDown(self):
        pass

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_job_connect(self, mock_log_debug, mock_socket_connect):
        self.client.job_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_transfer_connect(self, mock_log_debug, mock_socket_connect):
        self.client.transfer_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_heartbeat_connect(self, mock_log_debug, mock_socket_connect):
        self.client.heartbeat_connect()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("zmq.Poller.unregister", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_reset_heartbeat(
        self, mock_log_debug, mock_socket_connect, mock_poller
    ):
        self.client.bind_heatbeat = self.client.heartbeat_connect()
        self.client.reset_heartbeat()
        mock_poller.assert_called()
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat(self, mock_log_debug, mock_socket_connect):
        self.client.run_heartbeat(sentinel=True)
        mock_socket_connect.assert_called()
        mock_log_debug.assert_called()

        # TODO(cloudnull): More testing needs to be built out

    @patch("directord.utils.run_command", autospec=True)
    def test__run_command(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        mock_conn = MagicMock()
        self.client._run_command(
            command="command {{ test }} test",
            cache=tests.FakeCache(),
            conn=mock_conn,
        )
        mock_run_command.assert_called_with(command="command 1 test", env=None)
        self.assertEqual(mock_conn.info, b"command 1 test")

    @patch("directord.utils.run_command", autospec=True)
    def test__run_command_stdout_args(self, mock_run_command):
        mock_run_command.return_value = [b"testing", b"", True]
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        self.client._run_command(
            command="command {{ test }} test",
            cache=fake_cache,
            conn=mock_conn,
            stdout_arg="VALUE1",
        )
        mock_run_command.assert_called_with(command="command 1 test", env=None)
        self.assertEqual(mock_conn.info, b"command 1 test")
        self.assertDictEqual(
            fake_cache.get("args"), {"test": 1, "VALUE1": "testing"}
        )

    @patch("os.makedirs", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_workdir(self, mock_log_info, mock_makedirs):
        fake_cache = tests.FakeCache()
        self.client._run_workdir("/test/path", cache=fake_cache)
        mock_log_info.assert_called()
        mock_makedirs.assert_called_with("/test/path", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_workdir_jinja(self, mock_log_info, mock_makedirs):
        fake_cache = tests.FakeCache()
        self.client._run_workdir("/test/{{ test }}", cache=fake_cache)
        mock_log_info.assert_called()
        mock_makedirs.assert_called_with("/test/1", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_workdir_null(self, mock_log_info, mock_makedirs):
        fake_cache = tests.FakeCache()
        self.client._run_workdir("", cache=fake_cache)
        mock_log_info.assert_not_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_transfer_exists(
        self, mock_log_info, mock_isfile, mock_file_sha1, mock_socket_connect
    ):
        mock_isfile.return_value = True
        mock_file_sha1.return_value = "YYYYYYYYY"
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
            )
        self.assertEqual(
            stdout,
            (
                "File exists /test/file and SHA1"
                " YYYYYYYYY matches, nothing to transfer"
            ),
        )
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__run_transfer_exists_blueprinted(
        self, mock_log_info, mock_isfile, mock_file_sha1, mock_socket_connect
    ):
        mock_isfile.return_value = True
        mock_file_sha1.return_value = "YYYYYYYYY"
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
                blueprint=True,
            )
        self.assertEqual(stdout, "YYYYYYYYY")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, None)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_exists(
        self, mock_log_debug, mock_isfile, mock_file_sha1, mock_socket_connect
    ):
        mock_isfile.return_value = False
        mock_file_sha1.return_value = "YYYYYYYYY"
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
            )
        self.assertEqual(stdout, "YYYYYYYYY")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_socket_connect.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_exists_blueprinted(
        self, mock_log_debug, mock_isfile, mock_file_sha1, mock_socket_connect
    ):
        mock_isfile.return_value = False
        mock_file_sha1.return_value = "YYYYYYYYY"
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
                blueprint=True,
            )
        self.assertEqual(stdout, "YYYYYYYYY")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, None)
        mock_log_debug.assert_called()
        mock_socket_connect.assert_called()

    @patch("pwd.getpwnam", autospec=True)
    @patch("grp.getgrnam", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_chown_str(
        self,
        mock_log_debug,
        mock_chown,
        mock_isfile,
        mock_file_sha1,
        mock_socket_connect,
        mock_pwd,
        mock_grp,
    ):
        mock_isfile.return_value = False
        mock_file_sha1.return_value = "YYYYYYYYY"
        uid = MagicMock()
        uid.pw_uid = 9999
        mock_pwd.return_value = uid
        gid = MagicMock()
        gid.mock_grp = 9999
        mock_grp.return_value = gid
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
                user="nobody",
                group="nobody",
            )
        self.assertEqual(stdout, "YYYYYYYYY")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_socket_connect.assert_called()
        mock_chown.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_chown_int(
        self,
        mock_log_debug,
        mock_chown,
        mock_isfile,
        mock_file_sha1,
        mock_socket_connect,
    ):
        mock_isfile.return_value = False
        mock_file_sha1.return_value = "YYYYYYYYY"
        fake_cache = tests.FakeCache()
        self.client.bind_transfer = self.client.transfer_connect()
        with patch("builtins.open", unittest.mock.mock_open()):
            stdout, stderr, outcome = self.client._run_transfer(
                file_to="/test/file",
                job_id="XXX",
                source_file="/orig/file",
                cache=fake_cache,
                file_sha1="YYYYYYYYY",
                user=9999,
                group=9999,
            )
        self.assertEqual(stdout, "YYYYYYYYY")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_socket_connect.assert_called()
        mock_chown.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__job_executor_cached(self, mock_log_info, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=True,
            command=b"RUN",
        )
        self.assertEqual(stdout, None)
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, None)
        mock_log_debug.assert_called()
        mock_log_info.assert_called()

    @patch("directord.utils.run_command", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_run(self, mock_log_debug, mock_run_command):
        mock_run_command.return_value = None, None, True
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={
                "command": "command 1 test",
                "stdout_arg": False,
            },
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"RUN",
        )
        self.assertEqual(stdout, None)
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__job_executor_copy(
        self,
        mock_log_info,
        mock_log_debug,
        mock_isfile,
        mock_file_sha1,
        mock_socket_connect,
    ):
        self.client.bind_transfer = self.client.transfer_connect()
        mock_isfile.return_value = True
        mock_file_sha1.return_value = "YYYYYY"
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info="/source/file1",
            job={"file_to": "/target/file1", "file_sha1sum": "YYYYYY"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"COPY",
        )
        self.assertEqual(
            stdout,
            (
                "File exists /target/file1 and SHA1"
                " YYYYYY matches, nothing to transfer"
            ),
        )
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()

    @patch("directord.manager.Interface.socket_connect", autospec=True)
    @patch("directord.utils.file_sha1", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__job_executor_add(
        self,
        mock_log_info,
        mock_log_debug,
        mock_isfile,
        mock_file_sha1,
        mock_socket_connect,
    ):
        self.client.bind_transfer = self.client.transfer_connect()
        mock_isfile.return_value = True
        mock_file_sha1.return_value = "YYYYYY"
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info="/source/file1",
            job={"file_to": "/target/file1", "file_sha1sum": "YYYYYY"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"ADD",
        )
        self.assertEqual(
            stdout,
            (
                "File exists /target/file1 and SHA1"
                " YYYYYY matches, nothing to transfer"
            ),
        )
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()

    @patch("os.makedirs", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test__job_executor_workdir(
        self, mock_log_info, mock_log_debug, mock_makedirs
    ):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"workdir": "/target"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"WORKDIR",
        )
        self.assertEqual(stdout, "Directory /target OK")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        mock_log_debug.assert_called()
        mock_log_info.assert_called()
        mock_makedirs.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_arg(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"args": {"key-arg": "value-arg"}},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"ARG",
        )
        self.assertEqual(stdout, "args added to cache")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        self.assertEqual(fake_cache.get("args").get("key-arg"), "value-arg")
        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_env(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"envs": {"key-env": "value-env"}},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"ENV",
        )
        self.assertEqual(stdout, "envs added to cache")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        self.assertEqual(fake_cache.get("envs").get("key-env"), "value-env")
        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_cachefile(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=tests.TEST_CATALOG.encode()),
        ):
            stdout, stderr, outcome = self.client._job_executor(
                conn=mock_conn,
                cache=fake_cache,
                info=None,
                job={"cachefile": "/target/file1"},
                job_id="XXXXXX",
                job_sha1="YYYYYY",
                cached=False,
                command=b"CACHEFILE",
            )
        self.assertEqual(stdout, "Cache file loaded")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)
        self.assertDictEqual(
            fake_cache.get("args"),
            {
                "test": 1,
                "directord_server": {
                    "targets": [
                        {
                            "host": "172.16.27.2",
                            "port": 22,
                            "username": "centos",
                        }
                    ],
                    "jobs": [{"RUN": "command1"}],
                },
                "directord_clients": {
                    "args": {"port": 22, "username": "centos"},
                    "targets": [{"host": "172.16.27.2"}],
                    "jobs": [{"RUN": "command1"}],
                },
            },
        )
        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_cachefile_fail(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"cachefile": "/target/file1"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"CACHEFILE",
        )

        self.assertEqual(stdout, None)
        self.assertEqual(
            stderr, "[Errno 2] No such file or directory: '/target/file1'"
        )
        self.assertEqual(outcome, False)

        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_cacheevict_all(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"cacheevict": "all"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"CACHEEVICT",
        )

        self.assertEqual(stdout, "All cache has been cleared")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)

        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_cacheevict_evict(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"cacheevict": "args"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"CACHEEVICT",
        )

        self.assertEqual(stdout, "Evicted 1 items, tagged args")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)

        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    def test__job_executor_cacheevict_query(self, mock_log_debug):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={"query": "test"},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"QUERY",
        )

        self.assertEqual(stdout, "1")
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)

        mock_log_debug.assert_called()

    @patch("logging.Logger.debug", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    def test__job_executor_cacheevict_unknown(
        self, mock_log_debug, mock_log_warning
    ):
        mock_conn = MagicMock()
        fake_cache = tests.FakeCache()
        stdout, stderr, outcome = self.client._job_executor(
            conn=mock_conn,
            cache=fake_cache,
            info=None,
            job={},
            job_id="XXXXXX",
            job_sha1="YYYYYY",
            cached=False,
            command=b"UNKNOWN",
        )

        self.assertEqual(stdout, None)
        self.assertEqual(stderr, "Unknown command - COMMAND:UNKNOWN ID:XXXXXX")
        self.assertEqual(outcome, None)

        mock_log_debug.assert_called()
        mock_log_warning.assert_called()

    @patch("logging.Logger.info", autospec=True)
    def test_file_blueprinter(self, mock_log_info):
        fake_cache = tests.FakeCache()
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=tests.TEST_BLUEPRINT_CONTENT),
        ):
            self.assertTrue(
                self.client.file_blueprinter(
                    cache=fake_cache, file_to="/test/file1"
                )
            )
        mock_log_info.assert_called()

    @patch("logging.Logger.critical", autospec=True)
    def test_file_blueprinter_failed(self, mock_log_critical):
        fake_cache = tests.FakeCache()
        self.assertFalse(
            self.client.file_blueprinter(
                cache=fake_cache, file_to="/test/file1"
            )
        )
        mock_log_critical.assert_called()

    def test_blueprinter(self):
        blueprinted_content = self.client.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT, values={"test": 1}
        )
        self.assertEqual(blueprinted_content, "This is a blueprint string 1")

    def test_blueprinter_no_values(self):
        blueprinted_content = self.client.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT, values=None
        )
        self.assertEqual(
            blueprinted_content, "This is a blueprint string {{ test }}"
        )

    @patch("logging.Logger.critical", autospec=True)
    def test_blueprinter_failed(self, mock_log_critical):
        blueprinted_content = self.client.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT.encode(), values={"test": 1}
        )
        self.assertEqual(blueprinted_content, None)
        mock_log_critical.assert_called()

    def test_set_cache(self):
        fake_cache = tests.FakeCache()
        self.client.set_cache(cache=fake_cache, key="key1", value="value1")

    def test_set_cache_value_update(self):
        fake_cache = tests.FakeCache()
        self.client.set_cache(
            cache=fake_cache, key="key1", value="value1", value_update=True
        )

    def test_set_cache_value_expire_tag(self):
        fake_cache = tests.FakeCache()
        self.client.set_cache(
            cache=fake_cache,
            key="key1",
            value="value1",
            expire=12345,
            tag="test",
        )

    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job(self, mock_socket_connect, mock_time, mock_makedirs):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_socket_connect.assert_called()

    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_idle(
        self, mock_socket_connect, mock_time, mock_makedirs, mock_log_info
    ):
        mock_time.side_effect = [1, 1, 66, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_socket_connect.assert_called()
        mock_log_info.assert_called()

    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_ramp(
        self, mock_socket_connect, mock_time, mock_makedirs, mock_log_info
    ):
        mock_time.side_effect = [1, 1, 1, 34, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_socket_connect.assert_called()
        mock_log_info.assert_called()

    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_cache_check(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_warning,
        mock_diskcache,
    ):
        mock_time.side_effect = [1, 1, 1, 1, 5000, 1]
        mock_diskcache.return_value = tests.FakeCache()
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_socket_connect.assert_called()
        mock_log_info.assert_called()
        mock_log_warning.assert_called_with(
            ANY, "Client Cache Warning: [ %s ].", "warning"
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_skip_skip_cache_run(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "skip_cache": True,
            "command": "RUN",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        mock_diskcache.return_value = tests.FakeCache()
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha1="YYY",
            cached=False,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_skip_ignore_cache_run(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "ignore_cache": True,
            "command": "RUN",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        mock_diskcache.return_value = tests.FakeCache()
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha1="YYY",
            cached=False,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_parent_failed_run(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_error,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "parent_id": "ZZZ",
            "command": "RUN",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="ZZZ", value=False)
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_log_error.assert_called()
        mock_socket_connect.assert_called()

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_cache_hit_run(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "command": "RUN",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="YYY", value=self.client.job_end)
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha1="YYY",
            cached=True,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_run(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "command": "RUN",
            "parent_id": "ZZZ",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="YYY", value=self.client.job_end)
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_socket_connect.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha1="YYY",
            cached=True,
            command=b"RUN",
        )
        self.assertEqual(cache.get("ZZZ"), True)
        self.assertEqual(cache.get("YYY"), self.client.job_end)

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("directord.manager.Interface.socket_multipart_recv", autospec=True)
    @patch("directord.client.Client.job_connect", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("zmq.Poller.poll", autospec=True)
    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    @patch("directord.manager.Interface.socket_connect", autospec=True)
    def test_run_job_run_outcome_false(
        self,
        mock_socket_connect,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_error,
        mock_poller,
        mock_diskcache,
        mock_job_connect,
        mock_multipart_recv,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", False]
        job_def = {
            "task": "XXX",
            "task_sha1sum": "YYY",
            "command": "RUN",
        }
        mock_multipart_recv.side_effect = [
            (None, None, b"RUN", json.dumps(job_def).encode(), b"", None, None)
        ]
        bind = mock_job_connect.return_value = MagicMock()
        cache = mock_diskcache.return_value = tests.FakeCache()
        mock_poller.return_value = [(bind, "value")]
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_log_error.assert_called()
        mock_socket_connect.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha1="YYY",
            cached=False,
            command=b"RUN",
        )

        self.assertEqual(cache.get("YYY"), self.client.job_failed)

    @patch("directord.client.Client.run_threads", autospec=True)
    def test_worker_run(self, mock_run_threads):
        self.client.worker_run()
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY])
