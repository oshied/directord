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

from unittest.mock import patch

from directord import mixin
from directord import tests


TEST_FINGER_PRINTS = """count    parent                                                    verb    exec      job
-------  --------------------------------------------------------  ------  --------  --------------------------------------------------------
0        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command1  ea5b3554e61a173c25152ad6fe29b178f66b0e3727556995f5816d7e
1        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command2  a12748d70957f1f2d0ea3d2aae5af73983d8a0563f7b5a0ccd0b2767
2        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command3  f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd
3        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command1  ea5b3554e61a173c25152ad6fe29b178f66b0e3727556995f5816d7e
4        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command2  a12748d70957f1f2d0ea3d2aae5af73983d8a0563f7b5a0ccd0b2767
5        5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08  RUN     command3  f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd"""  # noqa


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


class TestMixin(tests.TestConnectionBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        self.mixin = mixin.Mixin(args=self.args)
        self.execute = ["long '{{ jinja }}' quoted string", "string"]
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

    def tearDown(self):
        super().tearDown()

    def test_format_action_unknown(self):
        self.assertRaises(
            SystemExit,
            self.mixin.format_action,
            verb="TEST",
            execute=self.execute,
        )

    def test_format_action_run(self):
        result = self.mixin.format_action(verb="RUN", execute=self.execute)
        print(result)
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "no_block": False,
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "df28f8fb5a4c06c52a3bf4f41035e71d1c641736ef424b3582eb30f2",  # noqa
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
                    "no_block": False,
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "df28f8fb5a4c06c52a3bf4f41035e71d1c641736ef424b3582eb30f2",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": ["test_target"],
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
                    "no_block": False,
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "df28f8fb5a4c06c52a3bf4f41035e71d1c641736ef424b3582eb30f2",  # noqa
                    "return_raw": False,
                    "skip_cache": True,
                }
            ),
        )

    def test_format_action_run_restrict(self):
        result = self.mixin.format_action(
            verb="RUN", execute=self.execute, restrict="Restrictedsha3_224"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "verb": "RUN",
                    "no_block": False,
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "df28f8fb5a4c06c52a3bf4f41035e71d1c641736ef424b3582eb30f2",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "restrict": "Restrictedsha3_224",
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
                    "no_block": False,
                    "command": "long '{{ jinja }}' quoted string string",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "df28f8fb5a4c06c52a3bf4f41035e71d1c641736ef424b3582eb30f2",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "parent_id": "ParentID",
                }
            ),
        )

    @patch("glob.glob")
    @patch("os.path.isfile")
    def test_format_action_copy(self, mock_isfile, mock_glob):
        mock_isfile.return_value = True
        mock_glob.return_value = ["/from/one", "/from/two"]
        expected_result = {
            "verb": "COPY",
            "to": "/to/path/",
            "from": ["/from/one", "/from/two"],
            "blueprint": False,
            "timeout": 600,
            "run_once": False,
            "job_sha3_224": "de85bef754e1c7652d64cfd19f0a731e70d9bdc42a6698fabfd0f3ac",  # noqa
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.mixin.format_action(
            verb="COPY", execute=["/from/*", "/to/path/"]
        )
        self.assertEqual(result, json.dumps(expected_result))

    @patch("glob.glob")
    @patch("os.path.isfile")
    def test_format_action_add(self, mock_isfile, mock_glob):
        mock_isfile.return_value = True
        mock_glob.return_value = ["/from/one", "/from/two"]
        expected_result = {
            "verb": "ADD",
            "to": "/to/path/",
            "from": ["/from/one", "/from/two"],
            "blueprint": False,
            "timeout": 600,
            "run_once": False,
            "job_sha3_224": "9420176ba6b63667ffdd0c2e51d896e74a9c8fe100a168bd6086db38",  # noqa
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.mixin.format_action(
            verb="ADD", execute=["/from/*", "/to/path/"]
        )
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_action_args(self):
        expected_result = {
            "verb": "ARG",
            "args": {"key": "value"},
            "timeout": 600,
            "run_once": False,
            "job_sha3_224": "a5d63364114e96a96e5be4261f31a9bc0a45ecd2d5edba11336dd896",  # noqa
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
            "job_sha3_224": "adb3790c327b3b2fd3c438c900ab8a2d6260e1d812eb22cdd056dfc9",  # noqa
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
                    "job_sha3_224": "b899de26c8055243a43cc0c28d5a689a8ce6510bfcb420397e673a5f",  # noqa
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
                    "job_sha3_224": "dfce171945da1e2079b3ac4a7066eba6efd4880cadd10a649f95a1b4",  # noqa
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
                    "job_sha3_224": "06460bd89ead48bd50398d0f9f1cd058c169492f88cf915db94eca7f",  # noqa
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
                    "no_wait": False,
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "1ff48da6d87a9f451029040c02f99cf26efa6614e5af7a20ba53352d",  # noqa
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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": ["test1", "test2", "test3"],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": [
                        "test-override1",
                        "test-override2",
                        "test-override3",
                    ],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": ["test1", "test2", "test3"],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": False,
                    "skip_cache": True,
                    "targets": ["test1", "test2", "test3"],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": True,
                    "skip_cache": False,
                    "targets": ["test1", "test2", "test3"],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
                }
            ),
        )

    @patch("builtins.print")
    def test_exec_orchestrations_finger_print(self, mock_print):
        try:
            setattr(self.args, "finger_print", True)
            setattr(self.args, "target", ["test1", "test2", "test3"])
            self.mixin.exec_orchestrations(
                orchestrations=self.target_orchestrations, return_raw=True
            )
        finally:
            self.args = tests.FakeArgs()

        mock_print.assert_called_with(TEST_FINGER_PRINTS)

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
                    "no_block": False,
                    "command": "command3",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "f23220892ee6f80b9934a5b014a808e21904862d1c3eba3c470991dd",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": ["test"],
                    "parent_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                    "parent_sha3_224": "5bc535e8fa927e4a4ab9ca188f8b560935b32a00dacc4f9e76b05d08",  # noqa
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
                    "no_block": False,
                    "command": "command 1",
                    "timeout": 600,
                    "run_once": False,
                    "job_sha3_224": "36796bb09a3838fa2c8bcb802eb9494546289a6fd6ed988579524ee1",  # noqa
                    "return_raw": False,
                    "skip_cache": False,
                    "targets": ["test"],
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
