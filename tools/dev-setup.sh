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
set -evo

VENV_PATH="${1:-${VENV_PATH:-/opt/directord}}"
PYTHON_BIN="${2:-${PYTHON_BIN:-python3.8}}"
CLONE_PATH="${3:-${CLONE_PATH-}}"
SETUP="${4:-${SETUP:-true}}"
DRIVER=${DRIVER:-zmq}

. /etc/os-release

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  dnf install -y 'dnf-command(repoquery)'
  TRIPLEO_REPOS=$(dnf --repofrompath tripleo-repo-dd,https://trunk.rdoproject.org/centos${VERSION_ID%.*}/component/tripleo/current --repo tripleo-repo-dd repoquery --location python3-tripleo-repos | grep python3-tripleo-repos)
  echo "tripleo-repos=${TRIPLEO_REPOS}"
  VERSION_INFO="${VERSION_ID%%"."*}"
  if [[ ${ID} == "rhel" ]]; then
    dnf install -y python3 ${TRIPLEO_REPOS}
    DISTRO="--no-stream --distro rhel${VERSION_INFO[0]}"
    tripleo-repos ${DISTRO} -b master current-tripleo ceph
  elif [[ ${ID} == "centos" ]]; then
    dnf install -y python3 ${TRIPLEO_REPOS}
    DISTRO="--distro centos${VERSION_INFO[0]}"
    if grep -qi "CentOS Stream" /etc/os-release; then
      DISTRO="--stream ${DISTRO}"
    else
      DISTRO="--no-stream ${DISTRO}"
    fi
    tripleo-repos ${DISTRO} -b master current-tripleo ceph
  fi
fi

if [[ ${ID} == "rhel" ]] && [[ ${DRIVER} == "messaging" ]]; then
    echo "messaging driver not yet supported with RHEL."
    exit 1
fi

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  PACKAGES="git gcc gcc-c++ python3-pyyaml zeromq libsodium"
  if [[ ${DRIVER} == "messaging" ]]; then
    PACKAGES+=" qpid-dispatch-router certmonger openssl openssl-devel python3-devel"
  fi
  if [[ ${ID} == "rhel" ]]; then
    PACKAGES+=" python38-devel"
    PYTHON_BIN=${2:-python3.8}
  else
    PACKAGES+=" python3-devel"
    PYTHON_BIN=${2:-python3}
  fi
  dnf -y install ${PACKAGES}
  CA_PATH=/etc/pki/ca-trust/source/anchors/directord-ca.crt
elif [[ ${ID} == "fedora" ]]; then
  PACKAGES="git python3-devel gcc gcc-c++ python3-pyyaml zeromq libsodium qpid-dispatch-router certmonger openssl openssl-devel python3-devel"
  dnf -y install ${PACKAGES}
  PYTHON_BIN=${2:-python3}
  CA_PATH=/etc/pki/ca-trust/source/anchors/directord-ca.crt
elif [[ ${ID} == "ubuntu" ]]; then
  export DEBIAN_FRONTEND=noninteractive
  add-apt-repository -y ppa:qpid/released
  PACKAGES="git python3-all python3-venv python3-yaml python3-zmq python3-dev qdrouterd openssl libssl-dev certmonger debhelper dh-python gcc g++ cmake swig pkg-config doxygen uuid-dev libssl-dev libsasl2-2 libsasl2-modules libsasl2-dev libjsoncpp-dev cyrus-dev python3-all-dev python3-setuptools python3 python3-dev acl"
  apt -y update
  apt -y install ${PACKAGES}
  PYTHON_BIN=${2:-python3}
  CA_PATH=/usr/local/share/ca-certificates/directord/directord-ca.crt
else
  echo -e "Failed unknown OS"
  exit 99
fi

# Create development workspace
${PYTHON_BIN} -m venv ${VENV_PATH}
${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel bindep pyyaml
${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel

if [ -z "${CLONE_PATH}" ] || [ ! -d "${CLONE_PATH}" ] ; then
  ${VENV_PATH}/bin/pip install --upgrade --pre directord[all]
else
  ${VENV_PATH}/bin/pip install --upgrade ${CLONE_PATH}[all]
fi

# Create basic development configuration
mkdir -p /etc/directord /etc/directord/private_keys /etc/directord/public_keys /etc/directord/messaging/ssl
${VENV_PATH}/bin/python3 <<EOC
import socket
import yaml
try:
    with open('/etc/directord/config.yaml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    config = dict()
config["debug"] = True
config["driver"] = "${DRIVER}"
if config["driver"] == "messaging":
    config["messaging_ssl_ca"] = "${CA_PATH}"
with open('/etc/directord/config.yaml', 'w') as f:
    f.write(yaml.safe_dump(config, default_flow_style=False))
EOC

if [ "${DRIVER}" == "zmq" ] && [ ! -f "/etc/directord/private_keys/server.key_secret" ]; then
  ${VENV_PATH}/bin/directord --driver zmq server --zmq-generate-keys
fi

if [ "${SETUP}" = true ]; then
  echo -e "\nDirectord is setup and installed within [ ${VENV_PATH} ]"
  echo "Activate the venv or run directord directly."

  if systemctl is-active directord-server &> /dev/null; then
    systemctl restart directord-server
    echo "Directord Server Restarted"
  else
    echo "Directord Server can be installed as a service using the following command(s):"
    echo "${VENV_PATH}/bin/directord-server-systemd"
  fi

  if systemctl is-active directord-client &> /dev/null; then
    systemctl restart directord-client
    echo "Directord Client Restarted"
  else
    echo "Directord Client can be installed as a service using the following command(s):"
    echo "${VENV_PATH}/bin/directord-client-systemd"
  fi
fi
