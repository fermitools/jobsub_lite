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
COLLECTOR_HOST = htcondor.param.get("COLLECTOR_HOST", None)


# pylint: disable-next=no-member
def get_schedd_list(vargs: Dict[str, Any]) -> List[classad.ClassAd]:
    """get jobsub* schedd classads from collector"""
    # pylint: disable-next=no-member
    coll = htcondor.Collector(COLLECTOR_HOST)
    # pylint: disable-next=no-member
    devnot = "" if vargs["devserver"] else "!"
    schedds: List[classad.ClassAd] = coll.query(
        htcondor.htcondor.AdTypes.Schedd,
        constraint="IsJobsubLite=?=true"
        " && "
        f"""STRINGLISTIMEMBER("{vargs['group']}", SupportedVOList)"""
        " && "
        "InDownTime != true"
        " && "
        f'{devnot} regexp(".*dev.*", Machine)',
    )

    if vargs.get("verbose", 0) > 1:
        print(f"post-query schedd classads: {schedds} ")

        print("")

    return schedds


def get_schedd_names(vargs: Dict[str, Any]) -> List[str]:
    """get jobsub* schedd names from collector"""
    schedds = get_schedd_list(vargs)
    res = []
    for s in schedds:
        name = s.eval("Name")
        res.append(name)
    return res


# pylint: disable-next=no-member
def get_schedd(vargs: Dict[str, Any]) -> classad.ClassAd:
    """pick a jobsub* schedd name from collector"""
    schedds = get_schedd_list(vargs)
    # pick weights based on (inverse) of  duty cycle of schedd
    weights = []
    for s in schedds:
        name = s.eval("Name")
        rdcdc = s.eval("RecentDaemonCoreDutyCycle")

        # avoid dividing by zero, and really crazy weights for idle servers
        # max it out at 1000
        if rdcdc > 0.01:
            weight = 10.0 / rdcdc
        else:
            weight = 1000.0

        weights.append(weight)

        if vargs.get("verbose", 0) > 0:
            print(f"Schedd: {name} DutyCycle {rdcdc} weight {weight}")

    res = random.choices(schedds, weights=weights)[0]
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

    if vargs.get("no_submit", False):
        print(f"NOT submitting file:\n{f}\n")
        return False
    if f:
        if vargs.get("verbose", 0) > 0:
            print(f"submitting: {f}")
        if vargs.get("verbose", 0) > 1:
            schedd_args = schedd_args + " -debug"
        schedd_args = schedd_args + f" {f}"

    if vargs.get("verbose", 0) > 1:
        print(f"cmd_args: {cmd_args}")

    # commenting this out for now since the 'else' is not implemented
    #    if True:

    qargs = " ".join([f"'{x}'" for x in cmd_args])
    cmd = f"/usr/bin/condor_submit -pool {COLLECTOR_HOST} {schedd_args} {qargs}"
    cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
    cmd = f"_condor_CREDD_HOST={schedd_name} {cmd}"
    packages.orig_env()
    if vargs.get("verbose", 0) > 0:
        print(f"Running: {cmd}")

    try:
        output = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, encoding="UTF-8", check=False
        )
        sys.stdout.write(output.stdout)

        hl = f"\n{'=-'*30}\n\n"  # highlight line to make result stand out

        if output.returncode < 0:
            sys.stderr.write(
                f"{hl}Error: Child was terminated by signal {-output.returncode}{hl}\n"
            )
            return None

        if output.returncode > 0:
            sys.stderr.write(
                f"{hl}Error: condor_submit exited with failed status code {output.returncode}{hl}\n"
            )
            return None

        m = re.search(r"\d+ job\(s\) submitted to cluster (\d+).", output.stdout)
        if m:
            print(f"{hl}Use job id {m.group(1)}.0@{schedd_name} to retrieve output{hl}")

            # call any job_info commands requested with the jobid
            for ji in vargs["job_info"]:
                os.system(
                    f'{ji} {m.group(1)}.0@{schedd_name} "{repr(sys.argv)}" </dev/null'
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
    subfile = f"{f}.condor.sub"
    if not os.path.exists(subfile):
        qargs = " ".join([f"'{x}'" for x in cmd_args])
        cmd = (
            f"/usr/bin/condor_submit_dag -append"
            f' "use_oauth_services = {vargs["group"]}" -no_submit {f} {qargs}'
        )

        cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
        if vargs.get("verbose", 0) > 0:
            print(f"Running: {cmd}")

        try:
            output = subprocess.run(cmd, shell=True, check=False)
            if output.returncode < 0:
                sys.stderr.write(
                    f"Error: Child was terminated by signal {-output.returncode}"
                )
        except OSError as e:
            print("Execution failed: ", e)

    return submit(subfile, vargs, schedd_name)


class JobIdError(Exception):
    pass


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
    seq: int
    proc: int
    schedd: str
    cluster: bool

    _id_regexp = re.compile(r"(\d+)(?:\.(\d+))?@([\w\.]+)")

    def __init__(self, job_id: str):
        self.id = job_id
        m = Job._id_regexp.match(job_id)
        if m is None:
            raise JobIdError(f'unable to parse job id "{job_id}"')
        try:
            self.seq = int(m.group(1))  # seq is required
            if m.group(2) is None:  # proc is optional
                self.cluster = True
                self.proc = 0
            else:
                self.cluster = False
                self.proc = int(m.group(2))
            self.schedd = m.group(3)  # schedd is required
        except TypeError as e:
            raise JobIdError(f'error when parsing job id "{job_id}"') from e

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

    def _constraint(self) -> str:
        q = f"ClusterId=={self.seq}"
        if not self.cluster:
            q += f" && ProcId=={self.proc}"
        return q

    def get_attribute(self, attr: str) -> Any:
        """
        Return the value of a single job attribute from the schedd. If self is a
        cluster of jobs, the attribute will be returned from the first job found
        on the schedd (not necessarily process 0).

        """
        s = self._get_schedd()
        q = self._constraint()
        res = s.query(q, [attr], limit=1)
        if len(res) == 0:
            raise Exception(f'job matching "{q}" not found on "{self.schedd}"')
        if attr not in res[0]:
            raise Exception(f'attribute "{attr}" not found for job "{str(self)}"')
        return res[0].eval(attr)

    def transfer_data(self, partial: bool = False) -> None:
        """
        Transfer the output sandbox, akin to calling condor_transfer_data. If
        partial is True, only fetch logs for the specified job, not the whole
        cluster.
        """
        s = self._get_schedd()
        # always retrieve whole cluster even if we were specified with
        # a particular process id, unless partial is True
        ssc = self.cluster
        if not partial:
            self.cluster = True
        s.retrieve(self._constraint())
        self.cluster = ssc
