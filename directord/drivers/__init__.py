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

import socket
import time

from directord import logger
from directord import utils


class BaseDriver:
    nullbyte = b"\000"  # Signals null
    coordination_failed = b"\007"  # Signals worker is ready
    coordination_ack = b"\020"  # Signals worker is ready
    coordination_notice = b"\021"  # Signals worker is ready

    transfer_start = b"\002"  # Signals start file transfer
    transfer_end = b"\003"  # Signals start file transfer

    heartbeat_notice = b"\005"  # Signals worker heartbeat
    job_ack = b"\006"  # Signals job started
    job_end = b"\004"  # Signals job ended
    job_failed = b"\025"  # Signals job failed
    job_processing = b"\026"  # Signals job running

    def __init__(
        self, args, encrypted_traffic_data=None, connection_string=None
    ):
        """Initialize the Driver.

        :param args: Arguments parsed by argparse.
        :type args: Object
        "param encrypted_traffic: Enable|Disable encrypted traffic.
        :type encrypted_traffic: Boolean
        """

        self.encrypted_traffic_data = encrypted_traffic_data
        self.connection_string = connection_string
        self.identity = socket.gethostname()
        self.log = logger.getLogger(name="directord")
        self.args = args

    def __copy__(self):
        """Return a copy of the base class.

        :returns: Object
        """

        return self

    def socket_send(
        self,
        socket,
        identity=None,
        msg_id=None,
        control=None,
        command=None,
        data=None,
        info=None,
        stderr=None,
        stdout=None,
    ):
        """Send a message over a socket.

        All message information is assumed to be byte encoded.

        All possible control characters are defined within the Interface class.
        For more on control characters review the following
        URL(https://donsnotes.com/tech/charsets/ascii.html#cntrl).

        :param socket: Socket object.
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
        """

        if not msg_id:
            msg_id = utils.get_uuid().encode()

        if not control:
            control = self.nullbyte

        if not command:
            command = self.nullbyte

        if not data:
            data = self.nullbyte

        if not info:
            info = self.nullbyte

        if not stderr:
            stderr = self.nullbyte

        if not stdout:
            stdout = self.nullbyte

        pass

    @staticmethod
    def socket_recv(socket):
        """Receive a message over a socket.

        :param socket: socket object.
        :type socket: Object
        """

        pass

    def job_connect(self):
        """Connect to a job socket and return the socket.

        :returns: Object
        """

        pass

    def backend_connect(self):
        """Connect to a transfer socket and return the socket.

        :returns: Object
        """

        pass

    def heartbeat_connect(self):
        """Connect to a heartbeat socket and return the socket.

        :returns: Object
        """

        pass

    def heartbeat_bind(self):
        """Bind an address to a heartbeat socket and return the socket.

        :returns: Object
        """

        pass

    def heartbeat_reset(self, bind_heatbeat=None):
        """Reset the connection on the heartbeat socket.

        Returns a new ttl after reconnect.

        :param bind_heatbeat: heart beat bind object.
        :type bind_heatbeat: Object
        :returns: Tuple
        """

        return (
            self.get_heartbeat(interval=self.args.heartbeat_interval),
            self.heartbeat_connect(),
        )

    def job_bind(self):
        """Bind an address to a job socket and return the socket.

        :returns: Object
        """

        pass

    def backend_bind(self):
        """Bind an address to a transfer socket and return the socket.

        :returns: Object
        """

        pass

    def bind_check(self, bind, interval=1, constant=1000):
        """Return True if a bind type contains work ready.

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

    def key_generate(self, keys_dir, key_type):
        """Generate certificate.

        :param keys_dir: Full Directory path where a given key will be stored.
        :type keys_dir: String
        :param key_type: Key type to be generated.
        :type key_type: String
        """

        pass

    def get_heartbeat(self, interval=0):
        """Return a new hearbeat interval time.

        :param interval: Padding for heartbeat interval.
        :type interval: Integer|Float
        :returns: Float
        """

        return time.time() + interval

    def get_expiry(self, heartbeat_interval=60, interval=3):
        """Return a new expiry time.

        :param interval: Exponential back off for expiration.
        :type interval: Integer|Float
        :returns: Float
        """

        return time.time() + (heartbeat_interval * interval)

    def create_proxy(front, back):
        """Create proxy bind.

        Bind two interfaces into a proxy.

        :param front: Frontend interface.
        :type front: Object
        :param back: Backend interface.
        :type back: Object
        """

        pass
