#!/usr/bin/env bash
set -eo

VENV_PATH="${1:-/opt/directord}"
PYTHON_BIN=${2:-python3}

# OS Detect
. /etc/os-release
if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  # Install lynx from the powertools repo
  if ! which lynx; then
    if ! dnf -y install lynx; then
      dnf -y install http://mirror.centos.org/centos/8/PowerTools/x86_64/os/Packages/lynx-2.8.9-2.el8.x86_64.rpm \
                     http://mirror.centos.org/centos/8/BaseOS/x86_64/os/Packages/centos-indexhtml-8.0-0.el8.noarch.rpm
    fi
  fi
  TRIPLEO_REPOS=$(lynx -dump -hiddenlinks=listonly https://trunk.rdoproject.org/centos8/component/tripleo/current/ | awk '/python3-tripleo-repos.*rpm$/ {print $2}')
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

# Python is required for our application
# Zeromq is for messaging
# Libsodium is for ZMQ encryption
dnf install -y zeromq libsodium

# Create development workspace
${PYTHON_BIN} -m venv ${VENV_PATH}
${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel bindep

# development packages
BASE_PATH="$(dirname $(readlink -f ${BASH_SOURCE[0]}))"
dnf install -y $(${VENV_PATH}/bin/bindep -b -f ${BASE_PATH}/bindep.txt test) python3
if [[ -f "${BASE_PATH}/../setup.py" ]]; then
  ${VENV_PATH}/bin/pip install "${BASE_PATH}/../[ui,dev]"
else
  rm -rf /opt/directord-src
  git clone https://github.com/cloudnull/directord /opt/directord-src
  ${VENV_PATH}/bin/pip install /opt/directord-src[ui,dev]
fi

echo -e "\nDirectord is setup and installed within [ ${VENV_PATH} ]"
echo "Activate the venv or run directord directly."
echo "Directord can be installed as a service using the following command(s):"
echo "${VENV_PATH}/bin/directord-client-systemd"
echo -e "${VENV_PATH}/bin/directord-server-systemd\n"
