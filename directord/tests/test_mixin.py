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
from directord import utils


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

    def tearDown(self):
        self.patched_object_sha1.stop()

    def test_sanitize_args(self):

        result = self.mixin.sanitized_args(execute=self.execute)
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
            self.mixin.format_exec,
            verb="TEST",
            execute=self.execute,
        )

    def test_format_exec_run(self):
        result = self.mixin.format_exec(verb="RUN", execute=self.execute)
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
        result = self.mixin.format_exec(
            verb="RUN", execute=self.execute, targets=["test_target"]
        )
        self.assertEqual(
            result,
            json.dumps(
                {
                    "command": "long '{{ jinja }}' quoted string string",
                    "targets": ["test_target"],
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
        result = self.mixin.format_exec(
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
        result = self.mixin.format_exec(
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
        result = self.mixin.format_exec(
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
        result = self.mixin.format_exec(
            verb="COPY", execute=["/from/*", "/to/path/"]
        )
        self.assertEqual(result, json.dumps(expected_result))
        result = self.mixin.format_exec(
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
        result = self.mixin.format_exec(verb="ARG", execute=["key", "value"])
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
        result = self.mixin.format_exec(verb="ENV", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_exec_workdir(self):
        result = self.mixin.format_exec(verb="WORKDIR", execute=["/test/path"])
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
        result = self.mixin.format_exec(
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
        result = self.mixin.format_exec(verb="CACHEEVICT", execute=["test"])
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
        result = self.mixin.format_exec(verb="QUERY", execute=["test"])
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

    def test_exec_orchestrations(self):
        pass

    def test_run_orchestration(self):
        pass

    def test_run_exec(self):
        pass

    def test_start_server(self):
        pass

    def test_start_client(self):
        pass

    def test_return_tabulated_info(self):
        pass

    def test_return_tabulated_data(self):
        pass

    def test_bootstrap_catalog_entry(self):
        pass

    def test_bootstrap_localfile_padding(self):
        pass

    def test_bootstrap_flatten_jobs(self):
        pass

    def test_bootstrap_run(self):
        pass

    def test_bootstrap_file_send(self):
        pass

    def test_bootstrap_file_get(self):
        pass

    def test_bootstrap_exec(self):
        pass

    def test_bootstrap_q_processor(self):
        pass

    def test_bootstrap_cluster(self):
        pass
