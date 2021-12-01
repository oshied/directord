#!/bin/bash

set -euxv

export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

SCRIPT_DIR=$(dirname $(readlink -f $0))
SSL_DIR=${1:-"/opt/directord/grpc-ssl"}

. $SCRIPT_DIR/set-ca.sh

mkdir -p ${SSL_DIR}
mkdir -p ${CA_DIR}
openssl req -x509 -subj /CN=directord-CA -days 3650 -nodes -newkey rsa:4096 -keyout ${SSL_DIR}/directord-ca.key  -out ${SSL_DIR}/directord-ca.crt
cp ${SSL_DIR}/directord-ca.key ${CA_DIR}
cp ${SSL_DIR}/directord-ca.crt ${CA_DIR}

${CA_UPDATE}
openssl x509 -checkend 0 -noout -in ${CA_DIR}/directord-ca.crt

${SCRIPT_DIR}/getcert.sh directord $SSL_DIR $(hostname)
mv $SSL_DIR/directord.crt /etc/directord/grpc/ssl/directord.crt
mv $SSL_DIR/directord.key /etc/directord/grpc/ssl/directord.key
