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
import utils

if not os.path.exists("jobsub_submit.py"):
    os.symlink("../bin/jobsub_submit", "jobsub_submit.py")
import jobsub_submit

class TestJobsubSubmitUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """

    # jobsub_submit functions

    def test_get_basefiles_1(self):
        dlist = [ os.path.dirname(__file__) ]
        fl = jobsub_submit.get_basefiles(dlist)
        assert os.path.basename(__file__) in fl

    def test_render_files_1(self):
        srcdir = os.path.dirname(os.path.dirname(__file__)) + "/templates/dataset_dag"
        dest = "/tmp/out{0}".format(os.getpid())
        os.mkdir(dest)
        jobsub_submit.render_files(srcdir, TestUnit.test_vargs, dest)
        assert os.path.exists("%s/dagbegin.cmd" % dest)

    def test_cleanup_1(self):
        # cleanup doesn't actually do anything right now...
        jobsub_submit.cleanup("")
        assert True

    def test_do_dataset_defaults_1(self):
        varg = TestUnit.test_vargs.copy()
        varg['dataset_definition'] = 'mwmtest'
        utils.set_extras_n_fix_units(varg, TestUnit.test_schedd, "", "")
        jobsub_submit.do_dataset_defaults(varg)
        for var in ["PROJECT", "DATASET", "USER", "GROUP", "STATION"]:
            assert repr(varg["environment"]).find("SAM_%s"%var) > 0

