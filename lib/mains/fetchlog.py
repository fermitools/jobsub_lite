#!/usr/bin/python3 -I

#
# api -- calls for apis
#

"""python command  apis for jobsub"""
# pylint: disable=wrong-import-position,wrong-import-order,import-error
import argparse
import os
import os.path
import sys
from pprint import pprint
import subprocess
import shutil
from typing import Optional, List
import condor

# bits that go in each file:
if os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["HIDE_LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    del os.environ["LD_LIBRARY_PATH"]
    os.execv(sys.argv[0], sys.argv)

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.path.join(PREFIX, "lib"))
from tracing import as_span, log_host_time
import get_parser

from utils import cleanup
import version
import htcondor  # type: ignore # pylint: disable=wrong-import-position
import creds
import requests  # type: ignore

from .common import VERBOSE

# environment variable containing base fetchlog server url
_FETCHLOG_URL_ENV = "JOBSUB_FETCHLOG_URL"
# archive download chunk size in bytes
_CHUNK_SIZE = 1024 * 1024


# pylint: disable=too-many-branches
def fetch_from_condor(
    jobid: str, destdir: Optional[str], archive_format: str, partial: bool
) -> None:
    # find where the condor_transfer_data will put the output
    j = condor.Job(jobid)
    iwd = j.get_attribute("SUBMIT_Iwd")
    if VERBOSE:
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
        if VERBOSE:
            print(f'running "{cmd}"')
        p = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        if p.wait() != 0:
            raise Exception("error creating archive")

    cleanup({"submitdir": iwd, "verbose": VERBOSE})

    if not transfer_complete:
        print("Transfer may be incomplete.")


# pylint: disable=too-many-locals,too-many-branches
def fetch_from_landscape(
    jobid: str, destdir: Optional[str], archive_format: str, partial: bool
) -> None:
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
    if VERBOSE:
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
    if VERBOSE:
        print(f"downloading archive to {of}")
    with open(of, "wb") as fb:
        n = 0
        for chunk in r.iter_content(chunk_size=_CHUNK_SIZE):
            n += fb.write(chunk)
    if VERBOSE:
        print(f"{n} bytes downloaded to {of}")

    if destdir is not None:
        cmd = ["/usr/bin/tar", "-C", owd, "-xzf", of]
        # -C: move into directory
        # -x: extract
        # -z: gzip
        # -f: filename
        if VERBOSE:
            print(f'running "{cmd}"')
        p = subprocess.Popen(cmd)  # pylint: disable=consider-using-with
        if p.wait() != 0:
            raise Exception(f"error extracting archive to {owd}. Archive left at {of}")
        os.unlink(of)


@as_span("transfer_data")
def traced_transfer_data(j: condor.Job) -> None:
    j.transfer_data()


@as_span("archive")
def traced_wait_archive(p: subprocess.Popen) -> int:  # type: ignore
    return p.wait()


def jobsub_fetchlog_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
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


# pylint: disable=dangerous-default-value
@as_span("jobsub_fetchlog", is_main=True)
def jobsub_fetchlog_main(argv: List[str] = sys.argv) -> None:
    """script mainline:
    - parse args
    - get credentials
    - get job info
    - condor_transfer_data
    - make tarball
    """
    global VERBOSE  # pylint: disable=global-statement,invalid-name
    transfer_complete = False  # pylint: disable=unused-variable

    parser = argparse.ArgumentParser()
    parser = jobsub_fetchlog_parser(parser)
    args = parser.parse_args(argv[1:])
    VERBOSE = args.verbose
    jobsub_fetchlog_args(args)


def jobsub_fetchlog_args(
    args: argparse.Namespace, passthru: Optional[List[str]] = None
) -> None:

    global VERBOSE  # pylint: disable=global-statement
    VERBOSE = args.verbose

    if passthru:
        raise argparse.ArgumentError(None, f"unknown arguments: {repr(passthru)}")

    log_host_time(VERBOSE)

    # If called from jobsub or jobsub_* commands, this is redundant. However, we keep it in there
    # for the case where the user imports this module and calls jobsub_cmd_args directly.
    if args.version:
        version.print_version()
        return

    if args.support_email:
        version.print_support_email()
        return

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
