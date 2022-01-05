#!/usr/bin/env bash

set -ev

SCRIPT_DIR=$(dirname $(readlink -f $0))
PROJECT_ROOT=$(dirname ${SCRIPT_DIR})

container_bin=$(command -v podman || command -v docker)
if [[ ${?} != 0 ]]; then
  echo "FAILURE: Neither docker nor podman is installed or in the current PATH."
  exit 99
fi

pushd ${PROJECT_ROOT}
  NAME="${PWD##*/}"
  pushd ../
    tar -czf /tmp/directord.tar.gz "${NAME}"
    mv /tmp/directord.tar.gz "${PROJECT_ROOT}/contrib/container-build/"
  popd

  eval ${container_bin} build -t directord-builder -f ${PROJECT_ROOT}/contrib/container-build/Containerfile ${PROJECT_ROOT}/contrib/container-build

  RELEASE_VERSION=$(awk -F'"' '/version/ {print $2}' ${PROJECT_ROOT}/directord/meta.py)
  eval ${container_bin} run --env RELEASE_VERSION="${RELEASE_VERSION}" --net=host -v ${PROJECT_ROOT}/contrib:/home/builder/rpm:Z directord-builder
popd
