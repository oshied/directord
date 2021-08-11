#!/bin/bash
set -e

SCRIPT_DIR=$(dirname $(readlink -f $0))
CONTAINER_NAME=localhost/centos8-builder

buildah bud -t $CONTAINER_NAME $SCRIPT_DIR/container-build
podman run -it -v $SCRIPT_DIR:/home/builder/rpm:z $CONTAINER_NAME:latest
