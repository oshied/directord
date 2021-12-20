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

import os
import queue
import socket
import time
import threading

from directord import iodict
from directord import logger
from directord import models


def parse_args(parser):
    """Add arguments for this driver to the parser.

    :param parser: Parser
    :type parser: Object
    """

    pass


class ExceptionThreadProcessor(threading.Thread):
    """Create an exception handling thread class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = None

    def run(self):
        """Run, but wrapped to store any encountered exception."""

        try:
            super().run()
        except Exception as e:
            self.exception = e


class _FlushQueue(queue.Queue, iodict.FlushQueue):
    """Flush queue capability helper class."""

    def __init__(self, path, lock, semaphore):
        super().__init__()
        self.path = path
        self.lock = lock
        self.semaphore = semaphore


class BaseDriver(models.BaseModel):
    thread_processor = ExceptionThreadProcessor
    event = threading.Event()
    semaphore = threading.Semaphore
    flushqueue = _FlushQueue

    def __init__(
        self,
        args,
        encrypted_traffic_data=None,
        interface=None,
    ):
        """Initialize the Driver.

        :param args: Arguments parsed by argparse.
        :type args: Object
        "param encrypted_traffic: Enable|Disable encrypted traffic.
        :type encrypted_traffic: Boolean
        """

        self.encrypted_traffic_data = encrypted_traffic_data
        self.log = logger.getLogger(name="directord")
        self.args = args

        self.identity = getattr(args, "identity", socket.gethostname())
        if not self.identity:
            self.identity = socket.gethostname()

        self.machine_id = getattr(args, "machine_id", self.get_machine_id())
        if not self.machine_id:
            self.machine_id = self.get_machine_id()

        self.interface = interface

    def shutdown(self):
        """Shutdown the driver."""

        pass

    @staticmethod
    def get_lock():
        """Returns a thread lock."""

        return threading.Lock()

    def get_queue(self, name):
        """Returns a thread lock.

        :param name: Queue name.
        :type name: String
        :returns: DurableQueue
        """

        path = os.path.join(
            getattr(self.args, "cache_path", "/var/cache/directord"),
            "queue",
            name,
        )
        q = self.flushqueue(
            path=path, lock=self.get_lock(), semaphore=self.semaphore
        )
        q.ingest()
        return q

    def __copy__(self):
        """Return a copy of the base class.

        :returns: Object
        """

        return self

    def backend_check(self, interval=1, constant=1000):
        """Return True if the backend contains work ready.

        :param bind: A given Socket bind to identify.
        :type bind: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Object
        """

        pass

    def backend_close(self):
        """Close the backend."""

        pass

    def backend_init(self):
        """Initialize the backend.

        For server mode, this is a bound local.
        For client mode, it is a connection to the server.

        :returns: Object
        """

        pass

    def backend_recv(self, nonblocking=False):
        """Receive a message.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message parts are byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        """

        pass

    def backend_send(self, *args, **kwargs):
        """Send a message over the backend.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message information is assumed to be byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param identity: Target where message will be sent.
        :type identity: Bytes
        :param msg_id: ID information for a given message. If no ID is
                       provided a UUID will be generated.
        :type msg_id: Bytes
        :param control: ASCII control charaters.
        :type control: Bytes
        :param command: Command definition for a given message.
        :type command: Bytes
        :param data: Encoded data that will be transmitted.
        :type data: Bytes
        :param info: Encoded information that will be transmitted.
        :type info: Bytes
        :param stderr: Encoded error information from a command.
        :type stderr: Bytes
        :param stdout: Encoded output information from a command.
        :type stdout: Bytes
        :param nonblocking: Enable non-blocking send.
        :type nonblocking: Boolean
        :returns: Object
        """

        pass

    def get_expiry(self, heartbeat_interval=60, interval=3):
        """Return a new expiry time.

        :param interval: Exponential back off for expiration.
        :type interval: Integer|Float
        :returns: Float
        """

        return time.time() + (heartbeat_interval * interval)

    def get_machine_id(self):
        """Return the unique machine ID.

        This property will iterate through list of known unique identifiers
        and return the first found with a valid value.

        If no valid unique identifier is found, return the identity.

        :returns: String
        """

        unique_identifiers = [
            "/sys/class/dmi/id/product_uuid",
            "/run/machine-id",
            "/etc/machine-id",
            "/var/lib/dbus/machine-id",
            "/proc/sys/kernel/random/boot_id",
        ]
        for identifier in unique_identifiers:
            try:
                with open(identifier, "r") as f:
                    machine_id = f.read().strip()
            except (FileNotFoundError, PermissionError):
                pass
            else:
                if machine_id:
                    return machine_id
        else:
            return self.identity

    def heartbeat_send(
        self, host_uptime=None, agent_uptime=None, version=None
    ):
        """Send a heartbeat.

        :param host_uptime: Sender uptime
        :type host_uptime: String
        :param agent_uptime: Sender agent uptime
        :type agent_uptime: String
        :param version: Sender directord version
        :type version: String
        """

        pass

    def job_check(self, interval=1, constant=1000):
        """Return True if a job contains work ready.

        :param bind: A given Socket bind to identify.
        :type bind: Object
        :param interval: Exponential Interval used to determine the polling
                         duration for a given socket.
        :type interval: Integer
        :param constant: Constant time used to poll for new jobs.
        :type constant: Integer
        :returns: Object
        """

        pass

    def job_close(self):
        """Close the job socket."""

        pass

    def job_init(self):
        """Initialize the job socket.

        For server mode, this is a bound local socket.
        For client mode, it is a connection to the server socket.

        :returns: Object
        """

        pass

    def job_recv(self, nonblocking=False):
        """Receive a message.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message parts are byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param nonblocking: Enable non-blocking receve.
        :type nonblocking: Boolean
        """

        pass

    def job_send(self, *args, **kwargs):
        """Send a job message.

        The message specification for server is as follows.

            [
                b"Identity"
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        The message specification for client is as follows.

            [
                b"ID",
                b"ASCII Control Characters",
                b"command",
                b"data",
                b"info",
                b"stderr",
                b"stdout",
            ]

        All message information is assumed to be byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: ZeroMQ socket object.
        :type socket: Object
        :param identity: Target where message will be sent.
        :type identity: Bytes
        :param msg_id: ID information for a given message. If no ID is
                       provided a UUID will be generated.
        :type msg_id: Bytes
        :param control: ASCII control charaters.
        :type control: Bytes
        :param command: Command definition for a given message.
        :type command: Bytes
        :param data: Encoded data that will be transmitted.
        :type data: Bytes
        :param info: Encoded information that will be transmitted.
        :type info: Bytes
        :param stderr: Encoded error information from a command.
        :type stderr: Bytes
        :param stdout: Encoded output information from a command.
        :type stdout: Bytes
        :param nonblocking: Enable non-blocking send.
        :type nonblocking: Boolean
        :returns: Object
        """

        pass
