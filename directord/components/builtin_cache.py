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
        """Initialize the component cache class.

        This component is not cacheable.
        """

        super().__init__(desc="Process cache commands")
        self.cacheable = False

    def args(self, cache_type):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            cache_type,
            nargs="+",
            action="append",
            help="Set a given argument. KEY VALUE",
        )

    def server(self, exec_string, data, arg_vars, verb):
        """Return data from formatted transfer action.

        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :param verb: Interaction key word.
        :type verb: String
        :returns: Dictionary
        """

        cache_type = "{}s".format(verb.lower())
        self.args(cache_type=cache_type)
        args, _ = self.exec_parser(
            parser=self.parser, exec_string=exec_string, arg_vars=arg_vars
        )
        cache_obj = getattr(args, cache_type)
        data[cache_type] = dict([" ".join(cache_obj[0]).split(" ", 1)])
        return data

    def client(self, command, conn, cache, job):
        """Run cache command operation.

        :param command: Work directory path.
        :type command: String
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
        # Sets the cache type to "args" or "envs"
        cache_type = "{}s".format(command.decode().lower())
        self.set_cache(
            cache=cache,
            key=cache_type,
            value=job[cache_type],
            value_update=True,
            tag=cache_type,
        )
        conn.info = "type:{}, value:{}".format(
            cache_type, job[cache_type]
        ).encode()

        return "{} added to cache".format(cache_type), None, True
