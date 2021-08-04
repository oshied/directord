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

from unittest.mock import ANY
from unittest.mock import patch

from directord import client
from directord import tests


class TestClient(tests.TestDriverBase):
    def setUp(self):
        super(TestClient, self).setUp()
        self.args = tests.FakeArgs()
        self.client = client.Client(args=self.args)
        self.client.driver = self.mock_driver

    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat(self, mock_log_debug):
        self.mock_driver.socket_recv.side_effect = [
            (None, None, None, json.dumps({}).encode(), b".001", None, None)
        ]
        self.client.run_heartbeat(sentinel=True)
        mock_log_debug.assert_called()

    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job(self, mock_time, mock_makedirs):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)

    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_idle(self, mock_time, mock_makedirs, mock_log_info):
        mock_time.side_effect = [1, 1, 66, 1, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()

    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_ramp(self, mock_time, mock_makedirs, mock_log_info):
        mock_time.side_effect = [1, 1, 1, 34, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()

    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.warning", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_cache_check(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_warning,
        mock_diskcache,
    ):
        mock_time.side_effect = [1, 1, 1, 1, 5000, 1]
        mock_diskcache.return_value = tests.FakeCache()
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_log_warning.assert_called_with(
            ANY, "Client Cache Warning: [ %s ].", "warning"
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_skip_skip_cache_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "skip_cache": True,
            "command": "RUN",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        mock_diskcache.return_value = tests.FakeCache()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha256="YYY",
            cached=False,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_skip_ignore_cache_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "ignore_cache": True,
            "command": "RUN",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        mock_diskcache.return_value = tests.FakeCache()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha256="YYY",
            cached=False,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_parent_failed_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_error,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "parent_id": "ZZZ",
            "command": "RUN",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="ZZZ", value=False)
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_log_error.assert_called()

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_cache_hit_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "command": "RUN",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="YYY", value=self.mock_driver.job_end)
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha256="YYY",
            cached=True,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "command": "RUN",
            "parent_id": "ZZZ",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        cache = mock_diskcache.return_value = tests.FakeCache()
        cache.set(key="YYY", value=self.mock_driver.job_end)
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha256="YYY",
            cached=True,
            command=b"RUN",
        )
        self.assertEqual(cache.get("ZZZ"), True)
        self.assertEqual(cache.get("YYY"), self.mock_driver.job_end)

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.error", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_run_outcome_false(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_log_error,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", False]
        job_def = {
            "task": "XXX",
            "task_sha256sum": "YYY",
            "command": "RUN",
        }
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"RUN",
                json.dumps(job_def).encode(),
                b"",
                None,
                None,
            )
        ]
        cache = mock_diskcache.return_value = tests.FakeCache()
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_log_error.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            cache=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            job_sha256="YYY",
            cached=False,
            command=b"RUN",
        )

        self.assertEqual(cache.get("YYY"), self.mock_driver.job_failed)

    @patch("directord.client.Client.run_threads", autospec=True)
    def test_worker_run(self, mock_run_threads):
        self.client.worker_run()
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY])
