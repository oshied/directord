import os
import subprocess


def run_command(
    command,
    debug=False,
    shell=True,
    env=None,
    execute="/bin/bash",
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

    if env is None:
        env = os.environ

    if debug is False:
        stdout = open(os.devnull, "wb")
    else:
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


class ClientStatus(object):
    """Context manager for transmitting client status."""

    def __init__(self, socket, job_id, ctx):
        """Initialize the UNIX socket connect context manager."""

        self.ctx = ctx
        self.job_id = self.encode_string(item=job_id)
        self.job_state = ctx.nullbyte
        self.info = ctx.nullbyte
        self.socket = socket
        self.ctx.socket_multipart_send(
            zsocket=self.socket,
            msg_id=bytes(self.encode_string(item=self.job_id)),
            control=ctx.job_processing,
        )

    @staticmethod
    def encode_string(item):
        """Inspect a given item and if it is a string type, encode it.

        :param item: Item to inspect, assumes item may be string type
        :type item: <ANY>
        :returns: String|<ANY>
        """
        if isinstance(item, str):
            return item.encode()
        else:
            return item

    def __enter__(self):
        """Upon enter, return the context manager object for future updates.

        :returns: Object
        """

        return self

    def __exit__(self, *args, **kwargs):
        """Upon exit, send a final status message."""

        self.ctx.socket_multipart_send(
            zsocket=self.socket,
            msg_id=bytes(self.encode_string(item=self.job_id)),
            control=bytes(self.encode_string(item=self.job_state)),
            info=bytes(self.encode_string(item=self.info)),
        )
