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
            "sha",
            help=("job sha to be completed."),
        )
        self.parser.add_argument(
            "--job-timeout",
            help=(
                "Wait for %(default)s seconds for a given item to be present"
                " in cache."
            ),
            default=600,
            type=int,
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
        data["job_sha"] = self.known_args.sha
        data["job_timeout"] = self.known_args.job_timeout
        return data

    def client(self, cache, job):
        """Run cache query_wait command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        start_time = time.time()
        while (time.time() - start_time) < job["job_timeout"]:
            if cache.get(job["sha"]) in [
                self.driver.job_end.decode(),
                self.driver.job_failed.decode(),
                self.driver.nullbyte.decode(),
            ]:
                return (
                    "Job completed",
                    None,
                    True,
                    "Job {} found complete".format(job["sha"]),
                )

            time.sleep(1)

        return (
            None,
            "Timeout after {} seconds".format(job["job_timeout"]),
            False,
            "Job {} was never found in a completed state".format(job["sha"]),
        )
