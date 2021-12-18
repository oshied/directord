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

import time


class BaseDocument(dict):
    """Create a document store object."""

    def prune(self):
        """Prune items that have a time based expiry."""

        for key, value in list(self.items()):
            try:
                if value.expired and value.active:
                    self.pop(key)
            except (AttributeError, KeyError):
                try:
                    if time.time() >= value["time"]:
                        self.pop(key)
                except (KeyError, TypeError):
                    pass

        return len(self)

    def set(self, key, value):
        """Set key and value if key doesn't already exist.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        :returns: Object
        """

        if key in self:
            return self[key]

        super().__setitem__(key, value)
        return self[key]

    def __repr__(self):
        return f"{type(self).__name__}({super().__repr__()})"
