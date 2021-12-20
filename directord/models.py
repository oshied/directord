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

import decimal
import time


class BaseModel:
    coordination_failed = "\x07"  # Signals coordination failed
    coordination_ack = "\x10"  # Signals coordination acknowledged
    coordination_notice = "\x11"  # Signals coordination notice
    job_end = "\x04"  # Signals job ended
    job_failed = "\x15"  # Signals job failed
    job_processing = "\x16"  # Signals job processing
    heartbeat_notice = "\x05"  # Signals heartbeat notice
    nullbyte = "\x00"  # Signals null
    transfer_start = "\x02"  # Signals transfer start
    transfer_end = "\x03"  # Signals transfer end


class Worker:
    """Worker class object."""

    def __init__(self, identity):
        """Initialize the worker object."""

        self.identity = identity
        self.active = True
        self.expire_time = None
        self.machine_id = None
        self.version = None
        self.host_uptime = None
        self.agent_uptime = None
        self.version = None
        self.driver = None

    @property
    def expired(self):
        """Return Boolean, True if expiry is greater than Now or None."""

        if self.expiry is None:
            return True
        else:
            return time.time() >= self.expire_time

    @property
    def expiry(self):
        """Return Float, for expiry."""

        return self.expire_time - time.time()


class Job(BaseModel):
    """Job class object."""

    def __init__(self, job_item):
        """Initialize the job object."""

        self._createtime = time.time()
        self._executiontime = dict()
        self._lasttime = time.time()
        self._processing = dict()
        self._roundtripltime = dict()

        self.job_id = job_item["job_id"]

        self.JOB_DEFINITION = job_item
        self.JOB_SHA3_224 = job_item["job_sha3_224"]
        self.JOB_NAME = job_item.get("job_name", self.JOB_SHA3_224)
        self.PARENT_JOB_ID = job_item.get("parent_id")
        self.PARENT_JOB_NAME = job_item.get("parent_name", self.PARENT_JOB_ID)
        self.VERB = job_item["verb"]
        self.COMPONENT_TIMESTAMP = None
        self.INFO = dict()
        self.PROCESSING = None
        self.RETURN_TIMESTAMP = None
        self.STDERR = dict()
        self.STDOUT = dict()

    @property
    def failed(self):
        """Return True or Flase if job failed."""

        return len(self.failed_nodes) > 0

    @property
    def _nodes(self):
        """Return a sorted list of all nodes."""

        return sorted(self._processing.keys())

    def _check_nodes(self, status_code):
        """Return a list of nodes based on a defined status code.

        :param status_code: Status code string.
        :type status_code: String
        :returns: List
        """
        nodes = list()
        for k, v in self._processing.items():
            if v == status_code:
                nodes.append(k)
        return nodes

    @property
    def failed_nodes(self):
        """Return a list of failed nodes."""

        return self._check_nodes(status_code=self.job_failed)

    @property
    def success_nodes(self):
        """Return a list of success nodes."""

        return self._check_nodes(status_code=self.job_end)

    @property
    def processing(self):
        """Set the processing flag and return boolean if processing."""

        processing = any(self._check_nodes(status_code=self.job_processing))
        if processing:
            self.PROCESSING = self.job_processing
        else:
            self.PROCESSING = self.job_end
        return processing

    def set_roundtripltime(self, identity, recv_time):
        """Set the round trip time.

        The constante ROUNDTRIP_TIME is used to represent the average
        roundtrip time.
        """

        if isinstance(recv_time, (int, float)):
            self._roundtripltime[identity] = (
                float(recv_time) - self._createtime
            )

        try:
            self.ROUNDTRIP_TIME = "{:.8f}".format(
                decimal.Decimal(
                    sum(self._roundtripltime.values())
                    / len(self._roundtripltime.keys())
                )
            )
        except ZeroDivisionError:
            pass

    def set_executiontime(self, identity, execution_time):
        """Set the execution time.

        The constante EXECUTION_TIME is used to represent the average
        execution time.
        """

        if isinstance(execution_time, (int, float)):
            self._executiontime[identity] = float(execution_time)

        try:
            self.EXECUTION_TIME = "{:.8f}".format(
                decimal.Decimal(
                    sum(self._executiontime.values())
                    / len(self._executiontime.keys())
                )
            )
        except ZeroDivisionError:
            pass
