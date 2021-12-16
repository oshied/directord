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

import collections
import json
import os
import time

import directord

from directord import interface
from directord import utils


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

    def analyze_job(self, job_id):
        """Run analysis on a given job UUID.

        :param job_id: Job UUID
        :type job_id: String
        :returns: String
        """

        data = directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage={"job_info": job_id})),
        )

        item = list(dict(json.loads(data)).values())

        if item and not item[0]:
            return json.dumps({"job_id_not_found": job_id})

        return self.analyze_data(parent_id=job_id, parent_jobs=item)

    def analyze_parent(self, parent_id):
        """Run analysis on a given parent UUID.

        :param parent_id: Parent UUID
        :type parent_id: String
        :returns: String
        """

        data = directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage={"list_jobs": None})),
        )
        parent_jobs = list()
        if data:
            data = dict(json.loads(data))
            for value in data.values():
                if value["PARENT_JOB_ID"] == parent_id:
                    parent_jobs.append(value)

        if not parent_jobs:
            return json.dumps({"parent_id_not_found": parent_id})

        return self.analyze_data(parent_id=parent_id, parent_jobs=parent_jobs)

    def analyze_all(self):
        """Run analysis on a given parent UUID.

        :param parent_id: Parent UUID
        :type parent_id: String
        :returns: String
        """

        data = directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage={"list_jobs": None})),
        )

        if data:
            data = dict(json.loads(data))
            return self.analyze_data(
                parent_id="All-Jobs", parent_jobs=list(data.values())
            )
        else:
            return json.dumps({"no_jobs_found": "All-Jobs"})

    def analyze_data(self, parent_id, parent_jobs):
        """Run Parent analysis.

        :param parent_id: Parent UUID
        :type parent_id: String
        :param parent_jobs: List of all jobs for a given parent.
        :type parent_jobs: List
        :returns: String
        """

        meta = dict(
            execution=collections.defaultdict(int),
            roundtrip=collections.defaultdict(int),
            nodes=set(),
            node_successes=collections.defaultdict(int),
            node_failures=collections.defaultdict(int),
        )
        analysis = dict(id=parent_id, total_jobs=len(parent_jobs))
        for job in parent_jobs:
            for k, v in job.get("_executiontime", dict()).items():
                meta["nodes"].add(k)
                meta["execution"][k] += v

            for k, v in job.get("_roundtripltime", dict()).items():
                meta["nodes"].add(k)
                meta["roundtrip"][k] += v

            for item in job.get("SUCCESS", list()):
                meta["node_successes"][item] += 1

            for item in job.get("FAILED", list()):
                meta["node_failures"][item] += 1

        analysis["actual_runtime"] = parent_jobs[-1].get(
            "_lasttime", 0
        ) - parent_jobs[0].get("_createtime", 0)
        analysis["slowest_node_execution"] = max(
            meta["execution"], key=meta["execution"].get
        )
        analysis["slowest_node_roundtrip"] = max(
            meta["roundtrip"], key=meta["roundtrip"].get
        )
        analysis["fastest_node_execution"] = min(
            meta["execution"], key=meta["execution"].get
        )
        analysis["fastest_node_roundtrip"] = min(
            meta["roundtrip"], key=meta["roundtrip"].get
        )
        analysis["combined_execution_time"] = sum(meta["execution"].values())
        analysis["total_successes"] = sum(meta["node_successes"].values())
        analysis["total_failures"] = sum(meta["node_failures"].values())
        analysis["total_node_count"] = len(meta["nodes"])
        analysis["total_avg_execution_time"] = (
            analysis["combined_execution_time"] / analysis["total_jobs"]
        )

        return json.dumps(analysis, sort_keys=True)

    def run(self, override=None):
        """Send the management command to the server.

        :param override: Set the job function regardless of args.
        :type override: String
        :returns: String
        """

        def _cache_dump():
            try:
                cache = utils.Cache(
                    path=os.path.join(self.args.cache_path, "client")
                )
                print(json.dumps(dict(cache.items()), indent=4))
            except KeyError:
                pass

        execution_map = {
            "dump-cache": _cache_dump,
            "export-jobs": {"list_jobs": None},
            "export-nodes": {"list_nodes": None},
            "job-info": {"job_info": override},
            "list-jobs": {"list_jobs": None},
            "list-nodes": {"list_nodes": None},
            "purge-jobs": {"purge_jobs": None},
            "purge-nodes": {"purge_nodes": None},
            "analyze-parent": self.analyze_parent,
            "analyze-job": self.analyze_job,
            "analyze-all": self.analyze_all,
        }

        if override and override in execution_map:
            manage = execution_map[override]
            if callable(manage):
                return manage()
        elif isinstance(override, str):
            manage = execution_map["job-info"]
        else:
            for k, v in execution_map.items():
                k_obj = k.replace("-", "_")
                k_arg = getattr(self.args, k_obj, False)
                if k_arg:
                    if callable(v):
                        if isinstance(override, str):
                            return v(override)
                        elif isinstance(k_arg, str):
                            return v(k_arg)
                        else:
                            return v()
                    else:
                        if isinstance(k_arg, str):
                            v[k_obj] = k_arg
                        manage = v
                        break
            else:
                raise SystemExit("No known management function was defined.")

        self.log.debug("Executing Management Command:%s", manage)
        return directord.send_data(
            socket_path=self.args.socket_path,
            data=json.dumps(dict(manage=manage)),
        )
