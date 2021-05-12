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

from unittest import mock
from unittest.mock import patch

from directord import mixin
from directord import tests
from directord import utils


TEST_FINGER_PRINTS = [
    b"\n****************************************************************************************************\n0     RUN           command1                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
    b"1     RUN           command2                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
    b"2     RUN           command3                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
    b"3     RUN           command1                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
    b"4     RUN           command2                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
    b"5     RUN           command3                                XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",  # noqa
]


TEST_ORCHESTRATION_READ = """---
- targets:
  - test1
  - test2
  - test3
  jobs:
  - RUN: command1
  - RUN: command2
  - RUN: command3
"""


class TestMixin(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.mixin = mixin.Mixin(args=self.args)
        self.execute = ["long '{{ jinja }}' quoted string", "string"]
        self.dummy_sha1 = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.patched_object_sha1 = patch.object(
            utils,
            "object_sha1",
            autospec=True,
            return_value=self.dummy_sha1,
        )
        self.patched_object_sha1.start()
        self.orchestration = {
            "targets": [
                "test1",
                "test2",
                "test3",
            ],
            "jobs": [
                {"RUN": "command1"},
                {"RUN": "command2"},
                {"RUN": "command3"},
            ],
        }
        self.target_orchestrations = [self.orchestration, self.orchestration]

        # Fake SSH
        self.buf = tests.MockChannelFile()
        self.mock_ssh = mock.MagicMock()
        self.mock_ssh.exec_command.return_value = (
            self.buf,
            self.buf,
            self.buf,
        )

    def tearDown(self):
        self.patched_object_sha1.stop()

    def test_format_action_unknown(self):
        self.assertRaises(
            SystemExit,
            self.mixin.format_action,
            verb="TEST",
            execute=self.execute,
        )

    def test_format_action_run(self):
        result = self.mixin.format_action(verb="RUN", execute=self.execute)
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_action_run_target(self):
        result = self.mixin.format_action(
            verb="RUN", execute=self.execute, targets=["test_target"]
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "command": "long '{{ jinja }}' quoted string string",
                    "targets": ["test_target"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_action_run_ignore_cache(self):
        result = self.mixin.format_action(
            verb="RUN", execute=self.execute, ignore_cache=True
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": True,
                }
            ),
        )

    def test_format_action_run_restrict(self):
        result = self.mixin.format_action(
            verb="RUN", execute=self.execute, restrict="RestrictedSHA1"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                    "restrict": "RestrictedSHA1",
                }
            ),
        )

    def test_format_action_run_parent_id(self):
        result = self.mixin.format_action(
            verb="RUN", execute=self.execute, parent_id="ParentID"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "ParentID",
                }
            ),
        )

    @patch("glob.glob")
    @patch("os.path.isfile")
    def test_format_action_add_copy(self, mock_isfile, mock_glob):
        mock_isfile.return_value = True
        mock_glob.return_value = ["/from/one", "/from/two"]
        expected_result = {
            "verb": "COPY",
            "to": "/to/path/",
            "from": ["/from/one", "/from/two"],
            "blueprint": False,
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.mixin.format_action(
            verb="COPY", execute=["/from/*", "/to/path/"]
        )
        self.assertEqual(result, json.dumps(expected_result))
        result = self.mixin.format_action(
            verb="ADD", execute=["/from/*", "/to/path/"]
        )
        expected_result["verb"] = "ADD"
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_action_args(self):
        expected_result = {
            "verb": "ARG",
            "args": {"key": "value"},
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.mixin.format_action(verb="ARG", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_action_envs(self):
        expected_result = {
            "verb": "ENV",
            "envs": {"key": "value"},
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.mixin.format_action(verb="ENV", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_action_workdir(self):
        result = self.mixin.format_action(
            verb="WORKDIR", execute=["/test/path"]
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "WORKDIR",
                    "workdir": "/test/path",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_action_cachefile(self):
        result = self.mixin.format_action(
            verb="CACHEFILE", execute=["/test/path"]
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "CACHEFILE",
                    "cachefile": "/test/path",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_action_cacheevict(self):
        result = self.mixin.format_action(verb="CACHEEVICT", execute=["test"])
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "CACHEEVICT",
                    "cacheevict": "test",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_action_query(self):
        result = self.mixin.format_action(verb="QUERY", execute=["test"])
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "QUERY",
                    "query": "test",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_exec_orchestrations(self, mock_send_data, mock_get_uuid):
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations
            )
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(len(return_data), 6)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": ["test1", "test2", "test3"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                }
            ),
        )

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_exec_orchestrations_defined_targets(
        self, mock_send_data, mock_get_uuid
    ):
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations,
                defined_targets=[
                    "test-override1",
                    "test-override2",
                    "test-override3",
                ],
            )
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(len(return_data), 6)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": [
                        "test-override1",
                        "test-override2",
                        "test-override3",
                    ],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                }
            ),
        )

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_exec_orchestrations_restrict(self, mock_send_data, mock_get_uuid):
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations,
                restrict=["a", "b", "c"],
            )
        finally:
            self.args = tests.FakeArgs()
        self.assertEqual(len(return_data), 6)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": ["test1", "test2", "test3"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "restrict": ["a", "b", "c"],
                }
            ),
        )

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_exec_orchestrations_ignore_cache(
        self, mock_send_data, mock_get_uuid
    ):
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations, ignore_cache=True
            )
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(len(return_data), 6)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": ["test1", "test2", "test3"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": True,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                }
            ),
        )

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_exec_orchestrations_return_raw(
        self, mock_send_data, mock_get_uuid
    ):
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations, return_raw=True
            )
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(len(return_data), 6)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": ["test1", "test2", "test3"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": True,
                    "skip_cache": False,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                }
            ),
        )

    def test_exec_orchestrations_finger_print(self):
        try:
            setattr(self.args, "finger_print", True)
            setattr(self.args, "target", ["test1", "test2", "test3"])
            return_data = self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations, return_raw=True
            )
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(return_data, TEST_FINGER_PRINTS)
        self.assertEqual(len(return_data), 6)

    @patch("os.path.exists", autospec=True)
    def test_run_orchestration_not_found(self, mock_path_exists):
        try:
            setattr(self.args, "finger_print", False)
            setattr(self.args, "target", ["test1", "test2", "test3"])
            mock_path_exists.return_value = False
            setattr(self.args, "orchestrate_files", ["/file1"])
            self.assertRaises(
                FileNotFoundError,
                self.mixin.run_orchestration,
            )
        finally:
            self.args = tests.FakeArgs()

    @patch("directord.utils.get_uuid", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_run_orchestration_duplicate_targets(
        self, mock_send_data, mock_path_exists, mock_get_uuid
    ):
        mock_path_exists.return_value = True
        mock_get_uuid.return_value = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        try:
            setattr(self.args, "finger_print", False)
            setattr(self.args, "target", ["test", "test", "test"])
            setattr(self.args, "restrict", [])
            setattr(self.args, "ignore_cache", False)
            setattr(self.args, "orchestrate_files", ["/file1"])
            m = unittest.mock.mock_open(
                read_data=TEST_ORCHESTRATION_READ.encode()
            )
            with patch("builtins.open", m):
                return_data = self.mixin.run_orchestration()
        finally:
            self.args = tests.FakeArgs()
        self.assertEqual(len(return_data), 3)
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command3",
                    "targets": ["test"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                }
            ),
        )

    @patch("os.path.exists", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_run_exec(self, mock_send_data, mock_path_exists):
        mock_path_exists.return_value = True

        try:
            setattr(self.args, "verb", "RUN")
            setattr(self.args, "exec", ["command", "1"])
            setattr(self.args, "target", ["test"])
            self.mixin.run_exec()
        finally:
            self.args = tests.FakeArgs()
        mock_send_data.assert_called_with(
            socket_path="/var/run/directord.sock",
            data=json.dumps(
                {
                    "verb": "RUN",
                    "command": "command 1",
                    "targets": ["test"],
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_return_tabulated_info(self):
        data = {
            "_test": "value",
            "dict": {"key1": "value1", "key2": "value2"},
            "list": ["item1", "item2"],
            "string": "string",
            "integer": 1,
            "boolean": True,
        }
        try:
            setattr(
                self.args, "job_info", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            )
            return_data = self.mixin.return_tabulated_info(data=data)
        finally:
            self.args = tests.FakeArgs()

        self.assertEqual(
            return_data,
            [
                ["ID", "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"],
                ["DICT", "key1 = value1\nkey2 = value2"],
                ["LIST", "item1\nitem2"],
                ["STRING", "string"],
                ["INTEGER", 1],
                ["BOOLEAN", True],
            ],
        )

    def test_return_tabulated_data(self):
        data = {
            "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx": {
                "_test": "value",
                "dict": {"key1": "value1", "key2": "value2"},
                "list": ["item1", "item2"],
                "string": "string",
                "integer": 1,
                "boolean": True,
            },
            "xxxxxxxx-xxxx-xxxx-yyyy-xxxxxxxxxxxx": {
                "_test": "value",
                "dict": {"key1": "value1", "key2": "value2"},
                "list": ["item1", "item2"],
                "string": "string",
                "integer": 1,
                "boolean": True,
            },
        }
        (
            tabulated_data,
            found_headings,
            computed_values,
        ) = self.mixin.return_tabulated_data(
            data=data, restrict_headings=["STRING", "INTEGER"]
        )

        self.assertEqual(computed_values, {"INTEGER": 2})
        self.assertEqual(found_headings, ["ID", "STRING", "INTEGER"])
        self.assertEqual(
            tabulated_data,
            [
                ["xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", "string", 1],
                ["xxxxxxxx-xxxx-xxxx-yyyy-xxxxxxxxxxxx", "string", 1],
            ],
        )

    def test_bootstrap_catalog_entry_no_args(self):
        entry = {
            "targets": [
                {
                    "host": "example.com",
                    "username": "example-user",
                    "port": 22,
                }
            ],
            "jobs": {"RUN": "command1"},
        }
        return_data = self.mixin.bootstrap_catalog_entry(entry=entry)
        self.assertEqual(
            return_data,
            [
                {
                    "host": "example.com",
                    "jobs": {"RUN": "command1"},
                    "port": 22,
                    "username": "example-user",
                }
            ],
        )

    def test_bootstrap_catalog_entry_args(self):
        entry = {
            "args": {
                "username": "example-user",
                "port": 22,
            },
            "targets": [
                {
                    "host": "example.com",
                }
            ],
            "jobs": {"RUN": "command1"},
        }
        return_data = self.mixin.bootstrap_catalog_entry(entry=entry)
        self.assertEqual(
            return_data,
            [
                {
                    "host": "example.com",
                    "jobs": {"RUN": "command1"},
                    "port": 22,
                    "username": "example-user",
                }
            ],
        )

    def test_bootstrap_catalog_entry_args_override(self):
        entry = {
            "args": {
                "username": "example-user",
                "port": 22,
            },
            "targets": [
                {
                    "host": "example.com",
                    "port": 2222,
                    "username": "example-user2",
                }
            ],
            "jobs": {"RUN": "command1"},
        }
        return_data = self.mixin.bootstrap_catalog_entry(entry=entry)
        self.assertEqual(
            return_data,
            [
                {
                    "host": "example.com",
                    "jobs": {"RUN": "command1"},
                    "port": 2222,
                    "username": "example-user2",
                }
            ],
        )

    def test_bootstrap_localfile_padding_shared(self):
        orig_prefix = mixin.sys.prefix
        orig_base_prefix = mixin.sys.base_prefix
        try:
            mixin.sys.prefix = "/test/path"
            mixin.sys.base_prefix = "/test/path"
            return_data = self.mixin.bootstrap_localfile_padding(
                localfile="file1"
            )
        finally:
            mixin.sys.prefix = orig_prefix
            mixin.sys.base_prefix = orig_base_prefix

        self.assertEqual(return_data, "/test/path/share/directord/tools/file1")

    def test_bootstrap_localfile_padding_shared_venv(self):
        orig_prefix = mixin.sys.prefix
        orig_base_prefix = mixin.sys.base_prefix
        try:
            mixin.sys.prefix = "/usr"
            mixin.sys.base_prefix = "/test/path"
            return_data = self.mixin.bootstrap_localfile_padding(
                localfile="file1"
            )
        finally:
            mixin.sys.prefix = orig_prefix
            mixin.sys.base_prefix = orig_base_prefix

        self.assertEqual(return_data, "/usr/share/directord/tools/file1")

    def test_bootstrap_localfile_padding_absolute(self):
        return_data = self.mixin.bootstrap_localfile_padding(
            localfile="/file1"
        )
        self.assertEqual(return_data, "/file1")

    def test_bootstrap_flatten_jobs(self):
        return_data = self.mixin.bootstrap_flatten_jobs(
            jobs=[["one", "two"], "three", "four"]
        )
        self.assertEqual(return_data, ["one", "two", "three", "four"])

    @patch("logging.Logger.info", autospec=True)
    @patch("directord.utils.ParamikoConnect.__enter__", autospec=True)
    def test_bootstrap_run(self, mock_paramikoconnect, mock_log_info):
        mock_paramikoconnect.return_value = self.mock_ssh
        job_def = {
            "host": "String",
            "port": 22,
            "username": "String",
            "key_file": None,
            "jobs": [{"RUN": "command 1", "ADD": "from to", "GET": "from to"}],
        }
        self.mixin.bootstrap_run(job_def=job_def, catalog={})
        mock_log_info.assert_called()

    def test_bootstrap_file_send(self):
        self.mixin.bootstrap_file_send(
            ssh=self.mock_ssh, localfile="/file1", remotefile="/file2"
        )

    def test_bootstrap_file_get(self):
        self.mixin.bootstrap_file_send(
            ssh=self.mock_ssh, localfile="/file1", remotefile="/file2"
        )

    def test_bootstrap_exec(self):
        self.mixin.bootstrap_exec(
            ssh=self.mock_ssh, command="command1", catalog={}
        )
        self.mock_ssh.exec_command.assert_called_with("command1")

    def test_bootstrap_exec_failure(self):
        self.mock_ssh.exec_command.return_value = (
            self.buf,
            tests.MockChannelFile(rc=2),
            self.buf,
        )
        self.assertRaises(
            SystemExit,
            self.mixin.bootstrap_exec,
            self.mock_ssh,
            "command1",
            {},
        )

    def test_bootstrap_exec_jinja(self):
        self.mixin.bootstrap_exec(
            ssh=self.mock_ssh,
            command="command {{ test }} test",
            catalog={"test": 1},
        )
        self.mock_ssh.exec_command.assert_called_with("command 1 test")

    @patch("queue.Queue", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("directord.utils.paramiko.SSHClient", autospec=True)
    @patch("directord.utils.ParamikoConnect.__enter__", autospec=True)
    def test_bootstrap_q_processor(
        self, mock_paramikoconnect, mock_sshclient, mock_log_info, mock_queue
    ):
        mock_paramikoconnect.return_value = self.mock_ssh
        mock_queue.get.side_effect = [
            {
                "host": "String",
                "port": 22,
                "username": "String",
                "key_file": None,
                "jobs": [
                    {"RUN": "command 1", "ADD": "from to", "GET": "from to"}
                ],
            }
        ]
        self.mixin.bootstrap_q_processor(queue=mock_queue, catalog={})
        mock_log_info.assert_called()

    @patch("multiprocessing.Process", autospec=True)
    @patch("multiprocessing.Queue", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    def test_bootstrap_cluster(self, mock_log_info, mock_queue, mock_process):
        try:
            setattr(self.args, "catalog", ["/file.yaml"])
            setattr(self.args, "threads", 3)
            m = unittest.mock.mock_open(read_data=tests.TEST_CATALOG.encode())
            with patch("builtins.open", m):
                self.mixin.bootstrap_cluster()
        finally:
            self.args = tests.FakeArgs()
        mock_queue.assert_called()
        mock_process.assert_called()
