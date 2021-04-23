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
import glob
import os
import setuptools


setuptools.setup(
    name="director",
    version="0.0.1",
    long_description=__doc__,
    packages=["director"],
    include_package_data=True,
    zip_safe=False,
    test_suite="tests",
    install_requires=[
        "diskcache",
        "jinja2",
        "paramiko",
        "pyyaml",
        "pyzmq",
        "tabulate",
        "tenacity",
    ],
    extras_require={"ui": ["flask"], "dev": ["etcd3"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.8",
        "Topic :: Utilities",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "director = director.main:main",
            "director-server-systemd = director.main:_systemd_server",
            "director-client-systemd = director.main:_systemd_client",
        ]
    },
    data_files=[
        (
            "share/director/orchestrations",
            [i for i in glob.glob("orchestrations/*") if os.path.isfile(i)],
        ),
        (
            "share/director/orchestrations/files",
            [
                i
                for i in glob.glob("orchestrations/files/*")
                if os.path.isfile(i)
            ],
        ),
        (
            "share/director/tools",
            [i for i in glob.glob("tools/*") if os.path.isfile(i)],
        ),
    ],
)
