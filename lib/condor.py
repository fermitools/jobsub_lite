import os
import sys
import glob
import re
import htcondor
import random
random.seed()

COLLECTOR="gpcollector03.fnal.gov"
DEVCOLLECTOR="jobsubdevgpvm01.fnal.gov"

def get_schedd(vargs):
    """ get jobsub* schedd names from collector, pick one. """
    coll = htcondor.Collector(DEVCOLLECTOR if args["devserver"] else COLLECTOR)
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)
    schedds = [ ca  for ca in schedd_classads if ca.eval("Machine").startswith("jobsub") ]
    return random.choice(schedds), "default"


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

def submit(f,args):
    """ Actually submit the job """
    print("submitting: %s" % f)
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    schedd_add, pool = get_schedd(vargs)
    schedd_name = schedd_add.eval("Machine")
    schedd = htcondor.Schedd(schedd_add)

    subm, nqueue = load_submit_file(f)
    print ("trying to submit to schedd: %s: %s" % (schedd_name,repr(schedd)))
    with schedd.transaction() as txn:
        cluster  = subm.queue(txn, count=nqueue)
    print("Got cluster: %s", cluster)
    return

def submit_dag(f,vargs):
    """ Actually submit the dag """
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    schedd_add, pool = get_schedd(vargs)
    schedd_name = schedd_add.eval("Machine")
    schedd = htcondor.Schedd(schedd_add)
    subm = htcondor.Schedd.from_dag(f)
    print("would: condor_submit_dag -name %s -remote %s %s" % (schedd, pool, f))
    with schedd.transaction() as txn:
        cluster  = subm.queue(txn)
    print("Got cluster: %s", cluster)
    return

