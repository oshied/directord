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
        """Initialize the component cacheevict class.

        This component is not cacheable.
        """

        super().__init__(desc="Process cacheevict commands")
        self.cacheable = False

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "cacheevict",
            help=(
                "Evict all tagged cached items from a client machine."
                " Typical tags are, but not limited to:"
                " [args, envs, jobs, parents, query, ...]. To evict 'all'"
                " cached items use the keyword 'all'."
            ),
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
        data["cacheevict"] = self.known_args.cacheevict
        return data

    def client(self, conn, cache, job):
        """Run cache evict command operation.

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
        tag = job["cacheevict"]
        if tag == "all":
            evicted = cache.clear()
            info = "All cache has been cleared"
        else:
            evicted = cache.evict(tag)
            info = "Evicted {} items, tagged {}".format(evicted, tag)
        return info, None, True
