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


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component service class."""

        super().__init__(desc="Manage services with systemd")
        self.requires_lock = True

    def args(self):
        """Set default arguments for a component."""

        super().args()
        running_group = self.parser.add_mutually_exclusive_group()
        running_group.add_argument(
            "--restarted",
            action="store_true",
            help="Ensure service is restarted",
        )
        running_group.add_argument(
            "--stopped", action="store_true", help="Ensure service is started"
        )
        state_group = self.parser.add_mutually_exclusive_group()
        state_group.add_argument(
            "--enable",
            help="Ensure service is enabled.",
            action="store_true",
        )
        state_group.add_argument(
            "--disable", help="Ensure service is disabled", action="store_true"
        )
        running_group.add_argument(
            "--daemon-reload",
            action="store_true",
            help="Reload the systemd daemon",
        )
        self.parser.add_argument(
            "services",
            nargs="+",
            help="A space delineated list of services to manage.",
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
        if self.known_args.enable:
            data["state"] = "enable"
        elif self.known_args.disable:
            data["state"] = "disable"

        elif self.known_args.restarted:
            data["running"] = "restart"
        elif self.known_args.stopped:
            data["running"] = "stop"
        else:
            data["running"] = "start"

        data["services"] = self.known_args.services
        data["daemon_reload"] = self.known_args.daemon_reload

        return data

    def client(self, cache, job):
        """Run service command operation.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        state = job.get("state")
        running = job.get("running", "start")
        services = job.get("services")

        job_stdout = []
        job_stderr = []
        outcome = False
        if not services:
            return None, None, False, None

        if job.get("daemon_reload") is True:
            stdout, stderr, outcome = self.run_command(
                command="systemctl daemon-reload", env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)

            # fail if enablement fails
            if not outcome:
                return (
                    b"".join(job_stdout),
                    b"".join(job_stderr),
                    outcome,
                    "Failed to reload the systemd daemon",
                )

        if state:
            cmd = "systemctl {} {}".format(state, " ".join(services))
            stdout, stderr, outcome = self.run_command(
                command=cmd, env=cache.get("envs")
            )
            job_stdout.append(stdout)
            job_stderr.append(stderr)

            # fail if enablement fails
            if not outcome:
                return (
                    b"".join(job_stdout),
                    b"".join(job_stderr),
                    outcome,
                    "Failed to set the systemd state",
                )

        cmd = "systemctl {} {}".format(running, " ".join(services))
        stdout, stderr, outcome = self.run_command(
            command=cmd, env=cache.get("envs")
        )
        job_stdout.append(stdout)
        job_stderr.append(stderr)

        return b"".join(job_stdout), b"".join(job_stderr), outcome, None
