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


import io

from collections import namedtuple
from unittest import mock

import paramiko


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


class FakePopen():
    """Fake Shell Commands."""

    def __init__(self, return_code=0, *args, **kwargs):
        self.returncode = return_code

    @staticmethod
    def communicate():
        return "stdout", "stderr"


class FakeStat():
    def __init__(self, uid, gid):
        self.st_uid = uid
        self.st_gid = gid
        self.st_size = 0
        self.st_mtime = 0
        self.st_mode = 0


class FakeArgs():
    config_file = None
    datastore = None
    debug = False
    heartbeat_interval = 60
    heartbeat_port = 5557
    job_port = 5555
    mode = "client"
    server_address = "localhost"
    shared_key = None
    socket_path = "/var/run/directord.sock"
    cache_path = "/var/cache/directord"
    transfer_port = 5556
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


class MockChannelFile(io.StringIO):
    channel = mock.MagicMock(spec=paramiko.Channel)()

    def __init__(self, rc=0):
        self.channel.recv_exit_status.return_value = rc


class FakeCache():
    def __init__(self):
        self.cache = {"args": {"test": 1}}

    def get(self, key):
        return self.cache.get(key)

    def pop(self, key, **kwargs):
        if key not in self.cache:
            if "default" in kwargs:
                return kwargs["default"]
        else:
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
