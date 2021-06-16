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

import logging
import os

from logging import handlers


def getLogger(name, debug_logging=False):
    """Return a logger from a given name.

    If the name does not have a log handler, this will create one for it based
    on the module name which will log everything to a log file in a location
    the executing user will have access to.

    :param name: Log handler name to retrieve.
    :type name: String
    :returns: Object
    """

    log = logging.getLogger(name=name)
    for handler in log.handlers:
        if name == handler.name:
            if debug_logging:
                handler.setLevel(logging.DEBUG)
                log.setLevel(logging.DEBUG)
            return log
    else:
        return LogSetup(debug_logging=debug_logging).default_logger(
            name=name.split(".")[0]
        )


class LogSetup:
    """Logging Class."""

    def __init__(self, max_size=500, max_backup=5, debug_logging=False):
        """Setup Logging.

        :param max_size: Set max log file size
        :type max_size: Integer
        :param max_backup: Set max log file back rotations.
        :type max_backup: Integer
        :param debug_logging: Enable | Disable debug logging.
        :type debug_logging: Boolean
        """

        self.max_size = max_size * 1024 * 1024
        self.max_backup = max_backup
        self.debug_logging = debug_logging
        self.format = None
        self.name = None
        self.enable_stream = False
        self.enable_file = False

    def default_logger(
        self, name=__name__, enable_stream=True, enable_file=False
    ):
        """Default Logger.

        This is set to use a rotating File handler and a stream handler.
        If you use this logger all logged output that is INFO and above will
        be logged, unless debug_logging is set then everything is logged.
        The logger will send the same data to a stdout as it does to the
        specified log file.

        You can disable the default handlers by setting either `enable_file` or
        `enable_stream` to `False`

        :param name: Log handler name to retrieve.
        :type name: String
        :param enable_stream: Enable | Disable log Streaming.
        :type enable_stream: Boolean
        :param enable_file: Enable | Disable log writting to a file.
        :type enable_file: Boolean
        :returns: Object
        """

        log = logging.getLogger(name)
        self.name = name

        if enable_file:
            self.enable_file = enable_file
            file_handler = handlers.RotatingFileHandler(
                filename=self.return_logfile(filename="%s.log" % name),
                maxBytes=self.max_size,
                backupCount=self.max_backup,
            )
            self.set_handler(log, handler=file_handler)

        if enable_stream:
            self.enable_stream = enable_stream
            stream_handler = logging.StreamHandler()
            self.set_handler(log, handler=stream_handler)

        return log

    def set_handler(self, log, handler):
        """Set the logging level as well as the handlers.

        :param log: Logging object.
        :type log: Object
        :param handler: Log handler object.
        :type handler: Object
        """

        if self.debug_logging:
            log.setLevel(logging.DEBUG)
            handler.setLevel(logging.DEBUG)
        else:
            log.setLevel(logging.INFO)
            handler.setLevel(logging.INFO)

        handler.name = self.name

        if not self.format:
            if self.enable_file:
                self.format = logging.Formatter(
                    "%(asctime)s %(levelname)s %(message)s"
                )
            else:
                self.format = logging.Formatter("%(levelname)s %(message)s")

        handler.setFormatter(self.format)
        log.addHandler(handler)

    @staticmethod
    def return_logfile(filename, log_dir="/var/log"):
        """Return a path for logging file.

        If `log_dir` exists and the userID is 0 the log file will be written
        to the provided log directory. If the UserID is not 0 or log_dir does
        not exist the log file will be written to the users home folder.

        :param filename: File name to write log messages.
        :type filename: String
        :param log_dir: Directory where the log file will be stored.
        :type log_dir: String
        :returns: String
        """

        user = os.getuid()
        home = os.path.expanduser("~")

        if not os.path.isdir(log_dir):
            return os.path.join(home, filename)

        log_dir_stat = os.stat(log_dir)
        if log_dir_stat.st_uid == user:
            return os.path.join(log_dir, filename)
        elif log_dir_stat.st_gid == user:
            return os.path.join(log_dir, filename)

        return os.path.join(home, filename)
