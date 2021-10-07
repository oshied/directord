#!/bin/bash

set -euxv

export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

SCRIPT_DIR=$(dirname $(readlink -f $0))

. /etc/os-release

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]] || {{ ${ID} == "fedora" }}; then
  CA_PATH=/etc/pki/ca-trust/source/anchors/cm-local-ca.pem
  CA_UPDATE="update-ca-trust extract"
elif [[ ${ID} == "ubuntu" ]]; then
  CA_PATH=/usr/local/share/ca-certificates/directord/cm-local-ca.pem
  CA_UPDATE="update-ca-certificates"
fi

systemctl enable certmonger.service
systemctl restart certmonger.service
timeout 10 bash -c "while ! ls /var/lib/certmonger/local/creds; do sleep 1; done"

mkdir -p $(dirname ${CA_PATH})
openssl pkcs12 -in /var/lib/certmonger/local/creds -out ${CA_PATH} -nokeys -nodes -passin pass:''
chmod 0644 ${CA_PATH}
${CA_UPDATE}
openssl x509 -checkend 0 -noout -in ${CA_PATH}

${SCRIPT_DIR}/getcert.sh directord /tmp $(hostname)
mv /tmp/directord.crt /etc/directord/messaging/ssl/directord.crt
mv /tmp/directord.key /etc/directord/messaging/ssl/directord.key
${SCRIPT_DIR}/getcert.sh qdrouterd /tmp $(hostname)
mv /tmp/qdrouterd.crt /etc/qpid-dispatch/qdrouterd.crt
mv /tmp/qdrouterd.key /etc/qpid-dispatch/qdrouterd.key
chown qdrouterd: /etc/qpid-dispatch/qdrouterd.crt
chown qdrouterd: /etc/qpid-dispatch/qdrouterd.key

cp /opt/directord/share/directord/tools/config/messaging/qdrouterd.conf /etc/qpid-dispatch/qdrouterd.conf
# Fix path to CA for ubuntu
sed -i "s#/etc/pki/ca-trust/source/anchors/cm-local-ca.pem#${CA_PATH}#g" /etc/qpid-dispatch/qdrouterd.conf
setfacl -m u:qdrouterd:r /etc/directord/messaging/ssl/*
systemctl enable qdrouterd
systemctl restart qdrouterd
