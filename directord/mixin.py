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

import argparse
import glob
import json
import multiprocessing
import os
import shlex
import sys
import yaml

import jinja2

import directord
from directord import utils


class Mixin(object):
    """Mixin class."""

    def __init__(self, args):
        """Initialize the Directord mixin.

        Sets up the mixin object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        self.args = args
        self.blueprint = jinja2.Environment(loader=jinja2.BaseLoader())
        self.log = directord.getLogger(name="directord")

    @staticmethod
    def sanitized_args(execute):
        """Return arguments in a flattened array.

        This will inspect the execution arguments and return everything found
        as a flattened array.

        :param execute: Execution string to parse.
        :type execute: String
        :returns: List
        """

        return [i for g in execute for i in g.split()]

    def _exec_parser(self, parser, exec_string):
        """Run the parser and return parsed arguments.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :returns: Tuple
        """

        known_args, unknown_args = parser.parse_known_args(
            self.sanitized_args(execute=exec_string)
        )
        if hasattr(known_args, "exec_help") and known_args.exec_help:
            raise SystemExit(parser.print_help())
        else:
            return known_args, unknown_args

    def _exec_action_run(self, parser, exec_string, data):
        """Return data from formatted run action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument(
            "--stdout-arg",
            help=(
                "Stores the stdout of a given command as a cached" " argument."
            ),
        )

        args, command = self._exec_parser(
            parser=parser, exec_string=exec_string
        )
        if args.stdout_arg:
            data["stdout_arg"] = args.stdout_arg
        data["command"] = " ".join(command)
        return data

    def _exec_action_transfer(self, parser, exec_string, data):
        """Return data from formatted transfer action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument("--chown", help="Set the file ownership")
        parser.add_argument(
            "--blueprint",
            action="store_true",
            help="Instruct the remote file to be blueprinted.",
        )
        parser.add_argument(
            "files",
            nargs="+",
            help="Set the file to transfer: 'FROM' 'TO'",
        )
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        if args.chown:
            chown = args.chown.split(":", 1)
            if len(chown) == 1:
                chown.append(None)
            data["user"], data["group"] = chown
        file_from, data["to"] = shlex.split(" ".join(args.files))
        data["from"] = [
            os.path.abspath(os.path.expanduser(i))
            for i in glob.glob(file_from)
            if os.path.isfile(os.path.expanduser(i))
        ]
        if not data["from"]:
            raise AttributeError(
                "The value of [ {} ] was not found.".format(file_from)
            )
        data["blueprint"] = args.blueprint
        return data

    def _exec_action_cache(self, parser, exec_string, data, verb):
        """Return data from formatted transfer action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :param verb: Interaction key word.
        :type verb: String
        :returns: Dictionary
        """

        cache_type = "{}s".format(verb.lower())
        parser.add_argument(
            cache_type,
            nargs="+",
            action="append",
            help="Set a given argument. KEY VALUE",
        )
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        cache_obj = getattr(args, cache_type)
        data[cache_type] = dict([" ".join(cache_obj[0]).split(" ", 1)])
        return data

    def _exec_action_workdir(self, parser, exec_string, data):
        """Return data from formatted workdir action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument("workdir", help="Create a directory.")
        args, _ = parser.parse_known_args(
            self.sanitized_args(execute=exec_string)
        )
        data["workdir"] = args.workdir
        return data

    def _exec_action_cachefile(self, parser, exec_string, data):
        """Return data from formatted cachefile action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument(
            "cachefile",
            help="Load a cached file and store it as an update to ARGs.",
        )
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        data["cachefile"] = args.cachefile
        return data

    def _exec_action_cacheevict(self, parser, exec_string, data):
        """Return data from formatted cacheevict action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument(
            "cacheevict",
            help=(
                "Evict all tagged cached items from a client machine."
                " Typical tags are, but not limited to:"
                " [args, envs, jobs, parents, query, ...]. To evict 'all'"
                " cached items use the keyword 'all'."
            ),
        )
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        data["cacheevict"] = args.cacheevict
        return data

    def _exec_action_query(self, parser, exec_string, data):
        """Return data from formatted query action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument(
            "query",
            help=(
                "Scan the environment for a given cached argument and"
                " store the resultant on the target. The resultant is"
                " set in dictionary format: `{'client-id': ...}`"
            ),
        )
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        if hasattr(args, "exec_help") and args.exec_help:
            return parser.print_help(1)

        data["query"] = args.query
        return data

    def _exec_action_pod(self, parser, exec_string, data):
        """Return data from formatted query action.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        parser.add_argument(
            "--socket-path",
            default="/var/run/podman/podman.sock",
            help="Path to the podman socket. Default: %(default)s",
        )
        parser.add_argument(
            "--env",
            help="Comma separated environment variables. KEY=VALUE,...",
            metavar="KEY=VALUE",
        )
        parser.add_argument(
            "--command",
            help="Run a command in an exec container.",
            nargs="+",
        )
        parser.add_argument(
            "--privileged",
            action="store_true",
            help="Access a container with privleges.",
        )
        parser.add_argument(
            "--tls-verify",
            action="store_true",
            help="Verify certificates when pulling container images.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="When running removal operations, Enable|Disable force.",
        )
        parser.add_argument(
            "--kill-signal",
            default="SIGKILL",
            help="Set the kill signal. Default: %(default)s",
            metavar="SIGNAL",
        )
        pod_group = parser.add_mutually_exclusive_group(required=True)
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
        args, _ = self._exec_parser(parser=parser, exec_string=exec_string)
        if args.start:
            data["pod_action"] = "start"
            data["kwargs"] = dict(name=args.start, timeout=args.timeout)
        elif args.stop:
            data["pod_action"] = "stop"
            data["kwargs"] = dict(name=args.stop, timeout=args.timeout)
        elif args.rm:
            data["pod_action"] = "rm"
            data["kwargs"] = dict(name=args.rm, force=args.force)
        elif args.kill:
            data["pod_action"] = "kill"
            data["kwargs"] = dict(name=args.kill, signal=args.kill_signal)
        elif args.inspect:
            data["pod_action"] = "inspect"
            data["kwargs"] = dict(name=args.inspect)
        elif args.play:
            data["pod_action"] = "play"
            data["kwargs"] = dict(
                pod_file=args.play, tls_verify=args.tls_verify
            )
        elif args.exec_run:
            data["pod_action"] = "exec_run"
            data["kwargs"] = dict(
                name=args.exec_run,
                privileged=args.privileged,
                command=args.command,
            )
            if args.env:
                data["kwargs"]["env"] = args.env.split(",")

        data["socket_path"] = args.socket_path
        return data

    def format_action(
        self,
        verb,
        execute,
        targets=None,
        ignore_cache=False,
        restrict=None,
        parent_id=None,
        return_raw=False,
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
        :param ignore_cache: Instruct the entire execution to
                             ignore client caching.
        :type ignore_cache: Boolean
        :param restrict: Restrict job execution based on a provided task SHA1.
        :type restrict: List
        :param parent_id: Set the parent UUID for execution jobs.
        :type parent_id: String
        :param return_raw: Enable a raw return from the server.
        :type return_raw: Boolean
        :returns: String
        """

        args = None
        data = dict()
        parser = argparse.ArgumentParser(
            description="Process exec commands",
            allow_abbrev=False,
            add_help=False,
        )
        parser.add_argument(
            "--exec-help",
            action="help",
            help="Show this execution help message.",
        )
        parser.add_argument(
            "--skip-cache",
            action="store_true",
            help="For a task to skip the on client cache.",
        )
        parser.add_argument(
            "--run-once",
            action="store_true",
            help="Force a given task to run once.",
        )
        parser.add_argument(
            "--timeout",
            default=600,
            type=int,
            help="Set the action timeout. Default %(default)s.",
        )
        self.log.debug("Executing - VERB:%s, EXEC:%s", verb, execute)
        if verb == "RUN":
            data.update(
                self._exec_action_run(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb in ["COPY", "ADD"]:
            data.update(
                self._exec_action_transfer(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb in ["ARG", "ENV"]:
            data.update(
                self._exec_action_cache(
                    parser=parser,
                    exec_string=execute,
                    data=data,
                    verb=verb,
                )
            )
        elif verb == "WORKDIR":
            data.update(
                self._exec_action_workdir(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb == "CACHEFILE":
            data.update(
                self._exec_action_cachefile(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb == "CACHEEVICT":
            data.update(
                self._exec_action_cacheevict(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb == "QUERY":
            data.update(
                self._exec_action_query(
                    parser=parser, exec_string=execute, data=data
                )
            )
        elif verb == "POD":
            data.update(
                self._exec_action_pod(
                    parser=parser, exec_string=execute, data=data
                )
            )
        else:
            raise SystemExit(parser.print_help())

        if targets:
            data["targets"] = targets

        data["verb"] = verb
        data["timeout"] = getattr(args, "timeout", 600)
        data["run_once"] = getattr(args, "run_once", False)
        data["task_sha1sum"] = utils.object_sha1(obj=data)
        data["return_raw"] = return_raw
        data["skip_cache"] = ignore_cache or getattr(args, "skip_cache", False)

        if parent_id:
            data["parent_id"] = parent_id

        if restrict:
            data["restrict"] = restrict

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
        :param restrict: Restrict a given orchestration job to a set of SHA1
                         job fingerprints.
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
            parent_id = utils.get_uuid()
            targets = defined_targets or orchestrate.get("targets", list())
            jobs = orchestrate["jobs"]
            for job in jobs:
                key, value = next(iter(job.items()))
                value = [value]
                job_to_run.append(
                    dict(
                        verb=key,
                        execute=value,
                        targets=targets,
                        restrict=restrict,
                        ignore_cache=ignore_cache,
                        parent_id=parent_id,
                        return_raw=return_raw,
                    )
                )

        return_data = list()
        count = 0
        for job in job_to_run:
            formatted_job = self.format_action(**job)
            if getattr(self.args, "finger_print", False):
                item = json.loads(formatted_job)
                exec_str = " ".join(job["execute"])
                if len(exec_str) >= 30:
                    exec_str = "{execute}...".format(execute=exec_str[:27])
                return_data.append(
                    "{count:<5} {verb:<13}"
                    " {execute:<39} {fingerprint:>13}".format(
                        count=count
                        or "\n{a}\n{b:<5}".format(a="*" * 100, b=0),
                        verb=item["verb"],
                        execute=exec_str,
                        fingerprint=item["task_sha1sum"],
                    ).encode()
                )
                count += 1
            else:
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
                        return_raw=getattr(self.args, "poll", False),
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
            return_raw=getattr(self.args, "poll", False),
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

        tabulated_data = [["ID", self.args.job_info]]
        for key, value in data.items():
            if not value:
                continue

            if key.startswith("_"):
                continue

            if isinstance(value, list):
                value = "\n".join(value)
            elif isinstance(value, dict):
                value = "\n".join(
                    ["{} = {}".format(k, v) for k, v in value.items() if v]
                )

            tabulated_data.append([key.upper(), value])
        else:
            return tabulated_data

    @staticmethod
    def return_tabulated_data(data, restrict_headings):
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
        for key, value in original_data:
            arranged_data = [key]
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

            seen_computed_key.append(key)
            tabulated_data.append(arranged_data)
        else:
            return tabulated_data, found_headings, computed_values

    @staticmethod
    def bootstrap_catalog_entry(entry):
        """Return a flattened list of bootstrap job entries.

        :param entry: Catalog entry for bootstraping.
        :type entry: Dictionary
        :returns: List
        """

        ordered_entries = list()
        args = entry.get("args", dict(port=22, username="root"))
        for target in entry["targets"]:
            item = dict(
                host=target["host"],
                username=target.get("username", args["username"]),
                port=target.get("port", args["port"]),
                jobs=entry["jobs"],
            )
            ordered_entries.append(item)
        return ordered_entries

    @staticmethod
    def bootstrap_localfile_padding(localfile):
        """Return a padded localfile.

        Local files should be a fully qualified path. If the path is
        not fully qualified, this method will add the tools prefix to the
        file.

        :param localfile: Path to file.
        :type localfile: String
        :returns: String
        """

        if not localfile.startswith(os.sep):
            if sys.prefix == sys.base_prefix:
                base_path = os.path.join(
                    sys.base_prefix, "share/directord/tools"
                )
            else:
                base_path = os.path.join(sys.prefix, "share/directord/tools")
            return os.path.join(base_path, localfile)
        else:
            return localfile

    def bootstrap_flatten_jobs(self, jobs, return_jobs=None):
        """Return a flattened list of jobs.

        This method will flatten a list of jobs, and if an entry is an array
        the method will recurse.

        :param jobs: List of jobs to parse.
        :type jobs: List
        :param return_jobs: Seed list to use when flattening the jobs array.
        :type: return_jobs: None|List
        :returns: List
        """

        if not return_jobs:
            return_jobs = list()

        for job in jobs:
            if isinstance(job, list):
                return_jobs = self.bootstrap_flatten_jobs(
                    jobs=job, return_jobs=return_jobs
                )
            else:
                return_jobs.append(job)
        return return_jobs

    def bootstrap_run(self, job_def, catalog):
        """Run a given set of jobs using a defined job definition.

        This method requires a job definition which contains the following.

        {
            "host": String,
            "port": Integer,
            "username": String,
            "key_file": String,
            "jobs": List,
        }

        :param jobs_def: Defined job definition.
        :type jobs_def: Dictionary
        :param catalog: The job catalog definition.
        :type catalog: Dictionary
        """

        self.log.info("Running bootstrap for %s", job_def["host"])
        for job in self.bootstrap_flatten_jobs(jobs=job_def["jobs"]):
            key, value = next(iter(job.items()))
            self.log.debug("Executing: {} {}".format(key, value))
            with utils.ParamikoConnect(
                host=job_def["host"],
                username=job_def["username"],
                port=job_def["port"],
                key_file=job_def.get("key_file"),
            ) as ssh:
                if key == "RUN":
                    self.bootstrap_exec(
                        ssh=ssh, command=value, catalog=catalog
                    )
                elif key == "ADD":
                    localfile, remotefile = value.split(" ", 1)
                    localfile = self.bootstrap_localfile_padding(localfile)
                    self.bootstrap_file_send(
                        ssh=ssh, localfile=localfile, remotefile=remotefile
                    )
                elif key == "GET":
                    remotefile, localfile = value.split(" ", 1)
                    self.bootstrap_file_get(
                        ssh=ssh, localfile=localfile, remotefile=remotefile
                    )

    @staticmethod
    def bootstrap_file_send(ssh, localfile, remotefile):
        """Run a remote put command.

        :param ssh: SSH connection object.
        :type ssh: Object
        :param localfile: Local file to transfer.
        :type localfile: String
        :param remotefile: Remote file destination.
        :type remotefile: String
        """

        ftp_client = ssh.open_sftp()
        try:
            ftp_client.put(localfile, remotefile)
        finally:
            ftp_client.close()

    @staticmethod
    def bootstrap_file_get(ssh, localfile, remotefile):
        """Run a remote get command.

        :param ssh: SSH connection object.
        :type ssh: Object
        :param localfile: Local file destination.
        :type localfile: String
        :param remotefile: Remote file to transfer.
        :type remotefile: String
        """

        ftp_client = ssh.open_sftp()
        try:
            ftp_client.get(remotefile, localfile)
        finally:
            ftp_client.close()

    def bootstrap_exec(self, ssh, command, catalog):
        """Run a remote command.

        Run a command and check the status. If there's a failure the
        method will exit error.

        :param session: SSH Session connection object.
        :type session: Object
        :param command: Plain-text execution string.
        :type command: String
        :param catalog: The job catalog definition.
        :type catalog: Dictionary
        """

        t_command = self.blueprint.from_string(command)
        _, stdout, stderr = ssh.exec_command(t_command.render(**catalog))
        if stdout.channel.recv_exit_status() != 0:
            raise SystemExit(
                "Bootstrap command failed: {}, Error: {}".format(
                    command, stderr
                )
            )

    def bootstrap_q_processor(self, queue, catalog):
        """Run a queing execution thread.

        The queue will be processed so long as there are objects to process.

        :param queue: SSH connection object.
        :type queue: Object
        :param catalog: The job catalog definition.
        :type catalog: Dictionary
        """

        while True:
            try:
                job_def = queue.get(timeout=3)
            except Exception:
                break
            else:
                self.bootstrap_run(
                    job_def=job_def,
                    catalog=catalog,
                )

    def bootstrap_cluster(self):
        """Run a cluster wide bootstrap using a catalog file.

        Cluster bootstrap requires a catalog file to run. Catalogs are broken
        up into two sections, `directord_server` and `directord_client`. All
        servers are processed serially and first. All clients are processing
        in parallel using a maximum of the threads argument.
        """

        q = multiprocessing.Queue()
        catalog = dict()
        for c in self.args.catalog:
            utils.merge_dict(base=catalog, new=yaml.safe_load(c))

        directord_server = catalog.get("directord_server")
        if directord_server:
            self.log.info("Loading server information")
            for s in self.bootstrap_catalog_entry(entry=directord_server):
                s["key_file"] = self.args.key_file
                self.bootstrap_run(job_def=s, catalog=catalog)

        directord_clients = catalog.get("directord_clients")
        if directord_clients:
            self.log.info("Loading client information")
            for c in self.bootstrap_catalog_entry(entry=directord_clients):
                c["key_file"] = self.args.key_file
                q.put(c)

        cleanup_threads = list()
        for _ in range(self.args.threads):
            t = multiprocessing.Process(
                target=self.bootstrap_q_processor, args=(q, catalog)
            )
            t.daemon = True
            t.start()
            cleanup_threads.append(t)

        for t in cleanup_threads:
            t.join()
