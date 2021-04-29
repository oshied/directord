import os
import subprocess
import yaml

import paramiko
from paramiko import agent


def run_command(
    command,
    shell=True,
    env=None,
    execute="/bin/sh",
    return_codes=None,
):
    """Run a shell command.

    The options available:

    * ``shell`` to be enabled or disabled, which provides the ability
        to execute arbitrary stings or not. if disabled commands must be
        in the format of a ``list``

    * ``env`` is an environment override and or manipulation setting
        which sets environment variables within the locally executed
        shell.

    * ``execute`` changes the interpreter which is executing the
        command(s).

    * ``return_codes`` defines the return code that the command must
        have in order to ensure success. This can be a list of return
        codes if multiple return codes are acceptable.

    :param command: String
    :param shell: Boolean
    :param env: Dictionary
    :param execute: String
    :param return_codes: Integer
    :returns: Truple
    """

    if env:
        _env = dict(os.environ)
        _env.update(env)
        env = _env
    else:
        env = os.environ

    stdout = subprocess.PIPE

    if return_codes is None:
        return_codes = [0]

    stderr = subprocess.PIPE
    process = subprocess.Popen(
        command,
        stdout=stdout,
        stderr=stderr,
        executable=execute,
        env=env,
        shell=shell,
    )

    output, error = process.communicate()
    if process.returncode not in return_codes:
        return error, False
    else:
        return output, True


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
        session = self.ssh.get_transport().open_session()
        agent.AgentRequestHandler(session)

        return self.ssh, session

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the ssh connection."""

        self.ssh.close()
