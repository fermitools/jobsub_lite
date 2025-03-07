from typing import Dict, List, Optional, Generator
import re
import sys
import contextlib
from io import StringIO
from mains import jobsub_submit_main, jobsub_fetchlog_main, jobsub_cmd_main
from condor import Job


@contextlib.contextmanager
def output_saver(should_i: bool) -> Generator[StringIO, bool, StringIO]:
    """
    context manager that optionally puts sys.stdio and sys.stderr into
    a StringIO() so you can look at them...
    """

    output = StringIO()
    if should_i:
        # save initial stdout, stderr
        save_out = sys.stdout
        save_err = sys.stderr
        # point them at our StringIO
        sys.stdout = output
        sys.stderr = output
    yield output
    if should_i:
        # put them back
        sys.stderr = save_err
        sys.stdout = save_out
    return output


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
    if not s:
        return ""
    return s


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
        self.group = group
        self.pool = pool
        self.auth_methods = auth_methods
        self.role = role
        self.submit_out = submit_out
        Job.__init__(self, jobid)

    def update_args(self, verbose: int, args: List[str]) -> None:
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

    def hold(self, verbose: int = 0) -> str:
        """Hold this job with jobsub_hold"""
        args = ["jobsub_hold", "-G", self.group, self.jobid()]
        self.update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def release(self, verbose: int = 0) -> str:
        """Release this job with jobsub_release"""
        args = ["jobsub_release", "-G", self.group, self.jobid()]
        self.update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    # pylint: disable=invalid-name
    def rm(self, verbose: int = 0) -> str:
        """Remove this job with jobsub_rm"""
        args = ["jobsub_rm", "-G", self.group, self.jobid()]
        self.update_args(verbose, args)
        rs = optfix(jobsub_call(args, True))
        return rs

    def fetchlog(
        self, destdir: str = "", condor: bool = False, verbose: int = 0
    ) -> str:
        """fetch job output either as tarfile or into directory"""
        args = ["jobsub_fetchlog", "-G", self.group]
        self.update_args(verbose, args)
        if destdir:
            args.append("--destdir")
            args.append(destdir)
        if condor:
            args.append("--condor")
        args.append(self.jobid())
        # print(f"calling jobsub_call {repr(args)}")
        rs = optfix(jobsub_call(args, True))
        return rs


jobsub_required_args = ["group"]

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

    # print(f"calling jobsub_call {repr(args)}")
    rs = optfix(jobsub_call(args, True))
    m = jobsub_submit_re.search(rs)
    if m:
        return SubmittedJob(
            kwargs["group"],
            m.group("jobid"),
            kwargs.get("pool", ""),
            kwargs.get("auth_methods", ""),
            kwargs.get("role", ""),
            rs,
        )
    raise RuntimeError("submission failed: {rs}")


class QResultJob(SubmittedJob):
    # pylint: disable=too-many-arguments
    def __init__(
        self,
        group: str,
        jobid: str,
        pool: str,
        auth_methods: str,
        role: str,
        owner: str,
        submitted: str,
        runtime: str,
        status: str,
        prio: str,
        size: str,
        command: str,
    ) -> None:
        SubmittedJob.__init__(self, group, jobid, pool, auth_methods, role)
        self.owner = owner
        self.submitted = submitted
        self.runtime = runtime
        self.status = status
        self.prio = prio
        self.size = size
        self.command = command

    def __str__(self) -> str:
        return f"{self.jobid():40}  {self.owner:10} {self.submitted:11} {self.runtime:11} {self.status} {self.prio} {self.size:6.1} {self.command}"


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
) -> List[QResultJob]:
    """
    Return list of QResultJob objects of running jobs

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
    res: List[QResultJob] = []
    for line in rs.split("\n")[1:]:
        m = jobsub_q_re.search(line)
        if m:
            res.append(
                QResultJob(
                    kwargs["group"],
                    m.group("jobid"),
                    kwargs.get("pool", ""),
                    kwargs.get("auth_methods", ""),
                    kwargs.get("role", ""),
                    m.group("owner"),
                    m.group("submitted"),
                    m.group("runtime"),
                    m.group("status"),
                    m.group("prio"),
                    m.group("size"),
                    m.group("command"),
                )
            )
    return res
