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

from distutils import util as dist_utils

import yaml

import directord

from directord import utils


class Mixin:
    """Mixin class."""

    def __init__(self, args):
        """Initialize the Directord mixin.

        Sets up the mixin object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        self.args = args

    def format_action(
        self,
        verb,
        execute,
        arg_vars=None,
        targets=None,
        ignore_cache=False,
        restrict=None,
        parent_id=None,
        parent_sha3_224=None,
        return_raw=False,
        parent_async=False,
    ):
        """Return a JSON encode object for task execution.

        While formatting the message, the method will treat each verb as a
        case and parse the underlying sub-command, formatting the information
        into a dictionary.

        :param verb: Action to parse.
        :type verb: String
        :param execute: Execution string to parse.
        :type execute: String
        :param targets: Target argents to send job to.
        :type targets: List
        :param arg_vars: Argument dictionary, used to set arguments in
                         dictionary format instead of string format.
        :type arg_vars: Dictionary
        :param ignore_cache: Instruct the entire execution to
                             ignore client caching.
        :type ignore_cache: Boolean
        :param restrict: Restrict job execution based on a provided task
                         SHA3_224.
        :type restrict: List
        :param parent_id: Set the parent UUID for execution jobs.
        :type parent_id: String
        :param parent_sha3_224: Set the parent sha3_224 for execution jobs.
        :type parent_id: String
        :param return_raw: Enable a raw return from the server.
        :type return_raw: Boolean
        :param parent_async: Enable a parent job to run asynchronously.
        :type parent_async: Boolean
        :returns: String
        """

        data = dict(verb=verb)
        component_kwargs = dict(
            exec_array=execute, data=data, arg_vars=arg_vars
        )

        success, transfer, component = directord.component_import(
            component=verb.lower(),
            job_id=parent_id,
        )
        if not success:
            raise SystemExit(component)

        setattr(component, "verb", verb)
        data.update(component.server(**component_kwargs))

        data["timeout"] = getattr(component.known_args, "timeout", 600)
        data["run_once"] = getattr(component.known_args, "run_once", False)
        data["job_sha3_224"] = utils.object_sha3_224(obj=data)
        data["return_raw"] = return_raw
        data["skip_cache"] = ignore_cache or getattr(
            component.known_args, "skip_cache", False
        )

        if targets:
            data["targets"] = targets

        if parent_async:
            data["parent_async"] = parent_async

        if parent_id:
            data["parent_id"] = parent_id

        if parent_sha3_224:
            data["parent_sha3_224"] = parent_sha3_224

        if restrict:
            data["restrict"] = restrict

        if transfer:
            job = {
                "jobs": [
                    {"WORKDIR": "/etc/directord/components"},
                    {
                        "ADD": "--skip-cache {} {}".format(
                            transfer, "/etc/directord/components/"
                        )
                    },
                ]
            }
            self.exec_orchestrations(
                orchestrations=[job],
                defined_targets=data.get("targets"),
                return_raw=True,
            )

        return json.dumps(data)

    def exec_orchestrations(
        self,
        orchestrations,
        defined_targets=None,
        restrict=None,
        ignore_cache=False,
        return_raw=False,
    ):
        """Execute orchestration jobs.

        Iterates over a list of orchestartion blobs, fingerprints the jobs,
        and then runs them.

        :param orchestrations: List of Dictionaries which are run as
                               orchestartion.
        :type orchestrations: List
        :param defined_targets: List of targets to limit a given execution to.
                                This target list provides an override for
                                targets found within a given orchestation.
        :type defined_targets: List
        :param restrict: Restrict a given orchestration job to a set of
                         SHA3_224 job fingerprints.
        :type restrict: Array
        :param ignore_cache: Instruct the orchestartion job to ignore cached
                             executions.
        :type ignore_cache: Boolean
        :param return_raw: Enable a raw return from the server.
        :type return_raw: Boolean
        :returns: List
        """

        job_to_run = list()
        for orchestrate in orchestrations:
            parent_sha3_224 = utils.object_sha3_224(obj=orchestrate)
            parent_id = utils.get_uuid()
            targets = defined_targets or orchestrate.get("targets", list())

            force_async = getattr(self.args, "force_async", False)
            if force_async:
                parent_async = force_async
            else:
                try:
                    parent_async = bool(
                        dist_utils.strtobool(orchestrate.get("async", "False"))
                    )
                except (ValueError, AttributeError):
                    parent_async = bool(orchestrate.get("async", False))

            for job in orchestrate["jobs"]:
                arg_vars = job.pop("vars", None)
                key, value = next(iter(job.items()))
                job_to_run.append(
                    dict(
                        verb=key,
                        execute=[value],
                        arg_vars=arg_vars,
                        targets=targets,
                        restrict=restrict,
                        ignore_cache=ignore_cache,
                        parent_id=parent_id,
                        parent_sha3_224=parent_sha3_224,
                        return_raw=return_raw,
                        parent_async=parent_async,
                    )
                )

        return_data = list()
        if getattr(self.args, "finger_print", False):
            count = 0
            for job in job_to_run:
                tabulated_data = list()
                formatted_job = self.format_action(**job)
                item = json.loads(formatted_job)
                exec_str = " ".join(job["execute"])
                if len(exec_str) >= 30:
                    exec_str = "{execute}...".format(execute=exec_str[:27])
                tabulated_data.extend(
                    [
                        count,
                        job["parent_sha3_224"],
                        item["verb"],
                        exec_str,
                        item["job_sha3_224"],
                    ]
                )
                return_data.append(tabulated_data)
                count += 1
            utils.print_tabulated_data(
                data=return_data,
                headers=["count", "parent_sha", "verb", "exec", "job_sha"],
            )
            return []
        else:
            for job in job_to_run:
                formatted_job = self.format_action(**job)
                return_data.append(
                    directord.send_data(
                        socket_path=self.args.socket_path, data=formatted_job
                    )
                )

        return return_data

    def run_orchestration(self):
        """Run orchestration jobs.

        When orchestration jobs are executed the files are organized and
        then indexed. Once indexed, the jobs are sent to the server. send
        returns are captured and returned on method exit.

        :returns: List
        """

        return_data = list()
        for orchestrate_file in self.args.orchestrate_files:
            orchestrate_file = os.path.abspath(
                os.path.expanduser(orchestrate_file)
            )
            if not os.path.exists(orchestrate_file):
                raise FileNotFoundError(
                    "The [ {} ] file was not found.".format(orchestrate_file)
                )
            else:
                with open(orchestrate_file) as f:
                    orchestrations = yaml.safe_load(f)

                if self.args.target:
                    defined_targets = list(set(self.args.target))
                else:
                    defined_targets = list()

                return_data.extend(
                    self.exec_orchestrations(
                        orchestrations=orchestrations,
                        defined_targets=defined_targets,
                        restrict=self.args.restrict,
                        ignore_cache=self.args.ignore_cache,
                        return_raw=getattr(
                            self.args,
                            "poll",
                            False,
                        )
                        or getattr(self.args, "stream", False)
                        or getattr(self.args, "wait", False),
                    )
                )
        else:
            return return_data

    def run_exec(self):
        """Execute an exec job.

        Jobs are parsed and then sent to the server for processing. All return
        items are captured in an array which is returned on method exit.

        :returns: List
        """

        format_kwargs = dict(
            verb=self.args.verb,
            execute=self.args.exec,
            parent_async=getattr(self.args, "force_async", False),
            return_raw=getattr(self.args, "poll", False)
            or getattr(self.args, "stream", False)
            or getattr(self.args, "wait", False),
        )
        if self.args.target:
            format_kwargs["targets"] = list(set(self.args.target))

        return [
            directord.send_data(
                socket_path=self.args.socket_path,
                data=self.format_action(**format_kwargs),
            )
        ]

    def return_tabulated_info(self, data):
        """Return a list of data that will be tabulated.

        :param data: Information to generally parse and return
        :type data: Dictionary
        :returns: List
        """

        data_id = data.pop("id", None) or self.args.job_info
        if data_id:
            tabulated_data = [["ID", data_id]]
        else:
            tabulated_data = list()

        for key, value in data.items():
            if value is None:
                continue

            if key.startswith("_"):
                continue

            if key == "PROCESSING":
                if value == "\x16":
                    value = "True"
                else:
                    value = "False"

            if isinstance(value, list):
                value = "\n".join(value)
            elif isinstance(value, dict):
                value = "\n".join(
                    ["{} = {}".format(k, v) for k, v in value.items() if v]
                )

            tabulated_data.append([key.upper(), value])
        else:
            return tabulated_data

    def return_tabulated_data(self, data, restrict_headings):
        """Return tabulated data displaying a limited set of information.

        :param data: Information to generally parse and return
        :type data: Dictionary
        :param restrict_headings: List of headings in string format to return
        :type restrict_headings: List
        :returns: List
        """

        def _computed_totals(item, value_heading, value):
            if item not in seen_computed_key:
                if isinstance(value, bool):
                    bool_heading = "{}_{}".format(value_heading, value).upper()
                    if bool_heading in computed_values:
                        computed_values[bool_heading] += 1
                    else:
                        computed_values[bool_heading] = 1
                elif isinstance(value, (float, int)):
                    if value_heading in computed_values:
                        computed_values[value_heading] += value
                    else:
                        computed_values[value_heading] = value

        tabulated_data = list()
        computed_values = dict()
        seen_computed_key = list()
        found_headings = ["ID"]
        original_data = list(dict(data).items())
        result_filter = getattr(self.args, "filter", None)
        for key, value in original_data:
            arranged_data = [key]
            include = result_filter is None
            for item in restrict_headings:
                if item not in found_headings:
                    found_headings.append(item)
                if item.upper() not in value and item.lower() not in value:
                    arranged_data.append(0)
                else:
                    try:
                        report_item = value[item.upper()]
                    except KeyError:
                        report_item = value[item.lower()]

                    if item.upper() == "PROCESSING":
                        if report_item == "\x16":
                            report_item = "True"
                            if result_filter == "processing":
                                include = True
                        else:
                            report_item = "False"
                    elif (
                        isinstance(report_item, list) and len(report_item) > 0
                    ):
                        if (
                            result_filter == "success"
                            and item.upper() == "SUCCESS"
                        ):
                            include = True
                        if (
                            result_filter == "failed"
                            and item.upper() == "FAILED"
                        ):
                            include = True

                    if not report_item:
                        arranged_data.append(0)
                    else:
                        if report_item and isinstance(report_item, list):
                            arranged_data.append(len(report_item))
                        elif isinstance(report_item, float):
                            arranged_data.append("{:.2f}".format(report_item))
                        else:
                            arranged_data.append(report_item)
                        _computed_totals(
                            item=key, value_heading=item, value=report_item
                        )

            if include:
                seen_computed_key.append(key)
                tabulated_data.append(arranged_data)

        return tabulated_data, found_headings, computed_values
