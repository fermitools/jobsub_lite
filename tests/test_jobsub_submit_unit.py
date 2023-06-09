import os
import sys

import pytest
from jinja2 import exceptions

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

import utils

from test_unit import TestUnit

try:
    os.unlink("jobsub_submit.py")
except:
    pass
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    if not os.path.exists("jobsub_submit.py"):
        os.symlink("/opt/jobsub_lite/bin/jobsub_submit", "jobsub_submit.py")
else:
    if not os.path.exists("jobsub_submit.py"):
        os.symlink("../bin/jobsub_submit", "jobsub_submit.py")
import jobsub_submit


class TestJobsubSubmitUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    # jobsub_submit functions

    @pytest.mark.unit
    def test_get_basefiles_1(self):
        """test the get_basefiles routine on our source directory,
        we should be in it"""
        dlist = [os.path.dirname(__file__)]
        fl = jobsub_submit.get_basefiles(dlist)
        assert os.path.basename(__file__) in fl

    @pytest.mark.unit
    def test_render_files_1(self):
        """test render files on the dataset_dag directory"""
        if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
            srcdir = "/opt/jobsub_lite/templates/dataset_dag"
        else:
            srcdir = (
                os.path.dirname(os.path.dirname(__file__)) + "/templates/dataset_dag"
            )
        dest = "/tmp/out{0}".format(os.getpid())
        os.mkdir(dest)
        args = {**TestUnit.test_vargs, **TestUnit.test_extra_template_args}
        args["outdir"] = dest
        args["proxy"] = "/fake/proxy/path"
        jobsub_submit.render_files(srcdir, args, dest)
        assert os.path.exists("%s/dagbegin.cmd" % dest)

    @pytest.mark.unit
    def test_render_files_dd_flags(self):
        """make sure --dd-percentage and --dd-extra-dataset values get into sambegin.sh"""
        if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
            srcdir = "/opt/jobsub_lite/templates/dataset_dag"
        else:
            srcdir = (
                os.path.dirname(os.path.dirname(__file__)) + "/templates/dataset_dag"
            )
        dest = "/tmp/out{0}".format(os.getpid())
        os.mkdir(dest)
        args = {**TestUnit.test_vargs, **TestUnit.test_extra_template_args}
        args["outdir"] = dest
        args["proxy"] = "/fake/proxy/path"
        args["dd_percentage"] = 33
        args["dd_extra_dataset"] = ["dataset1", "dataset2"]
        jobsub_submit.render_files(srcdir, args, dest)
        found_percent = False
        found_extra_dataset = False
        with open("%s/sambegin.sh" % dest, "r") as fin:
            for line in fin.readlines():
                if line.find("* 33 / 100") >= 0:
                    found_percent = True
                if line.find("for SAM_DATASET in $SAM_DATASET dataset1 dataset2") >= 0:
                    found_extra_dataset = True
        assert found_percent and found_extra_dataset

    @pytest.mark.unit
    def test_render_files_undefined_vars(self, tmp_path):
        """Test rendering files when a template variable is undefined.
        Should raise jinja2.exceptions.UndefinedError
        """
        test_vargs = {}
        if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
            srcdir = "/opt/jobsub_lite/templates/simple"
        else:
            srcdir = os.path.dirname(os.path.dirname(__file__)) + "/templates/simple"
        dest = tmp_path
        args = {**TestUnit.test_vargs, **TestUnit.test_extra_template_args}
        with pytest.raises(exceptions.UndefinedError, match="is undefined"):
            jobsub_submit.render_files(srcdir, args, dest)

    @pytest.mark.unit
    def test_do_dataset_defaults_1(self):
        """make sure do_dataset_defaults sets arguments its supposed to"""
        varg = TestUnit.test_vargs.copy()
        varg["dataset_definition"] = "mwmtest"
        utils.set_extras_n_fix_units(varg, TestUnit.test_schedd, "", "")
        jobsub_submit.do_dataset_defaults(varg)
        for var in ["PROJECT", "DATASET", "USER", "GROUP", "STATION"]:
            assert repr(varg["environment"]).find("SAM_%s" % var) > 0
