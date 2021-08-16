#!/usr/bin/env bash
if [[ $UID != 0 ]]; then
    echo "Please run this script with sudo:"
    echo "sudo $0 $*"
    exit 1
fi

set -eo

function get_latest_release() {                                                                                                                                                                                                                                130 ↵
  curl --silent "https://api.github.com/repos/$1/releases/latest" | # Get latest release from GitHub api
    grep '"tag_name":' |                                            # Get tag line
    sed -E 's/.*"([^"]+)".*/\1/'                                    # Pluck JSON value
}

. /etc/os-release
if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  dnf -y install https://www.rdoproject.org/repos/rdo-release.el8.rpm
  PACKAGES="git wget python3 python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium"
  COMMAND="dnf -y install"
  eval "${COMMAND} ${PACKAGES}"
elif [[ ${ID} == "fedora" ]]; then
  PACKAGES="git wget python3 python3-ssh2-python python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium python3-diskcache"
  COMMAND="dnf -y install"
  eval "${COMMAND} ${PACKAGES}"
elif [[ ${ID} == "ubuntu" ]]; then
  PACKAGES="git python3-all python3-venv python3-tabulate python3-zmq python3-yaml python3-jinja2"
  apt update
  COMMAND="apt -y install"
  eval "${COMMAND} ${PACKAGES}"
else
  echo -e "Failed unknown OS"
  exit 99
fi

RELEASE="$(get_latest_release cloudnull/directord)"

mkdir -p ~/directord-RPMS
pushd ~/directord-RPMS
  for item in python3-directord-0.7.3-1.el8.noarch.rpm python3-diskcache-5.2.1-1.el8.noarch.rpm python3-ssh2-python-0.26.0-1.el8.x86_64.rpm; do
    wget https://github.com/cloudnull/directord/releases/download/${RELEASE}/${item}
  done
  eval "${COMMAND} *.rpm"
popd

echo -e "\nDirectord is setup and installed within [ /usr/bin ]"
echo "Activate the venv or run directord directly."
echo "Directord can be installed as a service using the following command(s):"
echo "/usr/bin/directord-client-systemd"
echo -e "/usr/bin/directord-server-systemd\n"
