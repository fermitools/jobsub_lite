NAME = jobsub_lite
VERSION = v0.5.3
ROOTDIR = $(shell pwd)
rpmVersion := $(subst v,,$(VERSION))
BUILD_DIR = /tmp/$(NAME)-$(rpmVersion)
BUILD_TAR = /tmp/$(rpmVersion).tar.gz
RPMBUILD_DIR=${HOME}/rpmbuild
specfile := $(ROOTDIR)/config/spec/$(NAME).spec
versionfile := ${ROOTDIR}/lib/version.py
tarball_dirs = bin lib etc templates config # Dirs we need for the tarball

all: tarball set-version rpm
.PHONY: all clean tarball set-version rpm

rpm: rpmSourcesDir := $(RPMBUILD_DIR)/SOURCES
rpm: rpmSpecsDir := $(RPMBUILD_DIR)/SPECS
rpm: rpmDir := ${RPMBUILD}/RPMS/x86_64/
rpm: set-version tarball
	cp $(specfile) $(rpmSpecsDir)/
	cp $(BUILD_TAR) $(rpmSourcesDir)/
	cd $(rpmSpecsDir); \
	rpmbuild -ba $(NAME).spec
	find $(RPMBUILD_DIR)/RPMS -type f -name "$(NAME)-$(rpmVersion)*.rpm" -exec cp {} $(ROOTDIR) \;
	echo "Created RPM and copied it to current working directory"

tarball: set-version
	# cp -r $(ROOTDIR) $(BUILD_DIR)
	# cp -r $(ROOTDIR)/bin $(BUILD_DIR)/bin
	# cp -r $(ROOTDIR)/lib $(BUILD_DIR)/lib
	# cp -r $(ROOTDIR)/etc $(BUILD_DIR)/etc
	# cp -r $(ROOTDIR)/man $(BUILD_DIR)/man
	# cp -r $(ROOTDIR)/templates $(BUILD_DIR)/templates
	# cp -r $(ROOTDIR)/config $(BUILD_DIR)/config
	cp -r $(foreach tbdir,$(tarball_dirs),$(ROOTDIR)/$(tbdir) $(BUILD_DIR)/$(tbdir))
	tar -czf $(BUILD_TAR) $(BUILD_DIR)
	echo "Built sources tarball"

set-version:
	sed -Ei 's/Version\:[ ]*.+/Version:        $(rpmVersion)/' $(specfile)
	echo "Set version in spec file to $(rpmVersion)"
	sed -Ei 's/__version__ = \".+\"/__version__ = "$(VERSION)"' $(versionfile)
	echo "Set version in version file to $(VERSION)"
