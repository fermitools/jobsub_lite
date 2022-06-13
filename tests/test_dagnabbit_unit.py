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
import get_parser
import dagnabbit


class TestDagnabbitUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """

    #
    # lib/dagnabbit.py tests
    #

    def test_parse_dagnabbit_1(self):
        self.do_one_dagnabbit("dagTest", ["dag.dag", "stage_1.sh", "stage_2.sh", "stage_3.sh", "stage_4.sh", "stage_5.sh", "stage_1.cmd", "stage_2.cmd", "stage_3.cmd", "stage_4.cmd", "stage_5.cmd"])

    def do_one_dagnabbit(self, dagfile, flist):
        varg = TestUnit.test_vargs.copy()
        dest = "/tmp/dagout{0}".format(os.getpid())
        os.environ['SUBMIT_FLAGS'] = '--resource-provides=usage_model=DEDICATED,OPPORTUNISTIC'
        os.environ["GROUP"] = TestUnit.test_group
        os.mkdir(dest)
        d1 = os.path.join("..","..", "templates", "simple")
        os.chdir("dagnabbit")
        varg["dag"] = dagfile
        dagnabbit.parse_dagnabbit(d1, varg, dest, TestUnit.test_schedd)
        os.chdir(os.path.dirname(__file__))
        os.system("ls %s" % dest)
        for f in flist :
            assert os.path.exists("%s/%s" % (dest, f))
        os.system("rm -rf %s" % dest)
        
