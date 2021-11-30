#   Copyright Alex Schultz <aschultz@next-development.com>. All Rights Reserved
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

from directord.components.lib import cacheargs
from directord.components.lib import retry
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Manage packages with dnf")
        self.requires_lock = True

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--clear-metadata",
            action="store_true",
            help="Clear dnf metadata and make cache before running action.",
        )
        state_group = self.parser.add_mutually_exclusive_group()
        state_group.add_argument(
            "--latest",
            help="Ensure latest package is installed.",
            action="store_true",
        )
        state_group.add_argument(
            "--absent", help="Ensure packages are removed", action="store_true"
        )
        self.parser.add_argument(
            "packages",
            nargs="+",
            help="A space delineated list of packages to manage.",
        )
        self.parser.add_argument(
            "--retry",
            default=3,
            type=int,
            help="Number of times to retry",
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
        if self.known_args.absent:
            data["state"] = "absent"
        elif self.known_args.latest:
            data["state"] = "latest"
        else:
            data["state"] = "present"

        data["retry"] = self.known_args.retry
        data["clear"] = self.known_args.clear_metadata
        data["packages"] = self.known_args.packages

        return data

    @timeout
    @cacheargs
    @retry
    def client(self, cache, job):
        """Run file command operation.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        state = job.get("state")
        clear = job.get("clear")

        job_stdout = []
        job_stderr = []
        outcome = False
        if clear:
            cmd = "dnf clean all"
            job_stdout.append(b"=== dnf clean ===\n")
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)
            # TODO: check outcome
            cmd = "dnf makecache"
            job_stdout.append(b"=== dnf makecache ===\n")
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)
            # TODO: check outcome

        packages = job.get("packages")

        if not packages:
            return None, None, False, None

        to_remove = []
        to_install = []
        to_update_or_install = []
        if state == "absent":
            to_remove = packages
        elif state == "latest":
            to_update_or_install = packages
        else:
            to_install = packages

        if to_remove:
            cmd = "dnf -q -y remove {}".format(" ".join(to_remove))
            job_stdout.append(b"=== dnf remove ===\n")
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)

        if to_install:
            cmd = "dnf -q -y install {}".format(" ".join(to_install))
            job_stdout.append(b"=== dnf install ===\n")
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)

        if to_update_or_install:
            cmd = "dnf -q -y --best install {}".format(
                " ".join(to_update_or_install)
            )
            job_stdout.append(b"=== dnf update ===\n")
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)

        return b"".join(job_stdout), b"".join(job_stderr), outcome, None
