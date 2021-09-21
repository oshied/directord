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
            "--no-wait",
            action="store_true",
            help=(
                "Disable waiting for the queried key to be present in the"
                " local cache."
            ),
        )
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
        data["no_wait"] = self.known_args.no_wait
        return data

    def client(self, cache, job):
        """Run query command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        args = cache.get("args")
        if args:
            query = args.get(job["query"])
        else:
            query = None

        self.block_on_tasks = list()
        arg_job = job.copy()
        query_item = arg_job.pop("query")
        targets = arg_job.get("targets", list())
        arg_job.pop("parent_sha3_224", None)
        arg_job.pop("parent_id", None)
        arg_job.pop("job_sha3_224", None)
        arg_job.pop("job_id", None)
        arg_job["skip_cache"] = True
        arg_job["extend_args"] = True
        arg_job["verb"] = "ARG"
        arg_job["args"] = {
            "query": {self.driver.identity: {query_item: query}}
        }
        arg_job["parent_async_bypass"] = True
        arg_job["job_id"] = utils.get_uuid()
        arg_job["job_sha3_224"] = utils.object_sha3_224(obj=arg_job)
        arg_job["parent_id"] = utils.get_uuid()
        arg_job["parent_sha3_224"] = utils.object_sha3_224(obj=arg_job)
        self.block_on_tasks.append(arg_job)
        if self.driver.identity in targets:
            if not job.get("no_wait"):
                wait_job = dict(
                    skip_cache=True,
                    verb="QUERY_WAIT",
                    item=query_item,
                    query_timeout=600,
                    parent_async_bypass=True,
                    targets=targets,
                    identity=list(),
                )
                wait_job["job_id"] = utils.get_uuid()
                wait_job["job_sha3_224"] = utils.object_sha3_224(obj=wait_job)
                wait_job["parent_id"] = arg_job["parent_id"]
                wait_job["parent_sha3_224"] = arg_job["parent_sha3_224"]
                self.block_on_tasks.append(wait_job)

        return json.dumps(query), None, True, None
