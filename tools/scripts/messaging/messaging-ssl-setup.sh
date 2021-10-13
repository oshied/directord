#!/bin/bash

set -euxv

export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

SCRIPT_DIR=$(dirname $(readlink -f $0))
SSL_DIR=${1:-"/opt/directord/messaging-ssl"}

. $SCRIPT_DIR/set-ca.sh

mkdir -p ${SSL_DIR}
mkdir -p ${CA_DIR}
openssl req -x509 -subj /CN=directord-CA -days 3650 -nodes -newkey rsa:4096 -keyout ${SSL_DIR}/directord-ca.key  -out ${SSL_DIR}/directord-ca.crt
cp ${SSL_DIR}/directord-ca.key ${CA_DIR}
cp ${SSL_DIR}/directord-ca.crt ${CA_DIR}

${CA_UPDATE}
openssl x509 -checkend 0 -noout -in ${CA_DIR}/directord-ca.crt

${SCRIPT_DIR}/getcert.sh directord $SSL_DIR $(hostname)
mv $SSL_DIR/directord.crt /etc/directord/messaging/ssl/directord.crt
mv $SSL_DIR/directord.key /etc/directord/messaging/ssl/directord.key
${SCRIPT_DIR}/getcert.sh qdrouterd $SSL_DIR $(hostname)
mv $SSL_DIR/qdrouterd.crt /etc/qpid-dispatch/qdrouterd.crt
mv $SSL_DIR/qdrouterd.key /etc/qpid-dispatch/qdrouterd.key
chown qdrouterd: /etc/qpid-dispatch/qdrouterd.crt
chown qdrouterd: /etc/qpid-dispatch/qdrouterd.key

cp /opt/directord/share/directord/tools/config/messaging/qdrouterd.conf /etc/qpid-dispatch/qdrouterd.conf
# Fix path to CA for ubuntu
sed -i "s#/etc/pki/ca-trust/source/anchors/directord-ca.pem#${CA_CRT}#g" /etc/qpid-dispatch/qdrouterd.conf
setfacl -m u:qdrouterd:r /etc/directord/messaging/ssl/*
systemctl enable qdrouterd
systemctl restart qdrouterd
