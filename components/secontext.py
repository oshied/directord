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

from directord import components

from directord.components.lib import cacheargs
from directord.components.lib import timeout


try:
    import selinux

    AVAILABLE_SELINUX = True
except ImportError:
    AVAILABLE_SELINUX = False


try:
    import seobject

    AVAILABLE_SEOBJECT = True
except ImportError:
    AVAILABLE_SEOBJECT = False


class Component(components.ComponentBase):
    def __init__(self):
        super().__init__(desc="Process secontext commands")
        self.file_type_str = {
            "a": "all files",
            "b": "block device",
            "c": "character device",
            "d": "directory",
            "f": "regular file",
            "l": "symbolic link",
            "p": "named pipe",
            "s": "socket",
        }

    def semanage_exists(self, secontext, target, ftype):
        """Get the SELinux file context mapping definition from policy.

        :secontext: Object
        :target: String
        :ftype: String
        :returns: Tuple
        """

        record = (target, self.file_type_str[ftype])
        records = secontext.get_all()
        orig_seuser, _, _, orig_selevel = records[record]
        try:
            return True, orig_seuser, orig_selevel
        except KeyError:
            return False, None, None

    def args(self):
        """Set default arguments for a component."""

        super().args()
        self.parser.add_argument(
            "--ftype",
            help="The contexts type. %(default)s",
            choices=list(self.file_type_str.keys()),
        )
        self.parser.add_argument(
            "--reload",
            help="Reload policy after commit",
            default=False,
            type=bool,
        )
        self.parser.add_argument(
            "--selevel",
            help="Selinux level",
            default=str,
        )
        self.parser.add_argument(
            "--setype", help="Selinux type.", default=str, required=True
        )
        self.parser.add_argument(
            "--seuser",
            help="Selinux user.",
            default=str,
        )
        self.parser.add_argument(
            "target",
            help="Add or modify the selinux context for a given target.",
        )

    def server(self, exec_array, data, arg_vars):
        """Return data from formatted cacheevict action.

        :param exec_array: Input array from action
        :type exec_array: List
        :param data: Formatted data hash
        :type data: Dictionary
        :param arg_vars: Pre-Formatted arguments
        :type arg_vars: Dictionary
        :returns: Dictionary
        """

        super().server(exec_array=exec_array, data=data, arg_vars=arg_vars)
        if self.known_args.ftype:
            data["ftype"] = self.known_args.ftype

        if self.known_args.setype:
            data["setype"] = self.known_args.setype

        if self.known_args.seuser:
            data["seuser"] = self.known_args.seuser

        if self.known_args.selevel:
            data["selevel"] = self.known_args.selevel

        if self.known_args.target:
            data["target"] = self.known_args.target

        data["reload"] = self.known_args.reload

        return data

    @timeout
    @cacheargs
    def client(self, cache, job):
        """Run cache echo command operation.

        :param cache: Caching object used to template items within a command.
        :type cache: Object
        :param job: Information containing the original job specification.
        :type job: Dictionary
        :returns: tuple
        """

        if not selinux.is_selinux_enabled():
            return (None, "SELinux is not enabled.", True, None)

        if not AVAILABLE_SELINUX:
            return (
                None,
                "The required selinux library is not installed",
                False,
                None,
            )

        if not AVAILABLE_SEOBJECT:
            return (
                None,
                "The required seobject library is not installed",
                False,
                None,
            )

        target = job["target"]
        ftype = job.get("ftype")
        setype = job["setype"]
        seuser = job.get("seuser")
        selevel = job.get("selevel")

        secontext = seobject.fcontextRecords("")
        secontext.set_reload(job["reload"])

        (
            existing,
            orig_seuser,
            orig_selevel,
        ) = self.semanage_exists(secontext, target, ftype)

        if existing:
            if not seuser:
                seuser = orig_seuser

            if not selevel:
                selevel = orig_selevel

            secontext.modify(target, setype, ftype, selevel, seuser)
        else:
            if not seuser:
                seuser = "system_u"

            if not selevel:
                selevel = "s0"

            secontext.add(target, setype, ftype, selevel, seuser)

        return job["target"], None, True, None
