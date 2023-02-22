import os
import re
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
    _old_path = os.environ["PATH"]
    os.environ["PATH"] = f"/opt/jobsub_lite/bin:{_old_path}"
else:
    sys.path.append("../lib")
    _old_path = os.environ["PATH"]
    os.environ["PATH"] = f"../bin:{_old_path}"
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

    @pytest.mark.unit
    def test_parse_dagnabbit_dagTest6(self):
        """test dagnabbit parser on old jobsub dagTest example"""
        self.do_one_dagnabbit(
            "dagTest6",
            [
                "dag.dag",
                "stage_1.sh",
                "stage_2.sh",
                "stage_3.sh",
                "stage_4.sh",
                "stage_5.sh",
                "stage_6.sh",
                "stage_1.cmd",
                "stage_2.cmd",
                "stage_3.cmd",
                "stage_4.cmd",
                "stage_6.cmd",
            ],
            {
                "dag.dag": "PARENT stage_1 CHILD stage_2 stage_3",
                "dag.dag": "PARENT stage_2 stage_5 CHILD stage_6",
                "stage_1.sh": "ln .0 stage_1.sh",
                "stage_6.sh": "ln .0 stage_6.sh",
            },
        )

    @pytest.mark.unit
    def test_parse_dagnabbit_dagTest7(self):
        """test dagnabbit parser on old jobsub dagTest example"""
        self.do_one_dagnabbit(
            "dagTest7",
            [
                "dag.dag",
                "stage_1.sh",
                "stage_2.sh",
                "stage_3.sh",
                "stage_4.sh",
                "stage_5.sh",
                "stage_6.sh",
                "stage_1.cmd",
                "stage_2.cmd",
                "stage_3.cmd",
                "stage_4.cmd",
                "stage_6.cmd",
            ],
            {
                "dag.dag": "PARENT stage_1 CHILD stage_2 stage_4 stage_6",
                "dag.dag": "PARENT stage_3 stage_5 stage_7 CHILD stage_8",
                "stage_1.sh": "ln .0 stage_1.sh",
                "stage_6.sh": "ln .0 stage_6.sh",
            },
        )

    @pytest.mark.unit
    def test_parse_dagnabbit_collapse_H(self):
        """test dagnabbit parser collapsing project.py duplicated stage dags"""
        self.do_one_dagnabbit(
            "dagTestH",
            [
                # we should have scripts/cmd files for stages 1,2,12
                "dag.dag",
                "stage_1.sh",
                "stage_2.sh",
                "stage_12.sh",
            ],
            {
                # our stage_3..11 should all use stage_2.cmd
                "dag.dag": "JOB stage_3 stage_2.cmd",
                "dag.dag": "JOB stage_4 stage_2.cmd",
                "dag.dag": "JOB stage_11 stage_2.cmd",
            },
            [
                # we should NOT have scripts/cmd files for stages 3..11
                "stage_3.cmd",
                "stage_3.sh",
                "stage_4.cmd",
                "stage_4.sh",
                "stage_11.cmd",
                "stage_11.sh",
            ],
        )

    def do_one_dagnabbit(self, dagfile, flist, check4={}, fnotlist=[]):
        """test dagnabbit parser on given dagfile make sure it generates
        expected list of files"""
        varg = TestUnit.test_vargs.copy()
        dest = "/tmp/dagout{0}".format(os.getpid())
        if os.path.exists(dest):
            os.system("rm -rf %s" % dest)
        os.mkdir(dest)
        # the dagTest uses $SUBMIT_FLAGS so make sure we set it
        os.environ[
            "SUBMIT_FLAGS"
        ] = "--resource-provides=usage_model=DEDICATED,OPPORTUNISTIC"
        os.environ["JOBSUB_EXPORTS"] = "--mail-on-error"
        os.environ["GROUP"] = TestUnit.test_group
        if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
            d1 = "/opt/jobsub_lite/templates/simple"
        else:
            d1 = os.path.join("..", "..", "templates", "simple")
        # file has relative paths in it, so chdir there
        os.chdir(f"{os.path.dirname(__file__)}/dagnabbit")
        varg["dag"] = 1
        varg["executable"] = f"file://{dagfile}"
        dagnabbit.parse_dagnabbit(d1, varg, dest, TestUnit.test_schedd)
        os.chdir(os.path.dirname(__file__))

        for f in flist:
            assert os.path.exists(f"{dest}/{f}")

        for f in fnotlist:
            assert not os.path.exists(f"{dest}/{f}")

        for f, regexp in check4.items():
            with open(f"{dest}/{f}", "r") as fd:
                data = fd.read()
                assert re.search(regexp, data)

        os.system("rm -rf %s" % dest)
