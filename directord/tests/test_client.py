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

from directord import client
from directord import tests


class TestClient(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.client = client.Client(args=self.args)

    def tearDown(self):
        pass

    def test_job_connect(self):
        pass

    def test_transfer_connect(self):
        pass

    def test_heartbeat_connect(self):
        pass

    def test_reset_heartbeat(self):
        pass

    def test_run_heartbeat(self):
        pass

    def test__run_command(self):
        pass

    def test__run_workdir(self):
        pass

    def test_file_blueprinter(self):
        pass

    def test_blueprinter(self):
        pass

    def test_run_job(self):
        pass

    def test_worker_run(self):
        pass
