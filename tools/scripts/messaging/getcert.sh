#!/bin/bash

set -euxv

export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

SCRIPT_DIR=$(dirname $(readlink -f $0))
CERT_NAME=${CERT_NAME:-$1}
CERT_DIR=${CERT_DIR:-$2}
CERT_CN=${CERT_CN:-$3}

. $SCRIPT_DIR/set-ca.sh

openssl req -new -subj /CN=${CERT_CN} -days 3650 -nodes -newkey rsa:4096 -keyout ${CERT_DIR}/${CERT_NAME}.key -out ${CERT_DIR}/${CERT_NAME}.csr
openssl x509 -req -CA ${CA_CRT} -CAkey ${CA_KEY} -in ${CERT_DIR}/${CERT_NAME}.csr -out ${CERT_DIR}/${CERT_NAME}.crt -days 3650 -CAcreateserial
