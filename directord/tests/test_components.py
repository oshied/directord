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

import unittest

from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

from directord import client
from directord import components
from directord import drivers
from directord import tests

from directord.components import builtin_copy
from directord.components import builtin_dnf
from directord.components import builtin_service
from directord.components import builtin_run
from directord.components import builtin_workdir
from directord.components import builtin_queuesentinel


class TestComponents(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.client = client.Client(args=self.args)

        self.mock_q_patched = patch("queue.Queue", autospec=True)
        q = self.mock_q_patched.start()
        self.client.q_processes = q
        self.client.q_return = q

        self.fake_cache = tests.FakeCache()
        self.components = components.ComponentBase(desc="test")
        self.execute = ["long '{{ jinja }}' quoted string", "string"]
        self._dnf = builtin_dnf.Component()
        self._service = builtin_service.Component()
        self._transfer = builtin_copy.Component()
        self._run = builtin_run.Component()
        self._workdir = builtin_workdir.Component()
        self._queuesentinal = builtin_queuesentinel.Component()
        for item in [
            self._dnf,
            self._service,
            self._transfer,
            self._run,
            self._workdir,
            self._queuesentinal,
        ]:
            item.driver = drivers.BaseDriver(args=self.args)

    def tearDown(self):
        self.mock_q_patched.stop()

    def test_options_converter(self):
        self.components.args()
        self.components.options_converter(
            documentation=tests.MOCK_DOCUMENTATION
        )
        known_args, unknown_args = self.components.exec_parser(
            self.components.parser, exec_array=["--snake-case", "test"]
        )
        self.assertEqual(
            vars(known_args),
            {
                "skip_cache": False,
                "run_once": False,
                "timeout": 600,
                "force_lock": False,
                "snake_case": "test",
                "opt0": "*.json",
                "opt1": None,
                "opt2": False,
            },
        )
        self.assertEqual(unknown_args, list())

    def test_exec_parser(self):
        self.components.args()
        with self.assertRaises(SystemExit):
            self.components.exec_parser(
                self.components.parser, exec_array=["--exec-help"]
            )

    def test_sanitize_args(self):
        result = self.components.sanitized_args(execute=self.execute)
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

    def test_set_cache(self):
        self.components.set_cache(
            cache=self.fake_cache, key="key1", value="value1"
        )

    def test_set_cache_value_update(self):
        self.components.set_cache(
            cache=self.fake_cache,
            key="key1",
            value="value1",
            value_update=True,
        )

    def test_set_cache_value_expire_tag(self):
        self.components.set_cache(
            cache=self.fake_cache,
            key="key1",
            value="value1",
            expire=12345,
            tag="test",
        )

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    def test__run_transfer_exists(self, mock_isfile, mock_file_sha3_224):
        mock_isfile.return_value = True
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, return_info = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(
            stdout,
            (
                "File exists /test/file and SHA3_224"
                " YYYYYYYYY matches, nothing to transfer"
            ),
        )
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    def test__run_transfer_exists_blueprinted(
        self, mock_isfile, mock_file_sha3_224
    ):
        mock_isfile.return_value = True
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                job_id="XXXXXX",
                blueprint=True,
            )
            stdout, stderr, outcome, return_info = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(
            stdout,
            "File exists /test/file and SHA3_224 YYYYYYYYY matches,"
            " nothing to transfer",
        )
        self.assertEqual(stderr, None)
        self.assertEqual(outcome, True)

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_exists(
        self, mock_log_debug, mock_isfile, mock_file_sha3_224
    ):
        mock_isfile.return_value = False
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, return_info = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(stdout, None)
        self.assertEqual(outcome, False)
        mock_log_debug.assert_called()

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_exists_blueprinted(
        self, mock_log_debug, mock_isfile, mock_file_sha3_224
    ):
        mock_isfile.return_value = False
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                blueprint=True,
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, return_info = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(stdout, None)
        self.assertEqual(outcome, False)
        mock_log_debug.assert_called()

    @patch("pwd.getpwnam", autospec=True)
    @patch("grp.getgrnam", autospec=True)
    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_chown_str(
        self,
        mock_log_debug,
        mock_chown,
        mock_isfile,
        mock_file_sha3_224,
        mock_pwd,
        mock_grp,
    ):
        mock_isfile.return_value = False
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        uid = MagicMock()
        uid.pw_uid = 9999
        mock_pwd.return_value = uid
        gid = MagicMock()
        gid.mock_grp = 9999
        mock_grp.return_value = gid
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                user="nobody",
                group="nobody",
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, return_info = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(stdout, None)
        self.assertEqual(outcome, False)
        mock_log_debug.assert_called()

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_chown_int(
        self,
        mock_log_debug,
        mock_chown,
        mock_isfile,
        mock_file_sha3_224,
    ):
        mock_isfile.return_value = False
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                user=9999,
                group=9999,
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, _ = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(stdout, None)
        self.assertEqual(outcome, False)
        mock_log_debug.assert_called()

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chmod", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test__run_transfer_not_mode(
        self,
        mock_log_debug,
        mock_chmod,
        mock_isfile,
        mock_file_sha3_224,
    ):
        mock_isfile.return_value = False
        mock_file_sha3_224.return_value = "YYYYYYYYY"
        with patch("builtins.open", unittest.mock.mock_open()):
            job = dict(
                file_to="/test/file",
                file_sha3_224="YYYYYYYYY",
                mode="0o777",
                job_id="XXXXXX",
            )
            stdout, stderr, outcome, _ = self._transfer.client(
                cache=tests.FakeCache(),
                job=job,
            )
        self.assertEqual(stdout, None)
        self.assertEqual(outcome, False)
        mock_log_debug.assert_called()

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__dnf_command_success(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._dnf.client(
            cache=tests.FakeCache(),
            job={"packages": ["kernel", "gcc"]},
        )
        calls = [call(command="dnf -q -y install kernel gcc", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__dnf_command_fail(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", False]
        stdout, stderr, outcome, return_info = self._dnf.client(
            cache=tests.FakeCache(),
            job={"packages": ["kernel", "gcc"]},
        )
        calls = [call(command="dnf -q -y install kernel gcc", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertFalse(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__dnf_command_clear_cache(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._dnf.client(
            cache=tests.FakeCache(),
            job={"packages": ["kernel", "gcc"], "clear": True},
        )
        calls = [
            call(command="dnf clean all", env=None),
            call(command="dnf makecache", env=None),
            call(command="dnf -q -y install kernel gcc", env=None),
        ]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__dnf_command_latest(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._dnf.client(
            cache=tests.FakeCache(),
            job={"packages": ["kernel", "gcc"], "state": "latest"},
        )
        calls = [
            call(command="dnf list --installed kernel", env=None),
            call(command="dnf list --installed gcc", env=None),
            call(command="dnf -q -y update kernel gcc", env=None),
        ]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__dnf_command_absent(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._dnf.client(
            cache=tests.FakeCache(),
            job={"packages": ["kernel", "gcc"], "state": "absent"},
        )
        calls = [call(command="dnf -q -y remove kernel gcc", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_success(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={"services": ["httpd.service"]},
        )
        calls = [call(command="systemctl start httpd.service", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_fail(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", False]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={"services": ["httpd.service"]},
        )
        calls = [call(command="systemctl start httpd.service", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertFalse(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_enable_success(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={"services": ["httpd.service"], "state": "enable"},
        )
        calls = [
            call(command="systemctl enable httpd.service", env=None),
            call(command="systemctl start httpd.service", env=None),
        ]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertTrue(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_enable_fail(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", False]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={"services": ["httpd.service"], "state": "enable"},
        )
        calls = [call(command="systemctl enable httpd.service", env=None)]
        self.assertEqual(mock_run_command.call_args_list, calls)
        self.assertFalse(outcome)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_disable_success(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={
                "services": ["httpd.service"],
                "running": "stop",
                "state": "disable",
            },
        )
        calls = [
            call(command="systemctl disable httpd.service", env=None),
            call(command="systemctl stop httpd.service", env=None),
        ]
        self.assertTrue(outcome)
        self.assertEqual(mock_run_command.call_args_list, calls)

    @patch("subprocess.Popen")
    def test_run_command_success(self, popen):
        popen.return_value = tests.FakePopen()
        stdout, _, outcome = components.ComponentBase().run_command(
            command="test_command"
        )
        self.assertEqual(stdout, "stdout")
        self.assertEqual(outcome, True)

    @patch("subprocess.Popen")
    def test_run_command_fail(self, popen):
        popen.return_value = tests.FakePopen(return_code=1)
        _, stderr, outcome = components.ComponentBase().run_command(
            command="test_command"
        )
        self.assertEqual(stderr, "stderr")
        self.assertEqual(outcome, False)

    @patch("subprocess.Popen")
    def test_run_command_success_env(self, popen):
        popen.return_value = tests.FakePopen()
        with patch("os.environ", {"testBaseEnv": "value"}):
            stdout, _, outcome = components.ComponentBase().run_command(
                command="test_command", env={"testEnv": "value"}
            )
        self.assertEqual(stdout, "stdout")
        self.assertEqual(outcome, True)
        popen.assert_called_with(
            "test_command",
            stdout=-1,
            stderr=-1,
            executable="/bin/sh",
            env={"testBaseEnv": "value", "testEnv": "value"},
            shell=True,
            start_new_session=False,
        )

    @patch("subprocess.Popen")
    def test_run_command_return_codes_int(self, popen):
        popen.return_value = tests.FakePopen()
        with patch("os.environ", {"testBaseEnv": "value"}):
            stdout, _, outcome = components.ComponentBase().run_command(
                command="test_command", return_codes=99
            )
        self.assertEqual(stdout, "stdout")
        self.assertEqual(outcome, False)
        popen.assert_called_with(
            "test_command",
            stdout=-1,
            stderr=-1,
            executable="/bin/sh",
            env={"testBaseEnv": "value"},
            shell=True,
            start_new_session=False,
        )

    @patch("subprocess.Popen")
    def test_run_command_return_codes_list(self, popen):
        popen.return_value = tests.FakePopen()
        with patch("os.environ", {"testBaseEnv": "value"}):
            stdout, _, outcome = components.ComponentBase().run_command(
                command="test_command", return_codes=[0, 99]
            )
        self.assertEqual(stdout, "stdout")
        self.assertEqual(outcome, True)
        popen.assert_called_with(
            "test_command",
            stdout=-1,
            stderr=-1,
            executable="/bin/sh",
            env={"testBaseEnv": "value"},
            shell=True,
            start_new_session=False,
        )

    @patch("logging.Logger.info", autospec=True)
    def test_file_blueprinter(self, mock_log_info):
        fake_cache = tests.FakeCache()
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=tests.TEST_BLUEPRINT_CONTENT),
        ):
            success, _ = self.components.file_blueprinter(
                cache=fake_cache, file_to="/test/file1"
            )
            self.assertTrue(success)
        mock_log_info.assert_called()

    @patch("logging.Logger.critical", autospec=True)
    def test_file_blueprinter_failed(self, mock_log_critical):
        fake_cache = tests.FakeCache()
        success, _ = self.components.file_blueprinter(
            cache=fake_cache, file_to="/test/file1"
        )
        self.assertFalse(success)
        mock_log_critical.assert_called()

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__run_command(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        self._run.client(
            cache=tests.FakeCache(),
            job={"command": "command {{ test }} test"},
        )
        mock_run_command.assert_called_with(
            command="command 1 test", env=None, no_block=None
        )

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__run_command_stdout_args(self, mock_run_command):
        mock_run_command.return_value = [b"testing", b"", True]
        fake_cache = tests.FakeCache()
        self._run.client(
            cache=fake_cache,
            job={
                "command": "command {{ test }} test",
                "stdout_arg": "VALUE1",
            },
        )
        mock_run_command.assert_called_with(
            command="command 1 test", env=None, no_block=None
        )

    @patch("os.makedirs", autospec=True)
    def test__run_workdir(self, mock_makedirs):
        fake_cache = tests.FakeCache()
        self._workdir.client(cache=fake_cache, job={"workdir": "/test/path"})
        mock_makedirs.assert_called_with("/test/path", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    def test__run_workdir_jinja(self, mock_makedirs):
        fake_cache = tests.FakeCache()
        self._workdir.client(
            cache=fake_cache,
            job={"workdir": "/test/{{ test }}"},
        )
        mock_makedirs.assert_called_with("/test/1", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    def test__run_workdir_null(self, mock_makedirs):
        fake_cache = tests.FakeCache()
        self._workdir.client(cache=fake_cache, job={"workdir": ""})

    @patch("os.chmod", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test__run_workdir_mode(self, mock_makedirs, mock_chmod):
        fake_cache = tests.FakeCache()
        self._workdir.client(
            cache=fake_cache,
            job={"workdir": "/test/path", "mode": "0o777"},
        )
        mock_makedirs.assert_called_with("/test/path", exist_ok=True)
        mock_chmod.assert_called()

    @patch("os.chown", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test__run_workdir_mode_user_group(self, mock_makedirs, mock_chown):
        fake_cache = tests.FakeCache()
        self._workdir.client(
            cache=fake_cache,
            job={"workdir": "/test/path", "user": 9999, "group": 9999},
        )
        mock_makedirs.assert_called_with("/test/path", exist_ok=True)
        mock_chown.assert_called()

    def test_blueprinter(self):
        _, blueprinted_content = self.components.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT, values={"test": 1}
        )
        self.assertEqual(blueprinted_content, "This is a blueprint string 1")

    def test_blueprinter_no_values(self):
        _, blueprinted_content = self.components.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT, values=None
        )
        self.assertEqual(
            blueprinted_content, "No arguments were defined for blueprinting"
        )

    @patch("logging.Logger.debug", autospec=True)
    def test_blueprinter_failed(self, mock_log_debug):
        _, blueprinted_content = self.components.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT.encode(), values={"test": 1}
        )
        self.assertEqual(
            blueprinted_content, "Can't compile non template nodes"
        )
        mock_log_debug.assert_called()
