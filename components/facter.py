#   Copyright Sagi Shnaidman <sshnaidm@redhat.com>. All Rights Reserved.
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

import json
from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Run facter to collect facts")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--custom-dir",
            help="A directory to use for custom facts",
        )
        self.parser.add_argument(
            "--external-dir",
            help="A directory to use for external facts",
        )

    def server(self, exec_array, data, arg_vars):
        """Return data from formatted cacheevict action.

        :param exec_array: Input array from action
        :type exec_array: List
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        super().server(exec_array=exec_array, data=data, arg_vars=arg_vars)
        data["custom_dir"] = self.known_args.custom_dir
        data["external_dir"] = self.known_args.external_dir
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run cache echo command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        stdout, stderr, outcome = self.run_command(
            command="command -v facter",
            env=cache.get("envs"),
            no_block=False,
        )
        if not outcome:
            return None, "Facter is not installed!", False, None
        executable = stdout.decode().strip()
        command = f"{executable} --json"
        if job["custom_dir"]:
            command = f"{command} --custom-dir {job['custom_dir']}"
        if job["external_dir"]:
            command = f"{command} --external-dir {job['external_dir']}"
        stdout, stderr, outcome = self.run_command(
            command=command,
            env=cache.get("envs"),
            no_block=False,
        )
        try:
            json_data = json.loads(stdout.decode())
        except json.decoder.JSONDecodeError:
            return None, "Facter returned invalid JSON!", False, None
        cache_set = self.set_cache(
            cache=cache,
            key="args",
            value={"facter": json_data},
            value_update=False,
            extend=False,
        )
        if cache_set:
            self.log.debug("Facter data added to cache")
            return stdout, stderr, outcome, command
        else:
            return None, "Failed to add facter data to cache", False, None
