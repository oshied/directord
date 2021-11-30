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

from directord.components.lib import cacheargs
from directord.components.lib import retry
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process run commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--no-block",
            action="store_true",
            help="Run a command in 'fire and forget' mode.",
        )
        self.parser.add_argument(
            "--retry",
            default=1,
            type=int,
            help="Number of times to retry",
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
        data["no_block"] = self.known_args.no_block
        data["retry"] = self.known_args.retry
        data["command"] = " ".join(self.unknown_args)

        return data

    @timeout
    @cacheargs
    @retry
    def client(self, cache, job):
        """Run file command operation.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        success, command = self.blueprinter(
            content=job["command"],
            values=cache.get("args"),
            allow_empty_values=True,
        )
        if not success:
            return None, command, False, None
        elif not command:
            return None, None, False, None

        stdout, stderr, outcome = self.run_command(
            command=command,
            env=cache.get("envs"),
            no_block=job.get("no_block"),
        )

        return stdout, stderr, outcome, command
