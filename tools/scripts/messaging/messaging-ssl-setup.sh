#!/bin/bash

set -eux

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

getcert stop-tracking --keyfile /tmp/directord-server.key --certfile /tmp/directord-server.crt || true
getcert request --ca local --wait --wait-timeout 60 --keyfile /tmp/directord-server.key --certfile /tmp/directord-server.crt
mv /tmp/directord-server.key /etc/directord/messaging/ssl/directord-server.key
mv /tmp/directord-server.crt /etc/directord/messaging/ssl/directord-server.crt
getcert stop-tracking --keyfile /tmp/directord-client.key --certfile /tmp/directord-client.crt || true
getcert request --ca local --wait --wait-timeout 60 --keyfile /tmp/directord-client.key --certfile /tmp/directord-client.crt
mv /tmp/directord-client.key /etc/directord/messaging/ssl/directord-client.key
mv /tmp/directord-client.crt /etc/directord/messaging/ssl/directord-client.crt

cp /opt/directord/share/directord/tools/config/messaging/qdrouterd.conf /etc/qpid-dispatch/qdrouterd.conf
# Fix path to CA for ubuntu
sed -i "s#/etc/pki/ca-trust/source/anchors/cm-local-ca.pem#${CA_PATH}#g" /etc/qpid-dispatch/qdrouterd.conf
setfacl -m u:qdrouterd:r /etc/directord/messaging/ssl/*
systemctl enable qdrouterd
systemctl restart qdrouterd
