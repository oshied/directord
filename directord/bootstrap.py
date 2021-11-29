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

import getpass
import os
import sys

import jinja2
from jinja2 import StrictUndefined

import yaml

import directord

from directord import logger
from directord import utils


class PrintError:
    def __init__(self):
        self.line_break = "="
        self.line_multiplier = 20
        self.start = "Start Error Information"
        self.start_length = len(self.start)

    def __enter__(self):
        line = self.line_break * self.line_multiplier
        print("{line} {start} {line}".format(line=line, start=self.start))

    def __exit__(self, *args, **kwargs):
        end = "End Error Information"
        line_delta = self.start_length - len(end)
        line = self.line_break * (self.line_multiplier + line_delta // 2)
        print("{line} {end} {line}".format(line=line, end=end))


class Bootstrap(directord.Processor):
    """Mixin class."""

    def __init__(self, args):
        """Initialize the Directord mixin.

        Sets up the mixin object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(Bootstrap, self).__init__()
        self.args = args
        self.blueprint = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        self.log = logger.getLogger(
            name="directord", debug_logging=getattr(args, "debug", False)
        )
        self.indicator = None
        self.return_queue = self.get_queue()

    @staticmethod
    def bootstrap_catalog_entry(entry, required_entries=None):
        """Return a flattened list of bootstrap job entries.

        :param entry: Catalog entry for bootstraping.
        :type entry: Dictionary
        :param required_entries: List of required items
        :type required_entries: List
        :returns: List
        """

        if not required_entries:
            required_entries = ["jobs", "targets"]

        ordered_entries = list()
        for item in required_entries:
            if item not in entry:
                raise SystemExit(
                    "The bootstrap catalog is missing a"
                    " required component: {}".format(item)
                )

        args = entry.get("args", dict(port=22, username=getpass.getuser()))
        for target in entry["targets"]:
            try:
                target_host = target["host"]
            except KeyError:
                raise SystemExit("[host] is undefined in bootstrap catalog")
            if "jobs" in entry:
                item = dict(
                    host=target_host,
                    username=target.get(
                        "username", args.get("username", getpass.getuser())
                    ),
                    port=target.get("port", args.get("port", 22)),
                    jobs=entry["jobs"],
                )
                name = target.get("name")
                if name:
                    item["name"] = name
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

    @staticmethod
    def _read_chunks(fh, chunk_size=131072):
        """Read file in 2048 chunks."""

        while True:
            data = fh.read(chunk_size)
            if not data:
                break
            yield data

    def bootstrap_file_send(self, ssh, localfile, remotefile):
        """Run a remote put command.

        :param ssh: SSH connection object.
        :type ssh: Object
        :param localfile: Local file to transfer.
        :type localfile: String
        :param remotefile: Remote file destination.
        :type remotefile: String
        """

        if "sftp" in ssh.channels:
            chan = ssh.channels["sftp"]
        else:
            chan = ssh.channels["sftp"] = ssh.session.sftp_new()
        if isinstance(chan, int):
            with PrintError():
                self.log.critical(
                    "Failed to connect for file transfer ADD. Error Code"
                    " [ %s ]",
                    chan,
                )
                raise SystemExit(chan)

        chan.init()
        self.log.debug(
            "channel: %s, local file: %s, remote file: %s",
            chan,
            localfile,
            remotefile,
        )
        fileinfo = os.stat(localfile)
        try:
            try:
                chan.unlink(remotefile)
            except Exception as e:
                self.log.debug("file unlink error %s", str(e))

            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            with open(localfile, "rb") as local_f:
                for data in self._read_chunks(fh=local_f, chunk_size=131072):
                    with chan.open(
                        remotefile, flags, fileinfo.st_mode
                    ) as remote_f:
                        remote_f.write(data)
        except Exception as e:
            with PrintError():
                self.log.critical(str(e))
                raise SystemExit("File [ {} ] ADD failed.".format(remotefile))
        else:
            self.log.debug(
                "HOST: [ %s ] SUCCESS: ADD [ %s ] TO [ %s ]",
                ssh.host,
                localfile,
                remotefile,
            )

    def bootstrap_file_get(self, ssh, localfile, remotefile):
        """Run a remote get command.

        :param ssh: SSH connection object.
        :type ssh: Object
        :param localfile: Local file destination.
        :type localfile: String
        :param remotefile: Remote file to transfer.
        :type remotefile: String
        """

        if "sftp" in ssh.channels:
            chan = ssh.channels["sftp"]
        else:
            chan = ssh.channels["sftp"] = ssh.session.sftp_new()
        if isinstance(chan, int):
            with PrintError():
                self.log.critical(
                    "Failed to connect for file transfer GET. Error Code"
                    " [ %s ]",
                    chan,
                )
                raise SystemExit(chan)

        chan.init()
        self.log.debug(
            "channel: %s, local file: %s, remote file: %s",
            chan,
            localfile,
            remotefile,
        )
        try:
            with chan.open(remotefile, os.O_RDONLY, 0) as remote_f:
                with open(localfile, "wb") as f:
                    for _, data in remote_f:
                        f.write(data)
        except Exception as e:
            with PrintError():
                self.log.critical(str(e))
                raise SystemExit("File [ {} ] GET failed.".format(remotefile))
        else:
            self.log.debug(
                "HOST: [ %s ] SUCCESS: GET [ %s ] TO [ %s ]",
                ssh.host,
                remotefile,
                localfile,
            )

    def _blueprinter(self, string, catalog):
        """Return a blueprinted string.

        :param string: Plain-text execution string.
        :type string: String
        :param catalog: The job catalog definition.
        :type catalog: Dictionary
        :returns: String
        """

        return self.blueprint.from_string(string).render(**catalog)

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

        chan = ssh.session.channel_new()
        if isinstance(chan, int):
            self.log.critical(
                "Failed to connect for remote execution."
                " SSH Error Code [ %s ]",
                chan,
            )
            raise SystemExit(chan)

        try:
            chan.open_session()
            if chan.request_pty() == 0:
                self.log.debug("using PTY")
            command = self._blueprinter(string=command, catalog=catalog)
            self.log.debug(
                "channel: %s, command: %s",
                chan,
                command,
            )
            chan.request_exec(command)
            size, data = chan.read()
            while size > 0:
                size, _data = chan.read()
                data += _data
            try:
                data = data.decode()
            except AttributeError:
                pass

            if chan.get_exit_status() != 0:
                self.log.warning(
                    "\nHOST: [ %s ] FAILURE: [ %s ]", ssh.host, command
                )
                with PrintError():
                    self.log.critical(data)
                    raise SystemExit(
                        "Bootstrap command failed: {}".format(command)
                    )
            else:
                self.log.debug(
                    "HOST: [ %s ] SUCCESS: [ %s ]", ssh.host, command
                )
        finally:
            if hasattr(chan, "close"):
                chan.close()

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

        if self.indicator:
            msg = self.indicator.indicator_msg(
                msg="Connecting to {}".format(job_def["host"])
            )
            if msg:
                self.log.info(msg)
        else:
            self.log.info("Connecting to %s", job_def["host"])

        try:
            with utils.SSHConnect(
                host=job_def["host"],
                username=job_def["username"],
                port=job_def["port"],
                key_file=job_def.get("key_file"),
                debug=getattr(self.args, "debug", False),
            ) as ssh:
                for job in self.bootstrap_flatten_jobs(jobs=job_def["jobs"]):
                    key, value = next(iter(job.items()))
                    self.log.debug("Executing: %s %s", key, value)
                    if self.indicator:
                        msg = self.indicator.indicator_msg(
                            msg="Executing {} to {}".format(
                                key, job_def["host"]
                            )
                        )
                        if msg:
                            self.log.info(msg)
                    else:
                        self.log.info("Connecting to [ %s ]", job_def["host"])
                    if key == "RUN":
                        self.bootstrap_exec(
                            ssh=ssh, command=value, catalog=catalog
                        )
                    elif key == "ADD":
                        value = self._blueprinter(
                            string=value, catalog=catalog
                        )
                        localfile, remotefile = value.split(" ", 1)
                        localfile = self.bootstrap_localfile_padding(localfile)
                        self.bootstrap_file_send(
                            ssh=ssh,
                            localfile=localfile,
                            remotefile=remotefile,
                        )
                    elif key == "GET":
                        value = self._blueprinter(
                            string=value, catalog=catalog
                        )
                        remotefile, localfile = value.split(" ", 1)
                        self.bootstrap_file_get(
                            ssh=ssh,
                            localfile=localfile,
                            remotefile=remotefile,
                        )
        except OSError as e:
            print(
                "\nFailed to connect to [ {} ]: {}\n".format(
                    job_def["host"], str(e)
                )
            )

        self.return_queue.put(job_def["host"])

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
                catalog["directord_bootstrap"] = job_def
                self.bootstrap_run(
                    job_def=job_def,
                    catalog=catalog,
                )

    def bootstrap_cluster(self, run_indicator=None):
        """Run a cluster wide bootstrap using a catalog file.

        Cluster bootstrap requires a catalog file to run. Catalogs are broken
        up into two sections, `directord_server` and `directord_client`. All
        servers are processed serially and first. All clients are processing
        in parallel using a maximum of the threads argument.

        :param run_indicator: Enable | disable the run indicator
        :type run_indicator: Boolean
        :returns: Tuple
        """

        q = self.get_queue()
        catalog = dict()
        if not self.args.catalog:
            raise SystemExit("No catalog was defined.")

        for c in self.args.catalog:
            utils.merge_dict(base=catalog, new=yaml.safe_load(c))

        if run_indicator is None:
            run_indicator = not getattr(self.args, "debug", False)

        with directord.Spinner(run=run_indicator, queue=q) as indicator:
            self.indicator = indicator
            directord_server = catalog.get("directord_server")
            if directord_server:
                self.log.debug("Loading server information")
                for s in self.bootstrap_catalog_entry(
                    entry=directord_server, required_entries=["targets"]
                ):
                    s["key_file"] = self.args.key_file
                    catalog["directord_bootstrap"] = s
                    self.bootstrap_run(job_def=s, catalog=catalog)

            directord_clients = catalog.get("directord_clients")
            if directord_clients:
                self.log.debug("Loading client information")
                for c in self.bootstrap_catalog_entry(entry=directord_clients):
                    c["key_file"] = self.args.key_file
                    q.put(c)

            threads = list()
            for _ in range(self.args.threads):
                threads.append(
                    (
                        self.thread(
                            target=self.bootstrap_q_processor,
                            args=(q, catalog),
                        ),
                        True,
                    )
                )
            else:
                self.run_threads(threads=threads)

        targets = set()
        while not self.return_queue.empty():
            try:
                targets.add(self.return_queue.get_nowait())
            except Exception:
                pass

        return tuple(sorted(targets))
