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
import multiprocessing
import os
import signal
import socket
import sys

from types import SimpleNamespace

from directord import meta
from directord import logger
from directord.meta import __version__  # noqa


def send_data(socket_path, data):
    """Send data to the socket path.

    The send method takes serialized data and submits it to the given
    socket path.

    This method will return information provided by the server in
    String format.

    :returns: String
    """

    try:
        with UNIXSocketConnect(socket_path) as s:
            if not s:
                raise SystemExit("No connection available to server.")
            s.sendall(data.encode())
            fragments = []
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break

                fragments.append(chunk)
            return b"".join(fragments)
    except PermissionError:
        log = logger.getLogger(name="directord")
        error_msg = (
            "Permission error writing to {}. Check write permissions.".format(
                socket_path
            )
        )
        log.error(
            error_msg,
        )
        raise PermissionError(error_msg)


def plugin_import(plugin):
    """Import a plugin from string.

    :param plugin: Python import in dot notation.
    :type plugin: String
    :returns: Object
    """

    return importlib.import_module(plugin, package="directord")


def component_import(component, job_id=None):
    """Import a component and return a tuple with the class object.

    If the component isn't a builtin the system will search
    the shared path for a user defined component.

    > Return: (Boolean, Boolean, Object|String)

    :param component: String name of the component.
    :type component: String
    :param job_id: Job UUID, used client side.
    :type job_id: String
    :returns: Tuple
    """

    try:
        component_obj = plugin_import(
            plugin=".components.builtin_{}".format(component)
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


class Processor:
    """Processing class, provides queing and threading utilities.

    This is a base class.
    """

    cpu_count = multiprocessing.cpu_count() * 2
    if cpu_count > 16:
        cpu_count = 16

    thread = multiprocessing.Process

    def __init__(self):
        """Initialize Processor class creating all required manager objects.

        Managers maintain a multiprocessing proxy object which allows data to
        be shared across threads.
        """

        self.log = logger.getLogger(name="directord")

    @staticmethod
    def get_manager():
        """Returns a multiprocessing manager."""

        return multiprocessing.Manager()

    @staticmethod
    def get_lock():
        """Returns a multiprocessing lock."""

        return multiprocessing.Lock()

    @staticmethod
    def get_queue():
        """Returns a multiprocessing queue."""

        return multiprocessing.Queue()

    def terminate_process(self, process):
        """Terminate a processes when possible.

        * If the process object is null, return False
        * If the process is in an "alive", return False.

        :param process: Multiprocessing object.
        :type process: Object
        :returns: Boolean
        """

        if not process:
            return False

        try:
            if not process.is_alive():
                process.join(timeout=0.1)
                process.terminate()
                self.log.info("Process [ %s ] cleaned up", process.name)
                return True
        except Exception as e:
            self.log.warning(
                "Thread [ %s ] saw exception when terminating: %s",
                process.name,
                str(e),
            )

        return False

    def run_threads(self, threads):
        """Execute process objects from an array.

        The array of threads are processed and started in a "daemon" mode.
        Once started the thread object is added into a cleanup array which
        is then joined.

        > Each item within the threads list consists of a tuple
          (Process(), Boolean). The boolean is used to enable or disable
          a daemonic process.

        :param threads: An array of Process objects.
        :type threads: List
        """

        for t, daemon in threads:
            t.daemon = daemon
            t.start()

        for t, _ in threads:
            t.join()

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
                "Timeout encountered after [ %s ] seconds running [ %s ].",
                time,
                job_id,
            )
            if reraise:
                raise TimeoutError
        finally:
            signal.signal(signal.SIGALRM, signal.SIG_IGN)

    def raise_timeout(self, *args, **kwargs):
        """Log, then raise a Timeout error."""

        self.log.error("Task timeout encountered.")
        raise TimeoutError


class UNIXSocketConnect:
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

        try:
            self.sock.connect(self.socket_path)
        except ConnectionRefusedError as e:
            print(str(e))
            self.__exit__()
        else:
            return self.sock

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the unix socket."""

        self.sock.close()


class DirectordConnect:
    """Library context manager providing easy access into Directord."""

    def __init__(
        self,
        debug=False,
        socket_path="/var/run/directord.sock",
        driver=meta.__driver_default__,
        force_async=False,
    ):
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
        :param force_async: Forces all orchestrations to run asynchronously.
        :type: force_async: Boolean
        """

        args = SimpleNamespace(
            **{
                "debug": debug,
                "socket_path": socket_path,
                "driver": driver,
                "force_async": force_async,
            }
        )
        _mixin = plugin_import(plugin=".mixin")
        self.mixin = _mixin.Mixin(args=args)
        _user = plugin_import(plugin=".user")
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

        state, status, _, _, _ = self.manage.poll_job(job_id=job_id)
        return state, status

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


class Spinner(object):
    """Creates a visual indicator while normally performing actions."""

    def __init__(self, run=False):
        """Create an indicator thread while a job is running.

        Context Manager Usage:

        >>> with Spinner():
        ...     # Your awesome work here...
        ...     print('hello world')
        Object Usage:
        >>> spinner = Spinner()
        >>> job = spinner.start()
        >>> # Your amazing work here...
        >>> print('hello world')
        >>> job.terminate()

        :param run: Enable | disable debug
        :type run: Boolean
        """

        self.job = multiprocessing.Process(target=self.indicator, daemon=True)
        self.pipe_a, self.pipe_b = multiprocessing.Pipe()
        self.run = run
        self.msg = "Please wait..."

    def __enter__(self):
        if self.run:
            self.job.start()

        return self

    def __exit__(self, *args, **kwargs):
        if self.run:

            self.run = False
            self.pipe_a.close()
            self.pipe_b.close()
            self.job.terminate()
            print("Done.")

    def indicator_msg(self, msg):
        """Send a message to the indicator.

        If the indicator is running, send a message, otherwise return.

        :param msg: Indicator message.
        :type msg: String
        """

        if self.run:
            self.pipe_b.send(msg)
        else:
            return msg

    def indicator(self):
        """Produce the spinner."""

        while self.run:
            for item in ["|", "/", "-", "\\"]:
                if self.pipe_a.poll(timeout=0.1):
                    self.msg = self.pipe_a.recv()

                sys.stdout.write("\r[ {} ] {} ".format(item, self.msg))
                sys.stdout.flush()
