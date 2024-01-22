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
from contextlib import contextmanager
import os
import sys
import random
import re
import shutil
import subprocess
from typing import Dict, List, Any, Tuple, Optional, Union, Generator

# pylint: disable=import-error
import classad  # type: ignore
import htcondor  # type: ignore
import jinja2  # type: ignore

# pylint: disable=cyclic-import
import fake_ifdh
import packages
from render_files import render_files
from tracing import as_span
from transfer_sandbox import transfer_sandbox

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

random.seed()

# pylint: disable-next=no-member
COLLECTOR_HOST = htcondor.param.get("COLLECTOR_HOST", None)

# Global dict to hold onto schedd ads so we only have to query schedd once
# This should ONLY be changed by get_schedd_list
__schedd_ads: Dict[str, classad.ClassAd] = {}


# pylint: disable=invalid-name,too-many-branches
@contextmanager
def submit_vt(
    vo: str, role: str, schedd: str, verbose: int
) -> Generator[None, None, None]:
    """
    Rearrange vaulttoken files around a submit
    Rename them to keep timestamps, etc.
    """
    try:
        tmp = os.environ.get("TMPDIR", "/tmp")
        uid = os.getuid()
        pid = os.getpid()
        if verbose > 1:
            print("vault tokens before pre-submit renaming:")
            os.system(f"ls -l {tmp}/vt_u{uid}*")
        schedvtname = f"{tmp}/vt_u{uid}-{schedd}-{vo}_{role}"
        if role != fake_ifdh.DEFAULT_ROLE:
            vtname = f"{tmp}/vt_u{uid}-{vo}_{role}"
        else:
            vtname = f"{tmp}/vt_u{uid}-{vo}"
        plainvtname = f"{tmp}/vt_u{uid}"  # pylint: disable=unused-variable

        if os.path.exists(vtname) and not os.access(vtname, os.W_OK):
            if verbose > 1:
                print("Not doing vault token renaming: readonly vault token")
        else:
            if os.path.exists(schedvtname):
                if verbose > 0:
                    print(f"moving in saved vaulttoken {schedvtname}")

                if os.path.exists(vtname):
                    os.rename(vtname, f"{vtname}.{pid}")
                os.rename(schedvtname, vtname)

            if verbose > 1:
                print("vault tokens after pre-submit renaming:")
                os.system(f"ls -l {tmp}/vt_u{uid}*")

        yield None

    finally:
        if os.path.exists(vtname) and not os.access(vtname, os.W_OK):
            if verbose > 1:
                print("Not doing vault token renaming: readonly vault token")
        else:
            if os.path.exists(vtname):
                if verbose > 0:
                    print(f"saving vaulttoken as {schedvtname}")
                os.rename(vtname, schedvtname)

            # if we saved a vaulttokenfile earlier, put it back,
            if os.path.exists(f"{vtname}.{pid}"):
                os.rename(f"{vtname}.{pid}", vtname)

            if verbose > 1:
                print("vault tokens after post-submit renaming:")
                os.system(f"ls -l {tmp}/vt_u{uid}*")

        return None  # pylint: disable=lost-exception


# pylint: disable-next=no-member
@as_span("get_schedd_list")
def get_schedd_list(
    vargs: Dict[str, Any], refresh_schedd_ads: bool = False, available_only: bool = True
) -> List[classad.ClassAd]:
    """
    Get jobsub* schedd classads from collector.  Also, populate the in-memory store of the schedd
    classads
    """
    global __schedd_ads  # pylint: disable=global-statement

    # First, try to load schedd ads from memory
    if __schedd_ads and not refresh_schedd_ads and available_only:
        if vargs.get("verbose", 0) > 1:
            print("\nUsing cached schedd ads - NOT querying condor collector\n")
        return list(__schedd_ads.values())

    # If schedd ads not in memory or refresh_schedd_ads is True, go ahead and get the classads from the collector
    if vargs.get("verbose", 0) > 1:
        print(f"\nQuerying condor collector {COLLECTOR_HOST} for schedd ads\n")

    # Constraint setup
    constraint = (
        '{% if schedd_for_testing is defined and schedd_for_testing %} Name == "{{schedd_for_testing}}"{% else %}'
        "IsJobsubLite=?=true"
        '{% if group is defined and group %} && STRINGLISTIMEMBER("{{group}}", SupportedVOList){% endif %}'
        ' && {% if devserver is defined and devserver %}{% else %}!{%endif%}regexp(".*dev.*", Machine)'
        " && InDownTime != true"
        "{% endif %}"
    )
    if not available_only:
        constraint = ""

    jinja_env = jinja2.Environment()
    constraint_template = jinja_env.from_string(constraint)
    try:
        schedd_constraint = constraint_template.render(vargs)
    except jinja2.TemplateError as e:
        print(f"Could not render constraint template: {e}")
        raise

    # pylint: disable-next=no-member
    coll = htcondor.Collector(COLLECTOR_HOST)
    # pylint: disable-next=no-member
    if vargs.get("verbose", 0) > 0:
        print(
            f"Using the following constraint for finding schedds: {schedd_constraint}\n"
        )

    # Get schedd ads from collector and store them in memory
    schedds: List[classad.ClassAd] = coll.query(
        htcondor.htcondor.AdTypes.Schedd,
        constraint=schedd_constraint,
    )

    # only cache if we're getting the usual list
    if available_only:
        __schedd_ads = {ad.eval("Name"): ad for ad in schedds}

    if vargs.get("verbose", 0) > 1:
        print(f"post-query schedd classads: {schedds} ")

    return schedds


def get_schedd_names(vargs: Dict[str, Any], available_only: bool = True) -> List[str]:
    """get jobsub* schedd names from collector"""
    schedds = get_schedd_list(vargs, available_only=available_only)
    res = []
    for s in schedds:
        name = s.eval("Name")
        res.append(name)
    return res


# pylint: disable-next=no-member
def get_schedd(vargs: Dict[str, Any]) -> classad.ClassAd:
    """pick a jobsub* schedd name from collector"""
    schedds = get_schedd_list(vargs)
    if len(schedds) == 0:
        raise Exception("Error: No schedds satisfying the constraint were found")

    # pick weights based on (inverse) of  duty cycle of schedd
    weights = []
    for s in schedds:
        name = s.eval("Name")

        # If user has specified a schedd, just use that one.  Don't worry about
        #  weighting or anything like that
        if vargs.get("schedd_for_testing", None):
            if name == vargs["schedd_for_testing"]:
                print(f"Using requested schedd {name}")
                return s
            continue

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

    # If we requested a specific schedd to test with, we should have found it by now and returned
    # before we even got here.  If not, raise an error
    if vargs.get("schedd_for_testing", None):
        raise ValueError(
            "Requested testing schedd not found.  Please either remomve "
            "--schedd-for-testing flag or choose a different schedd to test "
            "with."
        )

    res = random.choices(schedds, weights=weights)[0]
    if vargs.get("verbose", 0) > 0:
        print(f'Chose schedd {res.eval("Name")}')
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


# pylint: disable=dangerous-default-value,too-many-locals,too-many-branches
@as_span("submit", arg_attrs=["*"])
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
    if vargs.get("token", None) is not None:
        cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"
    cmd = f"_condor_CREDD_HOST={schedd_name} {cmd}"
    #
    # set up to use our custom condor_vault_storer until we get
    # the updated one in the condor release
    #
    jldir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = f"_condor_SEC_CREDENTIAL_STORER={jldir}/bin/condor_vault_storer {cmd}"
    #
    packages.orig_env()
    verbose = int(vargs.get("verbose", 0))
    if verbose > 0:
        print(f"Running: {cmd}")

    try:
        # Submit the job!
        with submit_vt(vargs["group"], vargs["role"], schedd_name, verbose):
            output = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="UTF-8",
                check=False,
            )
            sys.stdout.write(output.stdout)
            sys.stderr.write(output.stderr)

        hl = f"\n{'=-'*30}\n\n"  # highlight line to make result stand out

        if output.returncode < 0:
            sys.stderr.write(
                f"{hl}Error: Child was terminated by signal {-output.returncode}{hl}\n"
            )
            return None

        if output.returncode > 0:
            specific_error_msg_list = []
            # Specific error text cases.  For each kind of error message we want to make more
            # user-friendly, search the output, generate the message, and append it to
            # specific_errors_msg_list.

            # 1. Number of submitted jobs > MAX_JOBS_PER_SUBMISSION
            m = re.search(
                "Number of submitted jobs would exceed MAX_JOBS_PER_SUBMISSION",
                output.stderr,
            )
            if m:
                msg = generate_error_message_for_too_many_procs(vargs, schedd_name)
                specific_error_msg_list.append(msg)
            ## Specify any more specific error messages here

            specific_error_msgs = "\n".join(specific_error_msg_list)
            sys.stderr.write(
                f"{hl}Error: condor_submit exited with failed status code {output.returncode}\n\n"
                f"{specific_error_msgs}{hl}\n"
            )
            return None

        # If we had a successful submission, give the job id to the user
        m = re.search(r"\d+ job\(s\) submitted to cluster (\d+).", output.stdout)
        if m:
            print(f"{hl}Use job id {m.group(1)}.0@{schedd_name} to retrieve output{hl}")

            # call any job_info commands requested with the jobid
            for ji in vargs.get("job_info", []):
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


def get_transfer_file_list(f: str) -> List[str]:
    """read submit file, look for needed SCRIPT or JOB files"""
    res = [f]
    cmdlist = []
    with open(f, "r") as inf:  # pylint: disable=unspecified-encoding
        for l in inf.readlines():
            m = re.match(r"(JOB|SCRIPT).* (\S+) *$", l)
            if m:
                res.append(m.group(2))
                if m.group(1) == "JOB":
                    cmdlist.append(m.group(2))
    for f in cmdlist:  # pylint: disable=redefined-argument-from-local
        with open(f, "r") as inf:  # pylint: disable=unspecified-encoding
            for l in inf.readlines():
                m = re.match(r"(executable|transfer_input_files) *= *(\S+) *$", l)
                if m and not m.group(2) in res:
                    res.append(m.group(2))
    return res


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
        # qargs = " ".join([f"'{x}'" for x in cmd_args])
        qargs = " ".join(cmd_args)

        vargs["transfer_files"] = vargs.get(
            "transfer_files", []
        ) + get_transfer_file_list(f)

        d1 = os.path.join(PREFIX, "templates", "condor_submit_dag")
        render_files(d1, vargs, vargs["outdir"], xfer=False)

        for cf in vargs["transfer_files"] + [f]:
            print(f"Copying file: {cf}")
            dst = f"{vargs['outdir']}/{os.path.basename(cf)}"
            if dst != cf:
                shutil.copyfile(cf, dst)

        os.chdir(vargs["outdir"])

        f = os.path.basename(f)
        subfile = os.path.basename(subfile)

        cmd = (
            f"/usr/bin/condor_submit_dag -insert_sub_file sub_file "
            f"-no_submit -dagman dagman_wrapper.sh {qargs} {f} "
        )

        # if vargs.get("token", None) is not None:
        #    cmd = f"BEARER_TOKEN_FILE={os.environ['BEARER_TOKEN_FILE']} {cmd}"

        if vargs["outurl"]:
            transfer_sandbox(vargs["outdir"], vargs["outurl"])

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

    return submit(subfile, vargs, schedd_name=schedd_name)


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


def generate_error_message_for_too_many_procs(
    vargs: Dict[str, Any], schedd_name: str
) -> str:
    """
    Number of submitted jobs > MAX_JOBS_PER_SUBMISSION, so generate an error message for that
    """
    default_msg = (
        "There was an error obtaining the MAX_JOBS_PER_SUBMISSION from the schedd. "
        "Please try breaking up your submission into clusters with fewer jobs."
    )
    try:
        limit = __schedd_ads[schedd_name].eval("Jobsub_Max_Jobs_Per_Submission")
    except (AttributeError, KeyError):
        # For whatever reason, get_schedd_list was never called before calling submit
        get_schedd_list(vargs, refresh_schedd_ads=True)
        limit = __schedd_ads[schedd_name].eval("Jobsub_Max_Jobs_Per_Submission")
    except ValueError:
        # The classad exists but doesn't have this attribute at all.  Fall back to default
        return default_msg

    try:
        msg = (
            "MAX_JOBS_PER_SUBMISSION limits the number of jobs allowed in a submission. "
            f"The limit is {limit}.\n"
            f"Please break up your submission into clusters with at most {limit} jobs each."
        )
    except NameError:
        return default_msg

    return msg
