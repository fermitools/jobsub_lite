import os
import sys
import glob
import re
import htcondor
import random
import packages

random.seed()

COLLECTOR="gpcollector03.fnal.gov"

def get_schedd(vargs):
    """ get jobsub* schedd names from collector, pick one. """
    coll = htcondor.Collector(COLLECTOR)
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)
    schedds = [ ca  for ca in schedd_classads if ca.eval("Machine").startswith("jobsubdev" if vargs["devserver"] else "jobsub0") ]
    res = random.choice(schedds)
    return res 

def load_submit_file(filename):
    """ pull in a condor submit file, make a dictionary """

    #
    # NOTICE: this needs extra bits as added by condor
    #   if you run condor_submit --dump filename
    #   until that's done, we have to call real condor_submit.
    #
    f=open(filename,"r")
    res = {}
    nqueue = None
    for line in f:
        line = line.strip()
        if line.startswith("#"):
           continue
        t = re.split("\s*=\s*", line, maxsplit=1)
        if len(t) == 2:
            res[t[0]] = t[1]
        elif line.startswith('queue'):
            nqueue = int(line[5:])
        elif not line:
            pass # blank lines ok
        else:
            raise SyntaxError("malformed line: %s" % line)
    f.close()
    return htcondor.Submit(res), nqueue

def submit(f,vargs, schedd_add):
    """ Actually submit the job, using condor python bindings """
    if vargs["no_submit"]:
         print("NOT submitting file:\n%s\n" % f)
         return
    print("submitting: %s" % f)
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    schedd_name = schedd_add.eval("Machine")
    schedd = htcondor.Schedd(schedd_add)
    print("schedd: %s" %  schedd_name)

    if (True):
        cmd='condor_submit -spool -pool %s -remote %s  %s' % (COLLECTOR, schedd_name,  f)
        cmd = 'BEARER_TOKEN_FILE=%s %s' % (os.environ['BEARER_TOKEN_FILE'],cmd)
        cmd = '_condor_AUTH_SSL_CLIENT_CADIR=/etc/grid-security/certificates %s' % cmd
        cmd = '_condor_SEC_CLIENT_AUTHENTICATION_METHODS=SCITOKENS %s' % cmd
        packages.orig_env()
        print("Running: %s" % cmd)
        os.system(cmd)
    else:
        subm, nqueue = load_submit_file(f)
        with schedd.transaction() as txn:
            cluster  = subm.queue(txn, count=nqueue)
        print("jobid: %s@%s" % (cluster, schedd_name))
    return

def submit_dag(f,vargs, schedd_add):
    """ 
       Actually submit the dag 
       for the moment, we call the commandline condor_submit_dag, 
       but in future we should template-ize the dagman submission file, and
       just call condor_submit() on it.
    """
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    subfile = "%s.condor.sub" % f
    if (not os.path.exists(subfile)):
        cmd = 'condor_submit_dag --no_submit %s' % f
        cmd = 'BEARER_TOKEN_FILE=%s %s' % (os.environ['BEARER_TOKEN_FILE'],cmd)
        cmd = '_condor_AUTH_SSL_CLIENT_CADIR=/etc/grid-security/certificates %s' % cmd
        cmd = '_condor_SEC_CLIENT_AUTHENTICATION_METHODS=SCITOKENS %s' % cmd
        print("Running: %s" % cmd)
        packages.orig_env()
        os.system(cmd)
    submit(subfile, vargs, schedd_add)
