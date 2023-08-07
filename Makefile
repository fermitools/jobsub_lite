NAME = jobsub_lite
VERSION = v1.3.7
ROOTDIR = $(shell pwd)
rpmVersion := $(subst v,,$(VERSION))
BUILD_DIR = $(NAME)-$(rpmVersion)
BUILD_TAR = $(rpmVersion).tar.gz
RPMBUILD_DIR=${HOME}/rpmbuild
specfile := $(ROOTDIR)/config/spec/$(NAME).spec
versionfile := ${ROOTDIR}/lib/version.py
tarball_dirs = bin lib etc man templates config # Dirs we need for the tarball

all: tarball set-version rpm clean
.PHONY: all clean tarball set-version rpm clean-all

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
	$(foreach tbdir,$(tarball_dirs),mkdir -p $(BUILD_DIR)/$(tbdir);)
	$(foreach tbdir,$(tarball_dirs),cp -r $(ROOTDIR)/$(tbdir)/* $(BUILD_DIR)/$(tbdir);)
	tar -czf $(BUILD_TAR) $(BUILD_DIR)
	echo "Built sources tarball"

set-version:
	sed -Ei 's/Version\:[ ]*.+/Version:        $(rpmVersion)/' $(specfile)
	echo "Set version in spec file to $(rpmVersion)"
	sed -Ei 's/__version__ = \".+\"/__version__ = "$(rpmVersion)"/' $(versionfile)
	echo "Set version in version file to $(rpmVersion)"

clean:
	(test -e $(BUILD_DIR)) && (rm -Rf $(BUILD_DIR)) || echo "$(BUILD_DIR) does not exist"
	(test -e $(BUILD_TAR)) && (rm $(BUILD_TAR)) || echo "$(BUILD_TAR) does not exist"

clean-all: clean
	(test -e $(ROOTDIR)/$(NAME)-$(rpmVersion)*.rpm) && (rm $(ROOTDIR)/$(NAME)-$(rpmVersion)*.rpm)
