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

from unittest.mock import MagicMock
from unittest.mock import patch

from directord import tests
from directord import ui


class TestUI(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.ui = ui.UI(args=self.args, jobs=[], nodes=[])

    def tearDown(self):
        pass

    @patch("flask.Flask", autospec=True)
    def test_start_app(self, mock_flask):
        jobs = {}
        nodes = {}
        args = tests.FakeArgs()
        setattr(args, "bind_address", "")
        setattr(args, "ui_port", 8080)
        app = ui.APP = mock_flask.return_value = MagicMock()
        app.run = MagicMock()

        ui.UI(args=args, jobs=jobs, nodes=nodes).start_app()
        app.run.assert_called_with(port=8080, host="")

    @patch("flask.Flask", autospec=True)
    def test_start_app_host(self, mock_flask):
        jobs = {}
        nodes = {}
        args = tests.FakeArgs()
        setattr(args, "bind_address", "10.1.10.1")
        setattr(args, "ui_port", 8080)
        app = ui.APP = mock_flask.return_value = MagicMock()
        app.run = MagicMock()

        ui.UI(args=args, jobs=jobs, nodes=nodes).start_app()
        app.run.assert_called_with(port=8080, host="10.1.10.1")
