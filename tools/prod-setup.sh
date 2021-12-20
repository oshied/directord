#!/usr/bin/env bash
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
set -eo

DRIVER=${DRIVER:-zmq}

if [[ $UID != 0 ]]; then
    echo "Please run this script with sudo:"
    echo "sudo $0 $*"
    exit 1
fi

function get_latest_release() {
  curl --silent "https://api.github.com/repos/$1/releases/latest" | # Get latest release from GitHub api
    grep '"tag_name":' |                                            # Get tag line
    sed -E 's/.*"([^"]+)".*/\1/'                                    # Pluck JSON value
}

. /etc/os-release

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  dnf -y install https://www.rdoproject.org/repos/rdo-release.el8.rpm
  PACKAGES="git wget python3 python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium"
  if [ "${DRIVER}" == "messaging" ]; then
    PACKAGES+=" qpid-dispatch-router"
  fi
  COMMAND="dnf -y install"
elif [[ ${ID} == "fedora" ]]; then
  PACKAGES="git wget python3 python3-ssh-python python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium"
  if [ "${DRIVER}" == "messaging" ]; then
    PACKAGES+=" qpid-dispatch-router"
  fi
  COMMAND="dnf -y install"
elif [[ ${ID} == "ubuntu" ]]; then
  sudo add-apt-repository ppa:qpid/released
  PACKAGES="git python3-all python3-venv python3-tabulate python3-zmq python3-yaml python3-jinja2 qdrouterd"
  apt update
  COMMAND="apt -y install"
else
  echo -e "Failed unknown OS"
  exit 99
fi

eval "${COMMAND} ${PACKAGES}"

RELEASE="$(get_latest_release directord/directord)"

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]] || [[ ${ID} == "fedora" ]]; then
  mkdir -p ~/directord-RPMS
  pushd ~/directord-RPMS
    rm -f rpm-bundle.tar.gz
    wget https://github.com/directord/directord/releases/download/${RELEASE}/rpm-bundle.tar.gz
    tar xf rpm-bundle.tar.gz
    RPMS=$(ls -1 *.rpm | egrep -v '(debug|src)')
  popd
  echo -e "\nDirectord is setup and installed within [ /usr/bin ]"
  echo "Activate the venv or run directord directly."
  echo "Directord can be installed as a service using the following command(s):"
  echo "/usr/bin/directord-client-systemd"
  echo -e "/usr/bin/directord-server-systemd\n"
  if [ ! -f "/etc/directord/private_keys/server.key_secret" ]; then
    directord --driver zmq server --zmq-generate-keys
  fi
else
  python3 -m venv --system-site-packages /opt/directord
  /opt/directord/bin/pip install --upgrade pip setuptools wheel
  /opt/directord/bin/pip install --upgrade directord[all]

  echo -e "\nDirectord is setup and installed within [ /opt/directord ]"
  echo "Activate the venv or run directord directly."
  echo "Directord can be installed as a service using the following command(s):"
  echo "/opt/directord/bin/directord-client-systemd"
  echo -e "/opt/directord/bin/directord-server-systemd\n"
  if [ ! -f "/etc/directord/private_keys/server.key_secret" ]; then
    /opt/directord/bin/directord --driver zmq server --zmq-generate-keys
  fi
fi

# Create basic development configuration
mkdir -p /etc/directord /etc/directord/private_keys /etc/directord/public_keys
python3 <<EOC
import yaml
try:
    with open('/etc/directord/config.yaml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    config = dict()
config["zmq_curve_encryption"] = True
config["driver"] = "${DRIVER}"
with open('/etc/directord/config.yaml', 'w') as f:
    f.write(yaml.safe_dump(config, default_flow_style=False))
EOC
