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
#
sys.path.append("../lib")
import packages


@pytest.fixture
def setup_ups(monkeypatch):
    """A fixture to set up UPS for our tests, in case it is not already set up in the test environment.
    Adapted from https://stackoverflow.com/a/3505826
    """
    env_to_add = {}

    command = shlex.split(
        "env -i bash -c 'source /cvmfs/fermilab.opensciencegrid.org/products/common/etc/setups.sh && env'"
    )
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
        # Let the test run, with the possiblity that we might fail.  The tester may have Spack, or the applicable package installed directly via RPM
        print(e)
    else:
        for env_key, env_value in env_to_add.items():
            monkeypatch.setenv(env_key, env_value)
    finally:
        yield
        for env_key in env_to_add.keys():
            monkeypatch.delenv(env_key)


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
