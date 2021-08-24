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

import time
import unittest

from directord import datastores


class TestDatastoreInternal(unittest.TestCase):
    def setUp(self):
        self.log_patched = unittest.mock.patch("directord.logger.getLogger")
        self.log = self.log_patched.start()

    def tearDown(self):
        self.log_patched.stop()

    def test_wq_prune_0(self):
        workers = datastores.BaseDocument()
        workers["test"] = 1
        workers.empty()
        self.assertDictEqual(workers, dict())
        self.log.debug.called_once()

    def test_wq_prune_valid(self):
        workers = datastores.BaseDocument()
        workers["valid1"] = {"time": time.time() + 2}
        workers["invalid1"] = {"time": time.time() - 2}
        workers["invalid2"] = {"time": time.time() - 3}
        workers.prune()
        self.assertEqual(len(workers), 1)
        self.assertIn("valid1", workers)
        self.log.debug.called_once()

    def test_wq_empty(self):
        workers = datastores.BaseDocument()
        workers["valid1"] = {"time": time.time() + 2}
        workers["invalid1"] = {"time": time.time() - 2}
        workers["invalid2"] = {"time": time.time() - 3}
        self.assertEqual(len(workers), 3)
        workers.empty()
        self.assertEqual(len(workers), 0)
