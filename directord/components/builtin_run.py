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
from directord import utils


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
        self.parser.add_argument(
            "--no-block",
            action="store_true",
            help="Run a command in 'fire and forget' mode.",
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
        if self.known_args.stdout_arg:
            data["stdout_arg"] = self.known_args.stdout_arg
        data["no_block"] = self.known_args.no_block
        data["command"] = " ".join(self.unknown_args)

        return data

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
        stdout_arg = job.get("stdout_arg")
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

        if stdout_arg and stdout:
            self.block_on_tasks = list()
            clean_info = stdout.decode().strip()
            arg_job = job.copy()
            arg_job.pop("parent_sha3_224", None)
            arg_job.pop("parent_id", None)
            arg_job.pop("job_sha3_224", None)
            arg_job.pop("job_id", None)
            arg_job["skip_cache"] = True
            arg_job["extend_args"] = True
            arg_job["verb"] = "ARG"
            arg_job["args"] = {stdout_arg: clean_info}
            arg_job["parent_async_bypass"] = True
            arg_job["targets"] = [self.driver.identity]
            arg_job["job_id"] = utils.get_uuid()
            arg_job["job_sha3_224"] = utils.object_sha3_224(obj=arg_job)
            arg_job["parent_id"] = utils.get_uuid()
            arg_job["parent_sha3_224"] = utils.object_sha3_224(obj=arg_job)
            self.block_on_tasks.append(arg_job)
        elif stdout_arg and not stdout:
            return stdout, stderr, False, command

        return stdout, stderr, outcome, command
