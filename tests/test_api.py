# pylint: disable=line-too-long
import os
import pytest
import re
import sys
import time

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

from jobsub_api import jobsub_call, jobsub_submit_re, jobsub_q_re


def test_api_demo():
    group = "fermilab"
    out1 = jobsub_call(
        ["jobsub_submit", "-G", group, "file://./job_scripts/lookaround.sh"], True
    )
    m1 = jobsub_submit_re.search(out1)
    if m1:
        jobid = m1.group("jobid")

        time.sleep(1)

        out2 = jobsub_call(["jobsub_q", "-G", group, jobid], True)
        for line in out2.split("\n")[1:]:
            m = jobsub_q_re.search(line)
            if m:
                print(f"saw job {m.group('jobid')} command {m.group('command')}")
    else:
        print("submission failed: output:\n", out1)


from jobsub_api import submit, q


def test_fancy_api_demo():
    group = "fermilab"
    try:
        job1 = submit(group=group, executable="job_scripts/lookaround.sh", verbose=1)
        qjobs = q(job1.jobid(), group=group)
        for qjob in qjobs:
            print(f"saw job {qjob.jobid()} status {qjob.status} ")
        rs = job1.fetchlog(destdir="/tmp/test_fetch", verbose=1)
        print(f"fetchlog says: {rs}")
    except RuntimeError:
        raise
