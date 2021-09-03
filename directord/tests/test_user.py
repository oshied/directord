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


class TestManager(tests.TestDriverBase):
    def setUp(self):
        super(TestManager, self).setUp()
        self.args = tests.FakeArgs()
        self.manage = user.Manage(args=self.args)
        self.manage.driver = self.mock_driver

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

    @patch("directord.send_data", autospec=True)
    def test_poll_job_unknown(self, mock_send_data):
        with patch.object(self.args, "timeout", 1):
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
    def test_poll_job_degraded(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node1"],
                    "FAILED": ["hostname-node0"],
                    "NODES": ["hostname-node0", "hostname-node1"],
                    "PROCESSING": b"\004".decode(),
                }
            }
        )
        status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, False)
        self.assertEqual(info, "Job Degrated: test-id")

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

    @patch("directord.send_data", autospec=True)
    def test_poll_job_skipped(self, mock_send_data):
        with patch.object(self.args, "timeout", 1):
            mock_send_data.return_value = json.dumps(
                {
                    "test-id": {
                        "SUCCESS": [],
                        "NODES": ["hostname-node1", "hostname-node2"],
                        "PROCESSING": b"\004".decode(),
                    }
                }
            )
            status, info = self.manage.poll_job("test-id")
        self.assertEqual(status, True)
        self.assertEqual(info, "Job Skipped: test-id")

    def test_run_override_unknown(self):
        self.assertRaises(SystemExit, self.manage.run, override=None)

    @patch("directord.send_data", autospec=True)
    def test_run_override_list_jobs(self, mock_send_data):
        self.manage.run(override="list-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": {"list_jobs": null}}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_list_nodes(self, mock_send_data):
        self.manage.run(override="list-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": {"list_nodes": null}}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_purge_jobs(self, mock_send_data):
        self.manage.run(override="purge-jobs")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": {"purge_jobs": null}}'
        )

    @patch("directord.send_data", autospec=True)
    def test_run_override_purge_nodes(self, mock_send_data):
        self.manage.run(override="purge-nodes")
        mock_send_data.assert_called_once_with(
            unittest.mock.ANY, data='{"manage": {"purge_nodes": null}}'
        )

    @patch("directord.user.Manage.generate_certificates", autospec=True)
    @patch("directord.send_data", autospec=True)
    def test_run_override_generate_keys(
        self, mock_send_data, mock_generate_certificates
    ):
        self.manage.run(override="generate-keys")
        mock_send_data.assert_not_called()

    @patch("os.makedirs", autospec=True)
    @patch("os.rename", autospec=True)
    @patch("os.listdir", autospec=True)
    def test_generate_certificates(
        self, mock_listdir, mock_rename, mock_makedirs
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
        self.manage.driver.key_generate.assert_has_calls(
            [
                call(
                    keys_dir="/etc/directord/certificates", key_type="server"
                ),
                call(
                    keys_dir="/etc/directord/certificates", key_type="client"
                ),
            ]
        )

    @patch("builtins.print")
    @patch("diskcache.Cache", autospec=True)
    def test_run_override_dump_cache(self, mock_diskcache, mock_print):
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="test", value="value")
        self.manage.run(override="dump-cache")
        mock_print.assert_called_with(
            '{\n    "args": {\n        "test": 1\n    },\n    "test": "value"\n}'  # noqa
        )

    @patch("builtins.print")
    @patch("diskcache.Cache", autospec=True)
    def test_run_override_dump_cache_empty(self, mock_diskcache, mock_print):
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.clear()
        self.manage.run(override="dump-cache")
        mock_print.assert_called_with("{}")
