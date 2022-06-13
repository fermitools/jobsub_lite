import os
import sys
import time

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
from test_unit import TestUnit 


class TestPackagesUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """

    # lib/packages.py routines

    def test_pkg_find_1(self):
        sp1 = sys.path.copy()
        packages.pkg_find("poms_client","-g poms41")
        sp2 = sys.path.copy()
        # should have changed sys.path, set POMS_CLIENT_DIR, and be importable
        assert sp1 != sp2
        assert os.path.exists(os.environ["POMS_CLIENT_DIR"])
        __import__("poms_client")

    def test_pkg_orig_env_1(self):
        packages.pkg_find("poms_client","-g poms41")
        env1 = os.environ.copy()
        packages.orig_env()
        env2 = os.environ.copy()
        # should have put the environment back
        assert env1 != env2


