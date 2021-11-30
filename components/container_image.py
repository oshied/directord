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
    from directord.components.lib.podman import PodmanImage

    AVAILABLE_PODMAN = True
except ImportError:
    AVAILABLE_PODMAN = False

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Process container images")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--socket-path",
            default="/var/run/podman/podman.sock",
            help="Path to the podman socket. Default: %(default)s",
        )
        self.parser.add_argument(
            "--no-tlsverify",
            default=False,
            action="store_true",
            help="Skip using TLS verify for registry Default: %(default)s",
        )
        action_group = self.parser.add_mutually_exclusive_group(required=True)
        action_group.add_argument(
            "--pull",
            action="store_true",
            help="Pull images from a registry.",
        )
        action_group.add_argument(
            "--push",
            action="store_true",
            help="Push images to a registry.",
        )
        action_group.add_argument(
            "--tag",
            action="store_true",
            help="Tag images with a new tag.",
        )
        action_group.add_argument(
            "--list",
            action="store_true",
            help="List all images on a host.",
        )
        action_group.add_argument(
            "--inspect",
            action="store_true",
            help="Inspect specific images on a host.",
        )

        self.parser.add_argument(
            "images",
            nargs="*",
            help="specify container images.",
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
        data["images"] = self.known_args.images
        data["socket_path"] = self.known_args.socket_path
        data["tlsverify"] = not self.known_args.no_tlsverify
        if self.known_args.pull:
            data["action"] = "pull"
        elif self.known_args.push:
            data["action"] = "push"
        elif self.known_args.tag:
            data["action"] = "tag"
        elif self.known_args.list:
            data["action"] = "list"
        elif self.known_args.inspect:
            data["action"] = "inspect"
        data["images"] = self.known_args.images
        if self.known_args.tag and len(self.known_args.images) != 2:
            msg = "Must specify exactly 2 images to tag."
            self.log.critical(msg)
            raise AttributeError(msg)
        if (
            self.known_args.push
            or self.known_args.pull
            or self.known_args.inspect
        ) and not len(self.known_args.images):
            msg = (
                "Must specify exactly at least one image to %s."
                % data["action"]
            )
            raise AttributeError(msg)
        if self.known_args.list and self.known_args.images:
            msg = b"Cannot specify images with --list."
            self.log.critical(msg)
            raise AttributeError(msg)
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run cache echo command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """
        self.log.debug("client(): job: %s, cache: %s", job, cache)
        if not AVAILABLE_PODMAN:
            return (
                None,
                "The required podman-py library is not installed",
                False,
                None,
            )

        try:
            with PodmanImage(socket=job["socket_path"]) as p:
                action = getattr(p, job["action"], None)
                if action:
                    status, data = action(**job)
                    if data and not isinstance(data, str):
                        data = json.dumps(data)
                else:
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
        else:
            if status:
                return data, None, status, None

            return None, data, status, None
