#!/bin/bash
set -e

ARTIFACT_DIR="build"
ARTIFACT_PATH=${ARTIFACT_PATH:-"/home/builder/rpm/$ARTIFACT_DIR"}
SPEC_PATH="/home/builder/build/directord.spec"
RELEASE_VERSION=${RELEASE_VERSION:-XXX}

sudo chown builder: /home/builder/rpm

echo "Creating artifact directory: ${ARTIFACT_DIR}"
mkdir -p ${ARTIFACT_PATH}

echo "Installing build deps..."
echo "Logging to ${ARTIFACT_DIR}/builddep.log"
sudo dnf -y builddep "${SPEC_PATH}" &> ${ARTIFACT_PATH}/builddep.log

echo "Building: ${SPEC_PATH}"
echo "Logging to ${ARTIFACT_DIR}/rpmbuild.log"
rpmbuild --undefine=_disable_source_fetch \
         --define "released_version ${RELEASE_VERSION}" \
         -ba ${SPEC_PATH} \
         --nocheck &> ${ARTIFACT_PATH}/rpmbuild.log

echo "Copying rpms to ${ARTIFACT_DIR}"
find /home/builder/build -name '*.rpm' -exec cp "{}" ${ARTIFACT_PATH} \;

# fixup permissions
USER_IDS=$(stat --format="%u:%g" ${SPEC_PATH})
sudo chown ${USER_IDS} /home/builder/rpm
sudo chown ${USER_IDS} -R ${ARTIFACT_PATH}
echo "Done!"
