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
import traceback

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process workdir commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--chown", help="Set the file ownership", type=str
        )
        self.parser.add_argument("--chmod", help="Set the file mode", type=str)
        self.parser.add_argument(
            "--recursive", help="Recursive chown/chmod", action="store_true"
        )
        self.parser.add_argument("workdir", help="Create a directory.")

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
            if len(chown) == 2:
                if chown[1] == "":
                    chown[1] = chown[0]
                if chown[0] == "":
                    chown[0] = None
            data["user"], data["group"] = chown

        data["mode"] = self.known_args.chmod
        if self.known_args.recursive and not (
            self.known_args.chown or self.known_args.chmod
        ):
            raise AttributeError(
                "Recursive chown/chmod requires chown or chmod"
            )
        data["recursive"] = self.known_args.recursive
        data["workdir"] = self.known_args.workdir
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run file work directory operation.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        success, workdir = self.blueprinter(
            content=job["workdir"],
            values=cache.get("args"),
            allow_empty_values=True,
        )
        if not success:
            return None, workdir, False, None

        user = job.get("user")
        group = job.get("group")
        mode = job.get("mode")
        recursive = job.get("recursive")

        if not workdir:
            return None, None, False, None

        try:
            os.makedirs(workdir, exist_ok=True)
        except (FileExistsError, PermissionError) as e:
            self.log.critical(str(e))
            return None, traceback.format_exc(), False, None
        else:
            update_info = f"Directory {workdir} OK"
            task_outcome = True
            task_stderr = ""
            task_info = ""
            if user or group:
                rec = " -R" if recursive else ""
                user_group = f"{user or ''}:{group or ''}".rstrip(":")
                stdout, stderr, outcome = self.run_command(
                    f"chown{rec} {user_group} {workdir}"
                )
                task_outcome = task_outcome and outcome
                task_stderr = stderr.decode()
                task_info = stdout.decode()

            if mode:
                rec = " -R" if recursive else ""
                stdout, stderr, outcome = self.run_command(
                    command=f"chmod{rec} {mode} {workdir}"
                )
                task_outcome = task_outcome and outcome
                task_stderr = "\n".join([task_stderr, stderr.decode()])
                task_info = "\n".join([task_info, stdout.decode()])

            return update_info, task_stderr, task_outcome, task_info
