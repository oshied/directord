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
import traceback

try:
    from directord.components.lib.podman import PodmanPod

    AVAILABLE_PODMAN = True
except ImportError:
    AVAILABLE_PODMAN = False

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component cache class."""

        super().__init__(desc="Process pod commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--socket-path",
            default="/var/run/podman/podman.sock",
            help="Path to the podman socket. Default: %(default)s",
        )
        self.parser.add_argument(
            "--env",
            help="Comma separated environment variables. KEY=VALUE,...",
            metavar="KEY=VALUE",
        )
        self.parser.add_argument(
            "--command",
            help="Run a command in an exec container.",
            nargs="+",
        )
        self.parser.add_argument(
            "--privileged",
            action="store_true",
            help="Access a container with privleges.",
        )
        self.parser.add_argument(
            "--no-tlsverify",
            default=False,
            action="store_true",
            help="Skip using TLS verify for registry Default: %(default)s",
        )
        self.parser.add_argument(
            "--force",
            action="store_true",
            help="When running removal operations, Enable|Disable force.",
        )
        self.parser.add_argument(
            "--kill-signal",
            default="SIGKILL",
            help="Set the kill signal. Default: %(default)s",
            metavar="SIGNAL",
        )
        pod_group = self.parser.add_mutually_exclusive_group(required=True)
        pod_group.add_argument(
            "--start", help="Start a pod.", metavar="POD_NAME"
        )
        pod_group.add_argument(
            "--stop", help="Stop a pod.", metavar="POD_NAME"
        )
        pod_group.add_argument(
            "--rm", help="Remove a pod.", metavar="POD_NAME"
        )
        pod_group.add_argument(
            "--kill", help="Kill a pod.", metavar="POD_NAME"
        )
        pod_group.add_argument(
            "--inspect", help="Inspect a pod.", metavar="POD_NAME"
        )
        pod_group.add_argument(
            "--play",
            help="Play a pod from a structured file.",
            metavar="POD_FILE",
        )
        pod_group.add_argument(
            "--exec-run",
            help="Create an execution container to run a command within.",
            metavar="CONTAINER_NAME",
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
        if self.known_args.start:
            data["pod_action"] = "start"
            data["kwargs"] = dict(
                name=self.known_args.start, timeout=self.known_args.timeout
            )
        elif self.known_args.stop:
            data["pod_action"] = "stop"
            data["kwargs"] = dict(
                name=self.known_args.stop, timeout=self.known_args.timeout
            )
        elif self.known_args.rm:
            data["pod_action"] = "rm"
            data["kwargs"] = dict(
                name=self.known_args.rm, force=self.known_args.force
            )
        elif self.known_args.kill:
            data["pod_action"] = "kill"
            data["kwargs"] = dict(
                name=self.known_args.kill, signal=self.known_args.kill_signal
            )
        elif self.known_args.inspect:
            data["pod_action"] = "inspect"
            data["kwargs"] = dict(name=self.known_args.inspect)
        elif self.known_args.play:
            data["pod_action"] = "play"
            data["kwargs"] = dict(
                pod_file=self.known_args.play,
                tlsverify=(not self.known_args.no_tlsverify),
            )
        elif self.known_args.exec_run:
            data["pod_action"] = "exec_run"
            data["kwargs"] = dict(
                name=self.known_args.exec_run,
                privileged=self.known_args.privileged,
                command=self.known_args.command,
            )
            if self.known_args.env:
                data["kwargs"]["env"] = self.known_args.env.split(",")

        data["socket_path"] = self.known_args.socket_path
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run pod command operation.

        :param command: Work directory path.
        :type command: String
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        if not AVAILABLE_PODMAN:
            return (
                None,
                "The required podman-py library is not installed",
                False,
                None,
            )
        try:
            with PodmanPod(socket=job["socket_path"]) as p:
                action = getattr(p, job["pod_action"], None)
                if action:
                    status, data = action(**job["kwargs"])
                    if data:
                        data = json.dumps(data)
                    if status:
                        return data, None, status, None

                    return None, data, status, None

                return (
                    None,
                    (
                        "The action [ {action} ] failed to return"
                        "  a function".format(action=job["pod_action"])
                    ),
                    False,
                    None,
                )
        except Exception as e:
            self.log.critical(
                "Job [ %s ] critical error %s", job["job_id"], str(e)
            )
            return None, traceback.format_exc(), False, None
