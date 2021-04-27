#!/usr/bin/env bash
set -eo

. /etc/os-release
PACKAGES="git python3 python3-paramiko python3-tenacity python3-tabulate python3-zmq python3-pyyaml python3-jinja2 zeromq libsodium"
if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]]; then
  dnf -y install https://www.rdoproject.org/repos/rdo-release.el8.rpm
else
  PACKAGES+=" python3-diskcache"
fi

dnf -y install ${PACKAGES}

python3 -m venv --system-site-packages /opt/directord
/opt/directord/bin/pip install --upgrade pip setuptools wheel
/opt/directord/bin/pip install directord

echo -e "\nDirectord is setup and installed within [ /opt/directord ]"
echo "Activate the venv or run directord directly."
echo "Directord can be installed as a service using the following command(s):"
echo "/opt/directord/bin/directord-client-systemd"
echo -e "/opt/directord/bin/directord-server-systemd\n"
