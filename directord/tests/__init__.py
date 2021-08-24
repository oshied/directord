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

from collections import namedtuple

from directord import drivers


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
    heartbeat_port = 5557
    job_port = 5555
    mode = "client"
    server_address = "localhost"
    shared_key = None
    socket_path = "/var/run/directord.sock"
    socket_group = "root"
    cache_path = "/var/cache/directord"
    transfer_port = 5556
    timeout = 600
    curve_encryption = None


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


class FakeCache:
    class transact:
        def __enter__(self):
            pass

        def __exit__(self, *args, **kwargs):
            pass

    def __init__(self):
        self.cache = {"args": {"test": 1}}

    def get(self, key):
        return self.cache.get(key)

    def pop(self, key, **kwargs):
        if key not in self.cache:
            if "default" in kwargs:
                return kwargs["default"]

        return self.cache.pop(key)

    def set(self, key, value, **kwargs):
        self.cache[key] = value

    def evict(self, key):
        popped = self.cache.pop(key, dict())
        return len(popped)

    def clear(self):
        current = len(self.cache)
        self.cache = dict()
        return current

    def volume(self):
        return len(self.cache)

    def check(self):
        return [namedtuple("check", ["message"])("warning")]

    def expire(self):
        pass

    def __enter__(self):
        return self

    def __exit__(*args, **kwargs):
        pass


class TestConnectionBase(unittest.TestCase):
    def setUp(self):
        self.patched_socket = patch("socket.socket.connect", autospec=True)
        self.patched_socket.start()
        fakesession = MagicMock()
        self.fakechannel = fakesession.open_session.return_value = MagicMock()
        self.fakechannel.read.return_value = (0, "test-exec-output")
        self.fakechannel.get_exit_status.return_value = 0
        self.patched_session = patch(
            "directord.utils.Session", autospec=True, return_value=fakesession
        )
        self.patched_session.start()

    def tearDown(self):
        self.patched_socket.stop()
        self.patched_session.stop()


class TestDriverBase(unittest.TestCase):
    def setUp(self):
        base_driver = drivers.BaseDriver(args=FakeArgs())
        self.mock_driver_patched = patch(
            "directord.drivers.BaseDriver",
            autospec=True,
        )
        self.mock_driver = self.mock_driver_patched.start()
        self.mock_driver.bind_check.return_value = True
        self.mock_driver.nullbyte = base_driver.nullbyte
        self.mock_driver.heartbeat_ready = base_driver.heartbeat_ready
        self.mock_driver.heartbeat_notice = base_driver.heartbeat_notice
        self.mock_driver.heartbeat_reset = base_driver.heartbeat_reset
        self.mock_driver.job_ack = base_driver.job_ack
        self.mock_driver.job_end = base_driver.job_end
        self.mock_driver.job_processing = base_driver.job_processing
        self.mock_driver.job_failed = base_driver.job_failed
        self.mock_driver.transfer_start = base_driver.transfer_start
        self.mock_driver.transfer_end = base_driver.transfer_end

    def tearDown(self) -> None:
        self.mock_driver_patched.stop()
