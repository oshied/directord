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
import time

import diskcache

import directord

from directord import interface


class User(interface.Interface):
    """Directord User interface class."""

    def __init__(self, args):
        """Initialize the User interface class.

        Sets up the user object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(User, self).__init__(args=args)


class Manage(User):
    """Directord Manage interface class."""

    def __init__(self, args):
        """Initialize the Manage interface class.

        Sets up the manage object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(User, self).__init__(args=args)

    @staticmethod
    def move_certificates(
        directory, target_directory=None, backup=False, suffix=".key"
    ):
        """Move certificates when required.

        :param directory: Set the origin path.
        :type directory: String
        :param target_directory: Set the target path.
        :type target_directory: String
        :param backup: Enable file backup before moving.
        :type backup:  Boolean
        :param suffix: Set the search suffix
        :type suffix: String
        """

        for item in os.listdir(directory):
            if backup:
                target_file = "{}.bak".format(os.path.basename(item))
            else:
                target_file = os.path.basename(item)

            if item.endswith(suffix):
                os.rename(
                    os.path.join(directory, item),
                    os.path.join(target_directory or directory, target_file),
                )

    def generate_certificates(self, base_dir="/etc/directord"):
        """Generate client and server CURVE certificate files.

        :param base_dir: Directord configuration path.
        :type base_dir: String
        """

        keys_dir = os.path.join(base_dir, "certificates")
        public_keys_dir = os.path.join(base_dir, "public_keys")
        secret_keys_dir = os.path.join(base_dir, "private_keys")

        for item in [keys_dir, public_keys_dir, secret_keys_dir]:
            os.makedirs(item, exist_ok=True)

        # Run certificate backup
        self.move_certificates(directory=public_keys_dir, backup=True)
        self.move_certificates(
            directory=secret_keys_dir, backup=True, suffix=".key_secret"
        )

        # create new keys in certificates dir
        for item in ["server", "client"]:
            self.driver.key_generate(keys_dir=keys_dir, key_type=item)

        # Move generated certificates in place
        self.move_certificates(
            directory=keys_dir,
            target_directory=public_keys_dir,
            suffix=".key",
        )
        self.move_certificates(
            directory=keys_dir,
            target_directory=secret_keys_dir,
            suffix=".key_secret",
        )

    def poll_job(self, job_id):
        """Given a job poll for its completion and return status.

        > The status return is (Boolean, String)

        :param job_id: UUID for job
        :type job_id: String
        :returns: Tuple
        """

        job_processing_interval = 0.25
        processing_attempts = 0
        state_timeout = time.time()
        timeout = getattr(self.args, "timeout", 600)
        while True:
            try:
                data = dict(json.loads(self.run(override=job_id)))
            except json.JSONDecodeError:
                if time.time() - state_timeout > timeout:
                    state_timeout = time.time()
                    return (
                        None,
                        "Job in an unknown state: {}".format(job_id),
                        None,
                        None,
                        None,
                    )
                else:
                    time.sleep(1)
                continue
            else:
                data_return = data.get(job_id, dict())
                if not data_return:
                    if time.time() - state_timeout > timeout:
                        state_timeout = time.time()
                        return (
                            None,
                            "Job in an unknown state: {}".format(job_id),
                            None,
                            None,
                            None,
                        )
                    else:
                        time.sleep(1)
                    continue
                info = data_return.get("INFO")
                stdout = data_return.get("STDOUT")
                stderr = data_return.get("STDERR")
                job_state = data_return.get("PROCESSING", "unknown")
                job_state = job_state.encode()
                if job_state == self.driver.job_processing:
                    time.sleep(job_processing_interval)
                    processing_attempts += 1
                    if processing_attempts > 20:
                        job_processing_interval = 1
                elif job_state == self.driver.job_failed:
                    state_timeout = time.time()
                    return (
                        False,
                        "Job Failed: {}".format(job_id),
                        stdout,
                        stderr,
                        info,
                    )
                elif job_state in [
                    self.driver.job_end,
                    self.driver.nullbyte,
                    self.driver.transfer_end,
                ]:
                    nodes = len(data_return.get("_nodes"))
                    if len(data_return.get("FAILED", list())) > 0:
                        state_timeout = time.time()
                        return (
                            False,
                            "Job Degrated: {}".format(job_id),
                            stdout,
                            stderr,
                            info,
                        )
                    elif len(data_return.get("SUCCESS", list())) == nodes:
                        state_timeout = time.time()
                        return (
                            True,
                            "Job Success: {}".format(job_id),
                            stdout,
                            stderr,
                            info,
                        )
                    else:
                        if time.time() - state_timeout > timeout:
                            state_timeout = time.time()
                            return (
                                True,
                                "Job Skipped: {}".format(job_id),
                                stdout,
                                stderr,
                                info,
                            )
                        else:
                            time.sleep(1)
                else:
                    if time.time() - state_timeout > timeout:
                        state_timeout = time.time()
                        return (
                            None,
                            "Job in an unknown state: {}".format(job_id),
                            stdout,
                            stderr,
                            info,
                        )
                    else:
                        time.sleep(1)

    def run(self, override=None):
        """Send the management command to the server.

        :param override: Set the job function regardless of args.
        :type override: String
        :returns: String
        """

        if (
            override == "list-jobs"
            or getattr(self.args, "list_jobs", False)
            or getattr(self.args, "export_jobs", False)
        ):
            manage = {"list_jobs": None}
        elif (
            override == "list-nodes"
            or getattr(self.args, "list_nodes", False)
            or getattr(self.args, "export_nodes", False)
        ):
            manage = {"list_nodes": None}
        elif override == "purge-jobs" or getattr(
            self.args, "purge_jobs", False
        ):
            manage = {"purge_jobs": None}
        elif override == "purge-nodes" or getattr(
            self.args, "purge_nodes", False
        ):
            manage = {"purge_nodes": None}
        elif override == "generate-keys" or getattr(
            self.args, "generate_keys", False
        ):
            return self.generate_certificates()
        elif override == "dump-cache" or getattr(
            self.args, "dump_cache", False
        ):
            manage = {"dump_cache": None}
            with diskcache.Cache(
                self.args.cache_path,
                tag_index=True,
                disk=diskcache.JSONDisk,
            ) as cache:
                cache_dict = {}
                for item in cache.iterkeys():
                    cache_dict[item] = cache.get(item)
                print(json.dumps(cache_dict, indent=4))
                return
        else:
            job_id = override or getattr(self.args, "job_info", None)
            if job_id:
                manage = {"job_info": job_id}
            else:
                raise SystemExit("No known management function was defined.")

        self.log.debug("Executing Management Command:%s", manage)
        return directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage=manage)),
        )
