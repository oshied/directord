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

import contextlib
import importlib
import importlib.util as importlib_util
import json
import logging
import multiprocessing
import os
import signal
import socket
import sys
import time

from logging import handlers
from types import SimpleNamespace


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
            return log
    else:
        return LogSetup(debug_logging=debug_logging).default_logger(
            name=name.split(".")[0]
        )


def send_data(socket_path, data):
    """Send data to the socket path.

    The send method takes serialized data and submits it to the given
    socket path.

    This method will return information provided by the server in
    String format.

    :returns: String
    """

    with UNIXSocketConnect(socket_path) as s:
        s.sendall(data.encode())
        fragments = []
        while True:
            chunk = s.recv(1024)
            if not chunk:
                break
            else:
                fragments.append(chunk)
        return b"".join(fragments)


def component_import(component, desc=None, job_id=None):
    """Import a component and return a tuple with the class object.

    If the component isn't a builtin the system will search
    the shared path for a user defined component.

    > Return: (Boolean, Boolean, Object|String)

    :param component: String name of the component.
    :type component: String
    :param desc: Optional component description, used server side.
    :type desc: String
    :param job_id: Job UUID, used client side.
    :type job_id: String
    :returns: Tuple
    """

    try:
        component_obj = importlib.import_module(
            ".components.builtin_{}".format(component), package="directord"
        )
        transfer = None
    except ImportError as e:
        error = str(e)
        paths = [
            os.path.join(sys.base_prefix, "share/directord/components"),
            "/etc/directord/components",
        ]
        if sys.base_prefix != sys.prefix:
            paths.insert(
                0, os.path.join(sys.prefix, "share/directord/components")
            )

        for path in paths:
            try:
                transfer = os.path.join(path, "{}.py".format(component))
                name = "directord_user_component_{}".format(component)
                spec = importlib_util.spec_from_file_location(name, transfer)
                component_obj = importlib_util.module_from_spec(spec)
                sys.modules[name] = component_obj
                spec.loader.exec_module(component_obj)
            except (ImportError, FileNotFoundError) as e:
                error += "\n{}".format(str(e))
            else:
                break
        else:
            info = (
                "Failure - Unknown Component\n"
                "ERROR:{}\nCOMMAND:{}\nID:{}\nPATH:{}".format(
                    error, component, job_id, paths
                )
            )
            return False, transfer, info

    return True, transfer, component_obj.Component()


class LogSetup(object):
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

        If ``log_dir`` exists and the userID is 0 the log file will be written
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
        else:
            return os.path.join(home, filename)


class Processor(object):
    """Processing class, provides queing and threading utilities.

    This is a base class.
    """

    job_queue = multiprocessing.Queue()
    thread = multiprocessing.Process
    manager = multiprocessing.Manager()
    processes = list()

    def __init__(self):
        """Initialize Processor class creating all required manager objects.

        Managers maintain a multiprocessing proxy object which allows data to
        be shared across threads.
        """

        self.workers = self.manager.dict()
        self.return_jobs = self.manager.dict()
        self.log = getLogger(name="directord")

    def run_threads(self, threads):
        """Execute process objects from an array.

        The array of threads are processed and started in a "daemon" mode.
        Once started the thread object is added into a cleanup array which
        is then joined.

        :param threads: An array of Process objects.
        :type threads: List
        """

        for t in threads:
            t.daemon = True
            self.processes.append(t)
            t.start()

        for t in self.processes:
            t.join()

    def wq_prune(self, workers):
        """Given a Manager.Dictionary object return a pruned hash.

        This will ensure that the items contained within the provided hash
        are valid.

        :param workers: Hash containing workers.
        :type workers: Manager.Dictionary()
        :returns: Tuple
        """

        try:
            return {
                key: value
                for (key, value) in workers.items()
                if time.time() <= value
            }
        finally:
            self.log.debug(
                "workers after prune {workers}".format(workers=len(workers))
            )

    @staticmethod
    def wq_empty(workers):
        """Empty all items from a Manager.Dict.

        Because a Manager Dict is a proxy object we don't want to replace the
        object we want to empty it keeping the original proxy intact. This
        method will pop all items from the object.
        """

        try:
            while workers.popitem():
                pass
        except KeyError:
            pass

    def read_in_chunks(self, file_object, chunk_size=10240):
        """Generator to read a file piece by piece.

        Default chunk size: 10K.

        :param file_object: Open File Object
        :type file_object: Object
        :yields: Data
        """

        while True:
            data = file_object.read(chunk_size)
            if not data:
                break
            self.log.debug(
                "Transimitting a {size} Chunk ".format(size=len(data))
            )
            yield data

    @contextlib.contextmanager
    def timeout(self, time, job_id, reraise=False):
        """Registers a context manager to raise whenever a timeout occurs.

        :param time: Time in seconds before an alarm is raised.
        :type time: Integer
        :param job_id: Job UUID
        :type job_id: String
        :param reraise: Reraise the timeout exception
        :type reraise: Boolean
        :yields:
        """

        signal.signal(signal.SIGALRM, self.raise_timeout)
        signal.alarm(time)
        try:
            yield
        except TimeoutError:
            self.log.warning(
                "Timeout encountered after {} seconds running {}.".format(
                    time, job_id
                )
            )
            if reraise:
                raise TimeoutError
        finally:
            signal.signal(signal.SIGALRM, signal.SIG_IGN)

    def raise_timeout(self, *args, **kwargs):
        """Log, then raise a Timeout error."""

        self.log.error("Task timeout encountered.")
        raise TimeoutError


class UNIXSocketConnect(object):
    """Context manager for connecting to a UNIX socket."""

    def __init__(self, sock_path):
        """Initialize the UNIX socket connect context manager.

        :param socket_path: Path to the local file system socket.
        :type socket_path: String
        """

        self.socket_path = sock_path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def __enter__(self):
        """Upon enter, connect to the socket and return the socket object.

        :returns: Object
        """

        self.sock.connect(self.socket_path)
        return self.sock

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the unix socket."""

        self.sock.close()


class DirectordConnect(object):
    """Library context manager providing easy access into Directord."""

    def __init__(self, debug=False, socket_path="/var/run/directord.sock"):
        """Initialize the connection.

        Basic usage.

        > with DirectordConnect() as d:
        ...   # Run orchestrations.
        ...   ids = d.orchestrate(
        ...       orchestrations=jobs
        ...   )

        :param debug: Enable|Disable debug mode.
        :type debug: Boolean
        :param socket_path: Socket path used to connect to Directord.
        :type socket_path: String
        """

        args = SimpleNamespace(**{"debug": debug, "socket_path": socket_path})
        _mixin = importlib.import_module(".mixin", package="directord")
        self.mixin = _mixin.Mixin(args=args)
        _user = importlib.import_module(".user", package="directord")
        self.manage = _user.Manage(args=args)

    def __enter__(self):
        """Enter the context manager returning self."""

        return self

    def __exit__(self, *args, **kwargs):
        """Shutdown the context manager."""

        pass

    @staticmethod
    def _from_json(return_obj):
        """Decode a byte object and return the loaded JSON data.

        :param return_obj: Byte encoded JSON string.
        :type return_objL Bytes
        :returns: Dictionary
        """

        return json.loads(return_obj.decode())

    def orchestrate(self, orchestrations, defined_targets=None):
        """Run an orchestration and return a list of job IDs.

        :param orchestrations: List of dictionary objects used to run
                               orchestrations.
        :type orchestrations: List
        :param defined_targets: List of Directord Targets.
        :type defined_targets: List
        :returns: List
        """

        return [
            i.decode()
            for i in self.mixin.exec_orchestrations(
                orchestrations,
                defined_targets=defined_targets,
                return_raw=True,
            )
        ]

    def poll(self, job_id):
        """Poll for the completion of a given job ID.

        :param job_id: Job UUID.
        :type job_id: String
        :returns: Tuple
        """
        return self.manage.poll_job(job_id=job_id)

    def list_nodes(self):
        """Return a list of all active Directord Nodes.

        :returns: List
        """

        return list(
            dict(
                self._from_json(self.manage.run(override="list-nodes"))
            ).keys()
        )

    def list_jobs(self):
        """Return a dictionary of all current Directord jobs.

        :returns: Dictionary
        """

        return dict(self._from_json(self.manage.run(override="list-jobs")))

    def purge_nodes(self):
        """Purge all nodes from the work pool.

        Purge all nodes from the pool, all remaining active nodes will
        recheck-in and be added to the pool.

        :returns: Boolean
        """

        return self._from_json(self.manage.run(override="purge-nodes"))[
            "success"
        ]

    def purge_jobs(self):
        """Purge all jobs from the return manager.

        Purge all jobs from the return manager.

        :returns: Boolean
        """

        return self._from_json(self.manage.run(override="purge-jobs"))[
            "success"
        ]
