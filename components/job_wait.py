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

import queue

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process coordination commands")
        self.cacheable = False

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "sha",
            help=("job sha to be completed."),
        )
        self.parser.add_argument(
            "--identity",
            help=(
                "Worker identities to search for a specific job item."
                " When an identity is defined, the lookup will search the"
                " defined identities for the item. JOB_WAIT will block"
                " until the `item` is found in all specified identities."
                " this value can be used multiple times to express many"
                " identities."
            ),
            metavar="STRING",
            nargs="+",
            required=True,
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
        data["identity"] = self.known_args.identity
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run file transfer operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        with components.Backend(
            driver=self.driver.__copy__(), log=self.log, job_id=job["job_id"]
        ) as driver:
            return self._client(cache, job, driver)

    def _client(self, cache, job, driver):
        """Run cache query_wait command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :param driver: Connection object used to store information used in a
                     return message.
        :type driver: Object
        :returns: tuple
        """

        if not job["identity"]:
            return (
                None,
                None,
                True,
                "No identities to process",
            )

        q = queue.Queue()

        if driver.identity in job["identity"]:
            job["identity"].remove(driver.identity)
            job["identity"].append(driver.identity)

        list(map(q.put, job["identity"]))
        confirmed_identities = set()
        all_identities_sent = False
        while True:
            try:
                identity = q.get_nowait()
            except queue.Empty:
                all_identities_sent = True
            else:
                driver.backend_send(
                    msg_id=job["job_id"],
                    control=driver.coordination_notice,
                    data=job["job_sha"],
                    info=identity,
                )
                self.log.debug(
                    "Job [ %s ] coordination notice sent to %s",
                    job["job_id"],
                    identity,
                )

            if driver.backend_check(interval=0.5) and driver.credit > 0:
                driver.credit -= 1
                (
                    msg_id,
                    control,
                    _,
                    data,
                    info,
                    stderr,
                    stdout,
                ) = driver.backend_recv()

                if control == driver.coordination_notice:
                    if data != job["job_sha"]:
                        self.log.debug(
                            "Job [ %s ] coordination notice received from"
                            " [ %s ] but data miss-matched, sending back.",
                            msg_id,
                            info,
                        )
                        driver.backend_send(
                            msg_id=msg_id,
                            control=control,
                            data=data,
                            info=info,
                            stderr=stderr,
                            stdout=stdout,
                        )
                    else:
                        self.log.debug(
                            "Job [ %s ] coordination notice received from"
                            " [ %s ]",
                            msg_id,
                            info,
                        )
                        for _ in range(2400):
                            if cache.get(data) in [
                                driver.job_end,
                                driver.job_failed,
                            ]:
                                self.log.debug(
                                    "Job [ %s ] coordination complete for"
                                    " [ %s ]",
                                    msg_id,
                                    info,
                                )
                                driver.backend_send(
                                    msg_id=msg_id,
                                    control=driver.coordination_ack,
                                    info=info,
                                )
                                break
                            self.driver.event.wait(0.25)
                        else:
                            self.log.debug(
                                "Job [ %s ] expected SHA [ %s ] was not"
                                " found.",
                                msg_id,
                                data,
                            )
                            driver.backend_send(
                                msg_id=msg_id,
                                control=driver.coordination_failed,
                                info=info,
                                stderr="Item was not found in cache",
                            )
                elif control == driver.coordination_ack:
                    self.log.debug(
                        "Job [ %s ] coordination ACK for [ %s ] received",
                        msg_id,
                        info,
                    )
                    confirmed_identities.add(info)
                elif control == driver.coordination_failed:
                    self.log.error(
                        "Job [ %s ] coordination failed from"
                        " [ %s ] error %s",
                        msg_id,
                        info,
                        data,
                    )
                    return (
                        stderr,
                        stdout,
                        False,
                        "Job [ {} ] failed when attempting coordination with"
                        " [ {} ]".format(msg_id, info),
                    )
                else:
                    self.log.critical(
                        "Unknown control received [ %s ] from [ %s ]",
                        control,
                        info,
                    )

            elif (
                sorted(confirmed_identities) == sorted(job["identity"])
                and all_identities_sent
            ):
                self.log.debug(
                    "Job [ %s ] coordination with %s success",
                    job["job_id"],
                    confirmed_identities,
                )
                return (
                    "Job completed, found SHA [ {} ]".format(job["job_sha"]),
                    None,
                    True,
                    "Job [ {} ] completed on all"
                    " coordinated targets: {}".format(
                        job["job_id"], job["identity"]
                    ),
                )
            else:
                self.log.debug(
                    "Waiting for coordination messages from %s",
                    sorted(set(job["identity"]) - confirmed_identities),
                )
