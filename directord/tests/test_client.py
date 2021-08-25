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

    @patch("logging.Logger.warning", autospec=True)
    def test_run_heartbeat_reset(self, mock_log_warning):
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"reset",
                json.dumps({}).encode(),
                b".001",
                None,
                None,
            )
        ]
        self.client.run_heartbeat(sentinel=True)
        mock_log_warning.assert_called()

    @patch("time.time", autospec=True)
    @patch("time.sleep", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat_missed(self, mock_log_debug, mock_sleep, mock_time):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.mock_driver.socket_recv.side_effect = [
            (None, None, None, json.dumps({}).encode(), b".001", None, None)
        ]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            with patch.object(
                self.mock_driver, "get_heartbeat", return_value=0
            ):
                self.client.run_heartbeat(sentinel=True, heartbeat_misses=10)
        mock_log_debug.assert_called()
        mock_sleep.assert_called()

    @patch("time.time", autospec=True)
    @patch("time.sleep", autospec=True)
    @patch("logging.Logger.debug", autospec=True)
    def test_run_heartbeat_missed_long_interval(
        self, mock_log_debug, mock_sleep, mock_time
    ):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.mock_driver.socket_recv.side_effect = [
            (None, None, None, json.dumps({}).encode(), b".001", None, None)
        ]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            with patch.object(
                self.mock_driver, "get_heartbeat", return_value=0
            ):
                self.client.heartbeat_failure_interval = 64
                self.client.run_heartbeat(sentinel=True, heartbeat_misses=10)
        mock_log_debug.assert_called()
        mock_sleep.assert_called()

    @patch("time.time", autospec=True)
    def test_run_heartbeat_update(self, mock_time):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.mock_driver.socket_recv.side_effect = [
            (
                None,
                None,
                b"reset",
                json.dumps({}).encode(),
                b".001",
                None,
                None,
            )
        ]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            with patch.object(
                self.mock_driver, "get_heartbeat", return_value=0
            ):
                self.client.run_heartbeat(sentinel=True)

    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job(self, mock_time, mock_makedirs):
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_idle(self, mock_time, mock_makedirs):
        mock_time.side_effect = [1, 1, 66, 1, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)

    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_ramp(self, mock_time, mock_makedirs):
        mock_time.side_effect = [1, 1, 1, 34, 1, 1]
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)

    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_cache_check(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
    ):
        mock_time.side_effect = [1, 1, 1, 1, 5000, 1]
        mock_diskcache.return_value = tests.FakeCache()
        with patch.object(self.mock_driver, "bind_check", return_value=False):
            self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()

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
        mock_job_executor.return_value = [b"", b"", True, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
            "skip_cache": True,
            "command": "RUN",
            "job_id": "XXX",
            "job_sha3_224": "YYY",
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
            info=b"",
            job=job_def,
            job_id="XXX",
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
        mock_job_executor.return_value = [b"", b"", True, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
            "ignore_cache": True,
            "command": "RUN",
            "job_id": "XXX",
            "job_sha3_224": "YYY",
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
            info=b"",
            job=job_def,
            job_id="XXX",
            cached=False,
            command=b"RUN",
        )

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_parent_failed_run(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", True, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
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
        mock_job_executor.return_value = [b"", b"", True, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
            "command": "RUN",
            "job_id": "XXX",
            "job_sha3_224": "YYY",
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
        cache.set(key="YYY", value=self.mock_driver.job_end.decode())
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
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
        mock_job_executor.return_value = [b"", b"", True, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
            "command": "RUN",
            "parent_id": "ZZZ",
            "job_id": "XXX",
            "job_sha3_224": "YYY",
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
        cache.set(key="YYY", value=self.mock_driver.job_end.decode())
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            cached=True,
            command=b"RUN",
        )
        self.assertEqual(cache.get("YYY"), self.mock_driver.job_end.decode())

    @patch("directord.client.Client._job_executor", autospec=True)
    @patch("diskcache.Cache", autospec=True)
    @patch("logging.Logger.info", autospec=True)
    @patch("os.makedirs", autospec=True)
    @patch("time.time", autospec=True)
    def test_run_job_run_outcome_false(
        self,
        mock_time,
        mock_makedirs,
        mock_log_info,
        mock_diskcache,
        mock_job_executor,
    ):
        mock_job_executor.return_value = [b"", b"", False, None]
        job_def = {
            "task": "XXX",
            "task_sha3_224": "YYY",
            "command": "RUN",
            "job_id": "XXX",
            "job_sha3_224": "YYY",
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
        cache.set(key="YYY", value=self.mock_driver.job_failed.decode())
        mock_time.side_effect = [1, 1, 1, 1, 1, 1]
        self.client.run_job(sentinel=True)
        mock_makedirs.assert_called_with("/var/cache/directord", exist_ok=True)
        mock_log_info.assert_called()
        mock_job_executor.assert_called_with(
            ANY,
            conn=ANY,
            info=b"",
            job=job_def,
            job_id="XXX",
            cached=False,
            command=b"RUN",
        )
        self.assertEqual(
            cache.get("YYY"), self.mock_driver.job_failed.decode()
        )

    @patch("directord.client.Client.run_threads", autospec=True)
    def test_worker_run(self, mock_run_threads):
        self.client.worker_run()
        mock_run_threads.assert_called_with(ANY, threads=[ANY, ANY, ANY, ANY])
