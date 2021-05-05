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


import unittest

from collections import namedtuple
from unittest import mock
from unittest.mock import patch

from directord import main
from directord import tests


class TestMain(unittest.TestCase):
    def setUp(self):
        self.args = tests.FakeArgs()
        self.systemdinstall = main.SystemdInstall()

    def tearDown(self):
        pass

    def test__args_default(self):
        main._args()

    def test__args_orchestrate(self):
        args, _ = main._args(["orchestrate", "file1 file2"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "finger_print": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "ignore_cache": False,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "orchestrate",
                "target": None,
                "orchestrate_files": ["file1 file2"],
                "poll": False,
                "restrict": None,
            },
        )

    def test__args_run(self):
        args, _ = main._args(["exec", "--verb", "RUN", "command1"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "RUN",
                "target": None,
                "exec": ["command1"],
                "poll": False,
            },
        )

    def test__args_copy(self):
        args, _ = main._args(["exec", "--verb", "COPY", "file1 file2"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "COPY",
                "target": None,
                "exec": ["file1 file2"],
                "poll": False,
            },
        )

    def test__args_add(self):
        args, _ = main._args(["exec", "--verb", "ADD", "file1 file2"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "ADD",
                "target": None,
                "exec": ["file1 file2"],
                "poll": False,
            },
        )

    def test__args_arg(self):
        args, _ = main._args(["exec", "--verb", "ARG", "key value"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "ARG",
                "target": None,
                "exec": ["key value"],
                "poll": False,
            },
        )

    def test__args_env(self):
        args, _ = main._args(["exec", "--verb", "ENV", "key value"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "ENV",
                "target": None,
                "exec": ["key value"],
                "poll": False,
            },
        )

    def test__args_workdir(self):
        args, _ = main._args(["exec", "--verb", "WORKDIR", "/path"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "WORKDIR",
                "target": None,
                "exec": ["/path"],
                "poll": False,
            },
        )

    def test__args_cachefile(self):
        args, _ = main._args(["exec", "--verb", "CACHEFILE", "/path"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "CACHEFILE",
                "target": None,
                "exec": ["/path"],
                "poll": False,
            },
        )

    def test__args_cacheevict(self):
        args, _ = main._args(["exec", "--verb", "CACHEEVICT", "all"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "CACHEEVICT",
                "target": None,
                "exec": ["all"],
                "poll": False,
            },
        )

    def test__args_cacheevict(self):
        args, _ = main._args(["exec", "--verb", "QUERY", "var"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "exec",
                "verb": "QUERY",
                "target": None,
                "exec": ["var"],
                "poll": False,
            },
        )

    def test__args_orchestrate(self):
        args, _ = main._args(["orchestrate", "file1 file2"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "finger_print": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "ignore_cache": False,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "orchestrate",
                "target": None,
                "orchestrate_files": ["file1 file2"],
                "poll": False,
                "restrict": None,
            },
        )

    def test__args_server(self):
        args, _ = main._args(["server"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "server",
                "bind_address": "*",
                "run_ui": False,
                "ui_port": 9000,
            },
        )

    def test__args_client(self):
        args, _ = main._args(["client"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "mode": "client",
                "server_address": "localhost",
            },
        )

    def test__args_manage_list_nodes(self):
        args, _ = main._args(["manage", "--list-nodes"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": True,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_list_jobs(self):
        args, _ = main._args(["manage", "--list-jobs"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": True,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_purge_jobs(self):
        args, _ = main._args(["manage", "--purge-jobs"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": True,
                "purge_nodes": False,
            },
        )

    def test__args_manage_purge_nodes(self):
        args, _ = main._args(["manage", "--purge-nodes"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": True,
            },
        )

    def test__args_manage_job_info(self):
        args, _ = main._args(["manage", "--job-info", "xxxx"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": False,
                "job_info": "xxxx",
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_export_jobs(self):
        args, _ = main._args(["manage", "--export-jobs", "xxxx"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": "xxxx",
                "export_nodes": None,
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_purge_nodes(self):
        args, _ = main._args(["manage", "--export-nodes", "xxxx"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": "xxxx",
                "generate_keys": False,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_generate_keys(self):
        args, _ = main._args(["manage", "--generate-keys"])
        self.assertDictEqual(
            vars(args),
            {
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "export_jobs": None,
                "export_nodes": None,
                "generate_keys": True,
                "job_info": None,
                "job_port": 5555,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "cache_path": "/var/cache/directord",
                "list_jobs": False,
                "list_nodes": False,
                "mode": "manage",
                "purge_jobs": False,
                "purge_nodes": False,
            },
        )

    def test__args_manage_bootstrap(self):
        m = unittest.mock.mock_open(read_data=tests.TEST_CATALOG.encode())
        with patch("builtins.open", m):
            args, _ = main._args(["bootstrap", "--catalog", "file"])
        self.assertDictEqual(
            vars(args),
            {
                "catalog": mock.ANY,
                "config_file": None,
                "shared_key": None,
                "curve_encryption": False,
                "debug": False,
                "job_port": 5555,
                "key_file": None,
                "transfer_port": 5556,
                "heartbeat_port": 5557,
                "heartbeat_interval": 60,
                "socket_path": "/var/run/directord.sock",
                "threads": 10,
                "cache_path": "/var/cache/directord",
                "mode": "bootstrap",
            },
        )

    @patch("builtins.print")
    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_path_setup(
        self, mock_makedirs, mock_exists, mock_print
    ):
        mock_exists.return_value = False
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().path_setup()
            m.assert_called()
        mock_makedirs.assert_called()
        mock_print.assert_called()

    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_path_setup_exists(
        self, mock_makedirs, mock_exists
    ):
        mock_exists.return_value = True
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().path_setup()
            m.assert_not_called()
        mock_makedirs.assert_called()

    @patch("builtins.print")
    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_writer(
        self, mock_makedirs, mock_exists, mock_print
    ):
        mock_exists.return_value = False
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().writer(service_file="testfile")
            m.assert_called()
        mock_print.assert_called()

    @patch("builtins.print")
    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_writer(
        self, mock_makedirs, mock_exists, mock_print
    ):
        mock_exists.return_value = True
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().writer(service_file="testfile")
            m.assert_not_called()
        mock_print.assert_called()

    @patch("builtins.print")
    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_server(
        self, mock_makedirs, mock_exists, mock_print
    ):
        mock_exists.return_value = False
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().writer(
                service_file="directord-client.service"
            )
            m.assert_called_with(
                "/etc/systemd/system/directord-client.service", "w"
            )
        mock_print.assert_called()

    @patch("builtins.print")
    @patch("os.path.exists", autospec=True)
    @patch("os.makedirs", autospec=True)
    def test_systemdinstall_client(
        self, mock_makedirs, mock_exists, mock_print
    ):
        mock_exists.return_value = False
        with patch("builtins.open", unittest.mock.mock_open()) as m:
            main.SystemdInstall().writer(
                service_file="directord-server.service"
            )
            m.assert_called_with(
                "/etc/systemd/system/directord-server.service", "w"
            )
        mock_print.assert_called()

    @patch("directord.main._args", autospec=True)
    def test_main_server(self, mock__args):
        _args = {
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "job_port": 5555,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "cache_path": "/var/cache/directord",
            "mode": "server",
            "bind_address": "*",
            "run_ui": False,
            "ui_port": 9000,
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.server.Server", autospec=True):
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_client(self, mock__args):
        _args = {
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "job_port": 5555,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "cache_path": "/var/cache/directord",
            "mode": "client",
            "server_address": "localhost",
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.client.Client", autospec=True):
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_exec(self, mock__args):
        _args = {
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "job_port": 5555,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "cache_path": "/var/cache/directord",
            "mode": "exec",
            "verb": "RUN",
            "target": None,
            "exec": ["command1"],
            "poll": False,
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.mixin.Mixin.run_exec", autospec=True):
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_orchestrate(self, mock__args):
        _args = {
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "finger_print": False,
            "job_port": 5555,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "ignore_cache": False,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "cache_path": "/var/cache/directord",
            "mode": "orchestrate",
            "target": None,
            "orchestrate_files": ["file1 file2"],
            "poll": False,
            "restrict": None,
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.mixin.Mixin.run_orchestration", autospec=True):
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_manage(self, mock__args):
        _args = {
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "export_jobs": None,
            "export_nodes": None,
            "generate_keys": False,
            "job_info": None,
            "job_port": 5555,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "cache_path": "/var/cache/directord",
            "list_jobs": False,
            "list_nodes": True,
            "mode": "manage",
            "purge_jobs": False,
            "purge_nodes": False,
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.user.Manage.run", autospec=True) as d:
            d.return_value = {}
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_bootstrap(self, mock__args):
        _args = {
            "catalog": mock.ANY,
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "job_port": 5555,
            "key_file": None,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "threads": 10,
            "cache_path": "/var/cache/directord",
            "mode": "bootstrap",
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        mock__args.return_value = [parsed_args, mock.MagicMock()]
        with patch("directord.mixin.Mixin.bootstrap_cluster", autospec=True):
            main.main()

    @patch("directord.main._args", autospec=True)
    def test_main_fail(self, mock__args):
        _args = {
            "catalog": mock.ANY,
            "config_file": None,
            "shared_key": None,
            "curve_encryption": False,
            "debug": False,
            "job_port": 5555,
            "key_file": None,
            "transfer_port": 5556,
            "heartbeat_port": 5557,
            "heartbeat_interval": 60,
            "socket_path": "/var/run/directord.sock",
            "threads": 10,
            "cache_path": "/var/cache/directord",
            "mode": "UNDEFINED",
        }
        parsed_args = namedtuple("NameSpace", _args.keys())(*_args.values())
        parser = mock.MagicMock()
        mock__args.return_value = [parsed_args, parser]
        self.assertRaises(SystemExit, main.main)
        parser.print_help.assert_called()
