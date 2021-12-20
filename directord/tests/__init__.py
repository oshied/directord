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

import tracemalloc
import queue
import unittest

from unittest.mock import MagicMock
from unittest.mock import patch

from directord import drivers
from directord import utils


tracemalloc.start()


TEST_BLUEPRINT_CONTENT = "This is a blueprint string {{ test }}"


TEST_CATALOG = """---
directord_server:
  targets:
  - host: 172.16.27.2
    port: 22
    username: centos
  jobs:
  - RUN: command1

directord_clients:
  args:
    port: 22
    username: centos
  targets:
  - host: 172.16.27.2
  jobs:
  - RUN: command1
"""


MOCK_CURVE_KEY = """
#   ****  Generated test key  ****
#   ZeroMQ CURVE **Secret** Certificate
#   DO NOT PROVIDE THIS FILE TO OTHER USERS nor change its permissions.

metadata
curve
    public-key = ".e7-:Y61tEcr)>n&RVB^N$[!56z!Ye=3ia?/GA<L"
    secret-key = "4S}VzCf0fj]{j>8X!Px#=)P<<1Em$8cWNY2&g[x="
"""


MOCK_DOCUMENTATION = """
---
component: test
author:
  - user
short_description: test
notes: []
description: test
options:
  snake_case:
    description:
      - test
    required: True
    type: str
  opt0:
    description:
      - test
    default: '*.json'
    required: False
    type: str
  opt1:
    description:
      - test
      - desc
    default: {}
    required: False
    type: dict
  opt2:
    description: test
    default: False
    required: False
    type: bool
"""


class FakePopen:
    """Fake Shell Commands."""

    def __init__(self, return_code=0, *args, **kwargs):
        self.returncode = return_code

    @staticmethod
    def communicate():
        return "stdout", "stderr"


class FakeStat:
    def __init__(self, uid, gid):
        self.st_uid = uid
        self.st_gid = gid
        self.st_size = 0
        self.st_mtime = 0
        self.st_mode = 0
        self.st_atime = 0


class FakeArgs:
    config_file = None
    datastore = None
    debug = False
    driver = "zmq"
    dump_cache = False
    heartbeat_interval = 60
    job_port = 5555
    mode = "client"
    zmq_server_address = "localhost"
    zmq_bind_address = "10.1.10.1"
    identity = "test-node"
    socket_path = "/var/run/directord.sock"
    stream = False
    socket_group = "root"
    cache_path = "/var/cache/directord"
    backend_port = 5556
    timeout = 600
    zmq_shared_key = None
    zmq_curve_encryption = None
    zmq_highwater_mark = 1
    force_async = False
    messaging_address = "localhost"
    messaging_ssl = True
    messaging_ssl_ca = "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem"
    messaging_ssl_cert = "/etc/directord/messaging/ssl/directord.crt"
    messaging_ssl_key = "/etc/directord/messaging/ssl/directord.key"
    machine_id = None
    grpc_port = 5558
    grpc_bind_address = "0.0.0.0"
    grpc_server_address = "127.0.0.1"
    grpc_server_workers = 4
    grpc_ssl = False
    grpc_disable_compression = False
    grpc_ssl_ca = "/etc/pki/ca-trust/source/anchors/cm-local-ca.pem"
    grpc_ssl_cert = "/etc/directord/grpc/ssl/directord.crt"
    grpc_ssl_key = "/etc/directord/grpc/ssl/directord.key"
    grpc_ssl_client_auth = False


class MockSocket:
    def __init__(self, *args, **kwargs):
        self.chunk_returned = False

    def sendall(self, *args, **kwargs):
        pass

    def connect(self, *args, **kwargs):
        pass

    def recv(self, *args, **kwargs):
        if not self.chunk_returned:
            self.chunk_returned = True
            return b"return data"

    def close(self):
        pass


class MockQueue(queue.Queue, utils.BaseQueue):

    pass


class FakeCache:
    def __init__(self):
        self.cache = {"args": {"test": 1}}

    def get(self, key, **kwargs):
        if key not in self.cache:
            if "default" in kwargs:
                return kwargs["default"]

        return self.cache.get(key)

    def pop(self, key, **kwargs):
        if key not in self.cache:
            if "default" in kwargs:
                return kwargs["default"]

        return self.cache.pop(key)

    def setdefault(self, key, value, **kwargs):
        self.cache[key] = value

    def clear(self):
        current = len(self.cache)
        self.cache = dict()
        return current

    def sync(self):
        pass

    def close(self):
        pass

    def expire(self):
        pass

    def items(self):
        return list(self.cache.items())

    def __enter__(self):
        return self

    def __exit__(*args, **kwargs):
        pass


class FakeThread:
    daemon = False

    def is_alive(self):
        pass

    def start(self):
        pass

    def join(self, *args, **kwargs):
        pass


class TestBase(unittest.TestCase):
    def setUp(self):
        self.patch_logger = patch("directord.logger.getLogger", autospec=True)
        self.patch_logger.start()

    def tearDown(self):
        self.patch_logger.stop()


class FakeQueue(queue.Queue):
    def close(self):
        pass


class TestConnectionBase(TestBase):
    def setUp(self):
        super().setUp()
        self.patched_socket = patch("socket.socket.connect", autospec=True)
        self.patched_socket.start()
        fakesession = MagicMock()
        fakesession.disconnect = MagicMock()
        self.fakechannel = MagicMock()
        self.fakechannel.read = MagicMock(return_value=[(0, b"end\n")])
        self.fakechannel.get_exit_status = MagicMock(return_value=0)
        self.patched_session = patch(
            "directord.utils.Session", autospec=True, return_value=fakesession
        )
        self.patched_session.start()
        self.addCleanup(self.restoreSocket)

    def restoreSocket(self):
        self.patched_session.stop()
        self.patched_socket.stop()

    def tearDown(self):
        super().tearDown()


class TestDriverBase(TestBase):
    def setUp(self):
        super().setUp()
        base_driver = drivers.BaseDriver(args=FakeArgs())
        self.patched_get_queue = patch(
            "directord.utils.DurableQueue", autospec=True
        )
        self.mock_driver_patched = patch(
            "directord.drivers.BaseDriver",
            autospec=True,
        )
        self.mocked_get_queue = self.patched_get_queue.start()
        self.mocked_get_queue.return_value = FakeQueue()
        self.mock_driver = self.mock_driver_patched.start()
        self.mock_driver.job_check.return_value = True
        self.mock_driver.nullbyte = base_driver.nullbyte
        self.mock_driver.heartbeat_notice = base_driver.heartbeat_notice
        self.mock_driver.job_end = base_driver.job_end
        self.mock_driver.job_processing = base_driver.job_processing
        self.mock_driver.job_failed = base_driver.job_failed
        self.mock_driver.transfer_start = base_driver.transfer_start
        self.mock_driver.transfer_end = base_driver.transfer_end
        self.mock_driver.bind_job = MagicMock()
        self.mock_driver.heartbeat_send = MagicMock()
        event = self.mock_driver.event = MagicMock()
        event.is_set.return_value = True

        self.addCleanup(self.restoreDrivers)

    def restoreDrivers(self):
        self.mock_driver_patched.stop()
        self.patched_get_queue.stop()
