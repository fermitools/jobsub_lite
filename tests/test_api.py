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
    testdir = os.path.dirname(__file__)
    out1 = jobsub_call(
        ["jobsub_submit", "-G", group, f"file://{testdir}/job_scripts/lookaround.sh"],
        True,
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


def test_fancy_api_demo(tmp_path):
    group = "fermilab"
    testdir = os.path.dirname(__file__)
    try:
        # Submit a job. submit will raise if it doesn't succeed, so we don't need to assert success
        job1 = submit(
            group=group, executable=f"{testdir}/job_scripts/lookaround.sh", verbose=1
        )
        print(f"submitted job: {job1.id}")
        print(f"submit output:\n=-=-=-=-=\n {job1.submit_out}")
        print(f"\n=-=-=-=-=\n")

        # Ensure that we can find the job in the queue
        qjobs = q(job1.id, group=group)
        assert len(qjobs) == 1  # We should have gotten only one job back
        assert (
            qjobs[0].id == job1.id
        )  # We should have gotten only an identical job to job1 back
        for qjob in qjobs:
            print(f"saw job {qjob.id} status {str(qjob.status)} ")

        # Make sure that we can fetch job1's log
        dest = tmp_path
        rs = job1.fetchlog(destdir=str(dest.absolute()), verbose=1)
        print(f"fetchlog says: {rs}")
        want_file_path = dest / "lookaround.sh"
        assert want_file_path.exists()

        # Make sure we can see the long form of the job's classad
        data = job1.q_long()
        print(f"after update, status: {str(job1.status)}")
        assert "ClusterId" in data
    except RuntimeError as e:
        print(f"failure: {repr(e)}")
        raise
