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
from directord.components import builtin_wait
from directord.components.lib.podman import PodmanConnect
from directord.components.lib.podman import PodmanPod
from directord.components.lib.podman import PodmanImage
from directord.components.lib.podman import PodmanClient


class TestComponents(tests.TestBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        with patch("directord.plugin_import", autospec=True):
            self.client = client.Client(args=self.args)

        self.patched_get_queue = patch(
            "directord.utils.DurableQueue", autospec=True
        )
        self.patched_get_queue.start()
        self.patched_get_queue.return_value = tests.FakeQueue()
        self.client.q_processes = tests.FakeQueue()
        self.client.q_return = tests.FakeQueue()
        self.fake_cache = tests.FakeCache()
        self.components = components.ComponentBase(desc="test")
        self.execute = ["long '{{ jinja }}' quoted string", "string"]
        self._dnf = builtin_dnf.Component()
        self._service = builtin_service.Component()
        self._transfer = builtin_copy.Component()
        self._run = builtin_run.Component()
        self._workdir = builtin_workdir.Component()
        self._queuesentinal = builtin_queuesentinel.Component()
        self._wait = builtin_wait.Component()
        self.podman_connect = PodmanConnect
        self.podman_image = PodmanImage
        self.podman_pod = PodmanPod
        self.podman_client = PodmanClient
        self.p_image = self.podman_image("/tmp/socket")
        self.pod = self.podman_pod("/tmp/socket")
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
        super().tearDown()
        self.patched_get_queue.stop()

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
                "stdout_arg": None,
                "stderr_arg": None,
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
    def test__run_transfer_not_exists(self, mock_isfile, mock_file_sha3_224):
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

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    def test__run_transfer_not_exists_blueprinted(
        self, mock_isfile, mock_file_sha3_224
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

    @patch("pwd.getpwnam", autospec=True)
    @patch("grp.getgrnam", autospec=True)
    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    def test__run_transfer_not_chown_str(
        self,
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

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chown", autospec=True)
    def test__run_transfer_not_chown_int(
        self,
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

    @patch("directord.utils.file_sha3_224", autospec=True)
    @patch("os.path.isfile", autospec=True)
    @patch("os.chmod", autospec=True)
    def test__run_transfer_not_mode(
        self,
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
            call(command="dnf -q -y --best install kernel gcc", env=None),
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

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__service_command_reload_success(self, mock_run_command):
        mock_run_command.return_value = [b"", b"", True]
        stdout, stderr, outcome, return_info = self._service.client(
            cache=tests.FakeCache(),
            job={"services": ["httpd.service"], "running": "reload"},
        )
        calls = [
            call(command="systemctl reload httpd.service", env=None),
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

    def test_file_blueprinter(self):
        fake_cache = tests.FakeCache()
        with patch(
            "builtins.open",
            unittest.mock.mock_open(read_data=tests.TEST_BLUEPRINT_CONTENT),
        ):
            success, _ = self.components.file_blueprinter(
                cache=fake_cache, file_to="/test/file1"
            )
            self.assertTrue(success)

    def test_file_blueprinter_failed(self):
        fake_cache = tests.FakeCache()
        success, _ = self.components.file_blueprinter(
            cache=fake_cache, file_to="/test/file1"
        )
        self.assertFalse(success)

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

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    def test__run_command_stderr_args(self, mock_run_command):
        mock_run_command.return_value = [b"testing", b"errors", True]
        fake_cache = tests.FakeCache()
        self._run.client(
            cache=fake_cache,
            job={
                "command": "command {{ test }} test",
                "stdout_arg": "VALUE1",
                "stderr_arg": "VALUE2",
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

    def test_blueprinter_failed(self):
        _, blueprinted_content = self.components.blueprinter(
            content=tests.TEST_BLUEPRINT_CONTENT.encode(), values={"test": 1}
        )
        self.assertEqual(
            blueprinted_content, "Can't compile non template nodes"
        )

    @patch("time.sleep")
    def test_wait_seconds(self, mock_sleep):
        stdout, stderr, outcome, return_info = self._wait.client(
            cache=tests.FakeCache(), job={"seconds": 5}
        )
        self.assertTrue(outcome)

        mock_sleep.assert_called_once_with(5)

    @patch("requests.get")
    @patch("time.sleep")
    def test_wait_url(self, mock_sleep, mock_get):
        r_500 = MagicMock()
        r_500.status_code = 500
        r_400 = MagicMock()
        r_400.status_code = 400
        r_200 = MagicMock()
        r_200.status_code = 200
        mock_get.side_effect = [r_500, r_400, r_200]

        stdout, stderr, outcome, return_info = self._wait.client(
            cache=tests.FakeCache(),
            job={"url": "http://localhost", "retry": 5, "retry_wait": 5},
        )
        self.assertTrue(outcome)

        sleep_calls = [call(5), call(5)]
        self.assertEqual(mock_sleep.mock_calls, sleep_calls)
        get_calls = [
            call("http://localhost", verify=True),
            call("http://localhost", verify=True),
            call("http://localhost", verify=True),
        ]
        self.assertEqual(mock_get.mock_calls, get_calls)

    @patch("requests.get")
    @patch("time.sleep")
    def test_wait_url_fail(self, mock_sleep, mock_get):
        r_500 = MagicMock()
        r_500.status_code = 500
        mock_get.return_value = r_500
        stdout, stderr, outcome, return_info = self._wait.client(
            cache=tests.FakeCache(),
            job={"url": "http://localhost", "insecure": True},
        )
        self.assertFalse(outcome)
        mock_get.assert_called_once_with("http://localhost", verify=False)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    @patch("time.sleep")
    def test_wait_cmd(self, mock_sleep, mock_run_command):
        mock_run_command.side_effect = [
            (b"", b"", False),
            (b"", b"", True),
        ]
        stdout, stderr, outcome, return_info = self._wait.client(
            cache=tests.FakeCache(),
            job={
                "command": "curl -k http://google.com",
                "retry": 5,
                "retry_wait": 5,
            },
        )
        self.assertTrue(outcome)

        mock_sleep.assert_called_once_with(5)
        run_calls = [
            call(command="curl -k http://google.com", env=None),
            call(command="curl -k http://google.com", env=None),
        ]
        self.assertEqual(mock_run_command.mock_calls, run_calls)

    @patch("directord.components.ComponentBase.run_command", autospec=True)
    @patch("time.sleep")
    def test_wait_cmd_fail(self, mock_sleep, mock_run_command):
        mock_run_command.return_value = (b"", b"", False)

        stdout, stderr, outcome, return_info = self._wait.client(
            cache=tests.FakeCache(), job={"command": "foo"}
        )
        self.assertFalse(outcome)

        mock_sleep.assert_not_called()
        mock_run_command.assert_called_once_with(command="foo", env=None)

    @patch("directord.components.lib.podman.PodmanClient", autospec=True)
    def test_podman_connect_call(self, mock_podman_client):
        mock_podman_client.return_value.api = MagicMock()
        self.podman_connect()
        mock_podman_client.assert_called_with(
            base_url="unix:///var/run/podman/podman.sock"
        )
        self.podman_connect("/path/to/file")
        mock_podman_client.assert_called_with(base_url="unix:///path/to/file")

    @patch("directord.components.lib.podman.PodmanClient", autospec=True)
    def test_podman_pod(self, mock_podman_client):
        mock_podman_client.return_value.api = MagicMock()
        self.podman_pod("/var/run/podman/podman.sock")
        mock_podman_client.assert_called_with(
            base_url="unix:///var/run/podman/podman.sock"
        )
        self.podman_pod("/path/to/file")
        mock_podman_client.assert_called_with(base_url="unix:///path/to/file")

    @patch("directord.components.lib.podman.PodmanClient", autospec=True)
    def test_podman_image(self, mock_podman_client):
        mock_podman_client.return_value.api = MagicMock()
        self.podman_image("/var/run/podman/podman.sock")
        mock_podman_client.assert_called_with(
            base_url="unix:///var/run/podman/podman.sock"
        )
        self.podman_image("/path/to/file")
        mock_podman_client.assert_called_with(base_url="unix:///path/to/file")

    def test_podman_pod_decode(self):
        data = b"test data"
        decoded = self.podman_pod._decode(data)
        self.assertEqual(decoded, data.decode())
        data = b'{"test data": "111"}'
        decoded = self.podman_pod._decode(data)
        self.assertEqual(decoded, {"test data": "111"})

    def test_podman_image_decode(self):
        data = b"test data"
        decoded = self.podman_image._decode(data)
        self.assertEqual(decoded, data.decode())
        data = b'{"test data": "111"}'
        decoded = self.podman_image._decode(data)
        self.assertEqual(decoded, {"test data": "111"})

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_pod_start(self, mock_client_post):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"sha256"),
                "name": "test_pod",
                "kwargs": {"name": "test_pod"},
                "post_dict": {
                    "path": "/pods/test_pod/start",
                    "params": {"t": 120},
                },
                "result": (True, "sha256"),
            },
            {
                "mock": MagicMock(ok=False, content=b""),
                "name": "test_pod2",
                "kwargs": {"name": "test_pod2", "timeout": 60},
                "post_dict": {
                    "path": "/pods/test_pod2/start",
                    "params": {"t": 60},
                },
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_post.return_value = data["mock"]
            pod_start = self.pod.start(**data["kwargs"])
            mock_client_post.assert_called_with(
                self.pod.api, **data["post_dict"]
            )
            self.assertEqual(pod_start, data["result"])

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_pod_stop(self, mock_client_post):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"sha256"),
                "name": "test_pod",
                "kwargs": {"name": "test_pod"},
                "post_dict": {
                    "path": "/pods/test_pod/stop",
                    "params": {"t": 120},
                },
                "result": (True, "sha256"),
            },
            {
                "mock": MagicMock(ok=False, content=b""),
                "name": "test_pod2",
                "kwargs": {"name": "test_pod2", "timeout": 60},
                "post_dict": {
                    "path": "/pods/test_pod2/stop",
                    "params": {"t": 60},
                },
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_post.return_value = data["mock"]
            pod_stop = self.pod.stop(**data["kwargs"])
            mock_client_post.assert_called_with(
                self.pod.api, **data["post_dict"]
            )
            self.assertEqual(pod_stop, data["result"])

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_pod_kill(self, mock_client_post):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"sha256"),
                "name": "test_pod",
                "kwargs": {"name": "test_pod"},
                "post_dict": {
                    "path": "/pods/test_pod/kill",
                    "params": {"signal": "SIGKILL"},
                },
                "result": (True, "sha256"),
            },
            {
                "mock": MagicMock(ok=False, content=b""),
                "name": "test_pod2",
                "kwargs": {"name": "test_pod2", "signal": "SIGTERM"},
                "post_dict": {
                    "path": "/pods/test_pod2/kill",
                    "params": {"signal": "SIGTERM"},
                },
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_post.return_value = data["mock"]
            pod_stop = self.pod.kill(**data["kwargs"])
            mock_client_post.assert_called_with(
                self.pod.api, **data["post_dict"]
            )
            self.assertEqual(pod_stop, data["result"])

    @patch("podman.api.client.APIClient.delete", autospec=True)
    def test_podman_pod_rm(self, mock_client_del):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"sha256"),
                "name": "test_pod",
                "kwargs": {"name": "test_pod"},
                "delete_dict": {
                    "path": "/pods/test_pod",
                    "params": {"force": False},
                },
                "result": (True, "sha256"),
            },
            {
                "mock": MagicMock(ok=False, content=b""),
                "name": "test_pod2",
                "kwargs": {"name": "test_pod2", "force": True},
                "delete_dict": {
                    "path": "/pods/test_pod2",
                    "params": {"force": True},
                },
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_del.return_value = data["mock"]
            pod_rm = self.pod.rm(**data["kwargs"])
            mock_client_del.assert_called_with(
                self.pod.api, **data["delete_dict"]
            )
            self.assertEqual(pod_rm, data["result"])

    @patch("podman.api.client.APIClient.get", autospec=True)
    def test_podman_pod_inspect(self, mock_client_get):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b'{"test": "data"}'),
                "name": "test_pod",
                "kwargs": {"name": "test_pod"},
                "get_dict": {"path": "/pods/test_pod/json"},
                "result": (True, {"test": "data"}),
            },
            {
                "mock": MagicMock(ok=False, content=None),
                "name": "test_pod2",
                "kwargs": {"name": "test_pod2"},
                "get_dict": {"path": "/pods/test_pod2/json"},
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_get.return_value = data["mock"]
            pod_rm = self.pod.inspect(**data["kwargs"])
            mock_client_get.assert_called_with(
                self.pod.api, **data["get_dict"]
            )
            self.assertEqual(pod_rm, data["result"])

    @patch("yaml.safe_load", autospec=True)
    @patch("builtins.open")
    @patch("os.path.exists", autospec=True)
    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_pod_play(
        self, mock_client_post, mock_file_exists, mopen, myaml
    ):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"sha256"),
                "kwargs": {"pod_file": "/path/to/file"},
                "post_dict": {
                    "path": "/play/kube",
                    "params": {"tlsVerify": True, "start": True},
                    "data": '{"pod": "kube_pod"}',
                },
                "result": (True, "sha256"),
            },
            {
                "mock": MagicMock(ok=False, content=None),
                "kwargs": {"pod_file": "/path/to/file", "tlsverify": False},
                "post_dict": {
                    "path": "/play/kube",
                    "params": {"tlsVerify": False, "start": True},
                    "data": '{"pod": "kube_pod"}',
                },
                "result": (False, None),
            },
        )
        for data in test_data:
            mock_client_post.return_value = data["mock"]
            mock_file_exists.return_value = True
            myaml.return_value = {"pod": "kube_pod"}
            pod_play = self.pod.play(**data["kwargs"])
            mock_client_post.assert_called_with(
                self.pod.api, **data["post_dict"]
            )
            self.assertEqual(pod_play, data["result"])
        mock_client_post.return_value = data["mock"]
        mock_file_exists.return_value = False
        pod_play = self.pod.play(**data["kwargs"])
        self.assertEqual(pod_play, (False, "Pod YAML did not exist"))

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_pod_exec_run(self, mock_client_post):
        test_data = {
            "mock": MagicMock(ok=True, content=b'{"Id": "sha256"}'),
            "name": "test_pod",
            "kwargs": {"name": "test_pod", "command": "ls /", "env": {}},
            "post_dict": {
                "path": "/pods/test_pod/kill",
                "params": {"signal": "SIGKILL"},
            },
            "result": (True, "sha256"),
        }
        mock_client_post.return_value = test_data["mock"]
        self.pod.exec_run(**test_data["kwargs"])
        calls = [
            call(
                self.pod.api,
                path="/containers/test_pod/exec",
                data=(
                    '{"AttachStderr": true, "AttachStdin": true, '
                    '"AttachStdout": true, "Cmd": "ls /", "Env": {}, '
                    '"Privileged": false, "Tty": true}'
                ),
            ),
            call(
                self.pod.api,
                path="/exec/sha256/start",
                data=('{"Detach": false, "Tty": true}'),
            ),
        ]
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_pull(self, mock_client_post):
        test_data = (
            {
                "mock": MagicMock(ok=True, content=b"image_pull_sha"),
                "kwargs": {"images": ["image1"]},
                "post_dict": {
                    "path": "/images/pull",
                    "params": {"reference": "image1", "tlsVerify": True},
                },
                "result": (True, "image_pull_sha"),
            },
            {
                "mock": MagicMock(ok=True, content=b'r{"error": "some err"}'),
                "kwargs": {"images": ["image2"], "tlsverify": False},
                "post_dict": {
                    "path": "/images/pull",
                    "params": {"reference": "image2", "tlsVerify": False},
                },
                "result": (False, 'r{"error": "some err"}'),
            },
        )
        for data in test_data:
            mock_client_post.return_value = data["mock"]
            img = self.p_image.pull(**data["kwargs"])
            mock_client_post.assert_called_with(
                self.p_image.api, **data["post_dict"]
            )
            self.assertEqual(img, data["result"])

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_pull_multi(self, mock_client_post):
        mock_client_post.side_effect = (
            MagicMock(ok=True, content=b"image_pull_sha"),
            MagicMock(ok=True, content=b"image_pull_sha2"),
        )
        img = self.p_image.pull(
            **{"images": ["image1", "image2"], "tlsverify": False}
        )
        calls = [
            call(
                self.p_image.api,
                path="/images/pull",
                params=({"reference": im, "tlsVerify": False}),
            )
            for im in ["image1", "image2"]
        ]
        self.assertEqual(img, (True, "image_pull_sha\nimage_pull_sha2"))
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_pull_multi_fail(self, mock_client_post):
        mock_client_post.side_effect = (
            MagicMock(ok=True, content=b'r{"error": "some err"}'),
            MagicMock(ok=True, content=b"image_pull_sha2"),
        )
        img = self.p_image.pull(
            **{"images": ["image1", "image2"], "tlsverify": False}
        )
        calls = [
            call(
                self.p_image.api,
                path="/images/pull",
                params=({"reference": im, "tlsVerify": False}),
            )
            for im in ["image1", "image2"]
        ]
        self.assertEqual(
            img, (False, 'r{"error": "some err"}\nimage_pull_sha2')
        )
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_push_multi(self, mock_client_post):
        mock_client_post.side_effect = (
            MagicMock(ok=True, content=b"pushed"),
            MagicMock(ok=True, content=b"pushed2"),
        )
        img = self.p_image.push(
            **{"images": ["image1", "image2"], "tlsverify": False}
        )
        calls = [
            call(
                self.p_image.api,
                path="/images/%s/push" % im,
                params=({"tlsVerify": False}),
            )
            for im in ["image1", "image2"]
        ]
        self.assertEqual(img, (True, "pushed\npushed2"))
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_push_multi_fail(self, mock_client_post):
        mock_client_post.side_effect = (
            MagicMock(ok=True, content=b"pushed"),
            MagicMock(ok=False, content=b"not_pushed"),
        )
        img = self.p_image.push(**{"images": ["image1", "image2"]})
        calls = [
            call(
                self.p_image.api,
                path="/images/%s/push" % im,
                params={"tlsVerify": True},
            )
            for im in ["image1", "image2"]
        ]
        self.assertEqual(img, (False, "pushed\nnot_pushed"))
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.post", autospec=True)
    def test_podman_image_tag(self, mock_client_post):
        mock_client_post.return_value = MagicMock(ok=True, content=b"tagged")
        img = self.p_image.tag(**{"images": ["image1", "quay.io/image2"]})
        img = self.p_image.tag(
            **{"images": ["image3:montag", "quay.io/image4:new"]}
        )
        calls = [
            call(
                self.p_image.api,
                path="/images/image1/tag",
                params={"repo": "quay.io/image2", "tag": "latest"},
            ),
            call(
                self.p_image.api,
                path="/images/image3:montag/tag",
                params={"repo": "quay.io/image4", "tag": "new"},
            ),
        ]
        self.assertEqual(img, (True, "tagged"))
        self.assertEqual(mock_client_post.mock_calls, calls)

    @patch("podman.api.client.APIClient.get", autospec=True)
    def test_podman_image_list(self, mock_client_get):
        mock_client_get.side_effect = (
            MagicMock(ok=True, content=b'["image1", "image2"]'),
            MagicMock(ok=False, content=b""),
        )
        img = self.p_image.list()
        img2 = self.p_image.list()
        calls = [call(self.p_image.api, path="/images/json")] * 2
        self.assertEqual(img, (True, ["image1", "image2"]))
        self.assertEqual(img2, (False, None))
        self.assertEqual(mock_client_get.mock_calls, calls)

    @patch("podman.api.client.APIClient.get", autospec=True)
    def test_podman_image_inspect(self, mock_client_get):
        mock_client_get.side_effect = (
            MagicMock(ok=True, content=b'{"image1": "some_data"}'),
            MagicMock(ok=False, content=b""),
        )
        img = self.p_image.inspect(["image1"])
        img2 = self.p_image.inspect(["image2"])
        calls = [
            call(self.p_image.api, path="/images/image1/json"),
            call(self.p_image.api, path="/images/image2/json"),
        ]
        self.assertEqual(img, (True, {"image1": "some_data"}))
        self.assertEqual(img2, (False, []))
        self.assertEqual(mock_client_get.mock_calls, calls)

    @patch("podman.api.client.APIClient.get", autospec=True)
    def test_podman_image_inspect_multi(self, mock_client_get):
        mock_client_get.side_effect = (
            MagicMock(ok=True, content=b'[{"image1": "some_data"}]'),
            MagicMock(ok=True, content=b'[{"image2": "some_data2"}]'),
            MagicMock(ok=False, content=b""),
        )
        img = self.p_image.inspect(["image1", "image2", "image3"])
        calls = [
            call(self.p_image.api, path="/images/image1/json"),
            call(self.p_image.api, path="/images/image2/json"),
            call(self.p_image.api, path="/images/image3/json"),
        ]
        self.assertEqual(
            img, (False, [{"image1": "some_data"}, {"image2": "some_data2"}])
        )
        self.assertEqual(mock_client_get.mock_calls, calls)
