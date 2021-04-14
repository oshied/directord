import os
import yaml

from director import client
from director import server
from director import user


class Mixin(object):
    """Mixin class."""

    def __init__(self, args):
        """Initialize the Director mixin.

        Sets up the mixin object.

        :param args: Arguments parsed by argparse.
        :type args: Object
        """

        self.args = args

    def run_orchestration(self):
        """Execute orchestration jobs.

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

                job_to_run = list()
                defined_targets = list()
                if self.args.target:
                    defined_targets = list(set(self.args.target))

                for orchestrate in orchestrations:
                    parent_id = user_exec.get_uuid
                    targets = defined_targets or orchestrate.get(
                        "targets", list()
                    )
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
                                    restrict=self.args.restrict,
                                    ignore_cache=self.args.ignore_cache,
                                    parent_id=parent_id,
                                )
                            )
                        if not targets:
                            job_to_run.append(
                                dict(
                                    verb=key,
                                    execute=value,
                                    restrict=self.args.restrict,
                                    ignore_cache=self.args.ignore_cache,
                                    parent_id=parent_id,
                                )
                            )

                for job in job_to_run:
                    return_data.append(
                        user_exec.send_data(data=user_exec.format_exec(**job))
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
                    verb=self.args.verb, execute=self.args.exec, target=target
                )
                return_data.append(user_exec.send_data(data=data))
        else:
            data = user_exec.format_exec(
                verb=self.args.verb, execute=self.args.exec
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
