#   Copyright Peznauts <kevin@peznauts.com>. All Rights Reserved.
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

import multiprocessing
import operator
import os
import pickle
import queue
import struct
import traceback
import time
import typing

from directord import utils


_S = typing.TypeVar("_S")
_T = typing.TypeVar("_T")
_KT = typing.TypeVar("_KT")
_VT = typing.TypeVar("_VT")


def _get_create_time(path: str):
    """Return the file object birthtime.

    :param path: Storage path
    :type path: String
    :returns: Float
    """
    try:
        birthtime = os.getxattr(path, "user.birthtime")
        return struct.unpack(">d", birthtime)[0]
    except OSError:
        stat = os.stat(path)
        try:
            return stat.st_birthtime
        except AttributeError:
            return stat.st_ctime


def _get_item_key(path: str):
    """Return the key name from a file object.

    :returns: String
    """
    try:
        key = os.getxattr(path, "user.key")
    except OSError:
        if not os.path.exists(path):
            raise FileNotFoundError(path) from None
        return os.path.basename(path)
    else:
        return key.decode()


def _makedirs(path: str, key: _KT = None):
    """Create a directory and set attributes."""
    try:
        os.makedirs(path, exist_ok=True)
    except FileExistsError:
        os.unlink(path)
        os.makedirs(path, exist_ok=True)

    _setxattr(path=path, key=key)


def _setxattr(path: str, key: _KT = None):
    """Set file object attributes.

    :param path: File path
    :type path: String
    :param key: Key information
    :type key: String
    :returns: Boolean
    """
    try:
        try:
            os.getxattr(path, "user.birthtime")
        except OSError:
            os.setxattr(
                path,
                "user.birthtime",
                struct.pack(">d", time.time()),
            )
    except OSError:
        pass
    else:
        if key:
            os.setxattr(path, "user.key", key.encode())


class BaseClass:
    """Base class for the iodict library."""

    def __exit__(
        self, exc_type: typing.Any, exc_value: typing.Any, tb: typing.Any
    ):
        """Exit and return boolean.

        :returns: Boolean
        """
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)
            return False

        return True


class BaseQueue:
    def getter(self):
        """Yield items from the queue until empty."""

        while True:
            try:
                item = self.get_nowait()
            except Exception:
                break
            else:
                yield item


class IODict(BaseClass):
    def __init__(self, path: str, lock: typing.Any = None):
        """Initialize the POSIX compatible datastore.

        The POSIX cache store uses xattrs to store metadata about stored
        objects. Metadata is used to store the key and expiry information
        which is used to ensure we're maintaining a POSIX compliant data
        store which leverages simple file hashing. If xattrs are not
        availble on the filesystem, the cache method will fallback to a
        standard string encoding, and rely on in file information for
        expiry times.

        > If a lock object is not provided, a multiprocessing lock will
          be used.

        :param path: Storage path
        :type path: String
        :param lock: Lock type object
        :type lock: Object
        """
        if not lock:
            lock = multiprocessing.Lock()

        self._lock = lock
        self._db_path = os.path.abspath(os.path.expanduser(path))
        _makedirs(path=self._db_path)
        try:
            os.listxattr(self._db_path)
        except Exception:
            self._encoder = str
        else:
            self._encoder = utils.object_sha3_224

    def __delitem__(self, key: _KT):
        """Delete an item from the datastore.

        :param key: Named object.
        :type key: Object
        """
        item = os.path.join(self._db_path, self._encoder(key))
        with self._lock:
            try:
                os.unlink(item)
            except FileNotFoundError:
                raise KeyError(key) from None

    def __enter__(self):
        """Contect manager enter object.

        Entering the context manager will return itself.

        :returns: Object
        """
        return self

    def __exit__(
        self, exc_type: typing.Any, exc_value: typing.Any, tb: typing.Any
    ):
        """Clean up the dictionary and exit the context manager.

        :returns: Boolean
        """
        try:
            self.clear()
        finally:
            return super().__exit__(exc_type, exc_value, tb)

    def __getitem__(self, key: _KT):
        """Return the value of a given key.

        If a given key is not found, get will raise a KeyError exception.

        :param key: Named object.
        :type key: Object
        :returns: Object
        """
        file_object = os.path.join(self._db_path, self._encoder(key))
        with self._lock:
            try:
                with open(file_object, "rb") as f:
                    return pickle.load(f)
            except FileNotFoundError:
                raise KeyError(key) from None

    def __iter__(self, index: int = None):
        """Iterate over the keys and Yield.

        :param index: Index number to start from.
        :type index: Integer
        :returns: List || :yield: Object
        """
        items = list()
        if not os.path.exists(self._db_path):
            return items

        for item in os.scandir(self._db_path):
            try:
                items.append(
                    (
                        _get_item_key(item.path),
                        _get_create_time(item.path),
                        item.path,
                    )
                )
            except FileNotFoundError:
                pass

        items = sorted(items, key=operator.itemgetter(1))
        if not items:
            return list()
        elif index is not None and isinstance(index, int):
            if not os.path.exists(items[index][-1]):
                yield next(self.__iter__(index=index))
            else:
                yield items[index][0]
        else:
            for item in items:
                try:
                    if not os.path.exists(item[-1]):
                        continue
                    yield item[0]
                except GeneratorExit:
                    pass

    def __len__(self):
        """Return a count of all keys in the datastore.

        :returns: Integer
        """
        count = 0
        for _ in self.__iter__():
            count += 1
        return count

    def __repr__(self):
        """Returns repr string."""
        return str(dict(self.items()))

    def __setitem__(self, key: _KT, value: _VT):
        """Set an item in the datastore.

        > objects are serialized. Files use xattrs to store meta-data which
          is used to enhance operations.

        :param key: Named object to set.
        :type key: Object
        :param value: Object to set.
        :type value: Object
        """
        file_object = os.path.join(self._db_path, self._encoder(key))
        with self._lock:
            with open(file_object, "wb") as f:
                pickle.dump(value, f)

            _setxattr(path=file_object, key=key)

    def clear(self):
        """Remove all cache."""
        for item in self.__iter__():
            self.__delitem__(item)

    def copy(self):
        """Return self.

        :returns: Object
        """
        return self

    def get(self, key: _KT, default: typing.Any = None):
        """Return the value of a given key.

        :param key: Named object.
        :type key: Object
        :param default: Default return.
        :type default: Object
        :returns: Object
        """
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def fromkeys(self, iterable: typing.Iterable[_T], value: _S = None):
        """Set a list of items using a default.

        :param iterable: Iterable object to add to the data-store.
        :type iterable: Iterable
        """
        for item in iterable:
            self.__setitem__(item, value)

    def items(self):
        """Iterate through all items and yield a tuples, for key and value.

        :yields: Tuple
        """
        for item in self.keys():
            yield item, self.__getitem__(item)

    def keys(self):
        """Return an array of all keys.

        :yields: item || :returns: List
        """
        for item in self.__iter__():
            yield item

    def pop(self, key: _KT, default: typing.Any = None):
        """Remove a given key from the cache.

        :param key: Named object.
        :type key: Object
        :param default: Default return.
        :type default: Object
        :returns: Object
        """
        try:
            try:
                return self.__getitem__(key)
            finally:
                self.__delitem__(key)
        except KeyError as e:
            if default:
                return default
            else:
                raise e

    def popitem(self):
        """Remove and return an item from the datastore.

        :returns: Object
        """
        try:
            return self.pop(next(self.__iter__(index=0)))
        except (IndexError, StopIteration):
            raise KeyError("popitem(): dictionary is empty") from None

    def setdefault(self, key: _KT, default: typing.Any = None):
        """Return the value of a given key.

        :param key: Named object.
        :type key: Object
        :param default: Default return.
        :type default: Object
        :returns: Object
        """
        self.__setitem__(key, default)
        return default

    def update(self, mapping: typing.Mapping[_KT, _VT]):
        """Update the datastore with a new mapping.

        :param mapping: Map object, assumes a call to items.
        :type mapping: Mapping
        """
        for k, v in mapping.items():
            self.__setitem__(k, v)

    def values(self):
        """Return an array of all values.

        :yields: item || :returns: List
        """
        for item in self.__iter__():
            yield self.__getitem__(item)


class DurableQueue(BaseQueue):
    """DurableQueue class, used to ensure queued items are disk backed.

    This implements the standard Queue API, allowing the user to replace
    queue.Queue or mulriprocessing.Queue with a DurableQueue.

    DurableQueue is IODict backed.
    """

    def __init__(
        self, path: str, lock: typing.Any = None, semaphore: typing.Any = None
    ):
        """Initiallize the DurableQueue class.

        Durable queues use a semephore to keep track of the puts vs gets. When
        a Durable queue is loaded, it will scan the queue for items, and set
        the initial `_count` accordingly.

        :param path: Storage path
        :type path: String
        :param lock: Lock type object
        :type lock: Object
        :param semaphore: Semaphore type object
        :type semaphore: Object
        """

        if not semaphore:
            semaphore = multiprocessing.Semaphore

        self._queue = IODict(path=path, lock=lock)

        self._count = semaphore(self.qsize())

    def close(self):
        """Close the current Queue and cleanup artifacts."""

        try:
            self._queue.clear()
            os.rmdir(self._queue._db_path)
        except FileNotFoundError:
            pass

    def empty(self):
        """Return True if the queue is empty, False otherwise.

        :returns: Boolean
        """

        return self.qsize() == 0

    def get(self, block: bool = True, timeout: float = None):
        """Retrieve the first item from the queue.

        :param block: Force the queue to block attempting to fetch an object.
        :type block: Boolean
        :param timeout: Set the block timeout
        :type timeout: Float
        :returns: Object
        """

        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")

        if not self._count.acquire(block, timeout):
            raise queue.Empty

        return self._queue.popitem()

    def get_nowait(self):
        """Retrieve the first item from the queue without blocking.

        :returns: Object
        """

        return self.get(block=False)

    def put(self, item: typing.Any, block: bool = True, timeout: float = None):
        """Put a new item within the queue.

        > The block and timeout options are present for API compatibility,
          but are otherwise unused.

        :param item: Object to be entered into the queue.
        :type item: Object
        :param block: Force the queue to block attempting to fetch an object.
        :type block: Boolean
        :param timeout: Set the block timeout
        :type timeout: Float
        """

        self._queue[utils.get_uuid()] = item
        self._count.release()

    def put_nowait(self, item: typing.Any):
        """Put a new item within the queue without blocking.

        :param item: Object to be entered into the queue.
        :type item: Object
        """

        self.put(item)

    def qsize(self):
        """Return the approximate size of the queue.

        :returns: Integer
        """

        try:
            return len(self._queue)
        except FileNotFoundError:
            return 0


class FlushQueue(BaseQueue):
    def __init__(self, path, lock=None, semaphore=None):
        """Queue class augmentation allowing queues to be flushed to disk.

        This class requires a queue class to be used along with it.

        >>> class _FlushQueue(queue.Queue, FlushQueue):
        ...     def __init__(self, path, lock, semaphore):
        ...         super().__init__()
        ...         self.path = path
        ...         self.lock = lock
        ...         self.semaphore = semaphore

        With multiple inheritence, we can create any queue object with flush
        capabilities.
        """

        self.path = path
        self.lock = lock
        self.semaphore = semaphore

    def flush(self):
        """Flush all remaining items in queue to disk."""

        durable = DurableQueue(
            path=self.path, lock=self.lock, semaphore=self.semaphore
        )
        while True:
            try:
                item = self.get_nowait()
            except Exception:
                break
            else:
                durable.put(item)

    def ingest(self):
        """Check for existing items in queue and restore them."""

        if not os.path.exists(self.path):
            return

        durable = DurableQueue(
            path=self.path, lock=self.lock, semaphore=self.semaphore
        )
        while True:
            try:
                item = durable.get_nowait()
            except Exception:
                break
            else:
                self.put(item)

        durable.close()


class Cache(IODict):
    """Helper class to create the Cache object."""

    pass
