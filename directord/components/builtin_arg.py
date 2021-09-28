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

import ast
import json

from directord import components


class Component(components.ComponentBase):
    command = "arg"

    def __init__(self):
        """Initialize the component cache class.

        This component is not cacheable.
        """

        super().__init__(desc="Process cache commands")
        self.cacheable = False
        self.requires_lock = True

    def args(self, cache_type):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--extend-args",
            action="store_true",
            help=(
                "When setting an ARG, allow complex args to extend"
                " existing ones."
            ),
        )
        self.parser.add_argument(
            cache_type,
            nargs="+",
            action="append",
            help="Set a given argument. KEY VALUE",
        )

    def server(self, exec_array, data, arg_vars):
        """Return data from formatted transfer action.

        :param exec_array: Input string from action
        :type exec_array: List
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        cache_type = "{}s".format(self.verb.lower())
        self.args(cache_type=cache_type)
        args, _ = self.exec_parser(
            parser=self.parser, exec_array=exec_array, arg_vars=arg_vars
        )
        cache_obj = getattr(args, cache_type)
        key, value = " ".join(cache_obj[0]).split(" ", 1)
        try:
            value = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            pass

        if args.extend_args:
            data["extend_args"] = args.extend_args

        data[cache_type] = {key: value}
        return data

    def client(self, cache, job):
        """Run cache command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :param command: Work directory path.
        :type command: String
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        # Sets the cache type to "args" or "envs"
        cache_type = "{}s".format(self.command.lower())

        try:
            cache_value = ast.literal_eval(job[cache_type])
        except (ValueError, SyntaxError):
            cache_value = job[cache_type]

        self.log.debug("Job [ %s ] ARG value: %s", job["job_id"], cache_value)
        success, value = self.blueprinter(
            content=json.dumps(cache_value),
            values=cache.get("args"),
            allow_empty_values=True,
        )
        if success:
            cache_value = json.loads(value)

        if cache_type == "envs":
            env_cache = dict()
            for key, value in cache_value.items():
                env_cache[key] = str(value)
            cache_value = env_cache

        if cache_value:
            cache_set = self.set_cache(
                cache=cache,
                key=cache_type,
                value=cache_value,
                value_update=True,
                tag=cache_type,
                extend=job.get("extend_args", False),
            )
            if cache_set:
                self.log.debug(
                    "%s [ %s ] = [ %s ] added to cache",
                    cache_type,
                    cache_type,
                    cache_value,
                )
                return (
                    "{} added to cache".format(cache_type),
                    None,
                    True,
                    "type:{}, value:{}".format(cache_type, cache_value),
                )
            else:
                return (
                    None,
                    "Failed to add {} to cache".format(cache_type),
                    False,
                    "type:{}, value:{}".format(cache_type, cache_value),
                )
        else:
            return (
                "Nothing added to cache. {} had no value".format(cache_type),
                None,
                True,
                "type:{}, value:{}".format(cache_type, cache_value),
            )
