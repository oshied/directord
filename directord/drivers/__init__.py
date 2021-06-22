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


class BaseDriver:
    nullbyte = b"\000"  # Signals null
    heartbeat_ready = b"\001"  # Signals worker is ready
    heartbeat_notice = b"\005"  # Signals worker heartbeat
    job_ack = b"\006"  # Signals job started
    job_end = b"\004"  # Signals job ended
    job_processing = b"\026"  # Signals job running
    job_failed = b"\025"  # Signals job failed
    transfer_start = b"\002"  # Signals start file transfer
    transfer_end = b"\003"  # Signals start file transfer
