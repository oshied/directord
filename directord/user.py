import argparse
import glob
import json
import os
import shlex
import time

import zmq.auth as zmq_auth

import directord

from directord import manager


class User(manager.Interface):
    """Directord User interface class."""

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
        :param target: Target argent to send job to.
        :type target: String
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
            parser.add_argument(
                "--stdout-arg",
                help=(
                    "Stores the stdout of a given command as a cached"
                    " argument."
                ),
            )
            args, command = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            if args.stdout_arg:
                data["stdout_arg"] = args.stdout_arg
            data["command"] = " ".join(command)
        elif verb in ["COPY", "ADD"]:
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
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
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
        elif verb in ["ARG", "ENV"]:
            cache_type = "{}s".format(verb.lower())
            parser.add_argument(
                cache_type,
                nargs="+",
                action="append",
                help="Set a given argument. KEY VALUE",
            )
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            cache_obj = getattr(args, cache_type)
            data[cache_type] = dict([" ".join(cache_obj[0]).split(" ", 1)])
        elif verb == "WORKDIR":
            parser.add_argument("workdir", help="Create a directory.")
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["workdir"] = args.workdir
        elif verb == "CACHEFILE":
            parser.add_argument(
                "cachefile",
                help="Load a cached file and store it as an update to ARGs.",
            )
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["cachefile"] = args.cachefile
        elif verb == "CACHEEVICT":
            parser.add_argument(
                "cacheevict",
                help=(
                    "Evict all tagged cached items from a client machine."
                    " Typical tags are, but not limited to:"
                    " [args, envs, jobs, parents, query, ...]. To evict 'all'"
                    " cached items use the keyword 'all'."
                ),
            )
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["cacheevict"] = args.cacheevict
        elif verb == "QUERY":
            parser.add_argument(
                "query",
                help=(
                    "Scan the environment for a given cached argument and"
                    " store the resultant on the target. The resultant is"
                    " set in dictionary format: `{'client-id': ...}`"
                ),
            )
            args, _ = parser.parse_known_args(
                self.sanitized_args(execute=execute)
            )
            data["query"] = args.query
        else:
            raise SystemExit("No known verb defined.")

        if hasattr(args, "exec_help") and args.exec_help:
            return parser.print_help(1)
        else:
            if target:
                data["target"] = target

            if restrict:
                data["restrict"] = restrict

            if parent_id:
                data["parent_id"] = parent_id

            data["verb"] = verb
            data["timeout"] = args.timeout

            if args:
                data["skip_cache"] = ignore_cache or args.skip_cache
                data["run_once"] = args.run_once
            else:
                if ignore_cache:
                    data["skip_cache"] = True

            data["return_raw"] = return_raw

            return json.dumps(data)

    def send_data(self, data):
        """Send data to the socket path.

        The send method takes serialized data and submits it to the given
        socket path.

        This method will return information provided by the server in
        String format.

        :returns: String
        """

        with directord.UNIXSocketConnect(self.args.socket_path) as s:
            s.sendall(data.encode())
            fragments = []
            while True:
                chunk = s.recv(1024)
                if not chunk:
                    break
                else:
                    fragments.append(chunk)
            return b"".join(fragments)


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
            zmq_auth.create_certificates(keys_dir, item)

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

    def poll_job(self, job_id):
        """Given a job poll for its completion and return status.

        > The status return is (Boolean, String)

        :param job_id: UUID for job
        :type job_id: String
        :returns: Tuple
        """

        with self.timeout(
            time=getattr(self.args, "timeout", 240), job_id=job_id
        ):
            while True:
                data = dict(json.loads(self.run(override="list-jobs")))
                data_return = data.get(job_id)
                if data_return:
                    if data_return.get("SUCCESS"):
                        return True, "Job Success: {}".format(job_id)
                    elif data_return.get("FAILED"):
                        return False, "Job Failed: {}".format(job_id)
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
        else:
            raise SystemExit("No known management function was defined.")

        self.log.debug("Executing Management Command:%s", manage)
        return self.send_data(data=json.dumps(dict(manage=manage)))
