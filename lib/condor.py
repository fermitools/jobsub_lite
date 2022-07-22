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
""" condor related routines """
import os
import sys
import glob
import re
import random
import subprocess
from typing import Dict, List, Any, Tuple, Optional, Union

import htcondor  # type: ignore
import classad  # type: ignore

import packages

random.seed()

# pylint: disable-next=no-member
COLLECTOR_HOST = htcondor.param.get("COLLECTOR_HOST", "gpcollector03.fnal.gov")


# pylint: disable-next=no-member
def get_schedd(vargs: Dict[str, str]) -> classad.ClassAd:
    """get jobsub* schedd names from collector, pick one."""
    # pylint: disable-next=no-member
    coll = htcondor.Collector(COLLECTOR_HOST)
    # pylint: disable-next=no-member
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)

    # locateAll gives a list of minimal classads... but
    # need to directQuery for the full classads to check for
    # SupportedVOList...

    if vargs.get("verbose"):
        print("classads: ", schedd_classads)

    # pick schedds who do or do not have "dev" in their name, depending if
    # we have "devserver" set...

    if "devserver" in vargs and vargs["devserver"]:
        schedd_classads = [
            ca for ca in schedd_classads if ca.eval("Machine").find("dev") != -1
        ]
    else:
        schedd_classads = [
            ca for ca in schedd_classads if ca.eval("Machine").find("dev") == -1
        ]

    # print("after dev check:" , [ca.eval("Machine") for ca in schedds])

    full_schedd_classads = []
    for ca in schedd_classads:
        full_schedd_classads.append(
            # pylint: disable-next=no-member
            coll.directQuery(htcondor.DaemonTypes.Schedd, name=ca.eval("Machine"))
        )

    # Filters to pick our schedds
    schedds = [
        schedd_classad
        for schedd_classad in full_schedd_classads
        # Pick the jobsub_lite schedds in the pool
        if (
            ("IsJobsubLite" in schedd_classad)
            and (schedd_classad.eval("IsJobsubLite") == True)
        )
        # Only get schedds whose SupportedVOLists include our VO (group)
        and (
            (
                ("SupportedVOList" in schedd_classad)
                and (schedd_classad.eval("SupportedVOList").find(vargs["group"]) != -1)
            )
        )
        # Make sure we don't pick any schedds in downtime
        and (
            ("InDownTime" not in schedd_classad)
            or (
                ("InDownTime" in schedd_classad)
                and (schedd_classad.eval("InDownTime") != True)
            )
        )
    ]

    res = random.choice(schedds)
    return res


def load_submit_file(filename: str) -> Tuple[Any, Optional[int]]:
    """pull in a condor submit file, make a dictionary"""

    #
    # NOTICE: this needs extra bits as added by condor
    #   if you run condor_submit --dump filename
    #   until that's done, we have to call real condor_submit.
    #
    with open(filename, "r", encoding="UTF-8") as f:
        res = {}
        nqueue = None
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                continue
            t = re.split(r"\s*=\s*", line, maxsplit=1)
            if len(t) == 2:
                res[t[0]] = t[1]
            elif line.startswith("queue"):
                nqueue = int(line[5:])
            elif not line:
                pass  # blank lines ok
            else:
                raise SyntaxError(f"malformed line: {line}")
    # pylint: disable-next=no-member
    return htcondor.Submit(res), nqueue


# pylint: disable-next=dangerous-default-value
def submit(
    f: str, vargs: Dict[str, Any], schedd_name: str, cmd_args: List[str] = []
) -> Union[Any, bool]:
    """Actually submit the job, using condor python bindings"""

    schedd_args = f"-remote {schedd_name}"

    if "no_submit" in vargs and vargs["no_submit"]:
        print(f"NOT submitting file:\n{f}\n")
        return False
    if f:
        if vargs["debug"] > 0:
            print(f"submitting: {f}")
        schedd_args = schedd_args + f" {f}"
        fl = glob.glob(f)
        if fl:
            f = fl[0]

    if vargs["debug"] > 1:
        print(f"cmd_args: {cmd_args}")

    # commenting this out for now since the 'else' is not implemented
    #    if True:

    qargs = " ".join([f"'{x}'" for x in cmd_args])
    cmd = f"/usr/bin/condor_submit -pool {COLLECTOR_HOST} {schedd_args} {qargs}"
    cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
    cmd = f"_condor_CREDD_HOST={schedd_name} {cmd}"
    packages.orig_env()
    if vargs["debug"] > 0:
        print(f"Running: {cmd}")

    try:
        output = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, encoding="UTF-8", check=False
        )
        sys.stdout.write(output.stdout)

        if output.returncode < 0:
            sys.stderr.write(
                f"Error: Child was terminated by signal {-output.returncode}"
            )
            return None

        m = re.search(r"\d+ job\(s\) submitted to cluster (\d+).", output.stdout)
        if m:
            print(f"Use job id {m.group(1)}.0@{schedd_name} to retrieve output")

        if "outdir" in vargs:
            print(
                f"Output will be in {vargs['outdir']} after running"
                " jobsub_transfer_data."
            )

        return True
    except OSError as e:
        print("Execution failed: ", e)
        return None

    # This 'else' is not currently implemented
    #    else:
    #        subm, nqueue = load_submit_file(f)
    #        with schedd.transaction() as txn:
    #            cluster = subm.queue(txn, count=nqueue)
    #        print(f"jobid: {cluster}@{schedd_name}")
    #        return True


# pylint: disable-next=dangerous-default-value
def submit_dag(
    f: str, vargs: Dict[str, Any], schedd_name: str, cmd_args: List[str] = []
) -> Union[Any, bool]:
    """
    Actually submit the dag
    for the moment, we call the commandline condor_submit_dag,
    but in future we should template-ize the dagman submission file, and
    just call condor_submit() on it.
    """
    fl = glob.glob(f)
    if fl:
        f = fl[0]
    subfile = f"{f}.condor.sub"
    if not os.path.exists(subfile):
        qargs = " ".join([f"'{x}'" for x in cmd_args])
        cmd = (
            f"/usr/bin/condor_submit_dag -append"
            f' "use_oauth_services = {vargs["group"]}" -no_submit {f} {qargs}'
        )

        cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
        if vargs["debug"] > 0:
            print(f"Running: {cmd}")

        try:
            output = subprocess.run(cmd, shell=True, check=False)
            if output.returncode < 0:
                sys.stderr.write(
                    f"Error: Child was terminated by signal {-output.returncode}"
                )
            else:
                if "outdir" in vargs:
                    print(
                        f"Output will be in {vargs['outdir']} after running jobsub_transfer_data."
                    )
        except OSError as e:
            print("Execution failed: ", e)

    return submit(subfile, vargs, schedd_name)


class Job:
    """
    Job represents a single HTCondor batch job or cluster with an id like
        <cluster>[.<process>]@<schedd>

    where if <process> is specified it is a single job, or if not then a cluster
    of jobs. Examples:


        123@schedd.example.com
        123.0@schedd.example.com
        123.456@schedd.example.com

    """

    id: str
    seq: str
    proc: str
    schedd: str
    cluster: bool

    _id_regexp = re.compile(r"(\d+)(?:\.(\d+))?@([\w\.]+)")

    def __init__(self, job_id: str):
        self.id = job_id
        m = Job._id_regexp.match(job_id)
        if m is None:
            raise Exception(f'unable to parse job id "{job_id}"')
        self.seq = m.group(1)
        self.proc = m.group(2)
        self.cluster = False
        if self.proc is None:
            self.proc = "0"
            self.cluster = True
        self.schedd = m.group(3)

    def __str__(self) -> str:
        if self.cluster:
            return f"{self.seq}@{self.schedd}"
        return f"{self.seq}.{self.proc}@{self.schedd}"

    def _get_schedd(self) -> htcondor.htcondor.Schedd:
        c = htcondor.Collector(COLLECTOR_HOST)
        s = c.locate(htcondor.DaemonTypes.Schedd, self.schedd)
        if s is None:
            raise Exception(f'unable to find schedd "{self.schedd}" in HTCondor pool')
        return htcondor.Schedd(s)

    def get_attribute(self, attr: str) -> Any:
        """
        Return the value of a single job attribute from the schedd. If self is a
        cluster of jobs, the attribute will be returned from the first job found
        on the schedd (not necessarily process 0).

        """
        s = self._get_schedd()
        q = f"ClusterId=={self.seq}"
        if not self.cluster:
            q += f" && ProcId=={self.proc}"
        res = s.query(q, [attr], limit=1)
        if len(res) == 0:
            raise Exception(f'job matching "{q}" not found on "{self.schedd}"')
        if attr not in res[0]:
            raise Exception(f'attribute "{attr}" not found for job "{str(self)}"')
        return res[0].eval(attr)
