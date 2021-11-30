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

import requests
import time

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


class Component(components.ComponentBase):
    def __init__(self):
        """Initialize the component wait class."""

        super().__init__(desc="Wait until a condition is met")
        self.requires_lock = False

    def args(self):
        """Set default arguments for a component."""

        super().args()
        condition_group = self.parser.add_mutually_exclusive_group(
            required=True
        )
        condition_group.add_argument(
            "--seconds",
            type=int,
            help="Wait for the provided seconds",
        )
        condition_group.add_argument(
            "--url",
            action="store_true",
            help="Wait for URL to return 2xx or 3xx",
        )
        condition_group.add_argument(
            "--cmd",
            action="store_true",
            help="Wait for the provided command to returns successful",
        )
        self.parser.add_argument(
            "--retry",
            default=30,
            type=int,
            help="Number of times to retry condition (ignored with --seconds)",
        )
        self.parser.add_argument(
            "--retry-wait",
            default=1,
            type=int,
            help="Time to wait between retries(ignored with --seconds)",
        )
        self.parser.add_argument(
            "--insecure",
            action="store_true",
            help="Allow insecure server connections when using SSL",
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
        if self.known_args.seconds:
            data["seconds"] = self.known_args.seconds
        elif self.known_args.url:
            data["url"] = " ".join(self.unknown_args)
        elif self.known_args.cmd:
            data["command"] = " ".join(self.unknown_args)
        data["retry"] = self.known_args.retry
        data["retry_wait"] = self.known_args.retry_wait
        data["insecure"] = self.known_args.insecure
        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Wait for condition.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        self.log.debug("client(): job: %s, cache: %s", job, cache)
        seconds = job.get("seconds")
        url = job.get("url")
        cmd = job.get("command")
        if url:
            _, url = self.blueprinter(
                content=url,
                values=cache.get("args"),
                allow_empty_values=True,
            )
        elif cmd:
            _, cmd = self.blueprinter(
                content=cmd,
                values=cache.get("args"),
                allow_empty_values=True,
            )
        retry = job.get("retry", 0)
        retry_wait = job.get("retry_wait", 0)
        insecure = job.get("insecure", False)

        out = b""
        err = b""
        success = True
        msg = None
        if seconds is not None:
            time.sleep(seconds)
            return out, err, success, msg
        elif url is not None:
            out, err, success = self._fetch_url(
                url, not insecure, retry, retry_wait
            )
            if not success:
                msg = f"URL did not return a 2xx or 3xx. Retired {retry} times"
            return out, err, success, msg
        elif cmd is not None:
            out, err, success = self._run_cmd(
                cmd, cache.get("envs"), retry, retry_wait
            )
            if not success:
                msg = f"Command was not successful. Retried {retry} times."
            return out, err, success, msg
        else:
            self.log.error("Invalid wait condition provided")
            return out, err, False, None

    def _fetch_url(
        self, url: str, verify: bool, retry: int = 0, retry_wait: int = 0
    ):
        """Fetch url with retry.

        Fetch a url and return True if response code is 2xx or 3xx.

        :param url: Url string to fetch
        :type url: String
        :param verify: Boolean to manage ssl validation
        :type verify: Boolean
        :param retry: Number of retries on failure
        :type retry: Integer
        :param: retry_wait: Number of seconds to wait between retry
        :type retry_wait: Integer
        :returns: tuple
        """
        stdout = b""
        stderr = b""
        outcome = False
        count = 0
        while not outcome and count < (retry + 1):
            count = count + 1
            try:
                r = requests.get(url, verify=verify)
                stdout = f"Response code was {r.status_code}"
                if r.status_code >= 200 and r.status_code < 400:
                    outcome = True
            except Exception as e:
                stderr = "Exception occured while fetching url {}".format(
                    str(e)
                )
                self.log.error(stderr)
            if not outcome and retry_wait > 0:
                self.log.debug("Url fetch failed, retrying with wait...")
                time.sleep(retry_wait)

        return stdout, stderr, outcome

    def _run_cmd(
        self, cmd: str, env: dict, retry: int = 0, retry_wait: int = 0
    ):
        """Run command with retry.

        Run a command and if not successful, retry.

        :param cmd: Command string to run
        :type cmd: String
        :param env: Environment dict to pass when running
        :type env: Dictionary
        :param retry: Number of retries on failure
        :type retry: Integer
        :param: retry_wait: Number of seconds to wait between retry
        :type retry_wait: Integer
        :returns: tuple
        """
        job_stdout = []
        job_stderr = []
        outcome = False
        count = 0
        while not outcome and count < (retry + 1):
            count = count + 1
            stdout, stderr, outcome = self.run_command(command=cmd, env=env)
            job_stdout.append(stdout)
            job_stderr.append(stderr)
            if not outcome and retry_wait > 0:
                self.log.debug("Command failed, retrying with wait...")
                time.sleep(retry_wait)

        return b"".join(job_stdout), b"".join(job_stderr), outcome
