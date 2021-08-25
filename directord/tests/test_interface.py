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

import logging
import unittest

from unittest.mock import patch

from directord import interface
from directord import tests


class TestInterface(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()

    def test_interface_debug(self):
        with patch.object(self.args, "debug", True):
            iface = interface.Interface(args=self.args)
        self.assertEqual(iface.log.level, logging.DEBUG)

    def test_interface_mode_client(self):
        with patch.object(self.args, "mode", "client"):
            iface = interface.Interface(args=self.args)
        self.assertEqual(iface.bind_address, "localhost")

    def test_interface_mode_server(self):
        with patch.object(self.args, "mode", "server"):
            iface = interface.Interface(args=self.args)
        self.assertEqual(iface.bind_address, "10.1.10.1")

    def test_interface_no_driver(self):
        with patch(
            "directord.plugin_import", autospec=True
        ) as mock_plugin_import:
            mock_plugin_import.side_effect = ImportError("fail")
            with self.assertRaises(SystemExit):
                interface.Interface(args=self.args)
