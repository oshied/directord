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


class TestUser(tests.TestBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        self.user = user.User(args=self.args)

    def test_send_data(self):
        user.directord.socket.socket = tests.MockSocket
        returned = directord.send_data(
            socket_path=self.args.socket_path, data="test"
        )
        self.assertEqual(returned, b"return data")


class TestManager(tests.TestDriverBase):
    def setUp(self):
        super().setUp()
        self.args = tests.FakeArgs()
        with patch("directord.plugin_import", autospec=True):
            self.manage = user.Manage(args=self.args)
        self.manage.driver = self.mock_driver

    @patch("directord.send_data", autospec=True)
    def test_poll_job_unknown(self, mock_send_data):
        with patch.object(self.args, "timeout", 1):
            mock_send_data.return_value = json.dumps(
                {
                    "test-id": {
                        "SUCCESS": ["hostname-node1"],
                        "_nodes": ["hostname-node1", "hostname-node2"],
                        "PROCESSING": "UNDEFINED",
                    }
                }
            )
            status, info, _, _, _ = self.manage.poll_job("test-id")
        self.assertEqual(status, None)
        self.assertEqual(info, "Job in an unknown state: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_success(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node"],
                    "_nodes": ["hostname-node"],
                    "PROCESSING": b"\004".decode(),
                }
            }
        )
        status, info, _, _, _ = self.manage.poll_job("test-id")
        self.assertEqual(status, True)
        self.assertEqual(info, "Job Success: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_degraded(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "SUCCESS": ["hostname-node1"],
                    "FAILED": ["hostname-node0"],
                    "_nodes": ["hostname-node0", "hostname-node1"],
                    "PROCESSING": b"\004".decode(),
                }
            }
        )
        status, info, _, _, _ = self.manage.poll_job("test-id")
        self.assertEqual(status, False)
        self.assertEqual(info, "Job Degrated: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_failed(self, mock_send_data):
        mock_send_data.return_value = json.dumps(
            {
                "test-id": {
                    "FAILED": ["hostname-node"],
                    "_nodes": ["hostname-node"],
                    "PROCESSING": b"\025".decode(),
                }
            }
        )
        status, info, _, _, _ = self.manage.poll_job("test-id")
        self.assertEqual(status, False)
        self.assertEqual(info, "Job Failed: test-id")

    @patch("directord.send_data", autospec=True)
    def test_poll_job_skipped(self, mock_send_data):
        with patch.object(self.args, "timeout", 1):
            mock_send_data.return_value = json.dumps(
                {
                    "test-id": {
                        "SUCCESS": [],
                        "_nodes": ["hostname-node1", "hostname-node2"],
                        "PROCESSING": b"\004".decode(),
                    }
                }
            )
            status, info, _, _, _ = self.manage.poll_job("test-id")
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

    @patch("builtins.print")
    @patch("directord.utils.Cache", autospec=True)
    def test_run_override_dump_cache(self, mock_diskcache, mock_print):
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.setdefault(key="test", value="value")
        self.manage.run(override="dump-cache")
        mock_print.assert_called_with(
            '{\n    "args": {\n        "test": 1\n    },\n    "test": "value"\n}'  # noqa
        )
