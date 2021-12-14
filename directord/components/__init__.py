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
import os
import subprocess
import time

import jinja2
from jinja2 import StrictUndefined

import yaml

from directord import logger
from directord import utils


class ComponentBase:
    """Component base class."""

    command = None
    info = None
    driver = None
    verb = None
    block_on_tasks = None
    queue_sentinel = False

    def __init__(self, desc=None):
        """Initialize the component base class.

        When setting up a component, the init should be inheritted allowing
        user defined components to have access to the full suite of defaults.

        > Set the `self.cacheable` object True|False according to how the
          component should be treated in terms of on system cache.
        """

        self.desc = desc
        self.log = logger.getLogger(name="directord")
        self.blueprint = jinja2.Environment(
            loader=jinja2.BaseLoader(),
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        self.known_args = None
        self.unknown_args = None
        self.cacheable = True  # Enables|Disables component caching
        self.requires_lock = False  # Enables|Disables component locking

    @staticmethod
    def run_command(
        command,
        shell=True,
        env=None,
        execute="/bin/sh",
        return_codes=None,
        no_block=False,
    ):
        """Run a shell command.

        The options available:

        * `shell` to be enabled or disabled, which provides the ability
        to execute arbitrary stings or not. if disabled commands must be
        in the format of a `list`

        * `env` is an environment override and or manipulation setting
        which sets environment variables within the locally executed
        shell.

        * `execute` changes the interpreter which is executing the
        command(s).

        * `return_codes` defines the return code that the command must
        have in order to ensure success. This can be a list of return
        codes if multiple return codes are acceptable.

        :param command: String
        :param shell: Boolean
        :param env: Dictionary
        :param execute: String
        :param return_codes: Integer|List
        :param no_block: Boolean
        :returns: Tuple
        """

        if env:
            _env = dict(os.environ)
            _env.update(env)
            env = _env
        else:
            env = os.environ

        stdout = subprocess.PIPE

        if return_codes is None:
            return_codes = [0]
        if isinstance(return_codes, int):
            return_codes = [return_codes]

        stderr = subprocess.PIPE
        process = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=stderr,
            executable=execute,
            env=env,
            shell=shell,
            start_new_session=no_block,
        )
        if no_block:
            return None, None, True

        output, error = process.communicate()
        if process.returncode not in return_codes:
            return output, error, False

        return output, error, True

    def options_converter(self, documentation):
        """Convert an options YAML to Arguments.

        :param documentation: YAML content.
        :type documentation: String
        """

        argument_spec = yaml.safe_load(documentation)["options"]
        for key, value in argument_spec.items():
            options = dict()
            description = value.pop("description", None)
            if description:
                if isinstance(description, list):
                    description = " ".join(description)
                options["help"] = description

            default = value.pop("default", None)
            if default:
                options["default"] = default

            required = value.pop("required", None)
            if isinstance(required, bool):
                options["required"] = required
            elif isinstance(required, str) and required.lower() in [
                "yes",
                "true",
            ]:
                options["required"] = True

            arg_type = value.pop("type", None)
            if isinstance(arg_type, str):
                arg_type = arg_type.lower()
                if arg_type == "bool":
                    options["action"] = "store_true"
                elif arg_type == "list":
                    options["type"] = list
                elif arg_type == "dict":
                    options["type"] = dict
                elif arg_type == "int":
                    options["type"] = int
                elif arg_type == "str":
                    options["type"] = str

            choices = value.pop("choices", None)
            if choices:
                options["choices"] = choices

            self.parser.add_argument(
                "--{}".format(key.replace("_", "-")), **options
            )

    @staticmethod
    def sanitized_args(execute):
        """Return arguments in a flattened array.

        This will inspect the execution arguments and return everything found
        as a flattened array.

        :param execute: Execution string to parse.
        :type execute: String
        :returns: List
        """

        if execute:
            return [i for g in execute if g for i in g.split()]
        else:
            return list()

    def exec_parser(self, parser, exec_array, arg_vars=None):
        """Run the parser and return parsed arguments.

        :param parser: Argument parser.
        :type parser: Object
        :param exec_array: Input array from action
        :type exec_array: List
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Tuple
        """

        self.known_args, self.unknown_args = parser.parse_known_args(
            self.sanitized_args(execute=exec_array)
        )
        if hasattr(self.known_args, "exec_help") and self.known_args.exec_help:
            raise SystemExit(parser.print_help())
        else:
            if arg_vars:
                for key, value in arg_vars.items():
                    self.known_args.__dict__[key] = value
            return self.known_args, self.unknown_args

    def args(self):
        """Set default arguments for a component."""

        self.parser = argparse.ArgumentParser(
            description=self.desc,
            allow_abbrev=False,
            add_help=False,
        )
        self.parser.add_argument(
            "--exec-help",
            action="help",
            help="Show this execution help message.",
        )
        self.parser.add_argument(
            "--skip-cache",
            action="store_true",
            help="For a task to skip the on client cache.",
        )
        self.parser.add_argument(
            "--run-once",
            action="store_true",
            help="Force a given task to run once.",
        )
        self.parser.add_argument(
            "--timeout",
            default=600,
            type=int,
            help="Set the action timeout. Default %(default)s.",
        )
        self.parser.add_argument(
            "--force-lock",
            action="store_true",
            help="Force a given task to run with a lock.",
        )
        self.parser.add_argument(
            "--stdout-arg",
            help="Stores the stdout of a given command as a cached argument.",
        )
        self.parser.add_argument(
            "--stderr-arg",
            help="Stores the stderr of a given command as a cached argument.",
        )

    @staticmethod
    def set_cache(
        cache,
        key,
        value,
        value_update=False,
        extend=False,
    ):
        """Set a cached item.

        :param cache: Cached access object.
        :type cache: Object
        :param key: Key for the cached item.
        :type key: String
        :param value: Value for the cached item.
        :type value: ANY
        :param value_update: Instructs the method to update a Dictionary with
                             another dictionary.
        :type value_update: Boolean
        :param extend: Enable|Disable Extend a map
        :type extend: Boolean
        :returns" Boolean
        """

        if value_update:
            orig = cache.get(key, default=dict())
            value = utils.merge_dict(orig, value, extend=extend)

        cache_set = cache.setdefault(key, value)
        if not cache_set:
            return cache.setdefault(key, value)
        return cache_set

    def file_blueprinter(self, cache, file_to):
        """Read a file and blueprint its contents.

        :param cache: Cached access object.
        :type cache: Object
        :param file_to: String path to a file which will blueprint.
        :type file_to: String
        :returns: Boolean
        """

        try:
            with open(file_to) as f:
                success, contents = self.blueprinter(
                    content=f.read(), values=cache.get("args")
                )

            if not success:
                return False, contents

            with open(file_to, "w") as f:
                f.write(contents)
        except Exception as e:
            error = str(e)
            self.log.critical("File blueprint failure: %s", error)
            return False, error
        else:
            self.log.info("File %s has been blueprinted.", file_to)
            return True, None

    def blueprinter(self, content, values, allow_empty_values=False):
        """Return blue printed content.

        :param content: A string item that will be interpreted and blueprinted.
        :type content: String
        :param values: Dictionary items that will be used to render a
                       blueprinted item.
        :type values: Dictionary
        :param allow_empty_values: Enable|Disable null values
        :type allow_empty_values: Boolean
        :returns: Tuple
        """

        if not values:
            if allow_empty_values:
                values = dict()
            else:
                return False, "No arguments were defined for blueprinting"

        try:
            _contents = self.blueprint.from_string(content)
            rendered_content = _contents.render(**values)
        except Exception as e:
            error = str(e)
            self.log.debug("blueprint error: %s, values: %s", error, values)
            return False, error
        else:
            return True, rendered_content

    def parser_error(self):
        """Return parser help information."""

        return self.parser.print_help()

    def server(self, exec_array, data, arg_vars):
        """Server operation.

        :param exec_array: Input array from action
        :type exec_array: List
        :param data: Formatted data hash
        :type data: Dictionary
        :returns: Dictionary
        """

        self.args()
        self.exec_parser(
            parser=self.parser, exec_array=exec_array, arg_vars=arg_vars
        )
        if self.known_args.stdout_arg:
            data["stdout_arg"] = self.known_args.stdout_arg
        if self.known_args.stderr_arg:
            data["stderr_arg"] = self.known_args.stderr_arg

    def client(self, cache, job):
        """Client operation.

        Command operations are rendered with cached data from the args dict.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        """

        pass

    def close(self):
        """Close a component."""

        pass

    def __enter__(self):
        """Return self when using a component as a context manager."""

        return self

    def __exit__(self, *args, **kwargs):
        """Exit the context manager and close."""

        self.close()


class Backend:
    """Coordination connection context manager."""

    def __init__(self, driver, log, job_id):
        """Initialize the backend context manager class."""

        self.driver = driver
        self.driver.backend_init()
        self.log = log
        self.job_id = job_id

    def __enter__(self):
        """Enter the job backend class and return the driver."""

        self.log.debug(
            "Backend connection started to %s for job [ %s ]",
            self.driver.identity,
            self.job_id,
        )
        return self.driver

    def __exit__(self, *args, **kwargs):
        """Close the bind backend object."""

        self.driver.backend_close()
        self.log.debug(
            "Backend connection ended for %s for job [ %s ]",
            self.driver.identity,
            self.job_id,
        )
        time.sleep(0.25)
