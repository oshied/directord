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

    def poll_job(self, job_id, miss=0):
        """Given a job poll for its completion and return status.

        > The status return is (Boolean, String)

        :param job_id: UUID for job
        :type job_id: String
        :param miss: Cache miss counter
        :type miss: Integer
        :returns: Tuple
        """

        while True:
            data = dict(json.loads(self.run(override="list-jobs")))
            data_return = data.get(job_id, dict())
            job_state = data_return.get("PROCESSING", "unknown")
            job_state = job_state.encode()
            if job_state == self.driver.job_processing:
                time.sleep(1)
            elif job_state == self.driver.job_failed:
                return False, "Job Failed: {}".format(job_id)
            elif job_state in [self.driver.job_end, self.driver.nullbyte]:
                nodes = len(data_return.get("NODES"))
                if len(data_return.get("SUCCESS", list())) == nodes:
                    return True, "Job Success: {}".format(job_id)
                elif len(data_return.get("FAILED", list())) > 0:
                    return False, "Job Degrated: {}".format(job_id)

                return True, "Job Skipped: {}".format(job_id)
            else:
                miss += 1
                if miss > getattr(self.args, "timeout", 600):
                    return None, "Job in an unknown state: {}".format(job_id)
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
            or getattr(self.args, "job_info", False)
            or getattr(self.args, "export_jobs", False)
        ):
            manage = "list-jobs"
        elif (
            override == "list-nodes"
            or getattr(self.args, "list_nodes", False)
            or getattr(self.args, "export_nodes", False)
        ):
            manage = "list-nodes"
        elif override == "purge-jobs" or getattr(
            self.args, "purge_jobs", False
        ):
            manage = "purge-jobs"
        elif override == "purge-nodes" or getattr(
            self.args, "purge_nodes", False
        ):
            manage = "purge-nodes"
        elif override == "generate-keys" or getattr(
            self.args, "generate_keys", False
        ):
            return self.generate_certificates()
        elif override == "dump-cache" or getattr(
            self.args, "dump_cache", False
        ):
            manage = "dump-cache"
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
            raise SystemExit("No known management function was defined.")

        self.log.debug("Executing Management Command:%s", manage)
        return directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage=manage)),
        )
