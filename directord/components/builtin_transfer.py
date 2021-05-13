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

import glob
import grp
import os
import pwd
import shlex
import traceback

from directord import components
from directord import utils


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process transfer commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument("--chown", help="Set the file ownership")
        self.parser.add_argument(
            "--blueprint",
            action="store_true",
            help="Instruct the remote file to be blueprinted.",
        )
        self.parser.add_argument(
            "files",
            nargs="+",
            help="Set the file to transfer: 'FROM' 'TO'",
        )

    def server(self, exec_string, data, arg_vars):
        """Return data from formatted transfer action.

        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        super().server(exec_string=exec_string, data=data, arg_vars=arg_vars)
        if self.known_args.chown:
            chown = self.known_args.chown.split(":", 1)
            if len(chown) == 1:
                chown.append(None)
            data["user"], data["group"] = chown
        file_from, data["to"] = shlex.split(" ".join(self.known_args.files))
        data["from"] = [
            os.path.abspath(os.path.expanduser(i))
            for i in glob.glob(file_from)
            if os.path.isfile(os.path.expanduser(i))
        ]
        if not data["from"]:
            raise AttributeError(
                "The value of [ {} ] was not found.".format(file_from)
            )
        data["blueprint"] = self.known_args.blueprint

        return data

    def client(self, job_id, source_file, conn, cache, job):
        """Run file transfer operation.

        File transfer operations will look at the cache, then look for an
        existing file, and finally compare the original SHA1 to what is on
        disk. If everything checks out the client will request the file
        from the server.

        If the user and group arguments are defined the file ownership
        will be set accordingly.

        :param job_id: Job information marker.
        :type job_id: String
        :param source_file: Original file location on server.
        :type source_file: String
        :param conn: Connection object used to store information used in a
                     return message.
        :type conn: Object
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        super().client(conn=conn, cache=cache, job=job)
        file_to = job["file_to"]
        user = job.get("user")
        group = job.get("group")
        file_sha1 = job.get("file_sha1sum")
        blueprint = job.get("blueprint", False)
        file_to = self.blueprinter(content=file_to, values=cache.get("args"))
        if os.path.isfile(file_to) and utils.file_sha1(file_to) == file_sha1:
            info = (
                "File exists {} and SHA1 {} matches, nothing to"
                " transfer".format(file_to, file_sha1)
            )
            conn.ctx.socket_multipart_send(
                zsocket=conn.ctx.bind_transfer,
                msg_id=job_id.encode(),
                control=conn.ctx.transfer_end,
            )
            if blueprint and not self.file_blueprinter(
                cache=cache, file_to=file_to
            ):
                return utils.file_sha1(file_to), None, None
            return info, None, True
        else:
            self.log.debug(
                "Requesting transfer of source file:%s", source_file
            )
            conn.ctx.socket_multipart_send(
                zsocket=conn.ctx.bind_transfer,
                msg_id=job_id.encode(),
                control=conn.ctx.job_ack,
                command=b"transfer",
                info=source_file,
            )
        try:
            with open(file_to, "wb") as f:
                while True:
                    try:
                        (
                            _,
                            control,
                            _,
                            data,
                            _,
                            _,
                            _,
                        ) = conn.ctx.socket_multipart_recv(
                            zsocket=conn.ctx.bind_transfer
                        )
                        if control == conn.ctx.transfer_end:
                            break
                    except Exception:
                        break
                    else:
                        f.write(data)
        except (FileNotFoundError, NotADirectoryError) as e:
            self.log.critical(str(e))
            return None, traceback.format_exc(), False

        if blueprint and not self.file_blueprinter(
            cache=cache, file_to=file_to
        ):
            return utils.file_sha1(file_to), None, None

        stderr = None
        outcome = True
        if user:
            try:
                try:
                    uid = int(user)
                except ValueError:
                    uid = pwd.getpwnam(user).pw_uid

                if group:
                    try:
                        gid = int(group)
                    except ValueError:
                        gid = grp.getgrnam(group).gr_gid
                else:
                    gid = -1
            except KeyError:
                outcome = False
                stderr = (
                    "Failed to set ownership properties."
                    " USER:{} GROUP:{}".format(user, group)
                )
            else:
                os.chown(file_to, uid, gid)
                outcome = True

        return utils.file_sha1(file_to), stderr, outcome
