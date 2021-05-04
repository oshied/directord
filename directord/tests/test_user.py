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

import directord

from directord import tests
from directord import user


class TestUser(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.user = user.User(args=self.args)

    def tearDown(self):
        pass

    def test_send_data(self):
        user.directord.socket.socket = tests.MockSocket
        returned = directord.send_data(
            socket_path=self.args.socket_path, data="test"
        )
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

    @patch("directord.send_data", autospec=True)
    def test_poll_job_unknown(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node1"],
                    "NODES": ["hostname-node1", "hostname-node2"],
                    "PROCESSING": "UNDEFINED",
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, None)
        self.assertEqual(info, "Job in an unknown state: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_success(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node"],
                    "NODES": ["hostname-node"],
                    "PROCESSING": b"\004".decode(),
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, True)
        self.assertEqual(info, "Job Success: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_failed(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "FAILED": ["hostname-node"],
                    "NODES": ["hostname-node"],
                    "PROCESSING": b"\025".decode(),
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, False)
        self.assertEqual(info, "Job Failed: test-id")

    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    @patch("directord.send_data", autospec=True)
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

    @patch("directord.send_data", autospec=True)
    def test_run_override_list_jobs(self, mock_send_data):
        self.manage.run(override="list-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "list-jobs"}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_list_nodes(self, mock_send_data):
        self.manage.run(override="list-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "list-nodes"}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_purge_jobs(self, mock_send_data):
        self.manage.run(override="purge-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "purge-jobs"}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_purge_nodes(self, mock_send_data):
        self.manage.run(override="purge-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": "purge-nodes"}'
        )

    @patch("directord.user.Manage.generate_certificates", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_run_override_generate_keys(
        self, mock_send_data, mock_generate_certificates
    ):
        self.manage.run(override="generate-keys")
        mock_send_data.assert_not_called()
