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

import os
import struct
import time

from directord import utils


class BaseDocument(utils.Cache):
    """Create a document store object."""

    def empty(self):
        """Remove all cache."""

        self.clear()

    def prune(self):
        """Prune items that have a time based expiry."""

        for key in self.keys():
            try:
                expire = struct.unpack(">d", os.getxattr(key, "user.expire"))[
                    0
                ]
            except (IndexError, OSError):
                value = self.get(key, dict())
                expire = value.get("time")

            if expire and time.time() >= expire:
                self.__delitem__(key)

        return len(list(self.keys()))

    def set(self, key, value):
        """Set key and value if key doesn't already exist.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        :returns: Object
        """

        item = self.__getitem__(key)
        if item:
            return item

        self.__setitem__(key, value)
        return value
