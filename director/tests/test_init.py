import time
import unittest

import director

from director import tests


class TestLogger(unittest.TestCase):
    def setUp(self):
        self.log = director.LogSetup()

        self.uid_patched = unittest.mock.patch("director.os.getuid")
        self.uid = self.uid_patched.start()

        self.env_patched = unittest.mock.patch("director.os.path.expanduser")
        self.env = self.env_patched.start()

        self.idr_patched = unittest.mock.patch("director.os.path.isdir")
        self.idr = self.idr_patched.start()

        self.stat_patched = unittest.mock.patch("director.os.stat")
        self.stat = self.stat_patched.start()

    def tearDown(self):
        self.uid_patched.stop()
        self.env_patched.stop()
        self.idr_patched.stop()

    def test_logger_max_backup(self):
        self.assertEqual(self.log.max_backup, 5)

    def test_logger_max_size(self):
        self.assertEqual(self.log.max_size, 524288000)

    def test_logger_debug_logging(self):
        self.assertEqual(self.log.debug_logging, False)

    def test_logger_override_backup(self):
        log = director.LogSetup(max_backup=10)
        self.assertEqual(log.max_backup, 10)

    def test_logger_override_max_backup(self):
        log = director.LogSetup(max_backup=10)
        self.assertEqual(log.max_backup, 10)

    def test_logger_override_max_size(self):
        log = director.LogSetup(max_size=10)
        self.assertEqual(log.max_size, 10485760)

    def test_logger_debug_logging_enabled(self):
        log = director.LogSetup(debug_logging=True)
        self.assertEqual(log.debug_logging, True)

    def test_logger_return_logfile_not_root_new_log_dir(self):
        self.uid.return_value = 99
        self.env.return_value = "/home/TestUser"
        self.idr.return_value = False
        self.stat.return_value = tests.FakeStat(uid=99, gid=99)
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/home/TestUser/test_file")

    def test_logger_return_logfile_root_new_log_dir(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = True
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/other/test_file")

    def test_logger_return_logfile_not_root(self):
        self.uid.return_value = 99
        self.env.return_value = "/home/TestUser"
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(filename="test_file")
        self.assertEqual(logfile, "/home/TestUser/test_file")

    def test_logger_return_logfile_root(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = True
        self.stat.return_value = tests.FakeStat(uid=0, gid=0)
        logfile = self.log.return_logfile(filename="test_file")
        self.assertEqual(logfile, "/var/log/test_file")

    def test_logger_return_logfile_root_log_dir_not_found(self):
        self.uid.return_value = 0
        self.env.return_value = "/root"
        self.idr.return_value = False
        logfile = self.log.return_logfile(
            filename="test_file", log_dir="/other"
        )
        self.assertEqual(logfile, "/root/test_file")


class TestLoggerHandlers(unittest.TestCase):
    def setUp(self):

        self.rh_patched = unittest.mock.patch(
            "director.handlers.RotatingFileHandler"
        )
        self.rh = self.rh_patched.start()

        self.sh_patched = unittest.mock.patch("director.logging.StreamHandler")
        self.sh = self.sh_patched.start()

        self.log = director.LogSetup()

        self._log = unittest.mock.Mock()
        self._handler = unittest.mock.Mock()

    def tearDown(self):
        self.rh_patched.stop()
        self.sh_patched.stop()

    def test_getlogger_new_logger(self):
        log = director.getLogger(name="testLogger")
        for handler in log.handlers:
            return self.assertTrue(handler.name == "testLogger")
        else:
            self.fail("The log handler name was not set")

    def test_logger_default_logger(self):
        self.log.format = "%(test)s"
        self.log.default_logger(
            name="test_log", enable_file=False, enable_stream=False
        )
        self.assertEqual(self.log.format, "%(test)s")

    def test_logger_enable_file(self):
        self.log.default_logger(
            name="test_log", enable_file=True, enable_stream=False
        )
        self.assertTrue(self.rh.called)
        self.assertFalse(self.sh.called)

    def test_logger_enable_stream(self):
        self.log.default_logger(
            name="test_log", enable_file=False, enable_stream=True
        )
        self.assertFalse(self.rh.called)
        self.assertTrue(self.sh.called)

    def test_logger_enable_stream_enable_file(self):
        self.log.default_logger(
            name="test_log", enable_file=True, enable_stream=True
        )
        self.assertTrue(self.rh.called)
        self.assertTrue(self.sh.called)

    def test_logger_set_handler(self):
        self.log.set_handler(log=self._log, handler=self._handler)
        self.assertTrue(self._log.setLevel.called)
        self.assertTrue(self._handler.setFormatter.called)
        self.assertTrue(self._log.addHandler.called)


class TestProcessor(unittest.TestCase):
    def setUp(self):
        self.log_patched = unittest.mock.patch("director.getLogger")
        self.log = self.log_patched.start()
        self.processor = director.Processor()

    def tearDown(self):
        self.log_patched.stop()

    def test_wq_prune_0(self):
        workers = self.processor.wq_prune(workers={})
        self.assertDictEqual(workers, dict())
        self.log.debug.called_once()

    def test_wq_prune_valid(self):
        workers = self.processor.wq_prune(
            workers={
                "valid1": time.time() + 2,
                "invalid1": time.time() - 2,
                "invalid2": time.time() - 3,
            }
        )
        self.assertEqual(len(workers), 1)
        self.assertIn("valid1", workers)
        self.log.debug.called_once()

    def test_wq_empty(self):
        self.processor.workers["valid1"] = (time.time() + 2,)
        self.processor.workers["invalid1"] = (time.time() - 2,)
        self.processor.workers["invalid2"] = time.time() - 3
        self.assertEqual(len(self.processor.workers), 3)
        self.processor.wq_empty(workers=self.processor.workers)
        self.assertEqual(len(self.processor.workers), 0)

    def test_read_in_chunks(self):
        chunks = list()
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data="data")
        ) as mock_file:
            with open(mock_file) as f:
                for d in self.processor.read_in_chunks(file_object=f):
                    chunks.append(d)
                    self.log.debug.called_once()
        self.assertListEqual(chunks, ["data"])

    def test_read_in_chunks_set_chunk(self):
        chunks = list()
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data="data")
        ) as mock_file:
            with open(mock_file) as f:
                for d in self.processor.read_in_chunks(
                    file_object=f, chunk_size=1
                ):
                    chunks.append(d)
                    self.log.debug.called_once()
        self.assertListEqual(chunks, ["d", "a", "t", "a"])

    def test_file_sha1(self):
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data=b"data")
        ) as mock_file:
            sha1 = self.processor.file_sha1(file_path=mock_file)
            self.assertEqual(sha1, "a17c9aaa61e80a1bf71d0d850af4e5baa9800bbd")

    def test_file_sha1_set_chunk(self):
        with unittest.mock.patch(
            "builtins.open", unittest.mock.mock_open(read_data=b"data")
        ) as mock_file:
            sha1 = self.processor.file_sha1(file_path=mock_file, chunk_size=1)
            self.assertEqual(sha1, "a17c9aaa61e80a1bf71d0d850af4e5baa9800bbd")

    def test_object_sha1(self):
        sha1 = self.processor.object_sha1(obj={"test": "value"})
        self.assertEqual(sha1, "4e0b1f3b9b1e08306ab4e388a65847c73a902097")

    def test_run_threads(self):
        pass


class TestUnixSocket(unittest.TestCase):
    def setUp(self):
        self.socket_patched = unittest.mock.patch("director.socket.socket")
        self.socket = self.socket_patched.start()

    def tearDown(self):
        self.socket_patched.stop()

    def test_unix_socket(self):
        with director.UNIXSocketConnect(sock_path="/test.sock") as c:
            c.connect.assert_called_once_with("/test.sock")
        c.close.assert_called_once()
        self.socket.assert_called_once_with(
            director.socket.AF_UNIX, director.socket.SOCK_STREAM
        )
