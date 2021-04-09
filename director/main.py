import argparse
import json
import os
import sys
import yaml

import tabulate

from director import client, mixin, utils
from director import server
from director import user
import director


def _args():
    """Setup client arguments."""

    parser = argparse.ArgumentParser(
        description="Deployment Framework Next.", prog="Director"
    )
    parser.add_argument(
        "--config-file",
        help="File path for client configuration. Default: %(default)s",
        metavar="STRING",
        default=os.getenv("DIRECTOR_CONFIG_FILE"),
        type=argparse.FileType(mode="r"),
    )
    parser.add_argument(
        "--shared-key",
        help="Shared key used for server client authentication.",
        metavar="STRING",
        default=os.getenv("DIRECTOR_SHARED_KEY"),
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
        default=int(os.getenv("DIRECTOR_MSG_PORT", 5555)),
        type=int,
    )
    parser.add_argument(
        "--transfer-port",
        help="Transfer port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_TRANSFER_PORT", 5556)),
        type=int,
    )
    parser.add_argument(
        "--heartbeat-port",
        help="heartbeat port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_HEARTBEAT_PORT", 5557)),
        type=int,
    )
    parser.add_argument(
        "--heartbeat-interval",
        help="heartbeat interval in seconds. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_HEARTBEAT_INTERVAL", 60)),
        type=int,
    )
    parser.add_argument(
        "--socket-path",
        help="Server file socket path for user interactions. Default: %(default)s",
        metavar="STRING",
        default=str(
            os.getenv("DIRECTOR_SOCKET_PATH", "/var/run/director.sock")
        ),
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
        help="Restrict orchestration to a set of Task SHA1(s).",
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
        "orchestrate_files",
        help="YAML files to use for orchestration.",
        metavar="STRING",
        nargs="+",
    )
    parser_exec = subparsers.add_parser("exec", help="Execution mode help")
    parser_exec.add_argument(
        "--verb",
        help="Module Invocation for exec. Choices: %(choices)s",
        metavar="STRING",
        choices=[
            "RUN",
            "COPY",
            "ADD",
            "FROM",
            "ARG",
            "ENV",
            "LABEL",
            "USER",
            "EXPOSE",
            "WORKDIR",
            "CACHEFILE",
        ],
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
    parser_server = subparsers.add_parser("server", help="Server mode help")
    parser_server.add_argument(
        "--bind-address",
        help="IP Address to bind a Director Server. Default: %(default)s",
        metavar="INT",
        default=os.getenv("DIRECTOR_BIND_ADDRESS", "*"),
    )
    parser_server.add_argument(
        "--etcd-server",
        help="Domain or IP address of the ETCD server. Default: %(default)s",
        metavar="STRING",
        default=os.getenv("DIRECTOR_ETCD_SERVER", "localhost"),
    )
    parser_server.add_argument(
        "--etcd-port",
        help="ETCD server bind port. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_ETCD_PORT", 2379)),
        type=int,
    )
    parser_client = subparsers.add_parser("client", help="Client mode help")
    parser_client.add_argument(
        "--server-address",
        help="Domain or IP address of the Director server. Default: %(default)s",
        metavar="STRING",
        default=os.getenv("DIRECTOR_SERVER_ADDRESS", "localhost"),
    )
    parser_manage = subparsers.add_parser(
        "manage", help="Server management mode help"
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
    args = parser.parse_args()
    # Check for configuration file and load it if found.
    if args.config_file:
        config_data = yaml.safe_load(args.config_file)
        for key, value in config_data.items():
            if isinstance(value, list) and key in args.__dict__:
                args.__dict__[key].extend(value)
            else:
                args.__dict__[key] = value

    return args


class SystemdInstall(object):
    """Simple system service unit creation class."""

    def __init__(self):
        """Class to create systemd service units.

        This class is used with the director-server-systemd and
        director-client-systemd entrypoints.
        """

        self.config_path = "/etc/director"

    def path_setup(self):
        """Create the configuration path and basic configuration file."""

        if not os.path.isdir(self.config_path):
            os.makedirs(self.config_path)
            print("[+] Created director configuration path")

        if not os.path.exists("/etc/director/config.yaml"):
            with open("/etc/director/config.yaml", "w") as f:
                f.write("---\nreplaceMe: true\n")
            print("[+] Created empty configuration file")

    def writer(self, service_file):
        """Write a given systemd service unit file.

        :param service_file: Name of the embedded service file to interact with.
        :type service_file: String
        """

        path = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.path_setup()
        base = os.path.dirname(director.__file__)
        service_file_path = "/etc/systemd/system/{}".format(service_file)
        if os.path.exists(service_file_path):
            print(
                "[-] Service file was not created because it already exists."
            )
            return
        with open(os.path.join(base, "static", service_file)) as f:
            with open(service_file_path, "w") as l:
                for line in f.readlines():
                    l.write(
                        line.replace(
                            "/usr/bin/director", os.path.join(path, "director")
                        )
                    )

        print("[+] Installed {} service unit file".format(service_file))
        print(
            "[?] Run `systemctl daemon-reload` for unit file to take effect."
        )

    def server(self):
        """Run the server systemd service unit file creation process."""

        self.writer(service_file="director-server.service")

    def client(self):
        """Run the client systemd service unit file creation process."""

        self.writer(service_file="director-client.service")


def _systemd_server():
    """Execute the systemd server unit file creation process."""

    _systemd = SystemdInstall()
    _systemd.server()


def _systemd_client():
    """Execute the systemd client unit file creation process."""

    _systemd = SystemdInstall()
    _systemd.client()


def main():
    """Execute the main application.

    * Server|Client operations run within the foreground of the application.

    * Exec will submit a job to be run across the cluster.

    * Manage jobs will return information about the cluster and all executed
      jobs. This data will be returned in table format for easy consumptions.
    """

    args = _args()
    _mixin = mixin.Mixin(args=args)

    if args.mode == "server":
        _mixin.start_server()
    elif args.mode == "client":
        _mixin.start_client()
    elif args.mode == "exec":
        return_data = _mixin.run_exec()
        for item in return_data:
            print(item)
    elif args.mode == "orchestrate":
        return_data = _mixin.run_orchestration()
        for item in return_data:
            print(item)
    elif args.mode == "manage":
        manage_exec = user.Manage(args=args)

        data = manage_exec.run()
        data = json.loads(data)
        if args.export_jobs or args.export_nodes:
            export_file = utils.dump_yaml(
                file_path=(args.export_jobs or args.export_nodes),
                data=dict(data),
            )
            print("Exported data to [ {} ]".format(export_file))
            return

        _mixin = mixin.Mixin(args=args)

        if data and isinstance(data, list):
            if args.job_info:
                headings = ["KEY", "VALUE"]

                item = dict(data).get(args.job_info)
                if not item:
                    return

                tabulated_data = _mixin.return_tabulated_info(data=item)
            else:
                headings = [
                    "ID",
                    "EXECUTION_TIME",
                    "SUCCESS",
                    "FAILED",
                    "EXPIRY",
                ]
                tabulated_data = _mixin.return_tabulated_data(
                    data=data, headings=headings
                )

            print(
                tabulate.tabulate(
                    [i for i in tabulated_data if i], headers=headings
                )
            )
            print("\nTotal Items: {}\n".format(len(tabulated_data)))
    else:
        raise AttributeError("Mode is set to an unsupported value.")
