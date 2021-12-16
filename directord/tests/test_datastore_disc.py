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

import pickle
import unittest
from unittest.mock import patch

from directord.datastores import disc as datastore_disc

from directord import tests


class TestDatastoreDisc(tests.TestBase):
    def setUp(self):
        super().setUp()
        self.makedirs_patched = patch("os.makedirs", autospec=True)
        self.makedirs_patched.start()
        self.chdir_patched = patch("os.chdir", autospec=True)
        self.chdir_patched.start()
        self.setxattr_patched = patch("os.setxattr", autospec=True)
        self.setxattr_patched.start()
        self.datastore = datastore_disc.BaseDocument(url="file:///test/things")

    def tearDown(self):
        super().tearDown()
        self.makedirs_patched.stop()
        self.chdir_patched.stop()
        self.setxattr_patched.stop()

    def test_prune(self):
        self.datastore.prune()

    def test_set(self):
        read_data = pickle.dumps("value")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            value = self.datastore.set(key="key", value="value")
            self.assertAlmostEqual(value, "value")
