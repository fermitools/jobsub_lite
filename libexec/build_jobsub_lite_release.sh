#!/bin/sh

PRODUCT=jobsub_lite

usage() {
	echo "Usage:  build_jobsub_lite_release.sh <RELEASE_NUMBER>"
	echo
	echo "Builds the jobsub_lite release RPM using the specfile in the jobsub_lite repository directory."
	echo "This script assumes that it is being run from the directory it is installed in.  It also assumes"
	echo "the following directory structure:"
	echo "."
	echo "|- build_jobsub_lite_release.sh  (this script)"
	echo "|- jobsub_lite/ (directory that contains the jobsub_lite repository)"
	echo "|- rpmbuild/ (directory to build the RPM)"
	echo "	  |- BUILD"
	echo "	  |- BUILDROOT"
	echo "	  |- RPMS"
	echo "	  |- SOURCES"
	echo "	  |- SPECS"
	echo "	  |- SRPMS"
	echo
	echo "The RPM will be built and copied to the current working directory"
	echo "-h      Print this message and exit"
	exit 0
}

if [ $# -ne 1 ]; then
	usage
fi

RELEASE=$1

if [ "$RELEASE" = "-h" ]; then
	usage
fi

START_DIR=$PWD
REPO_DIR=${START_DIR}/${PRODUCT}
SPEC_PATH=${REPO_DIR}/config/spec/jobsub_lite.spec

BUILD_DIR=${PRODUCT}-${RELEASE}
BUILD_TAR=${RELEASE}.tar.gz

RPMBUILD_DIR=${START_DIR}/rpmbuild

# Main
set -e

cd $START_DIR
cp -r $REPO_DIR $BUILD_DIR
tar -cvf $BUILD_TAR $BUILD_DIR
mv $BUILD_TAR $RPMBUILD_DIR/SOURCES/
cp ${SPEC_PATH} ${RPMBUILD_DIR}/SPECS/
cd ${RPMBUILD_DIR}/SPECS/

rpmbuild -ba ${PRODUCT}.spec
find ${RPMBUILD_DIR}/RPMS -type f -name "${PRODUCT}-${RELEASE}*.rpm" -exec cp {} ${START_DIR} \;
cd ${START_DIR}

rm -Rf $BUILD_DIR
exit $?
