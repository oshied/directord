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

from directord import components


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process run commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--stdout-arg",
            help="Stores the stdout of a given command as a cached argument.",
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
        if self.known_args.stdout_arg:
            data["stdout_arg"] = self.known_args.stdout_arg

        data["command"] = " ".join(self.unknown_args)

        return data

    def client(self, conn, cache, job):
        """Run file command operation.

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
        stdout_arg = job.get("stdout_arg")
        command = self.blueprinter(
            content=job["command"], values=cache.get("args")
        )
        if not command:
            return None, None, False

        stdout, stderr, outcome = self.run_command(
            command=command, env=cache.get("envs")
        )
        conn.info = command.encode()

        if stdout_arg and stdout:
            clean_info = stdout.decode().strip()
            self.set_cache(
                cache=cache,
                key="args",
                value={stdout_arg: clean_info},
                value_update=True,
                tag="args",
            )

        return stdout, stderr, outcome
