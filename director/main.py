import argparse
import json
import os
import yaml

import tabulate

from director import client
from director import server
from director import user


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
        "--job-port",
        help="Job port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_MSG_PORT", 5555)),
        type=int,
    )
    parser.add_argument(
        "--status-port",
        help="status port to bind. Default: %(default)s",
        metavar="INT",
        default=int(os.getenv("DIRECTOR_STATUS_PORT", 5556)),
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
        ],
        required=True,
    )
    parser_exec.add_argument(
        "--target",
        help="Worker target to run a particular job against.",
        metavar="STRING",
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
    manage_group.add_argument("--list-jobs", action="store_true")
    manage_group.add_argument("--list-nodes", action="store_true")
    manage_group.add_argument("--purge-jobs", action="store_true")
    manage_group.add_argument("--purge-nodes", action="store_true")
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


def main():
    """Execute the main application.

    * Server|Client operations run within the foreground of the application.

    * Exec will submit a job to be run across the cluster.

    * Manage jobs will return information about the cluster and all executed
      jobs. This data will be returned in table format for easy consumptions.
    """

    args = _args()
    if args.mode == "server":
        server.Server(args=args).worker_run()
    elif args.mode == "client":
        client.Client(args=args).worker_run()
    elif args.mode == "exec":
        user_exec = user.User(args=args)
        data = user_exec.format_exec()
        return_data = user_exec.send_data(data=data)
        print(return_data)
    elif args.mode == "manage":
        manage_exec = user.Manage(args=args)
        tabulated_data = list()
        data = manage_exec.run()
        data = json.loads(data)
        if data and isinstance(data, list):
            headings = ["ID"]
            raw_data = list()
            for key, value in data:
                value["ID"] = key
                raw_data.append(value)
                for item in value.keys():
                    if not item.startswith('_'):
                        if item not in headings:
                            headings.append(item)

            while raw_data:
                item = raw_data.pop(0)
                arranged_data = list()
                for heading in headings:
                    i = item.get(heading, "N/A")
                    if isinstance(i, list):
                        list_item = i.pop(0)
                        arranged_data.append(list_item)
                        new_item = item.copy()
                        if i:
                            new_item[heading] = i
                            raw_data.insert(0, new_item)
                    elif isinstance(i, float):
                        arranged_data.append("{:.2f}".format(i))
                    else:
                        arranged_data.append(i)
                tabulated_data.append(arranged_data)

            print(tabulate.tabulate([i for i in tabulated_data if i], headers=headings))
    else:
        raise AttributeError("Mode is set to an unsupported value.")
