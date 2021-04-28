import json
import unittest

from unittest.mock import patch

from directord import user
from directord import tests


class TestUser(unittest.TestCase):
    def setUp(self):
        self.user = user.User(args=tests.FakeArgs())
        self.execute = ["long '{{ jinja }}' quoted string", "string"]

    def tearDown(self):
        pass

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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "skip_cache": True,
                    "run_once": False,
                    "return_raw": False,
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
                    "restrict": "RestrictedSHA1",
                    "verb": "RUN",
                    "timeout": 600,
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "parent_id": "ParentID",
                    "verb": "RUN",
                    "timeout": 600,
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
            "skip_cache": False,
            "run_once": False,
            "return_raw": False,
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
            "skip_cache": False,
            "run_once": False,
            "return_raw": False,
        }
        result = self.user.format_exec(verb="ARG", execute=["key", "value"])
        self.assertEqual(result, json.dumps(expected_result))

    def test_format_exec_envs(self):
        expected_result = {
            "envs": {"key": "value"},
            "verb": "ENV",
            "timeout": 600,
            "skip_cache": False,
            "run_once": False,
            "return_raw": False,
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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
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
                    "skip_cache": False,
                    "run_once": False,
                    "return_raw": False,
                }
            ),
        )

    def test_send_data(self):
        user.directord.socket.socket = tests.MockSocket
        returned = self.user.send_data(data="test")
        self.assertEqual(returned, b"return data")


class TestManager(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_move_cetrificates(self):
        pass

    def test_generate_certificates(self):
        pass

    def test_poll_job(self):
        pass

    def test_run(self):
        pass
