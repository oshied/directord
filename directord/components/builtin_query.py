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

import json

from directord import components
from directord import utils


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class.

        This component is not cacheable.
        """

        super().__init__(desc="Process cachefile commands")
        self.cacheable = False
        self.requires_lock = True

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "query",
            help=(
                "Scan the environment for a given cached argument and"
                " store the resultant on the target. The resultant is"
                " set in dictionary format: `{'client-id': ...}`"
            ),
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
        data["query"] = self.known_args.query
        return data

    def client(self, cache, job):
        """Run query command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        args = cache.get("args")
        if args:
            query = args.get(job["query"])
        else:
            query = None

        if query:
            query_job = job.copy()
            targets = query_job.pop("targets", list())
            query_item = query_job.pop("query")
            query_job.pop("parent_sha3_224", None)
            query_job.pop("parent_id", None)
            query_job.pop("job_sha3_224", None)
            query_job.pop("job_id", None)
            query_job["skip_cache"] = True
            query_job["extend_args"] = True
            query_job["verb"] = "ARG"
            query_job["args"] = {
                "query": {self.driver.identity: {query_item: query}}
            }
            query_job["parent_async_bypass"] = True
            query_job["job_sha3_224"] = utils.object_sha3_224(obj=query_job)

            block_task = dict(
                skip_cache=True,
                verb="QUERY_WAIT",
                item=query_item,
                identity=targets,
                targets=targets,
                parent_async_bypass=True,
                query_timeout=600,
            )
            block_task["job_sha3_224"] = utils.object_sha3_224(obj=query_job)
            query_job["parent_sha3_224"] = block_task[
                "parent_sha3_224"
            ] = utils.object_sha3_224(obj=query_job)
            query_job["parent_id"] = block_task["parent_id"] = utils.get_uuid()

            self.block_on_tasks = [query_job, block_task]
            self.log.debug("query job call back [ %s ]", self.block_on_tasks)

        return json.dumps(query), None, True, None
