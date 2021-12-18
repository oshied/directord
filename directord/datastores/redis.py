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

import pickle
import time

import redis


class BaseDocument:
    """Create a document store object."""

    def __init__(self, url, database=0):
        """Initialize the redis datastore.

        :param url: Connection string to the redis deployment.
        :type url: String
        :param database: Keyspace used for Redis
        :type database: Integer
        """

        self.datastore = redis.Redis.from_url(url=url, db=database)

    def __getitem__(self, key):
        """Return the value of a given key.

        Objects stored in the keyspace are JSON, the getter will
        decode and load the JSON into a standard python object.

        :param key: Named object.
        :type key: Object
        :returns: Object
        """

        value = self.datastore.get(key)
        if value:
            try:
                value = pickle.loads(value)
            except Exception:
                return value
            else:
                return value

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

        try:
            expire = int(value.get("time") - time.time())
        except (AttributeError, TypeError):
            expire = None
        else:
            if expire < 1:
                expire = 1

        self.datastore.set(key, pickle.dumps(value), ex=expire)

    def __delitem__(self, key):
        """Delete an item from the datastore.

        :param key: Named object.
        :type key: Object
        """

        self.datastore.delete(key)

    def items(self):
        """Yield a tuple for key and value."""

        for item in reversed(self.datastore.keys("*")):
            yield item.decode(), self.__getitem__(item)

    def keys(self):
        """Return an array of all keys.

        :returns: List
        """

        for item in reversed(self.datastore.keys("*")):
            yield item.decode()

    def values(self):
        """Yield a each value."""

        for item in reversed(self.datastore.keys("*")):
            yield self.__getitem__(item)

    def clear(self):
        """Empty all items from the datastore.

        Because a Manager Dict is a proxy object we don't want to replace the
        object we want to empty it keeping the original proxy intact. This
        method will pop all items from the object.
        """

        self.datastore.flushdb()

    def pop(self, key):
        """Delete the value of a given key.

        :param key: Named object.
        :type key: Object
        """

        self.__delitem__(key)

    def prune(self):
        """Prune items that have a time based expiry."""

        count = 0
        for key, value in list(self.items()):
            try:
                if value.expired and value.active:
                    self.pop(key)
            except AttributeError:
                value = self.get(key, dict())
                expire = value.get("time")
                if expire and time.time() >= expire:
                    self.pop(key, None)
                else:
                    count += 1
            else:
                count += 1

        return count

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
        :returns: Object
        """

        item = self.__getitem__(key)
        if item:
            return item

        self.__setitem__(key, value)
        return value
