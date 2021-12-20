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
import pkgutil
import socket
import sys
import time
import uuid

import tabulate
import yaml

from ssh import options
from ssh.session import Session
from ssh import key as ssh_key

from directord import components
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
                elif isinstance(base.get(key), set):
                    base[key].update(value)
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

    def __init__(self, job_id, command, ctx):
        """Initialize the UNIX socket connect context manager."""

        self.ctx = ctx
        self.job_id = job_id
        self.command = command
        self.job_state = ctx.driver.nullbyte
        self.info = ctx.driver.nullbyte
        self.data = None
        self.stderr = ctx.driver.nullbyte
        self.stdout = ctx.driver.nullbyte

    def __enter__(self):
        """Upon enter, return the context manager object for future updates.

        :returns: Object
        """

        self.ctx.log.debug("Job [ %s ] start context", self.job_id)
        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, send a final status message."""

        try:
            self.stderr = self.stderr
        except AttributeError:
            pass

        try:
            self.stdout = self.stdout
        except AttributeError:
            pass

        try:
            self.info = self.info
        except AttributeError:
            pass

        job_sent = self.ctx.driver.job_send(
            msg_id=self.job_id,
            control=self.job_state,
            command=self.command,
            data=self.data,
            info=self.info,
            stderr=self.stderr,
            stdout=self.stdout,
        )
        self.ctx.log.debug(
            "Job [ %s ] message sent on exit, %s", self.job_id, job_sent
        )


class SSHConnect:
    """Context manager to remotely connect to servers using libssh.

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

        self.log = logger.getLogger(name="directord-ssh", debug_logging=debug)
        self.key_file = key_file
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.session = Session()
        self.session.options_set(options.HOST, host)
        self.session.options_set(options.USER, username)
        self.session.options_set_port(port)
        self.session.set_socket(self.sock)
        self.session.connect()

        self.log.debug(
            "Handshake with [ %s ] on port [ %s ] complete.", host, port
        )

        self.channels = dict()
        self.host = host
        self.username = username
        self.key_file = key_file

    def _userauth_publickey_fromfile(self, key_file):
        """Import a private key file.

        :param key_file: Fully qualified path to an ssh key file.
        :type key_file: String
        """

        key = ssh_key.import_privkey_file(key_file)
        self.session.userauth_publickey(key)

    def set_auth(self):
        """Set the ssh session auth."""

        if self.key_file:
            self._userauth_publickey_fromfile(key_file=self.key_file)
            self.log.debug("Key file [ %s ] added", self.key_file)
        else:
            try:
                self.session.userauth_agent(self.username)
                self.log.debug("User agent based authentication enabled")
            except Exception as e:
                self.log.warning(
                    "SSH Agent connection has failed: %s."
                    " Attempting to connect with the user's implicit ssh key.",
                    str(e),
                )
                home = os.path.abspath(os.path.expanduser("~"))
                default_keyfile = os.path.join(home, ".ssh/id_rsa")
                if os.path.exists(default_keyfile):
                    self._userauth_publickey_fromfile(key_file=default_keyfile)
                    self.log.debug(
                        "Implicit key file [ %s ] added", self.key_file
                    )
                else:
                    self.log.critical(
                        "No implicit key found [ %s ]. Setup user-agent"
                        " authentication or use the --key-file"
                        " argument to explicitly set the required"
                        " ssh key.",
                        default_keyfile,
                    )
                    raise SystemExit("Authentication failure")

    def __enter__(self):
        """Connect to the remote node and return the ssh and session objects.

        :returns: Tuple
        """

        self.set_auth()
        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the ssh connection."""

        for key, value in self.channels.items():
            if hasattr(value, "close"):
                value.close()
                self.log.debug("%s channel is closed.", key)

        self.session.disconnect()
        self.log.debug("SSH session is closed.")


def file_sha3_224(file_path, chunk_size=10240):
    """Return the SHA3_224 sum of a given file.

    Default chunk size: 10K.

    :param file_path: File path
    :type file_path: String
    :param chunk_size: Set the read chunk size.
    :type chunk_size: Integer
    :returns: String
    """

    sha3_224 = hashlib.sha3_224()
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                else:
                    sha3_224.update(data)

        return sha3_224.hexdigest()


def object_sha3_224(obj):
    """Return the SHA3_224 sum of a given object.

    The object used for generating a SHA3_224 must be JSON compatible.

    :param file_path: File path
    :type file_path: String
    :returns: String
    """

    return hashlib.sha3_224(json.dumps(obj).encode()).hexdigest()


def get_uuid():
    """Return a new UUID in String format.

    :returns: String
    """

    return str(uuid.uuid4())


def print_tabulated_data(data, headers):
    """Print data in tabulated form.

    :param data: Organized data
    :type data: List
    :param headers: List of headers
    :type headers: List
    """

    print(
        tabulate.tabulate(
            data,
            headers=headers,
            disable_numparse=True,
        )
    )


def return_poller_interval(poller_time, poller_interval, log=None):
    """Return a new poller interval time.

    Review the poller time vs the current time, and if the poller is outside
    our expected margins return a new poller time to cool down the poller
    processes.

    :returns: Integer
    """

    current_time = time.time()
    if current_time >= poller_time + 64:
        if poller_interval != 2048:
            if log:
                log.info("Directord entering idle state.")
        poller_interval = 2048
    elif current_time >= poller_time + 32:
        if poller_interval != 1024:
            if log:
                log.info("Directord ramping down.")
        poller_interval = 1024

    return poller_interval


def component_lock_search():
    """Return a list of available components."""

    paths = [
        os.path.dirname(components.__file__),
        os.path.join(sys.base_prefix, "share/directord/components"),
        "/etc/directord/components",
    ]
    if sys.base_prefix != sys.prefix:
        paths.insert(0, os.path.join(sys.prefix, "share/directord/components"))

    lock_commands = set()
    for importer, name, _ in pkgutil.iter_modules(paths):
        component = importer.find_module(name).load_module(name)
        try:
            component_obj = component.Component()
            if component_obj.requires_lock:
                lock_commands.add(
                    getattr(
                        component_obj, "lock_name", name.lstrip("builtin_")
                    )
                )
        except AttributeError:
            pass
    else:
        return lock_commands
