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

from directord import drivers


def parse_args(parser, parser_server, parser_client):
    """Add arguments for this driver to the parser.

    :param parser: Parser
    :type parser: Object
    :param parser_server: SubParser object
    :type parser_server: Object
    :param parser_client: SubParser object
    :type parser_client: Object
    :returns: Object
    """

    return parser


class Driver(drivers.BaseDriver):
    """Dummy driver implements the base class and nothing else."""

    pass
