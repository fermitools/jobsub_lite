
#
# COPYRIGHT 2021 FERMI NATIONAL ACCELERATOR LABORATORY
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys
import glob
import re
import htcondor
import random
import packages

random.seed()

COLLECTOR_HOST=htcondor.param.get('COLLECTOR_HOST','gpcollector03.fnal.gov')

def get_schedd(vargs):
    """ get jobsub* schedd names from collector, pick one. """
    coll = htcondor.Collector(COLLECTOR_HOST)
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)

    # locateAll gives a list of minimal classads... but 
    # need to directQuery for the full classads to check for 
    # SupportedVOList...

    full_schedd_classads = []
    for ca in schedd_classads:
        full_schedd_classads.append( 
           coll.directQuery( 
               htcondor.DaemonTypes.Schedd, 
               name=ca.eval("Machine")))


    # pick schedds who list our group in their vo list

    schedds = [ ca  for ca in full_schedd_classads if "SupportedVOList" in ca and ca.eval("SupportedVOList").find(vargs['group']) != -1 ]


    # pick schedds who do or do not have "dev" in their name, depending if
    # we have "devserver" set...

    if vargs["devserver"]:
        schedds = [ ca  for ca in schedds if ca.eval("Machine").find("dev") != -1 ]
    else:
        schedds = [ ca  for ca in schedds if ca.eval("Machine").find("dev") == -1 ]

    # print("after dev check:" , [ca.eval("Machine") for ca in schedds])
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

def submit(f,vargs, schedd_add, cmd_args = []):
    """ Actually submit the job, using condor python bindings """
    if vargs["no_submit"]:
         print("NOT submitting file:\n%s\n" % f)
         return
    if f:
        print("submitting: %s" % f)
        fl = glob.glob(f)
        if fl:
            f = fl[0]
    schedd_name = schedd_add.eval("Machine")
    schedd = htcondor.Schedd(schedd_add)
    print("schedd: %s" %  schedd_name)

    if (True):
        cmd='/usr/bin/condor_submit -spool -pool %s -remote %s %s %s' % (COLLECTOR_HOST, schedd_name,  f , ' '.join(["'%s'"%x for x in cmd_args]))
        cmd = 'BEARER_TOKEN_FILE=%s %s' % (os.environ['BEARER_TOKEN_FILE'],cmd) 
        cmd = '_condor_CREDD_HOST=%s %s'  % (schedd_name, cmd)
        packages.orig_env()
        print("Running: %s" % cmd)
        cmd = '%s | sed -e "s/\\(submitted.to.cluster.*\\)\\./\\1@%s/"' % (cmd, schedd_name)
        os.system(cmd)
        print("Output will be in %s after running jobub_tranfer_data." % vargs['outdir']  )
    else:
        subm, nqueue = load_submit_file(f)
        with schedd.transaction() as txn:
            cluster  = subm.queue(txn, count=nqueue)
        print("jobid: %s@%s" % (cluster, schedd_name))
    return

def submit_dag(f,vargs, schedd_add, cmd_args = []):
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
        cmd = '/usr/bin/condor_submit_dag -append "use_oauth_services = %s" -no_submit %s %s' % (vargs['group'], f, ' '.join(["'%s'"%x for x in cmd_args]))

        cmd = 'BEARER_TOKEN_FILE=%s %s' % (os.environ['BEARER_TOKEN_FILE'],cmd)
        print("Running: %s" % cmd)
        os.system(cmd)
    submit(subfile, vargs, schedd_add)
