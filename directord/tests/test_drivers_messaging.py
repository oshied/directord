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
from unittest.mock import ANY

from directord import tests
from directord.drivers import messaging


class TestDriverMessaging(unittest.TestCase):
    def setUp(self):
        self.mock_interface = MagicMock()
        args = tests.FakeArgs
        args.driver = "messaging"
        args.mode = "server"
        with patch.object(
            messaging.Driver, "get_machine_id"
        ) as mock_get_machine_id:
            mock_get_machine_id.return_value = "XXX123"
            self.driver = messaging.Driver(
                args=args,
                bind_address="localhost",
                interface=self.mock_interface,
            )

    def tearDown(self):
        pass

    @patch("directord.drivers.messaging.Driver._send")
    def test_heartbeat_send(self, mock_send):
        self.driver.heartbeat_send(10, 11, 12)
        data = json.dumps(
            {
                "version": 12,
                "host_uptime": 10,
                "agent_uptime": 11,
                "machine_id": "XXX123",
                "driver": None,
            }
        )
        mock_send.assert_called()
        mock_send.assert_called_with(
            method="_heartbeat",
            topic="directord",
            identity=ANY,
            data=data,
        )

        self.driver.identity = "foohost"
        self.driver.heartbeat_send(10, 11, 12)
        mock_send.assert_called()
        mock_send.assert_called_with(
            method="_heartbeat",
            topic="directord",
            identity=ANY,
            data=data,
        )

    @patch("directord.drivers.messaging.Driver._send")
    def test_job_send(self, mock_send):
        self.driver.job_send(
            identity="TEST",
            msg_id="XXX",
            control="TESTcontrol",
            command="RUN",
            data='{"JOB": "XXX"}',
            info="TEST INFO",
            stderr="TEST STDERR",
            stdout="TEST STDOUT",
        )
        mock_send.assert_called()
        mock_send.assert_called_with(
            method="_job",
            topic="directord",
            server=ANY,
            identity=ANY,
            job_id="XXX",
            control="TESTcontrol",
            command="RUN",
            data='{"JOB": "XXX"}',
            info="TEST INFO",
            stderr="TEST STDERR",
            stdout="TEST STDOUT",
        )
