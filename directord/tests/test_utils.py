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
import uuid

from unittest.mock import patch

from directord import tests
from directord import utils


class TestUtils(tests.TestConnectionBase):
    def test_dump_yaml(self):
        m = unittest.mock.mock_open()
        with patch("builtins.open", m):
            file_path = utils.dump_yaml(
                file_path="/test.yaml", data={"test": "data"}
            )
        m.assert_called_once_with("/test.yaml", "w")
        assert file_path == "/test.yaml"

    def test_merge_dict(self):
        a = {
            "dict": {"a": "test", "b": {"int1": 1}},
            "list": ["a"],
            "str": "a",
            "int": 1,
        }
        b = {
            "dict": {"b": {"int2": 2}, "c": "test2"},
            "list": ["b"],
            "key": "value",
        }
        merge = {
            "dict": {"a": "test", "b": {"int1": 1, "int2": 2}, "c": "test2"},
            "int": 1,
            "key": "value",
            "list": ["a", "b"],
            "str": "a",
        }
        new = utils.merge_dict(base=a, new=b)
        self.assertEqual(new, merge)

    def test_merge_dict_no_extend(self):
        a = {
            "dict": {"a": "test", "b": {"int1": 1}},
            "list": ["a"],
            "str": "a",
            "int": 1,
        }
        b = {
            "dict": {"b": {"int2": 2}, "c": "test2"},
            "list": ["b"],
            "key": "value",
        }
        merge = {
            "dict": {"b": {"int2": 2}, "c": "test2"},
            "int": 1,
            "key": "value",
            "list": ["b"],
            "str": "a",
        }
        new = utils.merge_dict(base=a, new=b, extend=False)
        self.assertEqual(new, merge)

    def test_ctx_mgr_clientstatus_enter_exit(self):
        ctx = unittest.mock.MagicMock()
        socket = unittest.mock.MagicMock()
        with utils.ClientStatus(
            socket=socket,
            job_id=b"test-id",
            command=b"test",
            ctx=ctx,
        ) as c:
            assert c.job_id == b"test-id"

        ctx.driver.socket_send.assert_called_with(
            socket=socket,
            msg_id=b"test-id",
            command=b"test",
            control=unittest.mock.ANY,
            data=unittest.mock.ANY,
            info=unittest.mock.ANY,
            stderr=unittest.mock.ANY,
            stdout=unittest.mock.ANY,
        )

    def test_sshconnect(
        self,
    ):
        with utils.SSHConnect(
            host="test", username="testuser", port=22, key_file="/test/key"
        ) as ssh:
            ssh.session.handshake(mock.ANY)
            ssh.session.knownhost_init()

    def test_file_sha256(self):
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data=b"data")
        ) as mock_file:
            sha256 = utils.file_sha256(file_path=mock_file)
            self.assertEqual(
                sha256,
                "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",  # noqa
            )

    def test_file_sha256_set_chunk(self):
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data=b"data")
        ) as mock_file:
            sha256 = utils.file_sha256(file_path=mock_file, chunk_size=1)
            self.assertEqual(
                sha256,
                "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7",  # noqa
            )

    def test_object_sha256(self):
        sha256 = utils.object_sha256(obj={"test": "value"})
        self.assertEqual(
            sha256,
            "71e1ec59dd990e14f06592c6146a79cbce0e1997810dd011923cc72a2ef1d1ae",  # noqa
        )

    def test_get_uuid(self):
        uuid1 = utils.get_uuid()
        uuid.UUID(uuid1, version=4)
        uuid2 = utils.get_uuid()
        uuid.UUID(uuid2, version=4)
        self.assertNotEqual(uuid1, uuid2)
