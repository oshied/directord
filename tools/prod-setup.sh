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
  PACKAGES="git wget python3 python3-ssh-python python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium python3-diskcache"
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

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]] || [[ ${ID} == "fedora" ]]; then
  mkdir -p ~/directord-RPMS
  pushd ~/directord-RPMS
    rm -f rpm-bundle.tar.gz
    wget https://github.com/cloudnull/directord/releases/download/${RELEASE}/rpm-bundle.tar.gz
    tar xf rpm-bundle.tar.gz
    RPMS=$(ls -1 *.rpm | egrep -v '(debug|src)')
    dnf -y install ${RPMS}
  popd
  echo -e "\nDirectord is setup and installed within [ /usr/bin ]"
  echo "Activate the venv or run directord directly."
  echo "Directord can be installed as a service using the following command(s):"
  echo "/usr/bin/directord-client-systemd"
  echo -e "/usr/bin/directord-server-systemd\n"
else
  python3 -m venv --system-site-packages /opt/directord
  /opt/directord/bin/pip install --upgrade pip setuptools wheel
  /opt/directord/bin/pip install directord

  echo -e "\nDirectord is setup and installed within [ /opt/directord ]"
  echo "Activate the venv or run directord directly."
  echo "Directord can be installed as a service using the following command(s):"
  echo "/opt/directord/bin/directord-client-systemd"
  echo -e "/opt/directord/bin/directord-server-systemd\n"
fi
