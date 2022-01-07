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

from unittest.mock import patch
from unittest.mock import MagicMock

from directord import bootstrap
from directord import tests
from directord import utils


class Testbootstrap(tests.TestConnectionBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        self.patch_spinner = patch("directord.Spinner")
        self.patch_spinner.start()
        self.bootstrap = bootstrap.Bootstrap(
            catalog=self.args.catalog,
            key_file=self.args.key_file,
            threads=self.args.threads,
            debug=self.args.debug,
        )
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

        # Fake SSH
        self.mock_ssh = utils.SSHConnect(
            host="test", username="tester", port=22
        ).__enter__()

        self.mock_chan_patched = patch.object(self.mock_ssh, "session")
        self.mock_chan = self.mock_chan_patched.start()
        self.mock_chan.sftp_new = MagicMock(return_value=self.fakechannel)
        self.mock_chan.scp_new = MagicMock(return_value=self.fakechannel)
        self.mock_chan.channel_new = MagicMock(return_value=self.fakechannel)
        self.mock_stat_patched = patch("directord.os.stat")
        self.mock_stat = self.mock_stat_patched.start()

    def tearDown(self):
        super().tearDown()
        self.patch_spinner.stop()
        self.mock_chan_patched.stop()
        self.mock_stat_patched.stop()
        self.mock_ssh.sock.close()

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
        return_data = self.bootstrap.bootstrap_catalog_entry(entry=entry)
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
        return_data = self.bootstrap.bootstrap_catalog_entry(entry=entry)
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
        return_data = self.bootstrap.bootstrap_catalog_entry(entry=entry)
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

    def test_bootstrap_catalog_entry_args_assumed_username(self):
        entry = {
            "args": {
                "port": 22,
            },
            "targets": [
                {
                    "host": "example.com",
                    "port": 2222,
                }
            ],
            "jobs": {"RUN": "command1"},
        }
        with patch("directord.bootstrap.getpass.getuser") as p:
            p.return_value = "assumed-user1"
            return_data = self.bootstrap.bootstrap_catalog_entry(entry=entry)

        self.assertEqual(
            return_data,
            [
                {
                    "host": "example.com",
                    "jobs": {"RUN": "command1"},
                    "port": 2222,
                    "username": "assumed-user1",
                }
            ],
        )

    def test_bootstrap_localfile_padding_shared(self):
        orig_prefix = bootstrap.sys.prefix
        orig_base_prefix = bootstrap.sys.base_prefix
        try:
            bootstrap.sys.prefix = "/test/path"
            bootstrap.sys.base_prefix = "/test/path"
            return_data = self.bootstrap.bootstrap_localfile_padding(
                localfile="file1"
            )
        finally:
            bootstrap.sys.prefix = orig_prefix
            bootstrap.sys.base_prefix = orig_base_prefix

        self.assertEqual(return_data, "/test/path/share/directord/tools/file1")

    def test_bootstrap_localfile_padding_shared_venv(self):
        orig_prefix = bootstrap.sys.prefix
        orig_base_prefix = bootstrap.sys.base_prefix
        try:
            bootstrap.sys.prefix = "/usr"
            bootstrap.sys.base_prefix = "/test/path"
            return_data = self.bootstrap.bootstrap_localfile_padding(
                localfile="file1"
            )
        finally:
            bootstrap.sys.prefix = orig_prefix
            bootstrap.sys.base_prefix = orig_base_prefix

        self.assertEqual(return_data, "/usr/share/directord/tools/file1")

    def test_bootstrap_localfile_padding_absolute(self):
        return_data = self.bootstrap.bootstrap_localfile_padding(
            localfile="/file1"
        )
        self.assertEqual(return_data, "/file1")

    def test_bootstrap_flatten_jobs(self):
        return_data = self.bootstrap.bootstrap_flatten_jobs(
            jobs=[["one", "two"], "three", "four"]
        )
        self.assertEqual(return_data, ["one", "two", "three", "four"])

    def test_bootstrap_run(self):
        job_def = {
            "host": "String",
            "port": 22,
            "username": "String",
            "key_file": None,
            "jobs": [{"RUN": "command 1", "ADD": "from to", "GET": "from to"}],
        }
        with patch("directord.utils.SSHConnect") as mock_ssh:
            mock_ssh.return_value = self.mock_ssh
            with patch.object(self.fakechannel, "read") as mock_read:
                mock_read.side_effect = [(5, b"start\n"), (0, b"end\n")]
                self.bootstrap.bootstrap_run(job_def=job_def, catalog={})

    def test_bootstrap_file_send(self):
        self.mock_stat.return_value = tests.FakeStat(uid=99, gid=99)
        m = unittest.mock.mock_open(read_data=b"testing")
        with patch("builtins.open", m):
            self.bootstrap.bootstrap_file_send(
                ssh=self.mock_ssh, localfile="/file1", remotefile="/file2"
            )

    def test_bootstrap_file_get(self):
        self.mock_stat.return_value = tests.FakeStat(uid=99, gid=99)
        m = unittest.mock.mock_open(read_data=b"testing")
        with patch("builtins.open", m):
            self.bootstrap.bootstrap_file_send(
                ssh=self.mock_ssh, localfile="/file1", remotefile="/file2"
            )

    def test_bootstrap_exec(self):
        with patch.object(self.fakechannel, "read") as mock_read:
            mock_read.side_effect = [(5, b"start\n"), (0, b"end\n")]
            self.bootstrap.bootstrap_exec(
                ssh=self.mock_ssh, command="command1", catalog={}
            )
        for _, value in self.mock_ssh.channels.items():
            value.request_exec.assert_called_with("command1")

    def test_bootstrap_exec_failure(self):
        with patch.object(self.fakechannel, "get_exit_status") as mock_status:
            mock_status.return_value = 1
            with patch.object(self.fakechannel, "read") as mock_read:
                mock_read.side_effect = [(5, b"start\n"), (0, b"end\n")]
                self.assertRaises(
                    SystemExit,
                    self.bootstrap.bootstrap_exec,
                    self.mock_ssh,
                    "command1",
                    {},
                )

    def test_bootstrap_exec_jinja(self):
        with patch.object(self.fakechannel, "read") as mock_read:
            mock_read.side_effect = [(5, b"start\n"), (0, b"end\n")]
            self.bootstrap.bootstrap_exec(
                ssh=self.mock_ssh,
                command="command {{ test }} test",
                catalog={"test": 1},
            )
        for _, value in self.mock_ssh.channels.items():
            value.request_exec.assert_called_with("command 1 test")

    @patch("queue.Queue", autospec=True)
    def test_bootstrap_q_processor(self, mock_queue):
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
        with patch("directord.utils.SSHConnect") as mock_ssh:
            mock_ssh.return_value = self.mock_ssh
            with patch.object(self.fakechannel, "read") as mock_read:
                mock_read.side_effect = [(5, b"start\n"), (0, b"end\n")]
                self.bootstrap.bootstrap_q_processor(
                    queue=mock_queue, catalog={}
                )

    @patch("directord.bootstrap.Bootstrap.run_threads", autospec=True)
    def test_bootstrap_cluster(self, mock_threads):
        try:
            self.bootstrap.catalog = ["/file.yaml"]
            self.bootstrap.threads = 3
            m = unittest.mock.mock_open(read_data=tests.TEST_CATALOG.encode())
            with patch("builtins.open", m):
                self.bootstrap.bootstrap_cluster()
        finally:
            self.args = tests.FakeArgs()
        mock_threads.assert_called()
