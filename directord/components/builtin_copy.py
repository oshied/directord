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

import base64
import glob
import grp
import os
import pwd
import shlex
import traceback

from directord import components
from directord import utils

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process transfer commands")
        self.requires_lock = True
        self.lock_name = "copy"  # ADD and COPY are aliases

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--chown", help="Set the file ownership", type=str
        )
        self.parser.add_argument("--chmod", help="Set the file mode", type=str)
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

    def server(self, exec_array, data, arg_vars):
        """Return data from formatted transfer action.

        :param exec_array: Input array from action
        :type exec_array: List
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        super().server(exec_array=exec_array, data=data, arg_vars=arg_vars)
        if self.known_args.chown:
            chown = self.known_args.chown.split(":", 1)
            if len(chown) == 1:
                chown.append(None)
            data["user"], data["group"] = chown

        if self.known_args.chmod:
            data["mode"] = int(oct(int(self.known_args.chmod, 8)), 8)

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

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run file transfer operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        with components.Backend(
            driver=self.driver.__copy__(), log=self.log, job_id=job["job_id"]
        ) as driver:
            return self._client(cache, job, self.info, driver)

    def _client(self, cache, job, source_file, driver):
        """Run file transfer operation.

        File transfer operations will look at the cache, then look for an
        existing file, and finally compare the original SHA3_224 to what is on
        disk. If everything checks out the client will request the file
        from the server.

        If the user and group arguments are defined the file ownership
        will be set accordingly.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :param source_file: Original file location on server.
        :type source_file: String
        :param driver: Connection object used to store information used in a
                     return message.
        :type driver: Object
        :returns: tuple
        """

        file_to = job["file_to"]
        user = job.get("user")
        group = job.get("group")
        file_sha3_224 = job.get("file_sha3_224")
        blueprint = job.get("blueprint", False)
        success, file_to = self.blueprinter(
            content=file_to, values=cache.get("args"), allow_empty_values=True
        )
        if not success:
            return None, file_to, False, None

        mode = job.get("mode")
        if (
            os.path.isfile(file_to)
            and utils.file_sha3_224(file_to) == file_sha3_224
        ):
            stdout = (
                "File exists {} and SHA3_224 {} matches, nothing to"
                " transfer".format(file_to, file_sha3_224)
            )
            if blueprint:
                success, error = self.file_blueprinter(
                    cache=cache, file_to=file_to
                )
                if not success:
                    return utils.file_sha3_224(file_to), error, False, None

            return stdout, None, True, None
        else:
            self.log.debug(
                "Job [ %s ] requesting transfer of source file:%s",
                job["job_id"],
                source_file,
            )

        try:
            offset = 0
            chunk = 131072
            with open(file_to, "wb") as f:
                while True:
                    driver.backend_send(
                        msg_id=job["job_id"],
                        control=driver.transfer_start,
                        command="{}".format(offset),
                        data="{}".format(chunk),
                        info=source_file,
                    )
                    offset += chunk
                    (
                        _,
                        control,
                        _,
                        data,
                        info,
                        _,
                        _,
                    ) = driver.backend_recv()
                    if control in [driver.job_processing, driver.transfer_end]:
                        data = base64.b64decode(data)
                        chunk_size = len(data)
                        self.log.debug(
                            "Job [ %s ] identity [ %s ] received %s",
                            job["job_id"],
                            driver.identity,
                            chunk_size,
                        )
                        f.write(data)
                        if control == driver.transfer_end:
                            self.log.debug(
                                "Job [ %s ] identity [ %s ] stopped transfer",
                                job["job_id"],
                                driver.identity,
                            )
                            break
                        elif chunk_size < chunk:
                            self.log.debug(
                                "Job [ %s ] identity [ %s ] received the last"
                                " chunk",
                                job["job_id"],
                                driver.identity,
                            )
                            break
                    elif control == driver.job_failed:
                        return (
                            None,
                            "Transfer failed: {}".format(info),
                            False,
                            None,
                        )
        except (FileNotFoundError, NotADirectoryError) as e:
            self.log.critical(
                "Job [ %s ] file failure: %s", job["job_id"], str(e)
            )
            return None, traceback.format_exc(), False, None
        except Exception as e:
            return (
                None,
                traceback.format_exc(),
                False,
                "Transfer never started: {}".format(str(e)),
            )
        else:
            self.log.debug(
                "Job [ %s ] transfer of source file:%s complete to [ %s ]",
                job["job_id"],
                source_file,
                file_to,
            )

        if blueprint:
            success, error = self.file_blueprinter(
                cache=cache, file_to=file_to
            )
            if not success:
                return utils.file_sha3_224(file_to), error, False, None

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

        if mode:
            os.chmod(file_to, mode)

        if not blueprint and utils.file_sha3_224(file_to) != file_sha3_224:
            stderr = (
                "Data integrity failure. Expected SHA {}, found SHA {}."
                " Check transfer logs for more details.".format(
                    utils.file_sha3_224(file_to), file_sha3_224
                )
            )
            return None, stderr, False, None

        return utils.file_sha3_224(file_to), stderr, outcome, None
