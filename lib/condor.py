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
import classad
import random
import packages
import subprocess
from typing import Union, Any, Dict, List

random.seed()

COLLECTOR_HOST = htcondor.param.get("COLLECTOR_HOST", "gpcollector03.fnal.gov")


def get_schedd(vargs: Dict[str, str]) -> classad.ClassAd:
    """get jobsub* schedd names from collector, pick one."""
    coll = htcondor.Collector(COLLECTOR_HOST)
    schedd_classads = coll.locateAll(htcondor.DaemonTypes.Schedd)

    # locateAll gives a list of minimal classads... but
    # need to directQuery for the full classads to check for
    # SupportedVOList...

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
            coll.directQuery(htcondor.DaemonTypes.Schedd, name=ca.eval("Machine"))
        )

    # pick schedds who list our group in their vo list

    schedds = [
        ca
        for ca in full_schedd_classads
        if (
            ("SupportedVOList" in ca)
            and (ca.eval("SupportedVOList").find(vargs["group"]) != -1)
        )
        and ("InDownTime" not in ca)
        or (("InDownTime" in ca) and (ca.eval("InDownTime") != True))
    ]
    res = random.choice(schedds)
    return res


def load_submit_file(filename: str) -> Dict[str, str]:
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
    return htcondor.Submit(res), nqueue


def submit(f: str, vargs: Dict[str, str], schedd_name: str, cmd_args: List[str] = []):
    """Actually submit the job, using condor python bindings"""

    schedd_args = f"-remote {schedd_name}"

    if "no_submit" in vargs and vargs["no_submit"]:
        print(f"NOT submitting file:\n{f}\n")
        return
    if f:
        print(f"submitting: {f}")
        schedd_args = schedd_args + f" {f}"
        fl = glob.glob(f)
        if fl:
            f = fl[0]

    print(f"cmd_args: {cmd_args}")

    # commenting this out for now since the 'else' is not implemented
    #    if True:

    qargs = " ".join([f"'{x}'" for x in cmd_args])
    cmd = f"/usr/bin/condor_submit -pool {COLLECTOR_HOST} {schedd_args} {qargs}"
    cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
    cmd = f"_condor_CREDD_HOST={schedd_name} {cmd}"
    packages.orig_env()
    print(f"Running: {cmd}")

    try:
        output = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, encoding="UTF-8"
        )
        sys.stdout.write(output.stdout)

        if output.returncode < 0:
            print("Child was terminated by signal", -output.returncode)
            return None
        else:
            m = re.search(r"\d+ job\(s\) submitted to cluster (\d+).", output.stdout)
            if m:
                print(
                    f"Use job id {m.group(1)}.0@{schedd_name} to retrieve output"
                )

            if "outdir" in vargs:
                print(
                    f"Output will be in {vargs['outdir']} after running jobsub_transfer_data."
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

    return


def submit_dag(
    f: str, vargs: Dict[str, str], schedd_name: str, cmd_args: List[str] = []
):
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
            f'/usr/bin/condor_submit_dag -append "use_oauth_services = {vargs['group']}" -no_submit {f} {qargs}'
        )

        cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
        print(f"Running: {cmd}")

        try:
            output = subprocess.run(cmd, shell=True)
            if output.returncode < 0:
                print("Child was terminated by signal", -output.returncode)
            else:
                if "outdir" in vargs:
                    print(
                        f"Output will be in {vargs['outdir']} after running jobsub_transfer_data."
                    )
        except OSError as e:
            print("Execution failed: ", e)

    return submit(subfile, vargs, schedd_name)
