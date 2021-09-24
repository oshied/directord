#   Copyright 2021 Red Hat, Inc.
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

from unittest.mock import MagicMock
from unittest.mock import patch

from directord import tests
from directord.drivers import messaging


class TestDriverMessaging(unittest.TestCase):
    def setUp(self):
        self.mock_interface = MagicMock()
        args = tests.FakeArgs
        args.mode = "server"
        self.driver = messaging.Driver(
            args=args,
            connection_string="tcp://localhost",
            interface=self.mock_interface,
        )

    def tearDown(self):
        pass

    @patch("directord.drivers.messaging.Driver.send")
    def test_heartbeat_send(self, mock_send):
        self.driver.heartbeat_send("foo", 10, 11, 12)

        data = json.dumps(
            {
                "version": 12,
                "host_uptime": 10,
                "agent_uptime": 11,
            }
        )
        mock_send.assert_called()
        mock_send.assert_called_with(
            "heartbeat",
            "directord",
            server="directord",
            identity="foo",
            data=data,
        )

        self.driver.identity = "foohost"
        self.driver.heartbeat_send(None, 10, 11, 12)
        mock_send.assert_called()
        mock_send.assert_called_with(
            "heartbeat",
            "directord",
            server="directord",
            identity="foohost",
            data=data,
        )
