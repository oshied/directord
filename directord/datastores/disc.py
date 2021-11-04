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

from directord import utils


class BaseDocument:
    """Create a document store object."""

    def __init__(self, url):
        """Initialize the redis datastore.

        :param url: Connection string to the file backend.
        :type url: String
        """

        self.datastore = utils.Cache(path=url, filename="server.db")

    def __getitem__(self, key):
        """Return the value of a given key.

        Objects stored in the keyspace are JSON, the getter will
        decode and load the JSON into a standard python object.

        :param key: Named object.
        :type key: Object
        :returns: Object
        """

        return self.datastore.get(key)

    def __setitem__(self, key, value):
        """Set an item in the datastore.

        objects are serialized JSON.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        """

        try:
            key = key.decode()
        except AttributeError:
            pass

        self.datastore.set(key, value)

    def __delitem__(self, key):
        """Delete an item from the datastore.

        :param key: Named object.
        :type key: Object
        """

        try:
            del self.datastore[key]
        except KeyError:
            pass

    def items(self):
        """Returns a generator, for key and value.

        :returns: Object
        """

        return self.datastore.items()

    def keys(self):
        """Return an array of all keys.

        :returns: List
        """

        return self.datastore.keys()

    def empty(self):
        """Empty all items from the datastore.

        Because a Manager Dict is a proxy object we don't want to replace the
        object we want to empty it keeping the original proxy intact. This
        method will pop all items from the object.
        """

        self.datastore.clear()

    def pop(self, key):
        """Delete the value of a given key.

        :param key: Named object.
        :type key: Object
        :returns: Object
        """

        value = self.__getitem__(key)
        self.__delitem__(key)
        return value

    def prune(self):
        """Prune items that have a time based expiry."""

        for key, value in list(self.items()):
            try:
                if time.time() >= value["time"]:
                    self.__delitem__(key)
            except (KeyError, TypeError):
                pass

        return len(self.keys())

    def get(self, key):
        """Return the value of a given key.

        :param key: Named object.
        :type key: Object
        :returns: Object
        """

        return self.__getitem__(key)

    def set(self, key, value):
        """Set key and value if key doesn't already exist.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        :param value: Object to set.
        :type value: Object
        :returns: Object
        """

        item = self.__getitem__(key)
        if item:
            return item

        self.__setitem__(key, value)
        return value
