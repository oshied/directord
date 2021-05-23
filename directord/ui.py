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

import flask

from flask import request
from flask.views import MethodView


APP = flask.Flask(__name__, instance_relative_config=True)
JOBS = list()
NODES = list()


class DirectordUI(MethodView):
    """Implement a method view for the Directord UI."""

    @staticmethod
    def get():
        """Return a get response from a template."""

        response = flask.make_response(
            flask.render_template(
                "index.html",
                remote_url=request.base_url,
                count=len(JOBS.keys()),
                jobs=JOBS.items(),
                nodes=NODES.items(),
            )
        )
        response.headers = {
            "X-Frame-Options": "SAMEORIGIN",
            "Cache-Control": "public, max-age=120",
        }
        return response


class UI:
    """The Directord UI execution class."""

    def __init__(self, args, jobs, nodes):
        """Initialize the Directord UI class.

        :param args: Arguments parsed by argparse.
        :type args: Object
        :params jobs: A manager object for all jobs.
        :type jobs: Dictionary
        :params nodes: A manager object for all nodes.
        :type nodes: Dictionary
        """

        global JOBS
        JOBS = jobs
        global NODES
        NODES = nodes
        self.args = args

    def start_app(self):
        """Start the application in production mode.

        Starts the flask application using the embedded server.
        """

        APP.add_url_rule("/", view_func=DirectordUI.as_view("index"))
        if self.args.bind_address == "*":
            host = "0.0.0.0"
        else:
            host = self.args.bind_address
        APP.run(port=self.args.ui_port, host=host)
