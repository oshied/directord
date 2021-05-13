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


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process workdir commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument("workdir", help="Create a directory.")

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
        data["workdir"] = self.known_args.workdir
        return data

    def client(self, conn, cache, job):
        """Run file work directory operation.

        Command operations are rendered with cached data from the args dict.

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
        workdir = self.blueprinter(
            content=job["workdir"], values=cache.get("args")
        )
        if not workdir:
            return None, None, False
        try:
            os.makedirs(workdir, exist_ok=True)
        except (FileExistsError, PermissionError) as e:
            self.log.critical(str(e))
            return None, traceback.format_exc(), False
        else:
            update_info = "Directory {} OK".format(workdir)
            return update_info, None, True
