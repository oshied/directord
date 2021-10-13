#!/bin/bash

set -eux

. /etc/os-release

if [[ ${ID} == "rhel" ]] || [[ ${ID} == "centos" ]] || [[ ${ID} == "fedora" ]]; then
  CA_DIR=/etc/pki/ca-trust/source/anchors
  CA_UPDATE="update-ca-trust extract"
elif [[ ${ID} == "ubuntu" ]]; then
  CA_DIR=/usr/local/share/ca-certificates/directord
  CA_UPDATE="update-ca-certificates"
fi

CA_CRT=${CA_DIR}/directord-ca.crt
CA_KEY=${CA_DIR}/directord-ca.key
