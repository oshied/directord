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
import json
import os
import sys

import jinja2
from jinja2 import StrictUndefined

import yaml

import directord

from directord import bootstrap
from directord import client
from directord import meta
from directord import mixin
from directord import server
from directord import user
from directord import utils


def _args(exec_args=None):
    """Setup client arguments."""

    parser = argparse.ArgumentParser(
        description="Deployment Framework Next.",
        prog="Directord",
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=32, width=128
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=directord.__version__),
    )
    parser.add_argument(
        "--config-file",
        help="File path for client configuration. Default: %(default)s",
        metavar="STRING",
        default=os.getenv("DIRECTORD_CONFIG_FILE", None),
        type=argparse.FileType(mode="r"),
    )
    parser.add_argument(
        "--datastore",
        help=(
            "Connect to an external datastore for job and worker tracking. The"
            " connection string is RFC-1738 compatible >"
            " driver://username:password@host:port/database. If undefined the"
            " datastore uses an internal manager object. Driver"
            " supports ['redis', 'file']. When using Redis, two"
            " keyspaces will be used and are incremented by 1 using the"
            " database value (which has a default of 0). If the datastore"
            " option is set to 'memory', the server will spawn a manager"
            " thread to facilitate the document store."
        ),
        metavar="STRING",
        default=os.getenv(
            "DIRECTORD_DATASTORE", "file:///var/cache/directord"
        ),
        type=str,
    )
    parser.add_argument(
        "--driver",
        help="Messaging driver used for workload transport.",
        default=os.getenv("DIRECTORD_DRIVER", meta.__driver_default__),
        choices=meta.__driver_options__,
        type=str,
    )
    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        "--shared-key",
        help="Shared key used for server client authentication.",
        metavar="STRING",
        default=os.getenv("DIRECTORD_SHARED_KEY", None),
    )
    auth_group.add_argument(
        "--curve-encryption",
        action="store_true",
        help=(
            "Server and client will connect using Curve authentication"
            " and encryption. Enabling this option assumes keys have been"
            " generated. see `manage --generate-keys` for more."
        ),
    )
    parser.add_argument(
        "--debug",
        help="Enable debug mode. Default: %(default)s",
        action="store_true",
    )
    parser.add_argument(
        "--job-port",
        help="Job port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTORD_MSG_PORT", 5555)),
        type=int,
    )
    parser.add_argument(
        "--backend-port",
        help="Backend port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTORD_BACKEND_PORT", 5556)),
        type=int,
    )
    parser.add_argument(
        "--heartbeat-interval",
        help="heartbeat interval in seconds. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTORD_HEARTBEAT_INTERVAL", 60)),
        type=int,
    )
    parser.add_argument(
        "--socket-path",
        help=(
            "Server file socket path for user interactions."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=str(
            os.getenv("DIRECTORD_SOCKET_PATH", "/var/run/directord.sock")
        ),
        type=str,
    )
    parser.add_argument(
        "--socket-group",
        help=(
            "Server file socket group ownership for user interactions."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=str(os.getenv("DIRECTORD_SOCKET_GROUP", 0)),
    )
    parser.add_argument(
        "--cache-path",
        help=("Client cache path. Default: %(default)s"),
        metavar="STRING",
        default=str(os.getenv("DIRECTORD_CACHE_PATH", "/var/cache/directord")),
        type=str,
    )
    subparsers = parser.add_subparsers(
        help="Mode sub-command help", dest="mode"
    )
    parser_orchestrate = subparsers.add_parser(
        "orchestrate", help="Orchestration mode help"
    )
    parser_orchestrate.add_argument(
        "--restrict",
        help="Restrict orchestration to a set of Task SHA3_224(s).",
        metavar="STRING",
        nargs="+",
    )
    parser_orchestrate.add_argument(
        "--target",
        help="Worker target(s) to run a particular job against.",
        metavar="STRING",
        nargs="+",
    )
    parser_orchestrate.add_argument(
        "--ignore-cache",
        help=(
            "Instruct the orchestration engine to ignore all"
            " cache for the entirety of the run."
        ),
        action="store_true",
    )
    parser_orchestrate.add_argument(
        "--force-async",
        help=(
            "Instruct the orchestration engine to run all orchestrations"
            " asynchronously."
        ),
        action="store_true",
    )
    orchestrate_group = parser_orchestrate.add_mutually_exclusive_group(
        required=False
    )
    orchestrate_group.add_argument(
        "--poll",
        help="Block on client return for the completion of executed jobs.",
        action="store_true",
    )
    orchestrate_group.add_argument(
        "--wait",
        help=(
            "Simplified Block on client return for the completion of"
            " executed jobs."
        ),
        action="store_true",
    )
    orchestrate_group.add_argument(
        "--finger-print",
        help="Finger print a set of orchestrations.",
        action="store_true",
    )
    orchestrate_group.add_argument(
        "--stream",
        help="Stream the STDOUT|STDERR for tasks.",
        action="store_true",
    )
    parser_orchestrate.add_argument(
        "--check",
        help=(
            "When polling is enabled this option can be used to check the"
            " outcome of a given task. If the task fails the client will"
            " fail too."
        ),
        action="store_true",
    )
    parser_orchestrate.add_argument(
        "orchestrate_files",
        help="YAML files to use for orchestration.",
        metavar="STRING",
        nargs="+",
    )
    parser_exec = subparsers.add_parser("exec", help="Execution mode help")
    parser_exec.add_argument(
        "--verb",
        help="Module Invocation for exec.",
        metavar="STRING",
        required=True,
    )
    parser_exec.add_argument(
        "--target",
        help="Worker target(s) to run a particular job against.",
        metavar="[STRING]",
        nargs="+",
    )
    parser_exec.add_argument(
        "exec",
        help="Freeform command. Use quotes for complex commands.",
        metavar="STRING",
        nargs="+",
    )
    parser_group = parser_exec.add_mutually_exclusive_group(required=False)
    parser_group.add_argument(
        "--poll",
        help="Block on client return for the completion of executed jobs.",
        action="store_true",
    )
    parser_group.add_argument(
        "--wait",
        help=(
            "Simplified Block on client return for the completion of"
            " executed jobs."
        ),
        action="store_true",
    )
    parser_group.add_argument(
        "--stream",
        help="Stream the STDOUT|STDERR for tasks.",
        action="store_true",
    )
    parser_exec.add_argument(
        "--check",
        help=(
            "When polling is enabled this option can be used to check the"
            " outcome of a given task. If the task fails the client will"
            " fail too."
        ),
        action="store_true",
    )
    parser_exec.add_argument(
        "--force-async",
        help=("Instruct the execution engine to run asynchronously."),
        action="store_true",
    )
    parser_server = subparsers.add_parser("server", help="Server mode help")
    parser_server.add_argument(
        "--bind-address",
        help="IP Address to bind a Directord Server. Default: %(default)s",
        metavar="STRING",
        default=os.getenv("DIRECTORD_BIND_ADDRESS", "*"),
    )
    parser_server.add_argument(
        "--run-ui",
        help="Enable the Directord UI. Default: %(default)s",
        action="store_true",
    )
    parser_server.add_argument(
        "--ui-port",
        help="UI server bind port. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTORD_UI_PORT", 9000)),
        type=int,
    )
    parser_client = subparsers.add_parser("client", help="Client mode help")
    parser_client.add_argument(
        "--server-address",
        help=(
            "Domain or IP address of the Directord server."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_SERVER_ADDRESS", "127.0.0.1"),
    )
    parser_manage = subparsers.add_parser(
        "manage", help="Server management mode help"
    )
    filter_group = parser_manage.add_mutually_exclusive_group(required=False)
    filter_group.add_argument(
        "--filter",
        choices=["success", "failed", "processing"],
        help="List filtered jobs.",
    )
    manage_group = parser_manage.add_mutually_exclusive_group(required=True)
    manage_group.add_argument(
        "--list-jobs", action="store_true", help="List all known jobs."
    )
    manage_group.add_argument(
        "--list-nodes", action="store_true", help="List all available nodes."
    )
    manage_group.add_argument(
        "--purge-jobs",
        action="store_true",
        help="Purge all jobs from the server.",
    )
    manage_group.add_argument(
        "--purge-nodes",
        action="store_true",
        help="Purge all nodes from the server.",
    )
    manage_group.add_argument(
        "--job-info",
        help="Pull information on a specific job ID.",
        metavar="STRING",
    )
    manage_group.add_argument(
        "--export-jobs",
        help="Exports all job records as YAML and dumps them to a file.",
        metavar="STRING",
    )
    manage_group.add_argument(
        "--export-nodes",
        help="Exports all node records as YAML and dumps them to a file.",
        metavar="STRING",
    )
    manage_group.add_argument(
        "--generate-keys",
        action="store_true",
        help="Generate encryption keys for Curve authentication.",
    )
    manage_group.add_argument(
        "--dump-cache",
        action="store_true",
        help="Dump the local cache to stdout.",
    )
    manage_group.add_argument(
        "--analyze-parent",
        help="Analyze a given parent ID.",
        metavar="STRING",
    )
    manage_group.add_argument(
        "--analyze-job",
        help="Analyze a given job ID.",
        metavar="STRING",
    )
    parser_bootstrap = subparsers.add_parser(
        "bootstrap",
        help=(
            "Bootstrap a directord cluster. This uses SSH to connect to remote"
            " machines and setup Directord. Once Directord is setup, SSH is no"
            " longer required."
        ),
    )
    parser_bootstrap.add_argument(
        "--catalog",
        help="File path for SSH catalog.",
        metavar="STRING",
        action="append",
        required=True,
        type=argparse.FileType(mode="r"),
    )
    parser_bootstrap.add_argument(
        "--key-file",
        help=(
            "SSH Key file to use when connecting to targets."
            " Default: %(default)s"
        ),
        metavar="STRING",
        default=os.getenv("DIRECTORD_BOOTSTRAP_SSH_KEY_FILE"),
    )
    parser_bootstrap.add_argument(
        "--threads",
        help="Client bootstrap threads. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTORD_BOOTSTRAP_THREADS", 10)),
        type=int,
    )
    if exec_args:
        args = parser.parse_args(args=exec_args)
    else:
        args = parser.parse_args()
    # Check for configuration file and load it if found.
    if args.config_file:
        config_data = yaml.safe_load(args.config_file)
        if config_data:
            for key, value in config_data.items():
                if isinstance(value, list) and key in args.__dict__:
                    args.__dict__[key].extend(value)
                else:
                    args.__dict__[key] = value

    return args, parser


class SystemdInstall:
    """Simple system service unit creation class."""

    def __init__(self, group="root", force=False):
        """Class to create systemd service units.

        This class is used with the directord-server-systemd and
        directord-client-systemd entrypoints.

        :param group: Name of the group used within the systemd service units.
        :type group: String
        :param force: Force install systemd service units.
        :type force: Boolean
        """

        self.config_path = "/etc/directord"
        self.socket_group = group
        self.force = force

    def path_setup(self):
        """Create the configuration path and basic configuration file."""

        os.makedirs(self.config_path, exist_ok=True)
        if not os.path.exists("/etc/directord/config.yaml"):
            with open("/etc/directord/config.yaml", "w") as f:
                f.write("---\ndebug: false\n")
            print("[+] Created empty configuration file")

    def writer(self, service_file):
        """Write a given systemd service unit file.

        :param service_file: Name of the embedded service file to
                             interact with.
        :type service_file: String
        """

        path = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.path_setup()
        base = os.path.dirname(directord.__file__)
        service_file_path = "/etc/systemd/system/{}".format(service_file)
        if os.path.exists(service_file_path) and not self.force:
            print(
                "[-] Service file was not created because it already exists."
            )
            return

        blueprintLoader = jinja2.FileSystemLoader(
            searchpath=os.path.join(base, "templates")
        )
        blueprintEnv = jinja2.Environment(
            loader=blueprintLoader,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        blueprint = blueprintEnv.get_template("{}.j2".format(service_file))
        blueprint_args = {
            "directord_binary": os.path.join(path, "directord"),
            "directord_group": self.socket_group,
        }
        outputText = blueprint.render(**blueprint_args)
        with open(service_file_path, "w") as f:
            f.write(outputText)

        print("[+] Installed {} service unit file".format(service_file))
        print(
            "[?] Run `systemctl daemon-reload` for unit file to take effect."
        )

    def server(self):
        """Run the server systemd service unit file creation process."""

        self.writer(service_file="directord-server.service")

    def client(self):
        """Run the client systemd service unit file creation process."""

        self.writer(service_file="directord-client.service")


def _systemd_loader():
    parser = argparse.ArgumentParser(
        description="Systemd install args.",
        prog="Directord-service",
        formatter_class=lambda prog: argparse.HelpFormatter(
            prog, max_help_position=32, width=128
        ),
    )
    parser.add_argument(
        "--group",
        help="Server group. Default: %(default)s.",
        metavar="STRING",
        default="root",
        type=str,
    )
    parser.add_argument(
        "--force",
        help="Force install systemd service unit file.",
        action="store_true",
    )
    args = parser.parse_args()
    return SystemdInstall(group=args.group, force=args.force)


def _systemd_server():
    """Execute the systemd server unit file creation process."""

    _systemd = _systemd_loader()
    _systemd.server()


def _systemd_client():
    """Execute the systemd client unit file creation process."""

    _systemd = _systemd_loader()
    _systemd.client()


def main():
    """Execute the main application.

    * Server|Client operations run within the foreground of the application.

    * Exec will submit a job to be run across the cluster.

    * Manage jobs will return information about the cluster and all executed
      jobs. This data will be returned in table format for easy consumptions.
    """

    args, parser = _args()
    _mixin = mixin.Mixin(args=args)

    if args.mode == "server":
        server.Server(args=args).worker_run()
    elif args.mode == "client":
        client.Client(args=args).worker_run()
    elif args.mode in ["exec", "orchestrate"]:
        if args.mode == "exec":
            return_data = _mixin.run_exec()
        else:
            return_data = _mixin.run_orchestration()

        job_items = [i.decode() for i in return_data if i]

        if args.poll or args.stream or args.wait:
            failed = set()
            manage = user.Manage(args=args)
            run_indicator = args.wait and not args.debug
            with directord.Spinner(run=run_indicator) as indicator:
                for item in job_items:
                    state, status, stdout, stderr, info = manage.poll_job(
                        job_id=item
                    )

                    if state is False:
                        failed.add(item)

                    if args.stream:
                        for node in sorted(
                            set(
                                i
                                for v in [stdout, stderr, info]
                                for i in v.keys()
                            )
                        ):
                            for k, n, v in [
                                (node, name, d[node])
                                for name, d in [
                                    ("STDOUT", stdout),
                                    ("STDERR", stderr),
                                ]
                                if node in d
                            ]:
                                print("{} -- {}\n{}".format(k, n, v))

                    if run_indicator:
                        indicator.pipe_b.send(status)
                    else:
                        print(status)

            if any(failed):
                if args.check:
                    print("FAILED JOBS")
                    for item in failed:
                        print(item)

                raise SystemExit(1)
        else:
            for item in job_items:
                print(item)

    elif args.mode == "manage":
        manage_exec = user.Manage(args=args)
        data = manage_exec.run()
        if args.generate_keys:
            print(
                "Keys generated. Synchronize the server and client public"
                " keys to client nodes to enable Curve encryption."
            )
            return

        try:
            data = json.loads(data)
        except Exception as e:
            print("No valid data found: {}".format(str(e)))
            return
        else:
            if not data:
                raise SystemExit("No data found")

        if args.export_jobs or args.export_nodes:
            export_file = utils.dump_yaml(
                file_path=(args.export_jobs or args.export_nodes),
                data=dict(data),
            )
            print("Exported data to [ {} ]".format(export_file))
            return

        computed_values = dict()
        headings = ["KEY", "VALUE"]
        tabulated_data = None
        if data and isinstance(data, dict):
            tabulated_data = _mixin.return_tabulated_info(data=data)
        elif data and isinstance(data, list):
            if args.job_info:
                item = dict(data).get(args.job_info)
                if not item:
                    print(
                        "Job information for ID:{} was not found".format(
                            args.job_info
                        )
                    )
                    return

                tabulated_data = _mixin.return_tabulated_info(data=item)
            else:
                if args.list_jobs:
                    restrict_headings = [
                        "PARENT_JOB_ID",
                        "VERB",
                        "EXECUTION_TIME",
                        "PROCESSING",
                        "SUCCESS",
                        "FAILED",
                    ]
                else:
                    restrict_headings = [
                        "EXPIRY",
                        "VERSION",
                        "HOST_UPTIME",
                        "AGENT_UPTIME",
                        "MACHINE_ID",
                    ]
                (
                    tabulated_data,
                    headings,
                    computed_values,
                ) = _mixin.return_tabulated_data(
                    data=data, restrict_headings=restrict_headings
                )

        if tabulated_data:
            utils.print_tabulated_data(
                data=[i for i in tabulated_data if i], headers=headings
            )
            print("\nTotal Items: {}".format(len(tabulated_data)))
            for k, v in computed_values.items():
                if isinstance(v, float):
                    print("Total {}: {:.2f}".format(k, v))
                else:
                    print("Total {}: {}".format(k, v))
            else:
                return
    elif args.mode == "bootstrap":
        _bootstrap = bootstrap.Bootstrap(args=args)
        _bootstrap.bootstrap_cluster()
    else:
        parser.print_help(sys.stderr)
        raise SystemExit("Mode is set to an unsupported value.")
