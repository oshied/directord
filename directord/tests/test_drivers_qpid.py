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
from unittest import mock

from directord import tests
from directord.drivers import qpid as qpid_driver


class TestDriverZMQ(unittest.TestCase):
    def setUp(self):
        self.driver = qpid_driver.Driver(
            args=tests.FakeArgs,
            connection_string="tcp://localhost"
        )
        self.socket = mock.MagicMock()

    def tearDown(self):
        pass

    def test_socket_send(self):
        self.driver.socket_send(self.socket)

    def test_socket_recv(self):
        self.driver.socket_recv(self.socket)

    def test_job_connect(self):
        self.driver.job_connect()

    def test_transfer_connect(self):
        self.driver.transfer_connect()

    def test_heartbeat_connect(self):
        self.driver.heartbeat_connect()

    def test_heartbeat_bind(self):
        self.driver.heartbeat_bind()

    def test_job_bind(self):
        self.driver.job_bind()

    def test_transfer_bind(self):
        self.driver.transfer_bind()

    def test_bind_check(self):
        self.driver.bind_check(bind=None, interval=1, constant=1000)

    def test_key_generate(self):
        self.driver.key_generate(keys_dir=None, key_type=None)
