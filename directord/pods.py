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
import yaml

try:
    from podman import PodmanClient

    AVAILABLE_PODMAN = True
except ImportError:
    AVAILABLE_PODMAN = False


class PodmanConnect(object):
    def __init__(self, socket="/var/run/podman/podman.sock"):
        self.pod = PodmanClient("unix://{socket}".format(socket=socket))
        self.api = self.pod.api

    def __exit__(self, *args, **kwargs):
        self.close()

    def __enter__(self):
        return self

    @staticmethod
    def _decode(data):
        data = data.decode()
        if data:
            return json.loads(data)

    def close(self):
        self.pod.close()

    def start(self, name, timeout=120):
        resp = self.api.post(
            path="/pods/{name}/start".format(name=name),
            params={"t": timeout},
        )
        return resp.ok, self._decode(resp.content)

    def stop(self, name, timeout=120):
        resp = self.api.post(
            path="/pods/{name}/stop".format(name=name),
            params={"t": timeout},
        )
        return resp.ok, self._decode(resp.content)

    def rm(self, name, force=False):
        resp = self.api.delete(
            path="/pods/{name}".format(name=name),
            params={"force": force},
        )
        return resp.ok, self._decode(resp.content)

    def kill(self, name, signal="SIGKILL"):
        resp = self.api.post(
            path="/pods/{name}/kill".format(name=name),
            params={"signal": signal},
        )
        return resp.ok, self._decode(resp.content)

    def play(self, pod_file, tls_verify=True):
        if os.path.exists(pod_file):
            with open(pod_file) as f:
                resp = self.api.post(
                    path="/play/kube",
                    data=json.dumps(yaml.safe_load(f)),
                    params={"tlsVerify": tls_verify},
                )
            return resp.ok, self._decode(resp.content)
        else:
            return False, "Pod YAML did not exist"

    def exec(self, name, command, env, privileged=False):
        _command = {
            "AttachStderr": True,
            "AttachStdin": True,
            "AttachStdout": True,
            "Cmd": [" ".join(command)],
            "DetachKeys": "string",
            "Env": env,
            "Privileged": privileged,
            "Tty": True,
            "User": "string",
            "WorkingDir": "string",
        }
        resp = self.api.post(
            path="libpod/containers/{name}/exec".format(name=name),
            data=json.dumps(_command),
        )
        return resp.ok, self._decode(resp.content)
