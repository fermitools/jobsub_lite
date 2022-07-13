import os
import sys
import re
import glob
import pytest
import time

#
# we assume everwhere our current directory is in the package 
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))
os.environ['PATH'] = (os.path.dirname(os.path.dirname(__file__)) + 
                        '/bin:' + os.environ['PATH'])

@pytest.fixture
def job_envs():
    os.environ['IFDH_DEBUG']='1'
    os.environ['IFDH_FORCE']='https'
    os.environ['IFDH_VERSION']='v2_6_5'
    os.environ['IFDHC_CONFIG_DIR'] = '/grid/fermiapp/products/common/db/../prd/ifdhc_config/v2_6_5/NULL'
    os.environ['IFDH_TOKEN_ENABLE']='1'
    os.environ['IFDH_PROXY_ENABLE']='0'
    os.environ['IFDH_CP_MAXRETRIES']='2'
    os.environ['VERSION'] ='v1_1'
    if os.environ.get('_condor_COLLECTOR_HOST'): del os.environ['_condor_COLLECTOR_HOST']

@pytest.fixture
def noexp(job_envs):
    if os.environ.get('GROUP', None): del os.environ['GROUP'] 
    if os.environ.get('EXPERIMENT', None): del os.environ['EXPERIMENT'] 
    if os.environ.get('SAM_EXPERIMENT', None): del os.environ['SAM_EXPERIMENT'] 
    if os.environ.get('SAM_STATION', None): del os.environ['SAM_STATION']

@pytest.fixture
def samdev(job_envs):
    ''' fixture to run launches for samdev/fermilab '''
    os.environ['GROUP']='fermilab'
    os.environ['EXPERIMENT']='samdev'
    os.environ['SAM_EXPERIMENT']='samdev'
    os.environ['SAM_STATION']='samdev'

@pytest.fixture
def nova(job_envs):
    ''' fixture to run launches for dune '''
    os.environ['GROUP']='nova'
    os.environ['EXPERIMENT']='nova'
    os.environ['SAM_EXPERIMENT']='nova'
    os.environ['SAM_STATION']='nova'

@pytest.fixture
def dune(job_envs):
    ''' fixture to run launches for dune '''
    os.environ['GROUP']='dune'
    os.environ['EXPERIMENT']='dune'
    os.environ['SAM_EXPERIMENT']='dune'
    os.environ['SAM_STATION']='dune'

@pytest.fixture
def dune_gp(dune):
    ''' fixture to run launches for dune global pool '''
    os.environ['_condor_COLLECTOR_HOST']='dunegpcoll02.fnal.gov'

joblist = []
outdirs = []

def run_launch(cmd):
    ''' 
       run a jobsub launch command, get jobids from output to watch
       for, etc.
    '''
    schedd = None
    jobid = None
    outdir = None
    added = False
    pf = os.popen(cmd + " 2>&1")
    for l in pf.readlines():
        print( l )
        m = re.match(r'Running:.*/usr/bin/condor_submit.*-remote (\S+)', l)
        if m:
            print("Found schedd!")
            schedd = m.group(1)
        m = re.match(r'\d+ job\(s\) submitted to cluster (\d+).', l)
        if m:
            print("Found jobid!")
            jobid = m.group(1)
        m = re.match(r'Output will be in (\S+) after running jobsub_transfer_data.', l)
        if m:
            print("Found outdir!")
            outdir = m.group(1)

        if jobid and schedd and outdir and not added:
            added = True
            print("Found all three!")
            joblist.append( "%s@%s" % ( jobid, schedd ) )
            outdirs.append( outdir )

    res = pf.close()

    if not added:
        raise ValueError("Did not get expected output from %s" % cmd)

    return res == None 
    
def lookaround_launch(extra):
    ''' Simple submit of our lookaround script '''
    assert run_launch("jobsub_submit -e SAM_EXPERIMENT %s --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE file://`pwd`/job_scripts/lookaround.sh" % extra)


def test_launch_lookaround_samdev(samdev):
    lookaround_launch('--devserver')

def test_launch_lookaround_dune(dune):
    lookaround_launch('--devserver')

def test_launch_lookaround_dune_gp(dune_gp):
    lookaround_launch('')


def fife_launch(extra):
    assert run_launch("""
        jobsub_submit \
          -e EXPERIMENT \
          -e IFDH_DEBUG \
          -e IFDH_FORCE \
          -e IFDH_VERSION \
          -e IFDH_TOKEN_ENABLE \
          -e IFDH_PROXY_ENABLE \
          -e IFDHC_CONFIG_DIR \
          -e SAM_EXPERIMENT \
          -e SAM_STATION \
          -e IFDH_CP_MAXRETRIES \
          -e VERSION \
          -N 5  \
          --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE  \
          --generate-email-summary \
          --expected-lifetime=2h  \
          --timeout=2h \
          --disk=100MB  \
          --memory=500MB  \
          %(extra)s \
          --dataset=gen_cfg  \
          file://///grid/fermiapp/products/common/db/../prd/fife_utils/v3_3_2/NULL/libexec/fife_wrap \
            --find_setups \
            --setup-unquote 'hypotcode%%20v1_1' \
            --setup-unquote 'ifdhc%%20v2_6_5,ifdhc_config%%20v2_6_5' \
            --prescript-unquote 'ups%%20active' \
            --self_destruct_timer '700' \
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
              hist_gen.troot """ % {'exp':os.environ['GROUP'], 'extra': extra})

def test_samdev_fife_launch(samdev):
    fife_launch('--devserver')

def test_dune_fife_launch(dune):
    fife_launch('--devserver')

def test_nova_fife_launch(nova):
    fife_launch('--devserver')

def test_dune_gp_fife_launch(dune_gp):
    fife_launch('')


def test_wait_for_jobs():
    ''' Not really a test, but we have to wait for jobs to complete... '''
    count = 1
    print("Waiting for jobs: " , " ".join(joblist))
    while count > 0:
        time.sleep(10)
        count = len(joblist)
        for jid in joblist:
            if jid.find('dunesched') > 0:
                group = 'dune'
                os.environ['_condor_COLLECTOR_HOST']='dunegpcoll02.fnal.gov'
            else:
                group = 'fermilab'
                if os.environ.get('_condor_COLLECTOR_HOST'): del os.environ['_condor_COLLECTOR_HOST']

            cmd = "jobsub_q -format '%%s' JobStatus -G %s %s" % ( group, jid)
            print("running: ", cmd)
            pf = os.popen(cmd)
            l = pf.readlines()
            res = pf.close()
            print("got output: ", repr(l))
            if l:
                status = l[0][0]
            else:
                status = None
            print("jobid: " , jid, " status: ", status)
            if status == '4' or status == 'A':
                # '4' is Completed.
                # 'A' is when it says 'All queues are empty' (so they're
                #     all completed...)
                count = count - 1
    print("Done.")
    assert True   

def test_fetch_output():
    for jid in joblist:
        if jid.find('dunesched') > 0:
            group = 'dune'
            os.environ['_condor_COLLECTOR_HOST']='dunegpcoll02.fnal.gov'
        else:
            group = 'fermilab'
            if os.environ.get('_condor_COLLECTOR_HOST'): del os.environ['_condor_COLLECTOR_HOST']

        os.system("jobsub_transfer_data %s" % jid)

def test_check_job_output():
    for outdir in outdirs:
        fl = glob.glob('%s/*.log' % outdir)
        for f in fl:
            print("Checking logfile: ", f)
            fd = open(f, "r")
            f_ok = False
            for l in fd.readlines():
                if l.find("(1) Normal termination") > 0:
                    # XXX this should also check for the exit code 0 part, but
                    # until the SAM instances all take tokens etc, it doesn't
                    f_ok = True
            fd.close()
            assert f_ok
