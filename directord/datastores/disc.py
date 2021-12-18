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

    def __init__(self, url):
        super().__init__(path=os.path.abspath(os.path.expanduser(url)))

    def __setitem__(self, key, value):
        """Set an item in the datastore.

        objects are serialized JSON. Files use xattrs to store meta-data which
        is used to enhance operations.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        """

        super().__setitem__(key=key, value=value)
        try:
            expire = value.get("time")
        except (AttributeError, TypeError):
            return
        else:
            if isinstance(expire, (float, int)):
                file_object = os.path.join(self._db_path, self._encoder(key))
                try:
                    os.setxattr(
                        file_object, "user.expire", struct.pack(">d", expire)
                    )
                except OSError:
                    pass

    def prune(self):
        """Prune items that have a time based expiry."""

        for key, value in list(self.items()):
            try:
                if value.expired and value.active:
                    self.pop(key, None)
            except AttributeError:
                try:
                    expire = struct.unpack(
                        ">d", os.getxattr(key, "user.expire")
                    )[0]
                except (IndexError, OSError):
                    value = self.get(key, dict())
                    expire = value.get("time")

                if expire and time.time() >= expire:
                    self.pop(key, None)

        return len(self)

    def set(self, key, value):
        """Set key and value if key doesn't already exist.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        :returns: Object
        """

        item = self.get(key)
        if item:
            return item

        return self.setdefault(key, value)
