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

from unittest.mock import call
from unittest.mock import patch

from directord import tests
from directord import user


class TestUser(unittest.TestCase):
    def setUp(self):
        self.user = user.User(args=tests.FakeArgs())
        self.execute = ["long '{{ jinja }}' quoted string", "string"]
        self.dummy_sha1 = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
        self.patched_object_sha1 = patch.object(
            self.user,
            "object_sha1",
            autospec=True,
            return_value=self.dummy_sha1,
        )
        self.patched_object_sha1.start()

    def tearDown(self):
        self.patched_object_sha1.stop()

    def test_sanitize_args(self):

        result = self.user.sanitized_args(execute=self.execute)
        expected = [
            "long",
            "'{{",
            "jinja",
            "}}'",
            "quoted",
            "string",
            "string",
        ]
        self.assertEqual(result, expected)

    def test_format_exec_unknown(self):
        self.assertRaises(
            SystemExit,
            self.user.format_exec,
            verb="TEST",
            execute=self.execute,
        )

    def test_format_exec_run(self):
        result = self.user.format_exec(verb="RUN", execute=self.execute)
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "verb": "RUN",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_exec_run_target(self):
        result = self.user.format_exec(
            verb="RUN", execute=self.execute, target="test_target"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "target": "test_target",
                    "verb": "RUN",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_exec_run_ignore_cache(self):
        result = self.user.format_exec(
            verb="RUN", execute=self.execute, ignore_cache=True
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "verb": "RUN",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": True,
                }
            ),
        )

    def test_format_exec_run_restrict(self):
        result = self.user.format_exec(
            verb="RUN", execute=self.execute, restrict="RestrictedSHA1"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "verb": "RUN",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                    "restrict": "RestrictedSHA1",
                }
            ),
        )

    def test_format_exec_run_parent_id(self):
        result = self.user.format_exec(
            verb="RUN", execute=self.execute, parent_id="ParentID"
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "verb": "RUN",
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
    def test_format_exec_add_copy(self, mock_isfile, mock_glob):
        mock_isfile.return_value = True
        mock_glob.return_value = ["/from/one", "/from/two"]
        expected_result = {
            "to": "/to/path/",
            "from": ["/from/one", "/from/two"],
            "blueprint": False,
            "verb": "COPY",
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.user.format_exec(
            verb="COPY", execute=["/from/*", "/to/path/"]
        )
        self.assertEqual(result, json.dumps(expected_result))
        result = self.user.format_exec(
            verb="ADD", execute=["/from/*", "/to/path/"]
        )
        expected_result["verb"] = "ADD"
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_exec_args(self):
        expected_result = {
            "args": {"key": "value"},
            "verb": "ARG",
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.user.format_exec(verb="ARG", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_exec_envs(self):
        expected_result = {
            "envs": {"key": "value"},
            "verb": "ENV",
            "timeout": 600,
            "run_once": False,
            "task_sha1sum": self.dummy_sha1,
            "return_raw": False,
            "skip_cache": False,
        }
        result = self.user.format_exec(verb="ENV", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_exec_workdir(self):
        result = self.user.format_exec(verb="WORKDIR", execute=["/test/path"])
        self.assertEqual(
            result,
            json.dumps(
                {
                    "workdir": "/test/path",
                    "verb": "WORKDIR",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_exec_cachefile(self):
        result = self.user.format_exec(
            verb="CACHEFILE", execute=["/test/path"]
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "cachefile": "/test/path",
                    "verb": "CACHEFILE",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_exec_cacheevict(self):
        result = self.user.format_exec(verb="CACHEEVICT", execute=["test"])
        self.assertEqual(
            result,
            json.dumps(
                {
                    "cacheevict": "test",
                    "verb": "CACHEEVICT",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_format_exec_query(self):
        result = self.user.format_exec(verb="QUERY", execute=["test"])
        self.assertEqual(
            result,
            json.dumps(
                {
                    "query": "test",
                    "verb": "QUERY",
                    "timeout": 600,
                    "run_once": False,
                    "task_sha1sum": self.dummy_sha1,
                    "return_raw": False,
                    "skip_cache": False,
                }
            ),
        )

    def test_send_data(self):
        user.directord.socket.socket = tests.MockSocket
        returned = self.user.send_data(data="test")
        self.assertEqual(returned, b"return data")


class TestManager(unittest.TestCase):
    def setUp(self):
        self.manage = user.Manage(args=tests.FakeArgs())

    def tearDown(self):
        pass

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_null(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one", "item-two"]
        self.manage.move_certificates(directory="/test/path")
        mock_rename.assert_not_called()

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_normal(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.manage.move_certificates(directory="/test/path")
        mock_rename.assert_called_with(
            "/test/path/item-two.key", "/test/path/item-two.key"
        )
        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/test/path/item-one.key"),
                call("/test/path/item-two.key", "/test/path/item-two.key"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_backup(self, mock_listdir, mock_rename):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.manage.move_certificates(directory="/test/path", backup=True)
        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/test/path/item-one.key.bak"),
                call("/test/path/item-two.key", "/test/path/item-two.key.bak"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_target_directory(
        self, mock_listdir, mock_rename
    ):
        mock_listdir.return_value = ["item-one.key", "item-two.key"]
        self.manage.move_certificates(
            directory="/test/path", target_directory="/new/test/path"
        )
        mock_rename.assert_has_calls(
            [
                call("/test/path/item-one.key", "/new/test/path/item-one.key"),
                call("/test/path/item-two.key", "/new/test/path/item-two.key"),
            ]
        )

    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_move_cetrificates_normal_selective(
        self, mock_listdir, mock_rename
    ):
        mock_listdir.return_value = ["item-one.test", "item-two.key"]
        self.manage.move_certificates(directory="/test/path", suffix=".test")
        mock_rename.assert_called_once_with(
            "/test/path/item-one.test", "/test/path/item-one.test"
        )

    @patch("zmq.auth.create_certificates", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_generate_certificates(
        self, mock_listdir, mock_rename, mock_makedirs, mock_zmqgencerts
    ):
        mock_listdir.return_value = ["item-one.test", "item-two.key"]
        self.manage.generate_certificates()
        mock_makedirs.assert_has_calls(
            [
                call("/etc/directord/certificates", exist_ok=True),
                call("/etc/directord/public_keys", exist_ok=True),
                call("/etc/directord/private_keys", exist_ok=True),
            ]
        )
        mock_zmqgencerts.assert_has_calls(
            [
                call("/etc/directord/certificates", "server"),
                call("/etc/directord/certificates", "client"),
            ]
        )

    @patch("directord.user.User.send_data", autospec=True)
    def test_poll_job_unknown(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node1"],
                    "NODES": ["hostname-node1", "hostname-node2"],
                    "PROCESSING": False,
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, None)
        self.assertEqual(info, "Job in an unknown state: test-id")

    @patch("directord.user.User.send_data", autospec=True)
    def test_poll_job_success(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node"],
                    "NODES": ["hostname-node"],
                    "PROCESSING": False,
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, True)
        self.assertEqual(info, "Job Success: test-id")

    @patch("directord.user.User.send_data", autospec=True)
    def test_poll_job_failed(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "FAILED": ["hostname-node"],
                    "NODES": ["hostname-node"],
                    "PROCESSING": False,
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, False)
        self.assertEqual(info, "Job Failed: test-id")

    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    @patch("directord.user.User.send_data", autospec=True)
    def test_poll_job_timeout(
        self, mock_send_data, mock_log_warn, mock_log_error
    ):
        setattr(self.manage.args, "timeout", 1)
        mock_send_data.return_value = '{"test-id-null": {}}'
        self.manage.poll_job("test-id")
        mock_log_warn.assert_called_once_with(
            unittest.mock.ANY,
            "Timeout encountered after 1 seconds running test-id.",
        )
        mock_log_error.assert_called_once_with(
            unittest.mock.ANY,
            "Task timeout encountered.",
        )

    def test_run_override_unknown(self):
        self.assertRaises(SystemExit, self.manage.run, override="UNKNOWN")

    @patch("directord.user.User.send_data", autospec=True)
    def test_run_override_list_jobs(self, mock_send_data):
        self.manage.run(override="list-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "list-jobs"}'
        )

    @patch("directord.user.User.send_data", autospec=True)
    def test_run_override_list_nodes(self, mock_send_data):
        self.manage.run(override="list-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "list-nodes"}'
        )

    @patch("directord.user.User.send_data", autospec=True)
    def test_run_override_purge_jobs(self, mock_send_data):
        self.manage.run(override="purge-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "purge-jobs"}'
        )

    @patch("directord.user.User.send_data", autospec=True)
    def test_run_override_purge_nodes(self, mock_send_data):
        self.manage.run(override="purge-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "purge-nodes"}'
        )

    @patch("directord.user.Manage.generate_certificates", autospec=True)
    @patch("directord.user.User.send_data", autospec=True)
    def test_run_override_generate_keys(
        self, mock_send_data, mock_generate_certificates
    ):
        self.manage.run(override="generate-keys")
        mock_send_data.assert_not_called()
