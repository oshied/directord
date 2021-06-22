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
import socket
import time

import directord


class Interface(directord.Processor):
    """The Interface class.

    This class defines everything required to connect to or from a given
    server.
    """

    def __init__(self, args):
        """Initialize the interface class.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Interface, self).__init__()

        self.args = args

        # Set log handlers to debug when enabled.
        if self.args.debug:
            self.log.setLevel(logging.DEBUG)
            for handler in self.log.handlers:
                handler.setLevel(logging.DEBUG)

        mode = getattr(self.args, "mode", None)
        if mode == "client":
            self.bind_address = self.args.server_address
        elif mode == "server":
            self.bind_address = self.args.bind_address
        else:
            self.bind_address = "*"

        self.proto = "tcp"
        self.connection_string = "{proto}://{addr}".format(
            proto=self.proto, addr=self.bind_address
        )

        self.identity = socket.gethostname()

        self.heartbeat_liveness = 3
        try:
            self.heartbeat_interval = self.args.heartbeat_interval
        except AttributeError:
            self.heartbeat_interval = 1

        self.log.info("Connecting to messaging driver")
        self.driver = directord.plugin_import(plugin=".drivers.zmq")

        self.base_dir = "/etc/directord"
        self.public_keys_dir = os.path.join(self.base_dir, "public_keys")
        self.secret_keys_dir = os.path.join(self.base_dir, "private_keys")
        self.keys_exist = os.path.exists(
            self.public_keys_dir
        ) and os.path.exists(self.secret_keys_dir)

    @property
    def get_heartbeat(self):
        """Return a new hearbeat interval time.

        :returns: Float
        """

        return time.time() + self.heartbeat_interval

    @property
    def get_expiry(self):
        """Return a new expiry time.

        :returns: Float
        """

        return time.time() + (
            self.heartbeat_interval * self.heartbeat_liveness
        )
