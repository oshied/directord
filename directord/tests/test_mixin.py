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

from directord import mixin
from directord import tests


class TestMixin(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.mixin = mixin.Mixin(args=self.args)

    def tearDown(self):
        pass

    def test_exec_orchestrations(self):
        pass

    def test_run_orchestration(self):
        pass

    def test_run_exec(self):
        pass

    def test_start_server(self):
        pass

    def test_start_client(self):
        pass

    def test_return_tabulated_info(self):
        pass

    def test_return_tabulated_data(self):
        pass

    def test_bootstrap_catalog_entry(self):
        pass

    def test_bootstrap_localfile_padding(self):
        pass

    def test_bootstrap_flatten_jobs(self):
        pass

    def test_bootstrap_run(self):
        pass

    def test_bootstrap_file_send(self):
        pass

    def test_bootstrap_file_get(self):
        pass

    def test_bootstrap_exec(self):
        pass

    def test_bootstrap_q_processor(self):
        pass

    def test_bootstrap_cluster(self):
        pass
