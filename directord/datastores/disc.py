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

import diskcache


class BaseDocument:
    """Create a document store object."""

    def __init__(self, url):
        """Initialize the redis datastore.

        :param url: Connection string to the redis deployment.
        :type url: String
        """

        self.datastore = diskcache.Cache(
            url,
            tag_index=True,
            disk=diskcache.JSONDisk,
        )

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

        if isinstance(value, dict):
            try:
                expire = int(value.get("time") - time.time())
            except TypeError:
                expire = None
            else:
                if expire < 1:
                    expire = 1
        else:
            expire = None

        self.datastore.set(key, value, expire=expire)

    def __delitem__(self, key):
        """Delete an item from the datastore.

        :param key: Named object.
        :type key: Object
        """

        self.datastore.pop(key)

    def items(self):
        """Yield a tuple for key and value."""

        for item in list(self.datastore):
            yield item, self.__getitem__(item)

    def keys(self):
        """Return an array of all keys.

        :returns: List
        """

        return [i for i in self.datastore]

    def empty(self):
        """Empty all items from the datastore.

        Because a Manager Dict is a proxy object we don't want to replace the
        object we want to empty it keeping the original proxy intact. This
        method will pop all items from the object.
        """

        self.datastore.clear(retry=True)

    def pop(self, key):
        """Delete the value of a given key.

        :param key: Named object.
        :type key: Object
        """

        self.__delitem__(key)

    def prune(self):
        """Prune items that have a time based expiry."""

        self.datastore.expire()
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
