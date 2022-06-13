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
import utils

class TestUtilsUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """
    #
    # utils.py routines...
    #

    def test_fixquote_1(self):
        assert utils.fixquote('test1') == 'test1'
        assert utils.fixquote('test2=test3') == 'test2="test3"'
        assert utils.fixquote('test2=test3=test4') == 'test2="test3=test4"'

    def test_grep_n_1(self):
        assert utils.grep_n(r"class (\w*):", 1, __file__) == "TestUnit"
        assert utils.grep_n(r"import (\w*)", 1, __file__) == "os"

    def test_fix_unit_1(self):
        args = TestUnit.test_vargs.copy()
        memtable = {"k": 1.0 / 1024, "m": 1, "g": 1024, "t": 1024 * 1024}
        utils.fix_unit(args, "memory", memtable, -1, "b", -2)
        assert args["memory"] == 64 * 1024

    def test_get_principal_1(self):
        # blatantly assumes you have a valid principal...
        res = utils.get_principal()
        assert res.split('@')[0] == os.environ['USER']

    def test_set_extras_1(self):
        os.environ["GROUP"] = TestUnit.test_group
        proxy, token = creds.get_creds()
        args = TestUnit.test_vargs.copy()
        utils.set_extras_n_fix_units(args, TestUnit.test_schedd, proxy, token)
        assert args["user"] == os.environ["USER"]
        assert args["memory"] == 64 * 1024

