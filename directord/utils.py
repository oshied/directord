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

import hashlib
import json
import os
import socket
import uuid

import yaml

import ssh2
from ssh2.session import Session

from directord import logger


def dump_yaml(file_path, data):
    """Dump data to a file.

    :param file_path: File path to dump data to
    :type file_path: String
    :param data: Dictionary|List data to dump
    :type data: Dictionary|List
    """

    with open(os.path.abspath(os.path.expanduser(file_path)), "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)

    return file_path


def merge_dict(base, new, extend=True):
    """Recursively merge new into base.

    :param base: Base dictionary to load items into
    :type base: Dictionary
    :param new: New dictionary to merge items from
    :type new: Dictionary
    :param extend: Boolean option to enable or disable extending
                   iterable arrays.
    :type extend: Boolean
    :returns: Dictionary
    """

    if isinstance(new, dict):
        for key, value in new.items():
            if key not in base:
                base[key] = value
            elif extend and isinstance(value, dict):
                base[key] = merge_dict(
                    base=base.get(key, {}), new=value, extend=extend
                )
            elif extend and isinstance(value, list):
                base[key].extend(value)
            elif extend and isinstance(value, (tuple, set)):
                if isinstance(base.get(key), tuple):
                    base[key] += tuple(value)
                elif isinstance(base.get(key), list):
                    base[key].extend(list(value))
            else:
                base[key] = new[key]
    elif isinstance(new, list):
        if extend:
            base.extend(new)
        else:
            base = new

    return base


class ClientStatus:
    """Context manager for transmitting client status."""

    def __init__(self, socket, job_id, command, ctx):
        """Initialize the UNIX socket connect context manager."""

        self.ctx = ctx
        self.job_id = job_id
        self.command = command
        self.job_state = ctx.driver.nullbyte
        self.info = ctx.driver.nullbyte
        self.socket = socket
        self.data = None
        self.stderr = ctx.driver.nullbyte
        self.stdout = ctx.driver.nullbyte

    def start_processing(self):
        self.ctx.driver.socket_send(
            socket=self.socket,
            msg_id=self.job_id,
            control=self.ctx.driver.job_processing,
        )

    def __enter__(self):
        """Upon enter, return the context manager object for future updates.

        :returns: Object
        """

        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, send a final status message."""

        self.ctx.driver.socket_send(
            socket=self.socket,
            msg_id=self.job_id,
            control=self.job_state,
            command=self.command,
            data=self.data,
            info=self.info,
            stderr=self.stderr,
            stdout=self.stdout,
        )


class SSHConnect:
    """Context manager to remotely connect to servers using libssh2.

    The connection manager requires an SSH key to be defined, and exist,
    however, upon enter the system will use the SSH agent is defined.
    """

    def __init__(self, host, username, port, key_file=None, debug=False):
        """Initialize the connection manager.

        :param host: IP or Domain to connect to.
        :type host: String
        :param username: Username for the connection.
        :type username: String
        :param port: Port number used to connect to the remote server.
        :type port: Int
        :param key_file: SSH key file used to connect.
        :type key_file: String
        :param debug: Enable or disable debug mode
        :type debug: Boolean
        """

        self.log = logger.getLogger(name="directord", debug_logging=debug)
        self.key_file = key_file
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.session = Session()
        self.session.handshake(self.sock)
        self.log.debug(
            "Handshake with [ %s ] on port [ %s ] complete.", host, port
        )

        self.known_hosts = self.session.knownhost_init()

        if key_file:
            self.session.userauth_publickey_fromfile(username, key_file)
            self.log.debug("Key file [ %s ] added", key_file)
        else:
            try:
                self.session.agent_auth(username)
                self.log.debug("User agent based authentication enabled")
            except ssh2.exceptions.AgentConnectionError as e:
                self.log.warning(
                    "SSH Agent connection has failed: %s."
                    " Attempting to connect with the user's implicit ssh key.",
                    str(e),
                )
                home = os.path.abspath(os.path.expanduser("~"))
                default_keyfile = os.path.join(home, ".ssh/id_rsa")
                if os.path.exists(default_keyfile):
                    self.session.userauth_publickey_fromfile(
                        username, default_keyfile
                    )
                    self.log.debug("Key file [ %s ] added", key_file)

        self.channel = None

    def open_channel(self):
        """Open a channel."""

        self.channel = self.session.open_session()
        if self.channel == 0:
            raise SystemExit("SSH Connection has failed.")
        self.log.debug("SSH channel is open.")

    def __enter__(self):
        """Connect to the remote node and return the ssh and session objects.

        :returns: Tuple
        """

        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the ssh connection."""

        if self.channel:
            self.channel.close()
            self.log.debug("SSH channel is closed.")


def file_sha256(file_path, chunk_size=10240):
    """Return the SHA256 sum of a given file.

    Default chunk size: 10K.

    :param file_path: File path
    :type file_path: String
    :param chunk_size: Set the read chunk size.
    :type chunk_size: Integer
    :returns: String
    """

    sha256 = hashlib.sha256()
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                else:
                    sha256.update(data)

        return sha256.hexdigest()


def object_sha256(obj):
    """Return the SHA256 sum of a given object.

    The object used for generating a SHA256 must be JSON compatible.

    :param file_path: File path
    :type file_path: String
    :returns: String
    """

    return hashlib.sha256(json.dumps(obj).encode()).hexdigest()


def object_sha1(obj):
    """Return the SHA1 sum of a given object.

    The object used for generating a SHA1 must be JSON compatible.

    :param file_path: File path
    :type file_path: String
    :returns: String
    """

    return hashlib.sha1(json.dumps(obj).encode()).hexdigest()


def get_uuid():
    """Return a new UUID in String format.

    :returns: String
    """

    return str(uuid.uuid4())
