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

import traceback

import yaml

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cachefile class.

        This component is not cacheable.
        """

        super().__init__(desc="Process cachefile commands")
        self.cacheable = False
        self.requires_lock = True

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "cachefile",
            help="Load a cached file and store it as an update to ARGs.",
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
        data["cachefile"] = self.known_args.cachefile
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run cache file operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        try:
            with open(job["cachefile"]) as f:
                cachefile_args = yaml.safe_load(f)
        except Exception as e:
            self.log.critical(str(e))
            return None, traceback.format_exc(), False, None
        else:
            self.set_cache(
                cache=cache,
                key="args",
                value=cachefile_args,
                value_update=True,
                extend=True,
            )
            return "Cache file loaded", None, True, None
