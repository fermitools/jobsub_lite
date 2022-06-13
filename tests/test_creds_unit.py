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
import creds
from test_unit import TestUnit 

class TestCredUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """

    # lib/creds.py routines...

    def test_get_creds_1(self):
        # to actually submit we do need creds, and our group set...
        os.environ["GROUP"] = TestUnit.test_group
        creds.get_creds()
        assert os.path.exists(os.environ["X509_USER_PROXY"])
        assert os.path.exists(os.environ["BEARER_TOKEN_FILE"])

