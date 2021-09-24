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

import time

from directord import components


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Process query_wait commands")
        self.cacheable = False

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "item",
            help=(
                "Wait for an item to be part of the query cache. An item is"
                " a keys within the host specific query cache."
            ),
        )
        self.parser.add_argument(
            "--query-timeout",
            help=(
                "Wait for %(default)s seconds for a given item to be present"
                " in cache."
            ),
            default=600,
            type=int,
        )
        self.parser.add_argument(
            "--identity",
            help=(
                "Worker identities to search for a specific query item."
                " When an identity is defined, the lookup will search the"
                " defined identities for the item. QUERY_WAIT will block"
                " until the `item` is found in all specified identities."
                " this value can be used multiple times to express many"
                " identities."
            ),
            metavar="STRING",
            nargs="+",
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
        data["item"] = self.known_args.item
        data["query_timeout"] = self.known_args.query_timeout
        data["identity"] = self.known_args.identity
        return data

    def client(self, cache, job):
        """Run cache query_wait command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        warning_loops = start_time = time.time()
        missing_identity = set()
        while (time.time() - start_time) < job["query_timeout"]:
            args = cache.get("args")
            if not args:
                continue

            query_args = args.get("query", dict())
            if not query_args:
                continue
            elif "identity" in job and job["identity"]:
                for identity in job["identity"]:
                    items = query_args.get(identity)
                    if isinstance(items, dict):
                        if job["item"] not in items.keys():
                            missing_identity.add(identity)
                            break
                        else:
                            if identity in missing_identity:
                                missing_identity.remove(identity)
                    else:
                        missing_identity.add(identity)
                        break
                else:
                    return (
                        "Item found in all identities",
                        None,
                        True,
                        (
                            "Item {} found in the query cache for"
                            " identities {}".format(
                                job["item"], job["identity"]
                            )
                        ),
                    )
                if missing_identity:
                    if time.time() - warning_loops >= 5:
                        self.log.warning(
                            "QUERY argument [ %s ] not found in cache for %s",
                            job["item"],
                            missing_identity,
                        )
                        warning_loops = time.time()
            else:
                for value in query_args.values():
                    if job["item"] in value:
                        return (
                            "Item found",
                            None,
                            True,
                            "Item {} found in the query cache".format(
                                job["item"]
                            ),
                        )

            if time.time() - warning_loops >= 5:
                self.log.debug(
                    "QUERY argument [ %s ] not found in cache", job["item"]
                )
                warning_loops = time.time()

            self.delay(0.01)

        if missing_identity:
            info = (
                "Item {} was not found in the query cache for the identities"
                " {} within {} seconds".format(
                    job["item"], list(missing_identity), job["query_timeout"]
                )
            )
        else:
            info = (
                "Item {} was not found in the query cache within"
                " {} seconds".format(job["item"], job["query_timeout"])
            )

        return (
            None,
            "Timeout after {} seconds".format(job["query_timeout"]),
            False,
            info,
        )
