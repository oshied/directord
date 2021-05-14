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

import glob
import json
import os

from directord import components
from directord import utils


# This component was adapted from here:
# https://github.com/openstack/tripleo-ansible/blob/master/tripleo_ansible/ansible_plugins/modules/container_config_data.py  # noqa


DOCUMENTATION = """
---
component: container_config_data
author:
  - Emilien Macchi <emilien@redhat.com>
short_description: Generates a dictionary which contains all container configs
notes: []
description:
  - This module reads container configs in JSON files and generate a dictionary
    which later will be used to manage the containers.
options:
  config_path:
    description:
      - The path of a directory or a file where the JSON files are.
        This parameter is required.
    required: True
    type: str
  config_pattern:
    description:
      - Search pattern to find JSON files.
    default: '*.json'
    required: False
    type: str
  config_overrides:
    description:
      - Allows to override any container configuration which will take
        precedence over the JSON files.
    default: {}
    required: False
    type: dict
  debug:
    description:
      - Whether or not debug is enabled.
    default: False
    required: False
    type: bool
"""


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Process echo commands")

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.options_converter(documentation=DOCUMENTATION)

    def server(self, exec_string, data, arg_vars):
        """Return data from formatted cacheevict action.

        :param exec_string: Inpute string from action
        :type exec_string: String
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        super().server(exec_string=exec_string, data=data, arg_vars=arg_vars)
        data.update(vars(self.known_args))
        return data

    def client(self, conn, cache, job):
        """Run cache echo command operation.

        :param conn: Connection object used to store information used in a
                     return message.
        :type conn: Object
        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        super().client(conn=conn, cache=cache, job=job)

        # Set parameters
        config_path = job["config_path"]
        config_pattern = job["config_pattern"]
        config_overrides = job["config_overrides"]

        # Generate dict from JSON files that match search pattern
        if os.path.exists(config_path):
            matched_configs = glob.glob(
                os.path.join(config_path, config_pattern)
            )
            config_dict = {}
            for mc in matched_configs:
                name = os.path.splitext(os.path.basename(mc))[0]
                config = json.loads(self._slurp(mc))
                self.log.debug("Config found for {}: {}".format(name, config))
                config_dict.update({name: config})

            # Merge the config dict with given overrides
            configs = utils.merge_dict(config_dict, config_overrides)
            self.set_cache(
                cache=cache,
                key="configs",
                value=configs,
                value_update=False,
                tag="component",
            )
        else:
            self.log.debug(
                "{} does not exists, skipping step".format(config_path)
            )
            configs = dict()

        return configs, None, True

    def _slurp(self, path):
        """Slurps a file and return its content.

        :param path: string
        :returns: string
        """
        if os.path.exists(path):
            f = open(path, "r")
            return f.read()
        else:
            self.log.warn("{} was not found.".format(path))
            return ""
