NAME = jobsub_lite

# In most cases, these two lines should be ALL that need to be changed
# Warning:  Make sure there is NO trailing whitespace in either of these lines!!
# Set RC to 0 for final release
VERSION = v1.6
RC = 0
### End expected changes

ROOTDIR = $(shell pwd)

rpmVersion := $(subst v,,$(VERSION))
ifeq ($(RC), 0)
rpmReleasePrefix = 1
libraryVersionSuffix =
else
rpmReleasePrefix := 0rc$(RC)
libraryVersionSuffix := -rc$(RC)
endif

BUILD_DIR = $(NAME)-$(rpmVersion)
BUILD_TAR = $(rpmVersion).tar.gz
RPMBUILD_DIR=${HOME}/rpmbuild
specfile := $(ROOTDIR)/config/spec/$(NAME).spec
versionfile := ${ROOTDIR}/lib/version.py
tarball_dirs = bin lib etc man templates config # Dirs we need for the tarball
OSR=$(shell /bin/sh -c ' . /etc/os-release; echo $$VERSION_ID | sed -e s/\..*//')




.PHONY: all clean tarball set-version rpm clean-all

ifeq ($(OSR), 7)

# we only need the tracing-rpm on SL7/EL7

all: tarball set-version tracing-rpm rpm clean
tracing-name := $(NAME)_tracing_deps
tracing-specfile := $(ROOTDIR)/config/spec/$(tracing-name).spec
tracing-rpm: NOWFILE := $(shell mktemp)
tracing-rpm: rpmSpecsDir := $(RPMBUILD_DIR)/SPECS
tracing-rpm:
	cp $(tracing-specfile) $(rpmSpecsDir)/
	cd $(rpmSpecsDir); \
	rpmbuild -ba $(tracing-name).spec
	find $(RPMBUILD_DIR)/RPMS -type f -name "$(tracing-name)*.rpm" -newer $(NOWFILE) -exec cp {} $(ROOTDIR) \;
	echo "Created RPM and copied it to current working directory"
	((test -e $(NOWFILE)) && (rm $(NOWFILE)) && echo "Cleaned up tempfile") || echo "$(NOWFILE) does not exist.  Continuing anyway"
else

all: tarball set-version rpm clean

endif

rpm: rpmSourcesDir := $(RPMBUILD_DIR)/SOURCES
rpm: rpmSpecsDir := $(RPMBUILD_DIR)/SPECS
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
	sed -Ei 's/Release\:[ ]*.+/Release:        $(rpmReleasePrefix)%{?dist}/' $(specfile)
	echo "Set version in spec file to $(rpmVersion), Release $(rpmReleasePrefix)"
	sed -Ei 's/__version__ = \".+\"/__version__ = "$(rpmVersion)$(libraryVersionSuffix)"/' $(versionfile)
	echo "Set version in version file to $(rpmVersion)$(libraryVersionSuffix)"

clean:
	(test -e $(BUILD_DIR)) && (rm -Rf $(BUILD_DIR)) || echo "$(BUILD_DIR) does not exist"
	(test -e $(BUILD_TAR)) && (rm $(BUILD_TAR)) || echo "$(BUILD_TAR) does not exist"

clean-all: clean
	(test -e $(ROOTDIR)/$(NAME)-$(rpmVersion)*.rpm) && (rm $(ROOTDIR)/$(NAME)-$(rpmVersion)*.rpm)
