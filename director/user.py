import argparse
import glob
import json
import os

import director

from director import manager


class User(manager.Interface):
    """Director User interface class."""

    def __init__(self, args):
        """Initialize the User interface class.

        Sets up the user object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(User, self).__init__(args=args)

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

    def format_exec(
        self,
        verb,
        execute,
        target=None,
        ignore_cache=False,
        restrict=None,
        parent_id=None,
    ):
        """Return a JSON encode object for task execution.

        While formatting the message, the method will treat each verb as a
        case and parse the underlying sub-command, formatting the information
        into a dictionary.

        :param verb: Action to parse.
        :type verb: String
        :param execute: Execution string to parse.
        :type execute: String
        :param target: Target argent to send job to.
        :type target: String
        :param ignore_cache: Instruct the entire execution to
                             ignore client caching.
        :type ignore_cache: Boolean
        :param restrict: Restrict job execution based on a provided task SHA1.
        :type restrict: List
        :param parent_id: Set the parent UUID for execution jobs.
        :type parent_id: String
        :returns: String
        """

        args = None
        data = dict()
        parser = argparse.ArgumentParser(
            description="Process exec commands", allow_abbrev=False
        )
        parser.add_argument("--skip-cache", action="store_true")
        parser.add_argument("--run-once", action="store_true")
        self.log.debug("Executing - VERB:%s, EXEC:%s", verb, execute)
        if verb == "RUN":
            parser.add_argument(
                "--stdout-arg",
                help="Stores the stdout of a given command as a cached argument.",
            )
            args, command = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            if args.stdout_arg:
                data["stdout_arg"] = args.stdout_arg
            data["command"] = " ".join(command)
        elif verb in ["COPY", "ADD"]:
            parser.add_argument("--chown")
            parser.add_argument("--blueprint", action="store_true")
            args, file_path = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            if args.chown:
                chown = args.chown.split(":", 1)
                if len(chown) == 1:
                    chown.append(None)
                data["user"], data["group"] = chown
            file_from, data["to"] = file_path
            data["from"] = [
                os.path.abspath(os.path.expanduser(i))
                for i in glob.glob(file_from)
                if os.path.isfile(os.path.expanduser(i))
            ]
            if not data["from"]:
                raise AttributeError(
                    "The value of {} was not found.".format(file_from)
                )
            data["blueprint"] = args.blueprint
        elif verb == "FROM":
            raise NotImplementedError()
        elif verb in ["ARG", "ENV"]:
            parser.add_argument("args", nargs="+", action="append")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["args"] = dict([" ".join(args.args[0]).split(" ", 1)])
        elif verb == "LABEL":
            raise NotImplementedError()
        elif verb == "USER":
            raise NotImplementedError()
            parser.add_argument("user")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            user = args.user.split(":", 1)
            if len(user) == 1:
                user.append(None)
            data["user"], data["group"] = user
        elif verb == "EXPOSE":
            raise NotImplementedError()
            parser.add_argument("expose")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            expose = args.expose.split("/", 1)
            if len(expose) == 1:
                expose.append("tcp")
            data["port"], data["proto"] = expose
        elif verb == "WORKDIR":
            parser.add_argument("workdir")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["workdir"] = args.workdir
        elif verb == "CACHEFILE":
            parser.add_argument("cachefile")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["cachefile"] = args.cachefile
        else:
            raise SystemExit("No known verb defined.")

        if target:
            data["target"] = target

        if restrict:
            data["restrict"] = restrict

        if parent_id:
            data["parent_id"] = parent_id

        data["verb"] = verb

        if args:
            data["skip_cache"] = ignore_cache or args.skip_cache
            data["run_once"] = args.run_once
        else:
            if ignore_cache:
                data["skip_cache"] = True

        return json.dumps(data)

    def send_data(self, data):
        """Send data to the socket path.

        The send method takes serialized data and submits it to the given
        socket path.

        This method will return information provided by the server in
        String format.

        :returns: String
        """

        with director.UNIXSocketConnect(self.args.socket_path) as s:
            s.sendall(data.encode())
            return s.recv(1024000).decode()


class Manage(User):
    """Director Manage interface class."""

    def __init__(self, args):
        """Initialize the Manage interface class.

        Sets up the manage object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        super(User, self).__init__(args=args)

    def run(self):
        """Send the management command to the server.

        :returns: String
        """

        if self.args.list_jobs or self.args.job_info or self.args.export_jobs:
            manage = "list-jobs"
        elif self.args.list_nodes or self.args.export_nodes:
            manage = "list-nodes"
        elif self.args.purge_jobs:
            manage = "purge-jobs"
        elif self.args.purge_nodes:
            manage = "purge-nodes"
        else:
            raise SystemExit("No known management function was defined.")

        self.log.debug("Executing Management Command:%s", manage)
        return self.send_data(data=json.dumps(dict(manage=manage)))
