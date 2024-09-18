#!/usr/bin/python3 -I

#
# api -- calls for apis
#

""" python command  apis for jobsub """
# pylint: disable=wrong-import-position,wrong-import-order,import-error
import argparse
import hashlib
import os
import os.path
import sys
from pprint import pprint
import subprocess
import shutil
from typing import Optional
from condor import Job

# bits that go in each file:
if os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["HIDE_LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    del os.environ["LD_LIBRARY_PATH"]
    os.execv(sys.argv[0], sys.argv)

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.path.join(PREFIX, "lib"))
from tracing import as_span, log_host_time
import get_parser


# pylint: disable=too-many-branches,too-many-statements
@as_span("jobsub_submit", is_main=True)
def jobsub_submit_main(argv=sys.argv):
    """script mainline:
    - parse args
    - get credentials
    - handle tarfile options
    - set added values from environment, etc.
    - convert/render template files to submission files
    - launch
    """
    global verbose  # pylint: disable=global-statement,invalid-name

    parser = get_parser(argparse.ArgumentParser())

    # Argument-checking code
    # old jobsub_client commands got run through a shell that replaced \x with x
    # so we do that here for backwards compatability
    backslash_escape_layer(argv)
    args = parser.parse_args(argv)
    jobsub_submit_args(args)


def jobsub_submit_args(args, passthru=None):

    if not args.global_pool and os.environ.get("JOBSUB_GLOBAL_POOL", ""):
        pool.set_pool(os.environ["JOBSUB_GLOBAL_POOL"])

    # Allow environment variables to append to some command lists to get rid of
    # need for poms_jobsub_wrapper to get in front of us on the path -- we will
    # just set these and have a job-info script report the job id, etc.
    args.environment.extend(get_env_list("JOBSUB_EXTRA_ENVIRONMENT"))
    args.lines.extend(get_env_list("JOBSUB_EXTRA_LINES"))
    args.job_info.extend(get_env_list("JOBSUB_EXTRA_JOB_INFO"))

    sanitize_lines(args.lines)

    verbose = args.verbose

    log_host_time(verbose)

    # if they were trying to pass LD_LIBRARY_PATH to the job, get it from HIDE_LD_LIBRARY_PATH
    if "LD_LIBRARY_PATH" in args.environment and os.environ.get(
        "HIDE_LD_LIBRARY_PATH", ""
    ):
        args.environment = [
            f"{x}={os.environ['HIDE_LD_LIBRARY_PATH']}" if x == "LD_LIBRARY_PATH" else x
            for x in args.environment
        ]

    if args.version:
        print_version()

    if args.support_email:
        print_support_email()

    if args.skip_check:
        if args.verbose:
            print(f"Will skip these checks: {args.skip_check}")
        # Run all the setup items for each check to skip
        for check in args.skip_check:
            skip_checks.skip_check_setup(check)

    # We want to push users to use jobsub_submit --dag, but there are still some legacy
    # users who use the old jobsub_submit_dag executable.  This patches that use case
    if os.path.basename(sys.argv[0]) == "jobsub_submit_dag":
        args.dag = True

    if os.environ.get("GROUP", None) is None:
        raise SystemExit(f"{sys.argv[0]} needs -G group or $GROUP in the environment.")

    # While we're running in hybrid proxy/token mode, force us to get a new proxy every time we submit
    # Eventually, this arg and its support in the underlying libraries should be removed
    args.force_proxy = True

    do_tarballs(args)

    if args.maxConcurrent and int(args.maxConcurrent) >= args.N and not args.dag:
        if args.verbose:
            sys.stderr.write(
                f"Note: ignoring --maxConcurrent {args.maxConcurrent} for {args.N} jobs\n"
            )
        args.maxConcurrent = None

    varg = vars(args)

    cred_set = get_creds(varg)
    if args.verbose:
        print_cred_paths_from_credset(cred_set)

    if args.verbose:
        sys.stderr.write(f"varg: {repr(varg)}\n")

    schedd_add = get_schedd(varg)
    schedd_name = schedd_add.eval("Machine")

    #
    # We work on a copy of our bearer token because
    # condor_vault_storer is going to overwrite it with a token with the weakened scope
    # then get our weakened job scopes, then
    # set the "oauth handle" we're going to use to a hash of our job scopes, so we have a
    # different handle for different scopes.  This makes condor
    # a) store the token as, say "mu2e_830a3a3188.use" and
    # b) refresh it there and
    # c) pass it to the jobs that way.
    # That way if they submit another job with, say,  an additional
    # storage.create:/mu2e/my/output/dir  they will store that token in a file with a
    # different hash, and *that* will get sent to *those* jobs.
    # If they submit another job with these *same* permissions, they will *share* the
    # token filename the conor_vault_credmon will only refresh it once for both (or all
    # three, etc.) submissions, and push that token to all the jobs with that same handle.
    #
    if cred_set.token:
        cred_set.token = use_token_copy(cred_set.token)
        varg["job_scope"] = " ".join(
            get_job_scopes(cred_set.token, args.need_storage_modify, args.need_scope)
        )
        m = hashlib.sha256()
        m.update(varg["job_scope"].encode())
        varg["oauth_handle"] = m.hexdigest()[:10]

    set_extras_n_fix_units(varg, schedd_name, cred_set)

    try:
        if args.dag:
            jobsub_submit_dag(varg, schedd_name)
        elif args.dataset_definition:
            jobsub_submit_dataset_definition(varg, schedd_name)
        elif args.maxConcurrent:
            jobsub_submit_maxconcurrent(varg, schedd_name)
        else:
            jobsub_submit_simple(varg, schedd_name)

        if args.verbose:
            # remind folks where transferred data goes.
            for f in args.orig_input_file:
                print(
                    f"File {f}\n ... will be available as: $CONDOR_DIR_INPUT/{os.path.basename(f)}"
                )
            i = 0
            for f in args.orig_tar_file_name:
                print(
                    f"Contents of {f}\n ... will be available in $INPUT_TAR_DIR_LOCAL{'_'+str(i) if i else ''}"
                )
                i = i + 1
            if args.orig_input_file or args.orig_tar_file_name:
                print("in your job.")
    finally:
        if varg.get("no_submit", False):
            print(f"Submission files are in: {varg['submitdir']}")
        else:
            cleanup(varg)


class StoreGroupinEnvironment(argparse.Action):
    """Action to store the given group in the GROUP environment variable"""

    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore
        os.environ["GROUP"] = values
        setattr(namespace, self.dest, values)


def jobsub_cmd_parser(jobsub_q_flag: bool, parser: argparse.ArgumentParser):
    parser = get_parser.get_jobid_parser(parser=parser)
    parser.add_argument("-name", help="Set schedd name", default=None)
    parser.add_argument(
        "--jobsub_server", help="backwards compatability; ignored", default=None
    )

    # and find the wrapped command name
    cmd = os.path.basename(sys.argv[0])

    # combine jobsub_q as well
    if jobsub_q_flag:
        parser.add_argument("--user", help="username to query", default=None)
    return parser


def jobsub_cmd_main(argv=sys.argv) -> None:
    """main line of code, proces args, etc."""
    parser = jobsub_cmd_parser(
        argv[0].find("jobsub_q") >= 0, parser=argparse.ArgumentParser()
    )

    arglist, passthru = parser.parse_known_args()
    jobsub_cmd_args(arglist, passthru)


def jobsub_cmd_args(arglist, passthru):
    global verbose  # pylint: disable=invalid-name,global-statement

    verbose = arglist.verbose

    log_host_time(verbose)

    if arglist.version:
        print_version()

    if arglist.support_email:
        print_support_email()

    if cmd != "jobsub_q":
        arglist.user = None

    # Re-insert --debug/--verbose if it was given
    if arglist.verbose:
        passthru.append("-debug")
    # if they gave us --jobid or --user put in the value plain, condor figures it out
    if arglist.jobid:
        for jid in arglist.jobid.split(","):
            passthru.append(jid)
    if arglist.user:
        passthru.append(arglist.user)
    # If they gave us --constraint, sanitize it and add to passthru
    if arglist.constraint:
        passthru.extend(["-constraint", arglist.constraint])

    if os.environ.get("GROUP", None) is None:
        raise SystemExit(f"{sys.argv[0]} needs -G group or $GROUP in the environment.")

    # make list of arguments to pass to condor command:
    # - the passthru arguments from above, except if we have
    #   any 234@schedd style arguments, pick out the schedd and
    #   keep the 234, and pass --name schedd as well
    execargs = []
    schedd_list = set()
    # save beginning of 1234@schedd in list of args for that schedd
    args_for_schedd = defaultdict(list)

    if arglist.name:
        schedd_list.add(arglist.name)

    default_formatting = True
    default_constraint = True

    for i in passthru:
        m = re.match(r"([\d.]*)@([\w.]+)", i)
        if m:
            # looks like a jobsub id 12.34@schedd.name
            match_jobid, match_schedd = m.groups()
            schedd_list.add(match_schedd)
            if match_jobid:
                jobid = match_jobid.strip(".")
                args_for_schedd[match_schedd].append(jobid)
            continue

        # convert --better-analyze to -better-analyze, etc.
        if i.startswith("--"):
            i = i[1:]

        if i in [
            "-autoformat",
            "-batch",
            "-better-analyze",
            "-dag",
            "-format",
            "-hold",
            "-io",
            "-json",
            "-long",
            "-nobatch",
            "-xml",
        ]:
            default_formatting = False

        if (
            i
            in [
                "-allusers",
                "-autocluster",
                "-better-analyze",
                "-constraint",
                "-factory",
                "-unmatchable",
            ]
            or i[:1].isalnum()
        ):
            default_constraint = False

        execargs.append(i)

    # also make sure we have suitable credentials...
    _ = creds.get_creds(vars(arglist))

    # and find the wrapped command name
    cmd = os.path.basename(sys.argv[0])

    # TODO:  This patch is to fix a small bug when condor_q is used directly. #pylint: disable=fixme
    # We're trying to combine totals because of the clause at the end of this
    # function that calculates totals.  So this is a patch until we can figure
    # out how we want to handle it properly
    cmd_jobsub_q = False
    # combine jobsub_q as well
    if cmd == "jobsub_q":
        cmd_jobsub_q = True

        # add -schedd-constraint IsJobsubLite==True
        execargs.insert(0, "IsJobsubLite==True")
        execargs.insert(0, "-schedd-constraint")

        if default_constraint:
            execargs.extend(
                [
                    "-allusers",
                    "-constraint",
                    f'''Jobsub_Group=?="{os.environ['GROUP']}"''',
                ]
            )

        if default_formatting:
            # default to old jobsub format
            execargs.extend(
                [
                    "-format",
                    "%-40s",
                    'strcat(split(GlobalJobId,"#")[1],"@",split(GlobalJobId,"#")[0])',
                    "-format",
                    "%-10s\t",
                    """(DAGNodeName=!=''?strcat(" |-",DAGNodeName):Owner)""",
                    "-format",
                    "%-11s ",
                    'formatTime(QDate,"%m/%d %H:%M")',
                    "-format",
                    "%T ",
                    "RemoteWallClockTime",
                    "-format",
                    " %s ",
                    'substr("UIRXCHE",JobStatus,1)',
                    "-format",
                    " %3d ",
                    "JobPrio",
                    "-format",
                    "%6.1f ",
                    "ImageSize/1024.0",
                    "-format",
                    "%s",
                    "JobsubCmd=!=''?JobsubCmd:Cmd",
                    "-format",
                    " %-.20s",
                    "Args",
                    "-format",
                    " %-.20s",
                    "Arguments",
                    "-format",
                    "\n",
                    "Owner",
                ]
            )

            print(
                "JOBSUBJOBID                             OWNER       \tSUBMITTED     RUNTIME"
                "   ST PRIO   SIZE  COMMAND"
            )
            sys.stdout.flush()

            # pipe our remaining output through sort (by date) and jobsub_totals next to us
            jobsub_totals_path = os.path.join(
                os.path.dirname(__file__), "jobsub_totals"
            )
            totalsf = os.popen(f"sort -k 3,4 | {jobsub_totals_path}", "w")
            os.close(1)
            os.dup2(totalsf.fileno(), 1)

    cmd = cmd.replace("jobsub_", "condor_")

    if not schedd_list:
        # if no specific schedds given, get list of all...
        schedd_list = set(condor.get_schedd_names(vars(arglist)))

    if verbose:
        print("schedd list:", schedd_list)

    for schedd in schedd_list:
        os.environ["_condor_CREDD_HOST"] = schedd
        these_args = [cmd, "-name", schedd] + execargs + args_for_schedd.get(schedd, [])
        if verbose:
            print("running:", these_args)
        pid = os.fork()
        if pid:
            os.wait()
        else:
            os.execvp("/usr/bin/" + cmd, these_args)

    if cmd == "condor_q" and default_formatting and cmd_jobsub_q:
        os.close(1)
        totalsf.close()


# environment variable containing base fetchlog server url
_FETCHLOG_URL_ENV = "JOBSUB_FETCHLOG_URL"
# archive download chunk size in bytes
_CHUNK_SIZE = 1024 * 1024


# pylint: disable=too-many-branches
def fetch_from_condor(
    jobid: str, destdir: Optional[str], archive_format: str, partial: bool
):
    # find where the condor_transfer_data will put the output
    j = Job(jobid)
    iwd = j.get_attribute("SUBMIT_Iwd")
    if verbose:
        print(f"job output to {iwd}")
    # make sure it exists, create if not
    try:
        os.stat(iwd)
    except FileNotFoundError:
        os.makedirs(iwd, mode=0o750)

    # get the output sandbox
    try:
        j.transfer_data(partial)
        transfer_complete = True
    except htcondor.HTCondorIOError as e1:
        print(f"Error in transfer_data(): {str(e1)}")
    files = os.listdir(iwd)

    if destdir is not None:
        # If the user wants output in a specific directory, copy files there,
        # don't build an archive. Old jobsub would get an archive from the
        # server, upack it into the dest dir, then delete the archive.
        owd = destdir
        try:
            os.stat(owd)
        except FileNotFoundError:
            os.makedirs(owd, mode=0o750)
        try:
            for f in files:
                shutil.copy2(
                    os.path.join(iwd, f), owd
                )  # copy2 tries to preserve metadata
        except:
            print(f"error copying logs to {owd}, leaving them in {iwd}")
            raise
        else:
            shutil.rmtree(iwd)
    else:
        # build archive
        cmd = []
        if archive_format == "tar":
            cmd = ["/usr/bin/tar", "-C", iwd, "-czf", f"{str(j)}.tgz"] + files
            # -C: move into directory so paths are relative
            # -c: create
            # -z: gzip
            # -f: filename
        elif archive_format == "zip":
            cmd = ["/usr/bin/zip", "-jq", f"{str(j)}.zip"] + [
                os.path.join(iwd, f) for f in files
            ]
            # -j: junk (don't record) directory names
            # -q: quiet
        else:
            raise Exception(f'unknown archive format "{archive_format}"')
        if verbose:
            print(f'running "{cmd}"')
        p = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        if p.wait() != 0:
            raise Exception("error creating archive")

    cleanup({"submitdir": iwd})

    if not transfer_complete:
        print("Transfer may be incomplete.")


# pylint: disable=too-many-locals,too-many-branches
def fetch_from_landscape(
    jobid: str, destdir: Optional[str], archive_format: str, partial: bool
):
    # landscape doesn't support zip, does anyone actually use it?
    if archive_format != "tar":
        raise Exception(f'unknown/unsupported archive format "{archive_format}"')

    if _FETCHLOG_URL_ENV not in os.environ:
        raise Exception(
            f"{_FETCHLOG_URL_ENV} not set in the environment. "
            "You may still be able to download with --condor"
        )
    base_url = os.environ[_FETCHLOG_URL_ENV]
    url = f"{base_url}/job/{jobid}.tar.gz"
    if partial:
        url = url + "?partial"

    owd = os.getcwd()
    if destdir is not None:
        owd = destdir
        try:
            os.stat(owd)
        except FileNotFoundError:
            os.makedirs(owd, mode=0o750)

    # pylint: disable=unspecified-encoding
    with open(os.environ["BEARER_TOKEN_FILE"]) as f:
        tok = f.readline().strip()
    if verbose:
        print(f"making request for archive from {url}")
    r = requests.get(url, stream=True, headers={"Authorization": f"Bearer {tok}"})
    if r.status_code == 401:
        print("Got permission denied from landscape: ")
        pprint(r.json())
        print("Token contents:")
        os.system("httokendecode")
    elif r.status_code >= 400:
        print(f"Got error from landscape:\n{r.text}")
    r.raise_for_status()

    of = os.path.join(owd, f"{jobid}.tgz")
    if verbose:
        print(f"downloading archive to {of}")
    with open(of, "wb") as fb:
        n = 0
        for chunk in r.iter_content(chunk_size=_CHUNK_SIZE):
            n += fb.write(chunk)
    if verbose:
        print(f"{n} bytes downloaded to {of}")

    if destdir is not None:
        cmd = ["/usr/bin/tar", "-C", owd, "-xzf", of]
        # -C: move into directory
        # -x: extract
        # -z: gzip
        # -f: filename
        if verbose:
            print(f'running "{cmd}"')
        p = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        if p.wait() != 0:
            raise Exception(f"error extracting archive to {owd}. Archive left at {of}")
        os.unlink(of)


@as_span("transfer_data")
def traced_transfer_data(j: Job) -> None:
    j.transfer_data()


@as_span("archive")
def traced_wait_archive(p: subprocess.Popen) -> int:
    return p.wait()


def jobsub_fetchlog_parser(parser):
    parser = get_parser.get_jobid_parser(parser)

    parser.add_argument(
        "--destdir",
        "--dest-dir",
        "--unzipdir",
        help="Directory to automatically unarchive logs into",
    )
    parser.add_argument(
        "--archive-format",
        help='format for downloaded archive: "tar" (default, compressed with gzip) or "zip"',
        default="tar",
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help="download only the stdout, stderr, and scripts for this jobid, not the entire sandbox",
        default=False,
    )
    parser.add_argument(
        "--condor",
        action="store_true",
        help="transfer logs directly from condor using condor_transfer_data",
        default=False,
    )
    parser.add_argument("job_id", nargs="?", help="job/submission ID")
    return parser


def jobsub_fetchlog_main(args=sys.argv):
    """script mainline:
    - parse args
    - get credentials
    - get job info
    - condor_transfer_data
    - make tarball
    """
    global verbose  # pylint: disable=global-statement,invalid-name
    transfer_complete = False  # pylint: disable=unused-variable

    parser = argparse.ArgumentParser()
    jobsub_fethlog_parser(parser)
    args = parser.parse_args()
    jobsub_fetchlog_args(args)


def jobsub_fetchlog_args(args, passthru=None):

    verbose = args.verbose

    log_host_time(verbose)

    if args.version:
        print_version()

    if args.support_email:
        print_support_email()

    # jobsub_fetchlog only supports tokens
    if "token" not in args.auth_methods:
        raise SystemExit(
            "jobsub_fetchlog only supports token authentication.  Please either omit the --auth-methods flag or make sure tokens is included in the value of that flag"
        )

    if not args.jobid and not args.job_id:
        raise SystemExit("jobid is required.")

    if not args.jobid and args.job_id:
        args.jobid = args.job_id

    # handle 1234.@jobsub0n.fnal.gov
    args.jobid = args.jobid.replace(".@", "@")

    if args.verbose:
        htcondor.set_subsystem("TOOL")
        htcondor.param["TOOL_DEBUG"] = "D_FULLDEBUG"
        htcondor.enable_debug()

    if os.environ.get("GROUP", None) is None:
        raise SystemExit(f"{sys.argv[0]} needs -G group or $GROUP in the environment.")

    cred_set = creds.get_creds(vars(args))
    if args.verbose:
        creds.print_cred_paths_from_credset(cred_set)

    fetcher = fetch_from_condor if args.condor else fetch_from_landscape
    fetcher(args.jobid, args.destdir, args.archive_format, args.partial)
