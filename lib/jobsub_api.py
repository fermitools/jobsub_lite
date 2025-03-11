from typing import Dict, List, Optional, Generator
import os
import re
import sys
import time
import contextlib
from datetime import datetime, timedelta
from io import StringIO
from htcondor import JobStatus  # type: ignore #pylint: disable=import-error
from mains import jobsub_submit_main, jobsub_fetchlog_main, jobsub_cmd_main
from condor import Job

__all__ = [
    "JobStatus",
    "Job",
    "SubmittedJob",
    "jobsub_call",
    "jobsub_submit_re",
    "jobsub_q_re",
    "submit",
    "q",
]


@contextlib.contextmanager
def output_saver(should_i: bool) -> Generator[StringIO, bool, StringIO]:
    """
    context manager that optionally puts sys.stdio and sys.stderr into
    a StringIO() so you can look at them...
    """

    output = StringIO()
    # save initial stdout, stderr
    save_out = sys.stdout
    save_err = sys.stderr
    try:
        if should_i:
            # point them at our StringIO
            sys.stdout = output
            sys.stderr = output
        yield output
        if should_i:
            # put them back
            sys.stderr = save_err
            sys.stdout = save_out
        return output
    except:
        sys.stderr = save_err
        sys.stdout = save_out
        raise


# so clients can easily parse the result strings
jobsub_submit_re = re.compile(r"Use job id (?P<jobid>[0-9.]+\@[^ ]+) to retrieve")

jobsub_q_re = re.compile(
    r"(?P<jobid>\S+)\s+"
    r"(?P<owner>\S+)\s+"
    r"(?P<submitted>\S+\s\S+)\s+"
    r"(?P<runtime>\S+)\s+"
    r"(?P<status>\S+)\s+"
    r"(?P<prio>\S+)\s+"
    r"(?P<size>\S+)\s+"
    r"(?P<command>.*)"
)


def jobsub_call(argv: List[str], return_output: bool = False) -> Optional[str]:
    """
    Low level API call for jobsub commands.

    You pass it an argv list and a flag.  (i.e.
          jobsub_call(["jobsub_submit","-G","fermilab","file://foo.sh"], True)

    If the flag is True, it returns a string of the output of the jobsub command,
    otherwise the output goes to stdout/stderr.
    """
    res = None
    if argv[0].find("_submit") > 0:
        func = jobsub_submit_main
    elif argv[0].find("_fetchlog") > 0:
        func = jobsub_fetchlog_main
    else:
        func = jobsub_cmd_main
    try:
        with output_saver(return_output) as output:
            func(argv)
            res = output.getvalue()
    except:
        print(f"Excepion in jobsub_call({argv})")
        raise
    return res


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=


def optfix(s: Optional[str]) -> str:
    """typing fix -- make string not Optional"""
    if not s:
        return ""
    return s


# pylint: disable=too-many-instance-attributes
class SubmittedJob(Job):
    """result of fancier jobsub_submit call"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        group: str,
        jobid: str,
        pool: str = "",
        auth_methods: str = "",
        role: str = "",
        submit_out: str = "",
    ) -> None:
        """save various job submission values to reuse for hold, queue, etc."""
        Job.__init__(self, jobid.strip())
        self.group = group.strip()
        self.pool = pool.strip()
        self.auth_methods = auth_methods.strip()
        self.role = role.strip()
        self.submit_out = submit_out
        self.status = None
        self.set_q_attrs()

    def set_q_attrs(
        self,
        owner: str = "",
        submitted: str = "",
        runtime: str = "",
        status: str = "",
        command: str = "",
        prio: str = "",
        size: str = "",
    ) -> None:
        """note values from jobsub_q output, owner, submitted, status, etc."""
        init_JSMAP()
        self.owner = owner
        self.submitted = jsq_date_to_datetime(submitted) if submitted else None
        self.runtime = jsq_runtime_to_timedelta(runtime) if runtime else None
        self.status = JSMAP[status] if status else None
        self.prio = float(prio) if prio else None
        self.size = float(size) if size else None
        self.command = command

    def _update_args(self, verbose: int, args: List[str]) -> None:
        """code adding common arguments to commands"""
        args.append("-G")
        args.append(self.group)
        if verbose:
            args.append("--verbose")
            args.append(str(verbose))
        if self.pool:
            args.append("--global-pool")
            args.append(self.pool)
        if self.auth_methods:
            args.append("--auth-methods")
            args.append(self.auth_methods)
        if self.role:
            args.append("--role")
            args.append(self.role)
        args.append(self.id)

    def hold(self, verbose: int = 0) -> str:
        """Hold this job with jobsub_hold"""
        args = ["jobsub_hold"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def release(self, verbose: int = 0) -> str:
        """Release this job with jobsub_release"""
        args = ["jobsub_release"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    # pylint: disable=invalid-name
    def rm(self, verbose: int = 0) -> str:
        """Remove this job with jobsub_rm"""
        args = ["jobsub_rm"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def q(self, verbose: int = 0) -> None:
        """run 'jobsub_q' on this job and update values, status"""
        args = ["jobsub_q"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        lines = rs.split("\n")
        if len(lines) == 2 and self.status is not None:
            # we saw it previously, and now it is not showing up..
            self.status = JobStatus.COMPLETED
            return
        if len(lines) > 1:
            line = rs.split("\n")[1]
            m = jobsub_q_re.search(line)
            if m:
                self.set_q_attrs(
                    m.group("owner"),
                    m.group("submitted"),
                    m.group("runtime"),
                    m.group("status"),
                    m.group("command"),
                    m.group("prio"),
                    m.group("size"),
                )
                return
        raise RuntimeError(f"failed jobsub_q:\n {rs}")

    def q_long(self, verbose: int = 0) -> Dict[str, str]:
        """run 'jobsub_q --long' on this job and update values, status,
        and return the dictionary of name/value pairs from the ouput"""
        args = ["jobsub_q", "--long"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        lines = rs.split("\n")
        res = {}
        for line in lines:
            if not line.find(" = ") > 0:
                continue
            k, v = line.split(" = ", 1)
            if v[0] == '"':
                v = v.strip('"')
            res[k] = v
        if len(lines) == 1 and self.status is not None:
            self.status = JobStatus.COMPLETED
        else:
            self.set_q_attrs(
                res.get("Owner", ""),
                res.get("QDate", ""),
                res.get("RemoteWallClockTime", ""),
                res.get("JobStatus", ""),
                res.get("Cmd", ""),
                res.get("JobPrio", ""),
                res.get("ExecutableSize", ""),
            )
        return res

    def q_analyze(self, verbose: int = 0) -> str:
        """run jobsub_q --better-analyze on the job and return results"""
        args = ["jobsub_q", "--better-analyze"]
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def wait(self, howoften: int = 300, verbose: int = 0) -> None:
        """poll with q() every howoften seconds until the job
        is COMPLETED, HELD, or REMOVED"""
        self.q()
        while self.status not in (
            JobStatus.COMPLETED,
            JobStatus.HELD,
            JobStatus.REMOVED,
        ):
            if verbose:
                print(str(self), end="\r")
            time.sleep(howoften)
            self.q()

        if verbose:
            print("", end="\r")

    def fetchlog(
        self, destdir: str = "", condor: bool = False, verbose: int = 0
    ) -> str:
        """fetch job output either as tarfile in current directory
        or unpacked into directory destdir"""
        args = ["jobsub_fetchlog"]
        if destdir:
            args.append("--destdir")
            args.append(destdir)
        if condor:
            args.append("--condor")
        self._update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def __str__(self) -> str:
        """return jobsub_q style text line (slightly wider)"""
        return f"{self.id:40} {self.owner:10.10} {str(self.submitted):19.19} {str(self.runtime):17} {str(self.status)[10:]:9} {self.prio:6.1f} {self.size:6.1f} {self.command}"


jobsub_required_args = ["group"]

# could we generate this from the option parser?
jobsub_flags = {
    "dag": "--dag",
    "mail_always": "--mail_always",
    "mail_on_error": "--mail_on_error",
    "managed_token": "--managed-token",
    "n": "-n",
    "mail_never": "--mail-never",
    "onsite": "--onsite",
    "offsite": "--offsite",
    "use_cvmfs_dropbox": "--use-cvmfs-dropbox",
    "use_pnfs_dropbox": "--use-pnfs-dropbox",
}

# could we generate this from the option parser?
jobsub_options = {
    "auth_methods": "--auth-methods",
    "blocklist": "--blocklist",
    "c": "-c",
    "cmtconfig": "--cmtconfig",
    "cpu": "--cpu",
    "dataset_definition": "--dataset-definition",
    "dd_extra_dataset": "--dd-extra-dataset",
    "dd_percentage": "--dd-percentage",
    "devserver": "--devserver",
    "disk": "--disk",
    "d": "-d",
    "e": "-e",
    "email_to": "--email-to",
    "expected_lifetime": "--expected-lifetime",
    "f": "-f",
    "generate_email_summary": "--generate-email-summary",
    "group": "-G",
    "global_pool": "--global-pool",
    "gpu": "--gpu",
    "i": "-i",
    "job_info": "--job-info",
    "L": "-L",
    "maxConcurrent": "--maxConcurrent",
    "memory": "--memory",
    "need_scope": "--need-scope",
    "need_storage_modify": "--need-storage-modify",
    "N": "-N",
    "no_env_cleanup": "--no-env-cleanup",
    "OS": "--OS",
    "overwrite_condor_requirements": "--overwrite-condor-requirements",
    "project_name": "--project-name",
    "resource_provides": "--resource-provides",
    "role": "--role",
    "r": "-r",
    "singularity_image": "--singularity-image",
    "site": "--site",
    "skip_check": "--skip-check",
    "subgroup": "--subgroup",
    "tarball_exclusion_file": "--tarball-exclusion-file",
    "tar_file_name": "--tar_file_name",
    "timeout": "--timeout",
    "t": "-t",
    "verbose": "--verbose",
}


# pylint: disable=dangerous-default-value, too-many-branches
def submit(
    executable: str,
    exe_arguments: List[str] = [],
    lines: List[str] = [],
    env: Dict[str, str] = {},
    **kwargs: str,
) -> SubmittedJob:
    """
    Submit a Condor job with jobsub_submit.  Takes a plethora of arguments
    based on the jobsub_submit script arguents, see that documentation for
    more details.

    Booolean arguments:
        dag -- executable is a dagnabbit dag file, not a script
        mail_always  -- when to send mail
        mail_on_error
        mail_never
        managed_token -- optimzie for managed tokens
        n -- don't actually submit, just generate files
        onsite -- restrict job to onsite
        offsite -- restrict job to offsite
        use_cvmfs_dropbox -- use cvmfs RCDS service for dropbox files
        use_pnfs_dropbox -- use DCahe for dropbox files
    Options taking lists of strings
        lines -- lines to append to job file
        exe_arguments -- command-line arguments to give to  executable
    Options taking a dictionary
        env environment variables and values to pass
    Options taking string values
        executable -- executable to run
        auth_methods -- comma separated list from toksn,proxy
        blocklist -- comma separated list of sites to avoid
        c -- condor requirements to append
        cmtconfig -- cmt configuration (Minerva speceific)
        cpu -- minimum cpu's to request
        dataset_definition -- SAM dataset definition for project/DAG
        dd_extra_dataset -- SAM extra datasaet definition to stage in start job
        dd_percentage -- Percentage staging to require in start job
        devserver -- use development schedd to submit
        disk -- disk space tor equest, with units from  KB,MB,GB,TB
        d -- tag:destination string;
             Writable directory $CONDOR_DIR_<tag>
            will exist on the execution node. After job
            completion, its contents will be moved to <dir>
        email_to -- email address for results
        expected_lifetime -- lifetime of job short,medium,long or digits and
            units from s,m,h,d
        f -- input file to copy into job working directory
        generate_email_summary -- one mail for DAG jobs summary
        G -- group / experiment name
        global_pool -- global pool name if any (.ie. "dune")
        gpu -- number of gpus  on nodes
        i - experiment release directory
        job_info -- script to call with jobid and command line upon submission
        L -- log file name for job output
        maxConcurrent -- maxumum number of jobs to run simultaneously
        memory -- amount of memory to request allows suffixes from KB,MB,GB,TB
        need_scope -- scopes needed in job auth tokens
        need_storage_modify -- paths to ave storage:modif in auth token scope
        N -- number of jobs to submit
        no_env_cleanup -- do not clean environment in wrapper script
        OS -- operating system to request, can be multiples comma separated
        overwrite_condor_requirements -- requirements to replace standard ones
        project_name -- name of SAM project to use in DAGS
        resource_provides -- request specific resources
        role -- token role to use
        r -- experiment release version
        singularity_image -- cvmfs path to singularity image for job
        site -- comma separated list of sites to use
        skip_check -- skip checks done by default from rcds
        subgroup -- subgroup with role for permissions
        tarball_exclusion_file -- file exculsions for tarfile generation
        tar_file_name -- tarfile to send to job and unpack in $TAR_DIR_LOCAL
        timeout -- end job if it runs longer than this units from ms,m,h,d
        t -- experiment test-relesase directory
        verbose -- verbosity, interger from 1 to 10
    """
    args = ["jobsub_submit"]

    for k in jobsub_required_args:
        if k not in kwargs:
            raise TypeError(f"missing required argument {k}")

    for k in env:
        args.append("-e")
        if env[k]:
            args.append(f"{k}={env[k]}")
        else:
            args.append(k)

    for k in lines:
        args.append("--lines")
        args.append(k)

    # pylint: disable=consider-using-dict-items
    for k in kwargs:
        if k in jobsub_options:
            args.append(jobsub_options[k])
            if k == "d":
                tag, dest = kwargs[k].split(":", 1)
                args.append(tag)
                args.append(dest)
            else:
                args.append(str(kwargs[k]))
        elif k in jobsub_flags:
            args.append(jobsub_flags[k])
        else:
            raise TypeError(f"unknown argument {k}")

    args.append(f"file://{executable}")
    args.extend(exe_arguments)

    rs = optfix(jobsub_call(args, True))
    m = jobsub_submit_re.search(rs)
    if m:
        job = SubmittedJob(
            kwargs["group"],
            m.group("jobid"),
            kwargs.get("pool", ""),
            kwargs.get("auth_methods", ""),
            kwargs.get("role", ""),
            rs,
        )
        # we think we know some jobsub_q attrs due to having just launched
        job.set_q_attrs(
            os.environ["USER"],
            str(int(time.time())),
            "0.0",
            "I",
            executable,
            "0.0",
            "0.0",
        )
        return job
    raise RuntimeError(f"submission failed: {rs}")


def jsq_date_to_datetime(s: str) -> datetime:
    """convert either jobsub_q start date or --long datestamp to datetime"""
    if s.find("/") > 0:
        # near the year boundary the start date may be from last year
        # indicated by a month larger than the current month (i.e
        # start date month is in December but it is January
        now = datetime.now()
        sdmonth = int(s[:2])
        year = now.year
        if sdmonth > now.month:
            year = year - 1
        # convert to full iso date string dashes for month-day, T before time
        isos = s.replace(" ", "T").replace("/", "-")
        # and year in front
        isos = f"{year}-{isos}"
        return datetime.fromisoformat(isos)
    return datetime.fromtimestamp(int(s))


def jsq_runtime_to_timedelta(s: str) -> timedelta:
    """convert jobsub_q runtime or --long float value to timedelta"""
    if s.find(":") > 0:
        days, hours, minutes, seconds = re.split("[+:]", s)
        return timedelta(
            days=int(days), hours=int(hours), minutes=int(minutes), seconds=int(seconds)
        )
    return timedelta(seconds=int(float(s)))


JSMAP: Dict[str, JobStatus] = {}


def init_JSMAP() -> None:
    """make a map that converts status strings to JobStatus values
    from either jobsub_q status leters IRXH or --long 01245 values
    by going through the htcondor.JobStatus enums class
    """
    if len(JSMAP.keys()):
        return
    for k in JobStatus.__members__:
        if k == "REMOVED":
            jl = "X"
        else:
            jl = k[0]
        if jl not in JSMAP:
            JSMAP[jl] = JobStatus.__members__[k]
            JSMAP[str(int(JobStatus.__members__[k]))] = JobStatus.__members__[k]


qargs = [
    "group",
    "auth_methods",
    "global_pool",
    "role",
    "subgroup",
    "constraint",
    "name",
    "user",
]


def q(
    *jobids: str, devserver: bool = False, verbose: int = 0, **kwargs: str
) -> List[SubmittedJob]:
    """
    Return list of SubmittedJob objects of running jobs

    Keyword Arguments:
    devserver -- (bool) use development server
    verbose -- (int) verbosity
    group -- group/experiment to authenticate under
    auth_methods -- comma sep list from token,proxy
    global_pool -- alternate pool i.e. "dune"
    role -- role to authenticate under
    subgroup -- further authentication subgroup
    constraint -- job limit constraint, see condor docs
    name -- schedd name to use
    user -- restrict to user's jobs

    Remaining arguments are jobids to query
    """
    args = ["jobsub_q"]
    if "group" not in kwargs:
        raise TypeError("G option is required")
    if devserver:
        args.append("--devserver")
    if verbose:
        args.append("--verbose")
        args.append(str(verbose))
    for k in qargs:
        if k in kwargs:
            opt = k.replace("_", "-")
            args.append(f"--{opt}")
            args.append(kwargs[k])
    for j in jobids:
        args.append(j)
    rs = optfix(jobsub_call(args, True))
    res: List[SubmittedJob] = []
    for line in rs.split("\n")[1:]:
        m = jobsub_q_re.search(line)
        if m:
            job = SubmittedJob(
                kwargs["group"],
                m.group("jobid"),
                kwargs.get("pool", ""),
                kwargs.get("auth_methods", ""),
                kwargs.get("role", ""),
            )
            job.set_q_attrs(
                m.group("owner"),
                m.group("submitted"),
                m.group("runtime"),
                m.group("status"),
                m.group("command"),
                m.group("prio"),
                m.group("size"),
            )
            res.append(job)
    return res
