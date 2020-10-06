import os
import sys
import glob
import re
import htcondor
import random
random.seed()

COLLECTOR="gpcollector03.fnal.gov"

def get_schedd(vargs):
    """ get jobsub* schedd names from collector, pick one. """
    coll = htcondor.Collector(COLLECTOR)
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)
    schedds = [ ca  for ca in schedd_classads if ca.eval("Machine").startswith("jobsubdev" if vargs["devserver"] else "jobsub0") ]
    res = random.choice(schedds)
    print("picked schedd: %s" % res.get('Machine'))
    return res 

def load_submit_file(filename):
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
    """ Actually submit the job """
    if vargs["nosubmit"]:
         print("NOT submitting file:\n%s\n" % f)
         return
    print("submitting: %s" % f)
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    schedd_name = schedd_add.eval("Machine")
    schedd = htcondor.Schedd(schedd_add)

    subm, nqueue = load_submit_file(f)
    print ("trying to submit to schedd: %s: %s" % (schedd_name,repr(schedd)))
    with schedd.transaction() as txn:
        cluster  = subm.queue(txn, count=nqueue)
    print("jobid: %s@%s" % (cluster, schedd_name))
    return

def submit_dag(f,vargs, schedd_add):
    """ Actually submit the dag """
    if vargs["nosubmit"]:
         print("NOT submitting dag\n%s\n" % f)
         return
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    schedd_name = schedd_add.eval("Machine")
    print('running: condor_submit_dag -append "x509userproxy=%s" -r %s  %s' % (os.environ['X509_USER_PROXY'],schedd_name,  f))
    os.system('condor_submit_dag -append "x509userproxy=%s" -r %s  %s' % (os.environ['X509_USER_PROXY'], schedd_name,  f))
    #schedd = htcondor.Schedd(schedd_add)
    #subm = htcondor.Schedd.from_dag(f)
    #with schedd.transaction() as txn:
    #    cluster  = subm.queue(txn)
    #print("Got cluster: %s", cluster)
    return

