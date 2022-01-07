#   Copyright Peznauts <kevin@peznauts.com>. All Rights Reserved.
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
import queue
import unittest

from unittest.mock import call
from unittest.mock import MagicMock
from unittest.mock import patch

from directord import iodict
from directord import tests
from directord import utils


class MockItem:
    def __init__(self, path):
        self.path = path


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.patched_makedirs = patch("os.makedirs", autospec=True)
        self.mock_makedirs = self.patched_makedirs.start()
        self.patched_stat = patch("os.stat")
        mock_stat = self.patched_stat.start()
        mock_stat.return_value = tests.FakeStat()

    def tearDown(self):
        self.patched_makedirs.stop()
        self.patched_stat.stop()


class TestIODict(BaseTest):
    def test_base___exit__(self):
        e = iodict.BaseClass()
        exit_value = e.__exit__(None, None, None)
        self.assertTrue(exit_value)

    @patch("traceback.print_exception", autospec=True)
    def test_base___exit__error(self, mock_print_exception):
        e = iodict.BaseClass()
        exit_value = e.__exit__(Exception, Exception, None)
        self.assertFalse(exit_value)
        mock_print_exception.assert_called()

    def test_init_no_lock(self):
        import multiprocessing

        d = iodict.IODict(path="/not/a/path")
        self.mock_makedirs.assert_called_with("/not/a/path", exist_ok=True)
        assert isinstance(d._lock, multiprocessing.synchronize.Lock)

    def test_init_thread_lock(self):
        import threading
        import _thread

        d = iodict.IODict(path="/not/a/path", lock=threading.Lock())
        self.mock_makedirs.assert_called_with("/not/a/path", exist_ok=True)
        assert isinstance(d._lock, _thread.LockType)

    @patch("os.listxattr", autospec=True)
    def test_init_xattr(self, mock_listxattr):
        mock_listxattr.return_value = ["user.birthtime"]
        d = iodict.IODict(path="/not/a/path")
        mock_listxattr.assert_called()
        assert d._encoder == utils.object_sha3_224

    @patch("os.listxattr", autospec=True)
    def test_init_no_xattr(self, mock_listxattr):
        mock_listxattr.side_effect = OSError("error")
        d = iodict.IODict(path="/not/a/path")
        assert d._encoder == str

    @patch("os.listxattr", autospec=True)
    @patch("os.unlink", autospec=True)
    def test__delitem___(self, mock_unlink, mock_listxattr):
        d = iodict.IODict(path="/not/a/path")
        d.__delitem__("not-an-item")
        mock_unlink.assert_called_with(
            "/not/a/path/9139d70ac1859518deb6c9adb589348b8e5b00b9b6acffdb4ee6443d"
        )

    @patch("os.unlink", autospec=True)
    def test__delitem___no_xattr(self, mock_unlink):
        d = iodict.IODict(path="/not/a/path")
        d.__delitem__("not-an-item")
        mock_unlink.assert_called_with("/not/a/path/not-an-item")

    @patch("os.unlink", autospec=True)
    def test__delitem__missing(self, mock_unlink):
        mock_unlink.side_effect = FileNotFoundError
        d = iodict.IODict(path="/not/a/path")
        with self.assertRaises(KeyError):
            d.__delitem__("not-an-item")

    @patch("os.scandir", autospec=True)
    @patch("os.listxattr", autospec=True)
    def test__exit__(self, mock_listxattr, mock_scandir):
        with patch("builtins.open", unittest.mock.mock_open()):
            with patch.object(
                iodict.IODict, "clear", autospec=True
            ) as mock_clear:
                with iodict.IODict(path="/not/a/path") as d:
                    d["not-an-item"] = {"a": 1}

            self.assertFalse(d)
            mock_clear.assert_called()

    def test__getitem__(self):
        read_data = pickle.dumps({"a": 1})
        d = iodict.IODict(path="/not/a/path")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            item = d.__getitem__("not-an-item")
        self.assertEqual(item, {"a": 1})

    def test__getitem__missing(self):
        d = iodict.IODict(path="/not/a/path")
        with patch("builtins.open", unittest.mock.mock_open()) as mock_f:
            mock_f.side_effect = FileNotFoundError
            with self.assertRaises(KeyError):
                d.__getitem__("not-an-item")

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("os.getcwd", autospec=True)
    @patch("os.chdir", autospec=True)
    def test__iter__(self, mock_chdir, mock_getcwd, mock_exists, mock_scandir):
        mock_getcwd.return_value = "/"
        mock_exists.return_value = True
        mock_scandir.return_value = [MockItem("file1"), MockItem("file2")]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kl\xc1\xb1\xd9]",
                b"key2",
                b"A\xd8kn\x0f}\xda\x16",
            ]
            return_items = [i for i in d.__iter__()]
            self.assertEqual(return_items, ["key1", "key2"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("os.getcwd", autospec=True)
    @patch("os.chdir", autospec=True)
    def test__iter__not_found(
        self, mock_chdir, mock_getcwd, mock_exists, mock_scandir
    ):
        mock_getcwd.return_value = "/"
        mock_exists.return_value = True
        mock_scandir.return_value = [MockItem("file1")]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kn\x0f}\xda\x16",
                FileNotFoundError,
            ]
            return_items = [i for i in d.__iter__()]
            self.assertEqual(return_items, ["key1"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("os.getcwd", autospec=True)
    @patch("os.chdir", autospec=True)
    def test__iter__no_xattr(
        self,
        mock_chdir,
        mock_getcwd,
        mock_exists,
        mock_scandir,
    ):
        mock_getcwd.return_value = "/"
        mock_exists.return_value = True
        mock_scandir.return_value = [
            MockItem("key1"),
            MockItem("key2"),
        ]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = OSError
            return_items = [i for i in d.__iter__()]
            self.assertEqual(return_items, ["key1", "key2"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("os.getcwd", autospec=True)
    @patch("os.chdir", autospec=True)
    def test__iter__index(
        self, mock_chdir, mock_getcwd, mock_exists, mock_scandir
    ):
        mock_getcwd.return_value = "/"
        mock_exists.return_value = True
        mock_scandir.return_value = [MockItem("file1"), MockItem("file2")]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kn\x0f}\xda\x16",
                b"key2",
                b"A\xd8kl\xc1\xb1\xd9]",
            ]
            self.assertEqual([i for i in d.__iter__(index=1)], ["key1"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    @patch("os.getcwd", autospec=True)
    @patch("os.chdir", autospec=True)
    def test__iter__no_items(
        self, mock_chdir, mock_getcwd, mock_exists, mock_scandir
    ):
        mock_getcwd.return_value = "/"
        mock_exists.return_value = True
        mock_scandir.return_value = []
        d = iodict.IODict(path="/not/a/path")
        self.assertEqual([i for i in d.__iter__()], [])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    def test__iter__no_exist(self, mock_exists, mock_scandir):
        mock_exists.side_effect = [True, True, False, True, True]
        mock_scandir.return_value = [
            MockItem("file1"),
            MockItem("file2"),
            MockItem("file3"),
        ]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kn\x0f}\xda\x16",
                FileNotFoundError,
                FileNotFoundError,
                b"key3",
                b"A\xd8kl\xc1\xb1\xd9]",
            ]
            self.assertEqual([i for i in d.__iter__()], ["key3", "key1"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    def test__iter__exist_no_exist(self, mock_exists, mock_scandir):
        mock_exists.side_effect = [True, True, False, False]
        mock_scandir.return_value = [
            MockItem("file1"),
            MockItem("file2"),
            MockItem("file3"),
        ]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kn\x0f}\xda\x16",
                b"key2",
                b"A\xd8kl\xc1\xb1\xd9]",
                b"key3",
                b"A\xd8kl\xc1\xb1\xd9]",
            ]
            self.assertEqual([i for i in d.__iter__()], ["key2"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    def test__iter__reindex(self, mock_exists, mock_scandir):
        mock_exists.side_effect = [True, False, True, True]
        mock_scandir.side_effect = [
            [MockItem("file1"), MockItem("file2")],
            [MockItem("file2")],
        ]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kn\x0f}\xda\x16",
                b"key2",
                b"A\xd8kl\xc1\xb1\xd9]",
                b"key2",
                b"A\xd8kl\xc1\xb1\xd9]",
            ]
            self.assertEqual([i for i in d.__iter__(index=0)], ["key2"])

    @patch("os.scandir", autospec=True)
    @patch("os.path.exists", autospec=True)
    def test__iter__generatorexit(self, mock_exists, mock_scandir):
        mock_exists.side_effect = [True, True, GeneratorExit]
        mock_scandir.return_value = [MockItem("file1"), MockItem("file2")]
        d = iodict.IODict(path="/not/a/path")
        with patch("os.getxattr") as mock_getxattr:
            mock_getxattr.side_effect = [
                b"key1",
                b"A\xd8kl\xc1\xb1\xd9]",
                b"key2",
                b"A\xd8kn\x0f}\xda\x16",
            ]
            return_items = [i for i in d.__iter__()]
            self.assertEqual(return_items, ["key1"])

    @patch("os.scandir", autospec=True)
    def test__len__zero(self, mock_scandir):
        mock_scandir.return_value = []
        d = iodict.IODict(path="/not/a/path")
        self.assertEqual(len(d), 0)

    def test__len__(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__iter__", autospec=True) as mock__iter__:
            mock__iter__.return_value = ["file1", "file2"]
            self.assertEqual(len(d), 2)

    @patch("os.setxattr", autospec=True)
    @patch("os.getxattr", autospec=True)
    @patch("os.listxattr", autospec=True)
    def test__setitem__(self, mock_listxattr, mock_getxattr, mock_setxattr):
        read_data = pickle.dumps({"a": 1})
        d = iodict.IODict(path="/not/a/path")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            d.__setitem__("not-an-item", {"a": 1})
        mock_listxattr.assert_called_with("/not/a/path")
        mock_getxattr.assert_called_with(
            "/not/a/path/9139d70ac1859518deb6c9adb589348b8e5b00b9b6acffdb4ee6443d",
            "user.birthtime",
        )
        mock_setxattr.assert_called_with(
            "/not/a/path/9139d70ac1859518deb6c9adb589348b8e5b00b9b6acffdb4ee6443d",
            "user.key",
            b"not-an-item",
        )

    @patch("os.getxattr", autospec=True)
    def test__setitem__no_xattrs(self, mock_getxattr):
        mock_getxattr.side_effect = OSError
        read_data = pickle.dumps({"a": 1})
        d = iodict.IODict(path="/not/a/path")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            d.__setitem__("not-an-item", {"a": 1})

    def test_clear(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__iter__", autospec=True) as mock__iter__:
            mock__iter__.return_value = ["file1", "file2"]
            with patch.object(
                d, "__delitem__", autospec=True
            ) as mock__delitem__:
                d.clear()
                mock__delitem__.assert_has_calls(
                    [call("file1"), call("file2")]
                )

    def test_copy(self):
        d = iodict.IODict(path="/not/a/path")
        self.assertEqual(d.copy(), d)

    def test_get(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True) as mock__getitem__:
            mock__getitem__.return_value = "value"
            self.assertEqual(d.get("file1"), "value")

    def test_get_default(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True) as mock__getitem__:
            mock__getitem__.side_effect = KeyError
            self.assertEqual(d.get("file1", "default"), "default")

    @patch("os.path.exists", autospec=True)
    @patch("os.getxattr", autospec=True)
    def test__get_item_key(self, mock_getxattr, mock_exists):
        mock_getxattr.side_effect = [b"key1"]
        mock_exists.return_value = True
        keyname = iodict._get_item_key("/not/a/path")
        self.assertEqual(keyname, "key1")

    @patch("os.path.exists", autospec=True)
    @patch("os.getxattr", autospec=True)
    def test__get_item_key_unicode(self, mock_getxattr, mock_exists):
        mock_getxattr.side_effect = OSError
        mock_exists.return_value = True
        keyname = iodict._get_item_key("/not/a/gAR9lC4=")
        self.assertEqual(keyname, {})

    @patch("os.path.exists", autospec=True)
    @patch("os.getxattr", autospec=True)
    def test__get_item_key_unicode(self, mock_getxattr, mock_exists):
        mock_getxattr.side_effect = OSError
        mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            iodict._get_item_key("/not/a/gAR9lC4=")

    def test_fromkeys(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__setitem__", autospec=True) as mock__setitem__:
            d.fromkeys(["file1", "file2"])
            mock__setitem__.assert_has_calls(
                [call("file1", None), call("file2", None)]
            )

    def test_fromkeys_default(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__setitem__", autospec=True) as mock__setitem__:
            d.fromkeys(["file1", "file2"], "testing")
            mock__setitem__.assert_has_calls(
                [call("file1", "testing"), call("file2", "testing")]
            )

    def test_items(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__iter__", autospec=True) as mock__iter__:
            mock__iter__.return_value = ["file1", "file2"]
            with patch.object(
                d, "__getitem__", autospec=True
            ) as mock__getitem__:
                mock__getitem__.side_effect = ["value1", "value2"]
                return_items = [i for i in d.items()]
        self.assertEqual(
            return_items, [("file1", "value1"), ("file2", "value2")]
        )

    def test_keys(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__iter__", autospec=True) as mock__iter__:
            mock__iter__.return_value = ["file1", "file2"]
            return_items = [i for i in d.keys()]

        self.assertEqual(return_items, ["file1", "file2"])

    @patch("os.setxattr", autospec=True)
    def test__makedirs(self, mock_setxattr):
        iodict._makedirs("/not/a/path")
        self.mock_makedirs.assert_called_with("/not/a/path", exist_ok=True)

    @patch("os.setxattr", autospec=True)
    def test__makedirs_key(self, mock_setxattr):
        iodict._makedirs("/not/a/path", key="things")
        self.mock_makedirs.assert_called_with("/not/a/path", exist_ok=True)
        mock_setxattr.assert_called_with(
            "/not/a/path", "user.key", "things".encode()
        )

    @patch("os.setxattr", autospec=True)
    @patch("os.unlink", autospec=True)
    def test__makedirs_file_exists(self, mock_unlink, mock_setxattr):
        self.mock_makedirs.side_effect = [FileExistsError, True]
        iodict._makedirs("/not/a/path", key="things")
        self.mock_makedirs.assert_called_with("/not/a/path", exist_ok=True)
        mock_setxattr.assert_called_with(
            "/not/a/path", "user.key", "things".encode()
        )
        mock_unlink.assert_called_with("/not/a/path")

    def test_pop(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True) as mock__getitem__:
            mock__getitem__.return_value = "value"
            with patch.object(
                d, "__delitem__", autospec=True
            ) as mock__delitem__:
                self.assertEqual(d.pop("file1"), "value")
                mock__delitem__.assert_called_with("file1")

    def test_pop_default(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True) as mock__getitem__:
            mock__getitem__.side_effect = KeyError
            with patch.object(
                d, "__delitem__", autospec=True
            ) as mock__delitem__:
                self.assertEqual(d.pop("file1", "default1"), "default1")
                mock__delitem__.assert_called_with("file1")

    def test_pop_no_default_keyerror(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True) as mock__getitem__:
            mock__getitem__.side_effect = KeyError
            with patch.object(
                d, "__delitem__", autospec=True
            ) as mock__delitem__:
                with self.assertRaises(KeyError):
                    d.pop("file1")
                mock__delitem__.assert_called_with("file1")

    def test_popitem(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True):
            with patch.object(d, "__delitem__", autospec=True):
                with patch.object(
                    d, "__iter__", autospec=True
                ) as mock__iter__:
                    mock__iter__.return_value = iter(["file1", "file2"])
                    with patch.object(d, "pop", autospec=True) as mock_pop:
                        mock_pop.side_effect = ["value1", "value2"]
                        item_value = d.popitem()

        self.assertEqual(item_value, "value1")

    def test_popitem(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__getitem__", autospec=True):
            with patch.object(d, "__delitem__", autospec=True):
                with patch.object(
                    d, "__iter__", autospec=True
                ) as mock__iter__:
                    mock__iter__.return_value = iter(["file1", "file2"])
                    with patch.object(d, "pop", autospec=True) as mock_pop:
                        mock_pop.side_effect = StopIteration
                        with self.assertRaises(KeyError):
                            d.popitem()

    @patch("os.scandir", autospec=True)
    def test_repr(self, mock_scandir):
        d = iodict.IODict(path="/not/a/path")
        self.assertEqual(d.__repr__(), "{}")

    def test_setdefault(self):
        read_data = pickle.dumps("")
        d = iodict.IODict(path="/not/a/path")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            item = d.setdefault("not-an-item")

        self.assertEqual(item, None)

    def test_setdefault_default(self):
        read_data = pickle.dumps({"a": 1})
        d = iodict.IODict(path="/not/a/path")
        with patch(
            "builtins.open", unittest.mock.mock_open(read_data=read_data)
        ):
            item = d.setdefault("not-an-item", {"a": 1})

        self.assertEqual(item, {"a": 1})

    def test_update(self):
        mapping = {"a": 1, "b": 2, "c": 3}
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__setitem__", autospec=True) as mock__setitem__:
            d.update(mapping)
        mock__setitem__.assert_has_calls(
            [call("a", 1), call("b", 2), call("c", 3)]
        )

    def test_values(self):
        d = iodict.IODict(path="/not/a/path")
        with patch.object(d, "__iter__", autospec=True) as mock__iter__:
            mock__iter__.return_value = ["file1", "file2"]
            with patch.object(
                d, "__getitem__", autospec=True
            ) as mock__getitem__:
                mock__getitem__.side_effect = ["value1", "value2"]
                return_items = [i for i in d.values()]

        self.assertEqual(return_items, ["value1", "value2"])


class TestDurableQueue(BaseTest):
    def setUp(self):
        super().setUp()
        self.patched_iodict = patch("directord.iodict.IODict")
        self.mock_iodict = self.patched_iodict.start()
        self.m = self.mock_iodict.return_value = MagicMock()
        self.m._db_path = "/not/a/path"

    def tearDown(self):
        super().tearDown()
        self.patched_iodict.stop()

    def test_close(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with patch("os.rmdir") as mock_rmdir:
            q.close()

    def test_close_missing(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with patch("os.rmdir") as mock_rmdir:
            mock_rmdir.side_effect = FileNotFoundError
            q.close()

    def test_empty(self):
        q = iodict.DurableQueue(path="/not/a/path")
        self.assertEqual(q.empty(), True)
        with patch.object(self.m, "__len__"):
            self.assertEqual(q.empty(), False)

    def test_get_negative_timeout(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with self.assertRaises(ValueError):
            q.get(timeout=-1)

    def test_get_timeout(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with self.assertRaises(queue.Empty):
            q.get(timeout=0.1)

    def test_get(self):
        with patch.object(self.m, "__len__") as mock_len:
            mock_len.return_value = 1
            q = iodict.DurableQueue(path="/not/a/path")
            with patch.object(
                q._count, "acquire", autospec=True
            ) as mock_acquire:
                with patch.object(q._queue, "popitem") as mock_popitem:
                    mock_popitem.return_value = "test"
                    self.assertEqual(q.get(), "test")
                    mock_acquire.assert_called_with(True, None)

    def test_getnowait(self):
        with patch.object(self.m, "__len__") as mock_len:
            mock_len.return_value = 1
            q = iodict.DurableQueue(path="/not/a/path")
            with patch.object(
                q._count, "acquire", autospec=True
            ) as mock_acquire:
                with patch.object(q._queue, "popitem") as mock_popitem:
                    mock_popitem.return_value = "test"
                    self.assertEqual(q.get_nowait(), "test")
                    mock_acquire.assert_called_with(False, None)

    def test_put(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with patch.object(self.m, "_queue") as mock__queue:
            mock__queue.return_value = dict()
            with patch("builtins.open", unittest.mock.mock_open()):
                q.put("test")

    def test_putnowait(self):
        q = iodict.DurableQueue(path="/not/a/path")
        with patch.object(self.m, "_queue") as mock__queue:
            mock__queue.return_value = dict()
            with patch("builtins.open", unittest.mock.mock_open()):
                q.put_nowait("test")


class _FlushQueue(queue.Queue, iodict.FlushQueue):
    def __init__(self, path, lock=None, semaphore=None):
        super().__init__()
        self.path = path
        self.lock = lock
        self.semaphore = semaphore


class TestFlushQueue(BaseTest):
    def setUp(self):
        super().setUp()
        self.patched_iodict = patch("directord.iodict.IODict")
        self.mock_iodict = self.patched_iodict.start()
        self.m = self.mock_iodict.return_value = MagicMock()
        self.m._db_path = "/not/a/path"
        self.patched_queue = patch.object(self.m, "_queue")
        self.mock__queue = self.patched_queue.start()
        self.mock__queue.return_value = dict()

    def tearDown(self):
        super().tearDown()
        self.patched_iodict.stop()
        self.patched_queue.stop()

    @patch("os.scandir", autospec=True)
    def test_flush_ingest(self, mock_scandir):
        mock_scandir.return_value = [MockItem("file1"), MockItem("file2")]
        q = _FlushQueue(path="/not/a/path")
        for i in range(10):
            q.put(i)

        self.assertEqual(q.qsize(), 10)
        with patch("builtins.open", unittest.mock.mock_open()):
            q.flush()
        self.assertEqual(q.qsize(), 0)
        with patch("os.path.exists", autospec=True) as mock_exists:
            mock_exists.return_value = True
            with patch("os.rmdir", autospec=True) as mock_rmdir:
                with patch("os.unlink", autospec=True):
                    q.ingest()

        mock_exists.assert_called()
        mock_rmdir.assert_called()

    def test_ingest_no_exists(self):
        q = _FlushQueue(path="/not/a/path")
        with patch("os.path.exists", autospec=True) as mock_exists:
            mock_exists.return_value = False
            q.ingest()
        self.mock__queue.assert_not_called()

    @patch("os.scandir", autospec=True)
    def test_ingest(self, mock_scandir):
        mock_scandir.return_value = [MockItem("file1"), MockItem("file2")]
        q = _FlushQueue(path="/not/a/path")
        with patch("os.path.exists", autospec=True) as mock_exists:
            mock_exists.return_value = True
            with patch("directord.iodict.DurableQueue") as mock_durablequeue:
                m = mock_durablequeue.return_value = MagicMock()
                g = m.get_nowait = MagicMock()
                g.side_effect = ["a", KeyError]
                with patch("os.unlink", autospec=True):
                    q.ingest()
        self.mock__queue.assert_not_called()

    def test_flushqueue_attrs(self):
        q = iodict.FlushQueue(path="/not/a/path")
        self.assertEqual(q.path, "/not/a/path")
        self.assertEqual(q.lock, None)
        self.assertEqual(q.semaphore, None)
