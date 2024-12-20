import os
import shlex
import subprocess
import sys
import pytest

#
# we assume everwhere our current directory is in the package
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))


#
# import modules we need to test, since we chdir()ed, can use relative path
# unless we're testing installed, then use /opt/jobsub_lite/...
#
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    sys.path.append("/opt/jobsub_lite/lib")
else:
    sys.path.append("../lib")

import packages


@pytest.fixture
def setup_ups(monkeypatch):
    """A fixture to set up UPS for our tests, in case it is not already set up in the test environment.
    Adapted from https://stackoverflow.com/a/3505826
    """
    ups_setup_script_locations = [
        "/cvmfs/fermilab.opensciencegrid.org/products/common/etc/setups.sh",
    ]
    env_to_add = {}

    for setup_script_location in ups_setup_script_locations:
        command = shlex.split(f"env -i bash -c 'source {setup_script_location} && env'")
        print(f"Trying to set up UPS from {setup_script_location}")
        try:
            source_proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            for line in source_proc.stdout:
                (env_key, _, env_value) = line.decode().partition("=")
                env_to_add[env_key] = env_value
            source_proc.communicate()
            if source_proc.returncode:
                raise OSError(
                    "Could not set up UPS in environment.  Any unit test using this fixture might fail."
                )
        except Exception as e:
            # We're OK with an exception being raised, since we can just try the next setup script location
            print(e)
        else:
            for env_key, env_value in env_to_add.items():
                monkeypatch.setenv(env_key, env_value)
            break

    # No matter whether or not we were able to set the env, let the test run, with the possiblity that we might fail.
    # The tester may have Spack, or the applicable package installed directly via RPM
    yield
    for env_key in env_to_add.keys():
        try:
            monkeypatch.delenv(env_key)
        except:
            pass


class TestPackagesUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    # lib/packages.py routines

    @pytest.mark.unit
    def test_pkg_find_1(self, setup_ups):
        """make sure we can find the poms_client ups package"""
        sp1 = sys.path.copy()
        packages.pkg_find("poms_client", "-g poms41")
        sp2 = sys.path.copy()
        # should have changed sys.path, set POMS_CLIENT_DIR, and be importable
        assert sp1 != sp2
        assert os.path.exists(os.environ["POMS_CLIENT_DIR"])
        __import__("poms_client")

    @pytest.mark.unit
    def test_pkg_orig_env_1(self, setup_ups):
        """make sure orig_env puts the environment back"""
        packages.pkg_find("poms_client", "-g poms41")
        env1 = os.environ.copy()
        packages.orig_env()
        env2 = os.environ.copy()
        # should have put the environment back
        assert env1 != env2


@pytest.mark.unit
def test_add_to_SAVED_ENV_if_not_empty():
    """This test tests the add_to_SAVED_ENV_if_not_empty function, which governs access to packages.SAVED_ENV"""
    # Test when SAVED_ENV is empty
    packages.SAVED_ENV = {}
    packages.add_to_SAVED_ENV_if_not_empty("key", "value")
    assert packages.SAVED_ENV == {}

    # Test when SAVED_ENV is not empty
    packages.SAVED_ENV = {"existing_key": "existing_value"}
    packages.add_to_SAVED_ENV_if_not_empty("new_key", "new_value")
    assert packages.SAVED_ENV == {
        "existing_key": "existing_value",
        "new_key": "new_value",
    }
