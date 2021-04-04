import hashlib
import multiprocessing
import os
import socket
import time


class Processor(object):
    """Processing class, provides queing and threading utilities.

    This is a base class.
    """

    job_queue = multiprocessing.Queue()
    thread = multiprocessing.Process
    manager = multiprocessing.Manager()

    def __init__(self):
        """Initialize Processor class creating all required manager objects.

        Managers maintain a multiprocessing proxy object which allows data to
        be shared across threads.
        """

        self.workers = self.manager.dict()
        self.return_jobs = self.manager.dict()  # This could likely be etcd

    @staticmethod
    def wq_next(workers):
        """Given a queue object return the next valid item.

        Valid items are determined by their value, which is an expiry object.

        :param workers: Hash containing workers.
        :type workers: Manager.Dictionary()
        :returns: Tuple
        """

        while True:
            try:
                key, value = workers.popitem()
            except KeyError:
                return tuple()
            else:
                if time.time() <= value:
                    workers[key] = value
                    return key, value

    @staticmethod
    def wq_prune(workers):
        """Given a Manager.Dictionary object return a pruned hash.

        This will ensure that the items contained within the provided hash
        are valid.

        :param workers: Hash containing workers.
        :type workers: Manager.Dictionary()
        :returns: Tuple
        """

        workers = {
            key: value
            for (key, value) in workers.items()
            if time.time() <= value
        }
        print("workers after prune {workers}".format(workers=len(workers)))
        return workers

    @staticmethod
    def wq_empty(workers):
        """Empty all items from a Manager.Dict.

        Because a Manager Dict is a proxy object we don't want to replace the
        object we want to empty it keeping the original proxy intact. This
        method will pop all items from the object.
        """

        try:
            while workers.popitem():
                pass
        except KeyError:
            pass

    @staticmethod
    def read_in_chunks(file_object, chunk_size=1024):
        """Generator to read a file piece by piece.

        Default chunk size: 1K.

        :param file_object: Open File Object
        :type file_object: Object
        :yields: Data
        """

        while True:
            data = file_object.read(chunk_size)
            if not data:
                break
            yield data

    @staticmethod
    def file_sha1(file_path, chunk_size=1024):
        """Return the SHA1 sum of a given file.

        :param file_path: File path
        :type file_path: String
        :returns: String
        """

        sha1 = hashlib.sha1()
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    else:
                        sha1.update(data)

            return sha1.hexdigest()


class UNIXSocketConnect(object):
    """Context manager for connecting to a UNIX socket."""

    def __init__(self, sock_path):
        """Initialize the UNIX socket connect context manager.

        :param socket_path: Path to the local file system socket.
        :type socket_path: String
        """

        self.socket_path = sock_path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def __enter__(self):
        """Upon enter, connect to the socket and return the socket object.

        :returns: Object
        """

        self.sock.connect(self.socket_path)
        return self.sock

    def __exit__(self, *args, **kwargs):
        """Upon exit, close the unix socket."""

        self.sock.close()
