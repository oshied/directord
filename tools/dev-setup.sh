#!/usr/bin/env bash
set -eo

CLONE_PATH="${1:-/opt/directord-src}"
VENV_PATH="${1:-/opt/directord}"

#!/usr/bin/env bash
set -eo

. /etc/os-release
if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  dnf -y install https://www.rdoproject.org/repos/rdo-release.el8.rpm
  PACKAGES="git python39 zeromq libsodium"
  dnf -y install ${PACKAGES}
  PYTHON_BIN=${2:-python3.9}
elif [[ ${ID} == "fedora" ]]; then
  PACKAGES="git python3 zeromq libsodium"
  dnf -y install ${PACKAGES}
  PYTHON_BIN=${2:-python3}
elif [[ ${ID} == "ubuntu" ]]; then
  PACKAGES="git python3-all python3-venv python3-zmq"
  apt update
  apt -y install ${PACKAGES}
  PYTHON_BIN=${2:-python3}
else
  echo -e "Failed unknown OS"
  exit 99
fi

# Create development workspace
rm -rf ${VENV_PATH}
${PYTHON_BIN} -m venv ${VENV_PATH}
${VENV_PATH}/bin/pip install --upgrade pip setuptools wheel bindep

BASE_PATH="$(dirname $(readlink -f ${BASH_SOURCE[0]}))"
BINDEP_PACKAGES=$(${VENV_PATH}/bin/bindep -b -f ${BASE_PATH}/bindep.txt test)
if [ ! -z "${BINDEP_PACKAGES}" ]; then
  dnf install -y ${BINDEP_PACKAGES}
fi

/opt/directord/bin/pip install --upgrade pip setuptools wheel

rm -rf ${CLONE_PATH}
git clone https://github.com/cloudnull/directord ${CLONE_PATH}
${VENV_PATH}/bin/pip install /opt/directord-src[ui,dev]

echo -e "\nDirectord is setup and installed within [ /opt/directord ]"
echo "Activate the venv or run directord directly."

if systemctl is-active directord-server &> /dev/null; then
  systemctl restart directord-server
  echo "Directord Server Restarted"
else
  echo "Directord Server can be installed as a service using the following command(s):"
  echo "/opt/directord/bin/directord-server-systemd"
fi

if systemctl is-active directord-client &> /dev/null; then
  systemctl restart directord-client
  echo "Directord Client Restarted"
else
  echo "Directord Client can be installed as a service using the following command(s):"
  echo "/opt/directord/bin/directord-client-systemd"
fi
