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

python3 -m venv --system-site-packages /opt/director
/opt/director/bin/pip install git+https://github.com/cloudnull/director

echo -e "\nDirector is setup and installed within [ /opt/director ]"
echo "Activate the venv or run director directly."
echo "Director can be installed as a service using the following command(s):"
echo "/opt/director/bin/director-client-systemd"
echo -e "/opt/director/bin/director-server-systemd\n"
