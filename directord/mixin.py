import multiprocessing
import os
import yaml
import sys

import jinja2

from directord import client
from directord import server
from directord import user
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

    @staticmethod
    def exec_orchestrations(
        user_exec,
        orchestrations,
        defined_targets=None,
        restrict=None,
        ignore_cache=False,
        return_raw=False,
    ):
        """Execute orchestration jobs.

        Iterates over a list of orchestartion blobs, fingerprints the jobs,
        and then runs them.

        :param user_exec: Intialized user-class, required to prepare jobs and
                          format execution.
        :type user_exec: Object
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
            parent_id = user_exec.get_uuid
            targets = defined_targets or orchestrate.get("targets", list())
            jobs = orchestrate["jobs"]
            for job in jobs:
                key, value = next(iter(job.items()))
                value = [value]
                for target in targets:
                    job_to_run.append(
                        dict(
                            verb=key,
                            execute=value,
                            target=target,
                            restrict=restrict,
                            ignore_cache=ignore_cache,
                            parent_id=parent_id,
                            return_raw=return_raw,
                        )
                    )
                if not targets:
                    job_to_run.append(
                        dict(
                            verb=key,
                            execute=value,
                            restrict=restrict,
                            ignore_cache=ignore_cache,
                            parent_id=parent_id,
                            return_raw=return_raw,
                        )
                    )

        return_data = list()
        for job in job_to_run:
            return_data.append(
                user_exec.send_data(data=user_exec.format_exec(**job))
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
        user_exec = user.User(args=self.args)
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
                        user_exec=user_exec,
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

        return_data = list()
        user_exec = user.User(args=self.args)
        if self.args.target:
            for target in set(self.args.target):
                data = user_exec.format_exec(
                    verb=self.args.verb,
                    execute=self.args.exec,
                    target=target,
                    return_raw=getattr(self.args, "poll", False),
                )
                return_data.append(user_exec.send_data(data=data))
        else:
            data = user_exec.format_exec(
                verb=self.args.verb,
                execute=self.args.exec,
                return_raw=getattr(self.args, "poll", False),
            )
            return_data.append(user_exec.send_data(data=data))
        return return_data

    def start_server(self):
        """Start the Server process."""

        server.Server(args=self.args).worker_run()

    def start_client(self):
        """Start the client process."""

        client.Client(args=self.args).worker_run()

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
                elif isinstance(value, (float)):
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
                            arranged_data.append(report_item.pop(0))
                            if report_item:
                                original_data.insert(0, (key, value))
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

    def bootstrap_run(self, job_def, catalog, quiet=False):
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
        :param quiet: Enable|Disable quiet mode.
        :type quiet: Boolean
        """

        print("Running bootstrap for {}".format(job_def["host"]))
        for job in self.bootstrap_flatten_jobs(jobs=job_def["jobs"]):
            key, value = next(iter(job.items()))
            if not quiet:
                print("Executing: {} {}".format(key, value))
            with utils.ParamikoConnect(
                host=job_def["host"],
                username=job_def["username"],
                port=job_def["port"],
                key_file=job_def.get("key_file"),
            ) as conn:
                ssh, session = conn
                if key == "RUN":
                    self.bootstrap_exec(
                        session=session, command=value, catalog=catalog
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

    def bootstrap_exec(self, session, command, catalog):
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
        session.exec_command(t_command.render(**catalog))
        if session.recv_exit_status() != 0:
            stderr = session.recv_stderr(4096)
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
                    job_def=job_def, catalog=catalog, quiet=True
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
            print("Loading server information")
            for s in self.bootstrap_catalog_entry(entry=directord_server):
                s["key_file"] = self.args.key_file
                self.bootstrap_run(job_def=s, catalog=catalog)

        directord_clients = catalog.get("directord_clients")
        if directord_clients:
            print("Loading client information")
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
