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

from directord import logger


class TestLoggerHandlers(unittest.TestCase):
    def setUp(self):

        self.rh_patched = unittest.mock.patch(
            "directord.logger.handlers.RotatingFileHandler"
        )
        self.rh = self.rh_patched.start()

        self.sh_patched = unittest.mock.patch(
            "directord.logger.logging.StreamHandler"
        )
        self.sh = self.sh_patched.start()

        self.log = logger.LogSetup()

        self._log = unittest.mock.Mock()
        self._handler = unittest.mock.Mock()

    def tearDown(self):
        self.rh_patched.stop()
        self.sh_patched.stop()

    def test_getlogger_new_logger(self):
        log = logger.getLogger(name="testLogger")
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
