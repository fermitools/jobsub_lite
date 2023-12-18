import os
import re
import glob
import inspect
import pytest
import sys
import time
import subprocess
import tempfile
import shutil

#
# we assume everwhere our current directory is in the package
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))

#
# add to path what we eed to test
# unless we're testing installed, then use /opt/jobsub_lite/...
#
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    sys.path.append("/opt/jobsub_lite/lib")
else:
    sys.path.append("../lib")

import fake_ifdh

if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    os.environ["PATH"] = "/opt/jobsub_lite/bin:" + os.environ["PATH"]
else:
    os.environ["PATH"] = (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        + "/bin:"
        + os.environ["PATH"]
    )


@pytest.fixture
def add_links():
    # add symlink and harlink in dagnabbit directory for tarfile tests
    os.system("/bin/pwd")
    f = "dagnabbit/jobA.sh"
    slf = "dagnabbit/test_symlink"
    hlf = "dagnabbit/test_hardlink"
    if not os.path.exists(slf):
        os.symlink("jobA.sh", slf)
    if not os.path.exists(hlf):
        os.link(f, str(hlf))
    return True


@pytest.fixture
def job_envs():
    os.environ["IFDH_DEBUG"] = "1"
    os.environ["IFDH_FORCE"] = "https"
    os.environ["IFDH_VERSION"] = "v2_6_10,ifdhc_config v2_6_15"
    os.environ["IFDH_TOKEN_ENABLE"] = "1"
    os.environ["IFDH_PROXY_ENABLE"] = "0"
    os.environ["IFDH_CP_MAXRETRIES"] = "2"
    os.environ["VERSION"] = "v1_1"
    if os.environ.get("_condor_COLLECTOR_HOST"):
        del os.environ["_condor_COLLECTOR_HOST"]


@pytest.fixture
def noexp(job_envs):
    if os.environ.get("GROUP", None):
        del os.environ["GROUP"]
    if os.environ.get("EXPERIMENT", None):
        del os.environ["EXPERIMENT"]
    if os.environ.get("SAM_EXPERIMENT", None):
        del os.environ["SAM_EXPERIMENT"]
    if os.environ.get("SAM_STATION", None):
        del os.environ["SAM_STATION"]


@pytest.fixture
def samdev(job_envs):
    """fixture to run launches for samdev/fermilab"""
    os.environ["GROUP"] = "fermilab"
    os.environ["EXPERIMENT"] = "samdev"
    os.environ["SAM_EXPERIMENT"] = "samdev"
    os.environ["SAM_STATION"] = "samdev"


@pytest.fixture
def nova(job_envs):
    """fixture to run launches for dune"""
    os.environ["GROUP"] = "nova"
    os.environ["EXPERIMENT"] = "nova"
    os.environ["SAM_EXPERIMENT"] = "nova"
    os.environ["SAM_STATION"] = "nova"


@pytest.fixture
def dune(job_envs):
    """fixture to run launches for dune"""
    os.environ["GROUP"] = "dune"
    os.environ["EXPERIMENT"] = "dune"
    os.environ["SAM_EXPERIMENT"] = "dune"
    os.environ["SAM_STATION"] = "dune"


@pytest.fixture
def dune_test_file(dune):
    datafile = f"/pnfs/dune/scratch/users/{os.environ['USER']}/test_file.txt"
    print("trying to generate {datafile}")
    exists = fake_ifdh.ls(datafile)
    if exists:
        print("found {datafile}")
    else:
        fake_ifdh.cp(__file__, datafile)
        print("copying to {datafile}")
    return datafile


def get_collector():
    """obfuscated way to find collector for dune pool"""
    cp = "collector"[:4]
    hn = os.environ["HOSTNAME"]
    exp = os.environ["GROUP"]
    dom = hn[hn.find(".") :]
    n = dom.find(".", 1) - 3
    col = f"{exp}gp{cp}0{n}{dom}"
    return col


@pytest.fixture
def dune_gp(dune):
    """fixture to run launches for dune global pool"""
    os.environ["_condor_COLLECTOR_HOST"] = get_collector()


joblist = []
jid2test = {}
jid2nout = {}
jid2group = {}
jid2pool = {}
outdirs = {}
ddirs = {}


def run_launch(cmd, expected_out=1, get_dir=False):
    """
    run a jobsub launch command, get jobids from output to watch
    for, etc.
    """
    schedd = None
    jobid = None
    outdir = None
    jobsubjobid = None
    added = False
    # do not submit too fast...
    time.sleep(1)

    if os.environ.get("JOBSUB_TEST_SUBMIT_EXTRA", ""):
        # add extra submit flags, if available
        cmd = cmd.replace(
            "jobsub_submit", "jobsub_submit " + os.environ["JOBSUB_TEST_SUBMIT_EXTRA"]
        )

    pf = os.popen(cmd + " 2>&1")
    for l in pf.readlines():
        print(l)
        m = re.match(r"Submission files are in: (\S+)", l)
        if get_dir and m:
            pf.close()
            return m.group(1).strip()
        m = re.match(r"Running:.*/usr/bin/condor_submit.*-remote (\S+)", l)
        if m:
            print("Found schedd!")
            schedd = m.group(1)
        m = re.match(r"\d+ job\(s\) submitted to cluster (\d+).", l)
        if m:
            print("Found jobid!")
            jobid = m.group(1)

        m = re.match(r"Use job id (\S+) to retrieve output", l)
        if m:
            jobsubjobid = m.group(1)
            print(f"Found jobsubjobid {jobsubjobid}!")

        if jobid and schedd and jobsubjobid and not added:
            added = True
            print("Found all three! ", jobid, schedd, jobsubjobid)
            joblist.append("%s.0@%s" % (jobid, schedd))
            # note which test led to this jobid
            jid2test["%s.0@%s" % (jobid, schedd)] = inspect.stack()[2][3]
            jid2nout["%s.0@%s" % (jobid, schedd)] = expected_out
            jid2group["%s.0@%s" % (jobid, schedd)] = os.environ.get("GROUP", "fermilab")
            jid2pool["%s.0@%s" % (jobid, schedd)] = os.environ.get(
                "_condor_COLLECTOR_HOST", ""
            )
    res = pf.close()

    if not added:
        raise ValueError(
            "Did not get expected output from %s\njobid %s schedd %s jobsubjobid %s "
            % (cmd, jobid, schedd, jobsubjobid)
        )

    if not jobsubjobid == "%s.0@%s" % (jobid, schedd):
        raise ValueError("Did not get consistent output from %s " % cmd)

    return res == None

class dircontext:
    def __init__(self, dirname):
        self.dirname = dirname
        self.returnto = os.getcwd()

    def __enter__(self):
        os.chdir(self.dirname)

    def __exit__(self,a,b,c):
        os.chdir(self.returnto)

def condor_dag_launch(dagfile):
    with dircontext(os.path.dirname(__file__)+"/data/condor_submit_dag"):
        assert run_launch(f"condor_submit_dag --verbose 1 {dagfile}")

@pytest.mark.integration
def test_condor_submit_dag1(samdev):
    condor_dag_launch("dataset.dag")

def lookaround_launch(extra, verify_files=""):
    """Simple submit of our lookaround script"""
    assert run_launch(
        f"jobsub_submit --mail-never --verbose=2 -e SAM_EXPERIMENT {extra} file://`pwd`/job_scripts/lookaround.sh {verify_files}"
    )


@pytest.mark.smoke
def test_launch_lookaround_samdev(samdev):
    lookaround_launch("")


@pytest.mark.integration
def test_launch_lookaround_samdev_dev(samdev):
    lookaround_launch("--devserver")


@pytest.mark.integration
def test_no_submit_condor_submit(samdev):
    dir = run_launch(
        "jobsub_submit --verbose=1 --no-submit "
        "file://`pwd`/job_scripts/lookaround.sh",
        get_dir=True,
    )
    assert run_launch(f"cd {dir} && condor_submit --verbose=1 simple.cmd")


@pytest.mark.integration
def test_launch_lookaround_ddir(samdev):
    pid = os.getpid()
    ddir = f"/pnfs/fermilab/users/$USER/d{pid}"
    fake_ifdh.mkdir_p(ddir)
    lookaround_launch(f"--devserver -d D1 {ddir}")
    ddirs[joblist[-1]] = ddir


@pytest.mark.integration
def test_launch_lookaround_dune(dune):
    lookaround_launch("--devserver")


@pytest.mark.integration
def test_launch_lookaround_dune_gp_poolflag(dune):
    lookaround_launch("--global-pool=dune")


@pytest.mark.integration
def test_launch_lookaround_dune_gp(dune_gp):
    lookaround_launch("")


@pytest.mark.integration
def test_maxconcurrent(samdev):
    lookaround_launch("--maxConcurrent 2 -N 6 ")


@pytest.mark.integration
def test_dd_args(samdev):
    fife_launch(" --dd-percentage 50 " " --dd-extra-dataset mwm_out_1 ")


@pytest.mark.integration
def test_maxconcurrent_dataset(samdev):
    fife_launch("--maxConcurrent 2")


@pytest.mark.integration
def test_dash_f_plain(dune_test_file):
    lookaround_launch(
        f"-f {dune_test_file}",
        f"\\$CONDOR_DIR_INPUT/{os.path.basename(dune_test_file)}",
    )


@pytest.mark.integration
def test_dash_f_sl6(dune_test_file):
    lookaround_launch(
        f"-f {dune_test_file} "
        "--singularity=/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl6:latest",
        f"\\$CONDOR_DIR_INPUT/{os.path.basename(dune_test_file)}",
    )


@pytest.mark.integration
def test_dash_f_dropbox_cvmfs(dune):
    lookaround_launch(
        f"-f dropbox://{__file__} --use-cvmfs-dropbox",
        f"\\$CONDOR_DIR_INPUT/{os.path.basename(__file__)}",
    )


@pytest.mark.integration
def test_tar_dir_cvmfs(dune, add_links):
    lookaround_launch(
        f"--tar_file_name tardir://{os.path.dirname(__file__)}/dagnabbit --use-cvmfs-dropbox",
        f"\\$INPUT_TAR_DIR_LOCAL/ckjobA.sh",
    )


@pytest.mark.integration
def test_tar_dir_pnfs(dune, add_links):
    lookaround_launch(
        f"--tar_file_name tardir://{os.path.dirname(__file__)}/dagnabbit --use-pnfs-dropbox",
        f"\\$INPUT_TAR_DIR_LOCAL/ckjobA.sh",
    )


@pytest.mark.integration
def test_dash_f_dropbox_pnfs(dune):
    lookaround_launch(
        f"-f dropbox://{__file__} --use-pnfs-dropbox",
        f"\\$CONDOR_DIR_INPUT/{os.path.basename(__file__)}",
    )


@pytest.mark.integration
def test_dash_f_dropbox_pnfs_exra_slashes(dune):
    lookaround_launch(
        f"-f dropbox:////{__file__} --use-pnfs-dropbox",
        f"\\$CONDOR_DIR_INPUT/{os.path.basename(__file__)}",
    )


def dagnabbit_launch(extra, which="", nout_files=5):
    os.environ["SUBMIT_FLAGS"] = ""
    os.chdir(os.path.join(os.path.dirname(__file__), "dagnabbit"))
    res = run_launch(
        f"""
        jobsub_submit \
          --mail-never \
          --verbose=2 \
          -e SAM_EXPERIMENT {extra} \
          --dag file://dagTest{which} \
        """,
        nout_files,
    )
    os.chdir(os.path.dirname(__file__))
    assert res


@pytest.mark.integration
def test_launch_dagnabbit_simple(samdev):
    dagnabbit_launch("--devserver", "")


@pytest.mark.integration
def test_launch_dagnabbit_collapse(samdev):
    dagnabbit_launch("--devserver", "HS", 12)


@pytest.mark.integration
def test_launch_dagnabbit_dropbox(samdev):
    dagnabbit_launch("--devserver", "Dropbox")


@pytest.mark.integration
def test_launch_dagnabbit_complex(samdev):
    os.environ["JOBSUB_EXPORTS"] = ""
    os.environ["SUBMIT_FLAGS"] = ""

    dagnabbit_launch("--devserver", "7", 8)


def fife_launch(extra):
    assert run_launch(
        """
        jobsub_submit \
          --mail-never \
          --verbose=2 \
          -e EXPERIMENT \
          -e IFDH_DEBUG \
          -e IFDH_FORCE \
          -e IFDH_VERSION \
          -e IFDH_TOKEN_ENABLE \
          -e IFDH_PROXY_ENABLE \
          -e SAM_EXPERIMENT \
          -e SAM_STATION \
          -e IFDH_CP_MAXRETRIES \
          -e VERSION \
          -N 5  \
          --generate-email-summary \
          --expected-lifetime=2h  \
          --timeout=2h \
          --disk=100MB  \
          --memory=500MB  \
          %(extra)s \
          --dataset-definition=gen_cfg  \
          file://///grid/fermiapp/products/common/db/../prd/fife_utils/v3_3_2/NULL/libexec/fife_wrap \
            --find_setups \
            --setup-unquote 'hypotcode%%20v1_1' \
            --setup-unquote 'ifdhc%%20v2_6_10,ifdhc_config%%20v2_6_15' \
            --prescript-unquote 'ups%%20active' \
            --self_destruct_timer '1400' \
            --debug \
            --getconfig \
            --limit '1' \
            --schema 'https' \
            --appvers 'v1_1' \
            --metadata_extractor 'hypot_metadata_extractor' \
            --addoutput 'gen.troot' \
            --rename 'unique' \
            --dest '/pnfs/%(exp)s/users/mengel/dropbox' \
            --add_location \
            --declare_metadata \
            --addoutput1 'hist_gen.troot' \
            --rename1 'unique' \
            --dest1 '/pnfs/%(exp)s/users/mengel/dropbox' \
            --add_location1 \
            --declare_metadata1 \
            --exe  hypot.exe \
            -- \
              -o \
              gen.troot \
              -c \
              hist_gen.troot """
        % {"exp": os.environ["GROUP"], "extra": extra},
        expected_out=5,
    )


@pytest.mark.integration
def test_samdev_fife_launch(samdev):
    fife_launch("--devserver")


@pytest.mark.integration
def test_dune_fife_launch(dune):
    fife_launch("--devserver")


@pytest.mark.integration
def test_nova_fife_launch(nova):
    fife_launch("--devserver")


@pytest.mark.integration
def test_dune_gp_fife_launch(dune_gp):
    fife_launch("")


def group_for_job(jid):

    group = jid2group.get(jid, "")

    if jid.find("dune") > 0:
        if not group:
            group = "dune"
        if jid2pool.get(jid, ""):
            os.environ["_condor_COLLECTOR_HOST"] = get_collector()
    else:
        if not group:
            group = "fermilab"
        if os.environ.get("_condor_COLLECTOR_HOST"):
            del os.environ["_condor_COLLECTOR_HOST"]
    os.environ["GROUP"] = group
    return group


# turning this test off for now; I can not seem to get it to consistently get
# the setup of two jobs each on two schedd's... mengel
# @pytest.mark.integration
def xx_test_jobsub_q_repetitions(samdev):
    # test to make sure if we do jobsub_q 1@jobsub01 2@jobsub01 3@jobsub02 4@jobsub02 we get only one repitition
    # first submit a few more jobs so we have fresh ones
    lookaround_launch("")
    lookaround_launch("")
    lookaround_launch("")
    lookaround_launch("")
    lookaround_launch("")
    lookaround_launch("")
    jobs_by_schedd = {}
    all_schedds = set()
    for jid in joblist:
        schedd = re.sub(r".*@", "", jid)
        all_schedds.add(schedd)
        if schedd in jobs_by_schedd:
            jobs_by_schedd[schedd].append(jid)
        else:
            jobs_by_schedd[schedd] = [jid]

    print(f"jobs_by_schedd: {repr(jobs_by_schedd)}")
    args = ["jobsub_q", "-G", "fermilab"]
    jcount = 0
    all_schedds_l = list(all_schedds)
    all_schedds_l.sort()
    for schedd in all_schedds_l:
        # pick the most recent 2 of jobs from each schedd
        nj = len(jobs_by_schedd[schedd])
        if nj > 1 and not schedd.find("dune") == 0:
            args.append(jobs_by_schedd[schedd][-1])
            args.append(jobs_by_schedd[schedd][-2])
            jcount = jcount + 2
            if jcount == 4:
                break

    # now we have 4 jobs on 2 schedd's from our list
    count = 0
    cmd = " ".join(args)
    print("Running: ", cmd)
    with os.popen(cmd, "r") as fin:
        for line in fin.readlines():
            print("got: ", line)
            count = count + 1
    assert count == 5


@pytest.mark.smoke
@pytest.mark.integration
def test_wait_for_jobs():
    """Not really a test, but we have to wait for jobs to complete..."""
    count = 1
    print("Waiting for jobs: ", " ".join(joblist))

    # put the list somewhere so we can see what the test is waiting for
    # when not running with -s or whatever...
    with open("/tmp/jobsub_lite_test_joblist", "w") as f:
        f.write(" ".join(joblist))

    repeats = 0
    while count > 0 and repeats < 3:
        if repeats == 0:
            time.sleep(20)
        count = len(joblist)
        for jid in joblist:
            group = group_for_job(jid)
            cmd = "jobsub_q -format '%%s' JobStatus -G %s %s" % (group, jid)
            print("running: ", cmd)
            pf = os.popen(cmd)
            l = pf.readlines()
            res = pf.close()
            print("got output: ", repr(l))
            if l:
                status = l[0][0]
            else:
                status = None
            print("jobid: ", jid, " status: ", status)
            if status == "4" or status == "A" or status == None:
                # '4' is Completed.
                # 'A' is when it says 'All queues are empty' (so they're
                #     all completed...)
                # None is when there's no output...
                count = count - 1

        # have to all look good 3 times in a row...
        if count == 0:
            repeats = repeats + 1
        else:
            repeats = 0

    print("Done.")
    assert True


@pytest.mark.smoke
@pytest.mark.integration
def test_fetch_output():
    for jid in joblist:
        group = group_for_job(jid)
        owd = tempfile.mkdtemp()
        outdirs[jid] = owd
        subprocess.run(
            ["jobsub_fetchlog", "--group", group, "--jobid", jid, "--destdir", owd],
            check=True,
        )


@pytest.mark.smoke
@pytest.mark.integration
def test_check_job_output():
    res = True
    for jid, ddir in ddirs.items():
        print(f"Checking {jid2test[jid]} {jid} -d tag  {ddir}...")
        fl = fake_ifdh.ls(ddir)
        res = res and bool(len(fl))

    for jid, outdir in outdirs.items():
        fl = glob.glob("%s/*[0-9].out" % outdir)

        if len(fl) < jid2nout[jid]:
            # if not enough files, try fetching again...
            # sometimes when we look later they're all there
            print(f"Notice: re-fetching {jid} logs...")
            group = group_for_job(jid)
            subprocess.run(
                [
                    "jobsub_fetchlog",
                    "--group",
                    group,
                    "--jobid",
                    jid,
                    "--destdir",
                    outdir,
                ],
                check=True,
            )
            fl = glob.glob("%s/*[0-9].out" % outdir)

        # make sure we have enough output files
        print(
            f"Checking out file count test {jid2test[jid]} {jid} expecting {jid2nout[jid]} actual count {len(fl)}"
        )
        if len(fl) >= jid2nout[jid]:
            print("-- ok")
        else:
            res = False
            print("-- bad")

        for f in fl:
            print(f"Checking {jid2test[jid]} {jid} output file {f}...")
            fd = open(f, "r")
            f_ok = False
            ll = fd.readlines()
            fd.close()
            if ll[-1].endswith("status 0\n") or ll[-1].endswith("success!\n"):
                print("-- ok")
            else:
                print("-- bad")
                res = False

        shutil.rmtree(outdir)
        assert res


@pytest.mark.integration
@pytest.mark.parametrize(
    "constraint_flag_and_arg",
    ["--constraint 'Owner==\"{user}\"'", "--constraint='Owner==\"{user}\"'"],
)
def test_valid_constraint(samdev, constraint_flag_and_arg):
    lookaround_launch("--devserver")
    if len(joblist) == 0:
        raise AssertionError("No jobs submitted")
    jid = joblist[-1]
    group = group_for_job(jid)
    user = os.environ["USER"]
    cmd = f"jobsub_q -G {group} {constraint_flag_and_arg} --jobid={jid} -format '%s' ClusterId"
    cmd = cmd.format(user=user)
    with os.popen(cmd) as query:
        output = query.readlines()
        assert len(output) == 1 and output[0] in jid


@pytest.mark.integration
@pytest.mark.parametrize(
    "constraint_flag_and_arg",
    [
        "--constraint 'thisisabadconstraintbutwillparse==true'",
        "--constraint='thisisabadconstraintbutwillparse==true'",
    ],
)
def test_invalid_constraint(samdev, constraint_flag_and_arg):
    cmd = f"jobsub_q -G fermilab {constraint_flag_and_arg} -autoformat ClusterId"
    query = os.popen(cmd)
    output = query.readlines()
    assert len(output) == 0
    rc = query.close()
    assert (
        rc is None
    )  # We got a 0 return code from the query even if it returned nothing
