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

import asyncio

from directord import utils


def cacheargs(func):
    """Cache stdout and stderr."""

    def wrapper_func(*args, **kwargs):
        self = args[0]
        job = kwargs["job"]
        stdout_arg = job.get("stdout_arg")
        stderr_arg = job.get("stderr_arg")
        stdout, stderr, outcome, command = func(*args, **kwargs)

        if stdout_arg or stderr_arg:
            self.block_on_tasks = list()
            clean_info = (
                stdout.decode()
                if stdout and isinstance(stdout, bytes)
                else stdout or ""
            )
            clean_info_err = (
                stderr.decode()
                if stderr and isinstance(stderr, bytes)
                else stderr or ""
            )
            arg_job = job.copy()
            arg_job.pop("parent_sha3_224", None)
            arg_job.pop("parent_id", None)
            arg_job.pop("job_sha3_224", None)
            arg_job.pop("job_id", None)
            arg_job.pop("stdout_arg", None)
            arg_job.pop("stderr_arg", None)
            arg_job["skip_cache"] = True
            arg_job["extend_args"] = True
            arg_job["verb"] = "ARG"
            arg_job["args"] = {}
            if stdout_arg:
                arg_job["args"].update({stdout_arg: clean_info.strip()})
            if stderr_arg:
                arg_job["args"].update({stderr_arg: clean_info_err.strip()})
            arg_job["parent_async_bypass"] = True
            arg_job["targets"] = [self.driver.identity]
            arg_job["job_id"] = utils.get_uuid()
            arg_job["job_sha3_224"] = utils.object_sha3_224(obj=arg_job)
            arg_job["parent_id"] = utils.get_uuid()
            arg_job["parent_sha3_224"] = utils.object_sha3_224(obj=arg_job)
            self.block_on_tasks.append(arg_job)

        return stdout, stderr, outcome, command

    return wrapper_func


def retry(func):
    """Retry executor."""

    def wrapper_func(*args, **kwargs):
        retry = kwargs["job"].get("retry", 1)
        attempt = 0
        outcome = False
        while attempt < retry and not outcome:
            stdout, stderr, outcome, command = func(*args, **kwargs)
            attempt += 1

        return stdout, stderr, outcome, command

    return wrapper_func


def timeout(func):
    """Timeout coroutine."""

    def wrapper_func(*args, **kwargs):
        async def _main(*args, **kwargs):
            future = loop.run_in_executor(None, lambda: func(*args, **kwargs))
            try:
                return await asyncio.wait_for(future, timeout=user_timeout)
            except asyncio.TimeoutError:
                self.log.warning(
                    "Job [ %s ] timeout after %s.",
                    kwargs["job"].get("job_id"),
                    user_timeout,
                )
                future.cancel()
                return None, "Timeout encountered", False, None

        self = args[0]
        user_timeout = float(kwargs["job"].get("timeout", 600))
        self.log.debug(
            "Job [ %s ] running, timeout set for %s.",
            kwargs["job"].get("job_id"),
            user_timeout,
        )
        try:
            loop = asyncio.get_running_loop()
        except (AttributeError, RuntimeError):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()

        return loop.run_until_complete(_main(*args, **kwargs))

    return wrapper_func
