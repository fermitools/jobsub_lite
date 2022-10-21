import os
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
import dagnabbit

from test_unit import TestUnit


class TestDagnabbitUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    #
    # lib/dagnabbit.py tests
    #

    @pytest.mark.unit
    def test_parse_dagnabbit_dagTest(self):
        """test dagnabbit parser on old jobsub dagTest example"""
        self.do_one_dagnabbit(
            "dagTest",
            [
                "dag.dag",
                "stage_1.sh",
                "stage_2.sh",
                "stage_3.sh",
                "stage_4.sh",
                "stage_5.sh",
                "stage_1.cmd",
                "stage_2.cmd",
                "stage_3.cmd",
                "stage_4.cmd",
                "stage_5.cmd",
            ],
        )

    def do_one_dagnabbit(self, dagfile, flist):
        """test dagnabbit parser on given dagfile make sure it generates
        expected list of files"""
        varg = TestUnit.test_vargs.copy()
        dest = "/tmp/dagout{0}".format(os.getpid())
        os.mkdir(dest)
        # the dagTest uses $SUBMIT_FLAGS so make sure we set it
        os.environ[
            "SUBMIT_FLAGS"
        ] = "--resource-provides=usage_model=DEDICATED,OPPORTUNISTIC"
        os.environ["GROUP"] = TestUnit.test_group
        d1 = os.path.join("..", "..", "templates", "simple")
        # file has relative paths in it, so chdir there
        os.chdir("dagnabbit")
        varg["dag"] = 1
        varg["executable"] = f"file://{dagfile}"
        dagnabbit.parse_dagnabbit(d1, varg, dest, TestUnit.test_schedd)
        os.chdir(os.path.dirname(__file__))
        for f in flist:
            assert os.path.exists("%s/%s" % (dest, f))
        os.system("rm -rf %s" % dest)
