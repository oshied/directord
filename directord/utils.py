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
import uuid
import yaml

import paramiko


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


def merge_dict(base, new):
    """Recursively merge new into base.

    :param base: Base dictionary to load items into
    :type base: Dictionary
    :param new: New dictionary to merge items from
    :type new: Dictionary
    :returns: Dictionary
    """

    if isinstance(new, dict):
        for key, value in new.items():
            if key not in base:
                base[key] = value
            elif isinstance(value, dict):
                base[key] = merge_dict(base=base.get(key, {}), new=value)
            elif isinstance(value, list):
                base[key].extend(value)
            elif isinstance(value, (tuple, set)):
                if isinstance(base.get(key), tuple):
                    base[key] += tuple(value)
                elif isinstance(base.get(key), list):
                    base[key].extend(list(value))
            else:
                base[key] = new[key]
    elif isinstance(new, list):
        base.extend(new)
    return base


class ClientStatus(object):
    """Context manager for transmitting client status."""

    def __init__(self, socket, job_id, command, ctx):
        """Initialize the UNIX socket connect context manager."""

        self.ctx = ctx
        self.job_id = job_id
        self.command = command
        self.job_state = ctx.nullbyte
        self.info = ctx.nullbyte
        self.socket = socket
        self.data = None
        self.stderr = ctx.nullbyte
        self.stdout = ctx.nullbyte

    def start_processing(self):
        self.ctx.socket_multipart_send(
            zsocket=self.socket,
            msg_id=self.job_id,
            control=self.ctx.job_processing,
        )

    def __enter__(self):
        """Upon enter, return the context manager object for future updates.

        :returns: Object
        """

        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, send a final status message."""

        self.ctx.socket_multipart_send(
            zsocket=self.socket,
            msg_id=self.job_id,
            control=self.job_state,
            command=self.command,
            data=self.data,
            info=self.info,
            stderr=self.stderr,
            stdout=self.stdout,
        )


class ParamikoConnect(object):
    """Context manager to remotly connect to servers using paramiko.

    The connection manager requires an SSH key to be defined, and exist,
    however, upon enter the system will use the SSH agent is defined.
    """

    def __init__(self, host, username, port, key_file=None):
        """Initialize the connection manager.

        :param host: IP or Domain to connect to.
        :type host: String
        :param username: Username for the connection.
        :type username: String
        :param port: Port number used to connect to the remote server.
        :type port: Int
        :param key_file: SSH key file used to connect.
        :type key_file: String
        """

        self.key_file = key_file
        self.ssh = paramiko.SSHClient()
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.host = host
        self.username = username
        self.port = port
        self.connect_kwargs = dict(
            hostname=self.host,
            username=self.username,
            port=self.port,
            allow_agent=True,
        )
        if key_file:
            self.connect_kwargs["pkey"] = paramiko.RSAKey(filename=key_file)

    def __enter__(self):
        """Connect to the remote node and return the ssh and session objects.

        :returns: Tuple
        """

        self.ssh.connect(**self.connect_kwargs)
        return self.ssh

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the ssh connection."""

        self.ssh.close()


def file_sha1(file_path, chunk_size=10240):
    """Return the SHA1 sum of a given file.

    Default chunk size: 10K.

    :param file_path: File path
    :type file_path: String
    :param chunk_size: Set the read chunk size.
    :type chunk_size: Integer
    :returns: String
    """

    sha1 = hashlib.sha1()
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                else:
                    sha1.update(data)

        return sha1.hexdigest()


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
