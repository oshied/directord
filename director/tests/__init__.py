class FakePopen(object):
    """Fake Shell Commands."""

    def __init__(self, return_code=0, *args, **kwargs):
        self.returncode = return_code

    @staticmethod
    def communicate():
        return "stdout", "stderr"


class FakeStat(object):
    def __init__(self, uid, gid):
        self.st_uid = uid
        self.st_gid = gid
        self.st_size = 0
        self.st_mtime = 0
        self.st_mode = 0


class FakeArgs(object):
    config_file = None
    Nonecurve_encryption = False
    debug = False
    heartbeat_interval = 60
    heartbeat_port = 5557
    job_port = 5555
    mode = "client"
    server_address = "localhost"
    shared_key = None
    socket_path = "/var/run/director.sock"
    transfer_port = 5556
    curve_encryption = None
