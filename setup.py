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

from directord import meta


with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()


REQUIREMENTS = {
    "ui": ["flask"],
    "dev": ["podman-py"],
    "test": ["flake8", "coverage"],
    "redis": ["redis"],
    "oslo_messaging": ["oslo_messaging[amqp1]"],
}
REQUIREMENTS["all"] = [item for line in REQUIREMENTS.values() for item in line]


setuptools.setup(
    name="directord",
    author=meta.__author__,
    author_email=meta.__email__,
    description=(
        "A deployment framework built to manage the data center life cycle."
    ),
    version=meta.__version__,
    packages=["directord"],
    include_package_data=True,
    zip_safe=False,
    test_suite="tests",
    install_requires=[
        "diskcache",
        "jinja2",
        "pyyaml",
        "pyzmq",
        "ssh-python",
        "tabulate",
        "tenacity",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cloudnull/directord",
    project_urls={
        "Bug Tracker": "https://github.com/cloudnull/directord/issues",
    },
    python_requires=">=3.6",
    extras_require=REQUIREMENTS,
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
            "directord = directord.main:main",
            "directord-server-systemd = directord.main:_systemd_server",
            "directord-client-systemd = directord.main:_systemd_client",
        ]
    },
    data_files=[
        (
            "share/directord/components",
            [i for i in glob.glob("components/*") if os.path.isfile(i)],
        ),
        (
            "share/directord/orchestrations",
            [i for i in glob.glob("orchestrations/*") if os.path.isfile(i)],
        ),
        (
            "share/directord/orchestrations/files",
            [
                i
                for i in glob.glob("orchestrations/files/*")
                if os.path.isfile(i)
            ],
        ),
        (
            "share/directord/pods",
            [i for i in glob.glob("pods/*") if os.path.isfile(i)],
        ),
        (
            "share/directord/tools",
            [i for i in glob.glob("tools/*") if os.path.isfile(i)],
        ),
    ],
)
