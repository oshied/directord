#!/bin/bash

set -euxv

export PS4='+(${BASH_SOURCE}:${LINENO}): ${FUNCNAME[0]:+${FUNCNAME[0]}(): }'

CERT_NAME=${CERT_NAME:-$1}
CERT_DIR=${CERT_DIR:-$2}
CERT_CN=${CERT_CN:-$3}

getcert stop-tracking --keyfile /${CERT_DIR}/${CERT_NAME}.key --certfile /${CERT_DIR}/${CERT_NAME}.crt || true
getcert request --ca local --wait --wait-timeout 60 --keyfile /${CERT_DIR}/${CERT_NAME}.key --certfile /${CERT_DIR}/${CERT_NAME}.crt --subject-name ${CERT_CN}
