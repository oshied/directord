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
import os
import traceback

import yaml

try:
    from podman import PodmanClient

    AVAILABLE_PODMAN = True
except ImportError:
    AVAILABLE_PODMAN = False

from directord import components


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
            "--tls-verify",
            action="store_true",
            help="Verify certificates when pulling container images.",
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
                tls_verify=self.known_args.tls_verify,
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


class PodmanConnect:
    """Connect to the podman unix socket."""

    def __init__(self, socket="/var/run/podman/podman.sock"):
        """Initialize the Directord pod connection class.

        Sets up the pod api object.

        :param socket: Socket path to connect to.
        :type socket: String
        """

        self.pod = PodmanClient(
            base_url="unix://{socket}".format(socket=socket)
        )
        self.api = self.pod.api

    def __exit__(self, *args, **kwargs):
        """Close the connection and exit."""

        self.close()

    def __enter__(self):
        """Return self for use within a context manager."""

        return self

    def close(self):
        """Close the connection."""

        self.pod.close()


class PodmanPod(PodmanConnect):
    def __init__(self, socket):
        """Initialize the Directord pod class.

        Sets up the pod api object.

        :param socket: Socket path to connect to.
        :type socket: String
        """

        super(PodmanPod, self).__init__(socket=socket)

    @staticmethod
    def _decode(data):
        """Decode byte data and return it.

        If the byte data is JSON type the returned value will
        be a JSON string.
        """

        data = data.decode()
        if data:
            try:
                return json.loads(data)
            except Exception:
                return data

    def start(self, name, timeout=120):
        """Start a given pod and return the action status.

        :param name: Pod name.
        :type name: String
        :param timeout: API timeout when running a pod interaction.
        :type timeout: Integer
        :returns: Tuple
        """

        resp = self.api.post(
            path="/pods/{name}/start".format(name=name),
            params={"t": timeout},
        )
        return resp.ok, self._decode(resp.content)

    def stop(self, name, timeout=120):
        """Stop a given pod and return the action status.

        :param name: Pod name.
        :type name: String
        :param timeout: API timeout when running a pod interaction.
        :type timeout: Integer
        :returns: Tuple
        """

        resp = self.api.post(
            path="/pods/{name}/stop".format(name=name),
            params={"t": timeout},
        )
        return resp.ok, self._decode(resp.content)

    def rm(self, name, force=False):
        """Remove a given pod and return the action status.

        :param name: Pod name.
        :type name: String
        :param force: Force remove a pod
        :type force: Boolean
        :returns: Tuple
        """

        resp = self.api.delete(
            path="/pods/{name}".format(name=name),
            params={"force": force},
        )
        return resp.ok, self._decode(resp.content)

    def kill(self, name, signal="SIGKILL"):
        """Kill a given pod and return the action status.

        :param name: Pod name.
        :type name: String
        :param signal: Signal used when killing a pod
        :type signal: String
        :returns: Tuple
        """

        resp = self.api.post(
            path="/pods/{name}/kill".format(name=name),
            params={"signal": signal},
        )
        return resp.ok, self._decode(resp.content)

    def inspect(self, name):
        """Inspect a given pod and return the action status.

        :param name: Pod name.
        :type name: String
        :returns: Tuple
        """

        resp = self.api.get(path="/pods/{name}/json".format(name=name))
        return resp.ok, self._decode(resp.content)

    def play(self, pod_file, tls_verify=True):
        """Instantiate a given pod and return the action status.

        :param pod_file: Full path to a pod YAML file.
        :type pod_file: String
        :returns: Tuple
        """

        if os.path.exists(os.path.abspath(os.path.expanduser(pod_file))):
            with open(pod_file) as f:
                resp = self.api.post(
                    path="/play/kube",
                    data=json.dumps(yaml.safe_load(f)),
                    params={"tlsVerify": tls_verify, "start": True},
                )
            return resp.ok, self._decode(resp.content)

        return False, "Pod YAML did not exist"

    def exec_run(self, name, command, env, privileged=False):
        """Create an exec container and run it.

        :param name: Container name.
        :type name: String
        :param command: Command to be run in list format.
        :type command: List
        :param env: Environment used when executing a command.
        :type env: List
        :param privileged: Enable|Disable privileged commands.
        :type privileged: Boolean
        :returns: Tuple
        """

        _command = {
            "AttachStderr": True,
            "AttachStdin": True,
            "AttachStdout": True,
            "Cmd": command,
            "Env": env,
            "Privileged": privileged,
            "Tty": True,
        }
        resp = self.api.post(
            path="containers/{name}/exec".format(name=name),
            data=json.dumps(_command),
        )
        if resp.ok:
            resp = self.api.post(
                path="/exec/{id}/start".format(
                    id=self._decode(resp.content)["Id"]
                ),
                data=json.dumps({"Detach": False, "Tty": True}),
            )
        return resp.ok, self._decode(resp.content)
