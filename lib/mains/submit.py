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
from typing import Optional, List
import condor
from token_mods import use_token_copy, get_job_scopes

# bits that go in each file:
if os.environ.get("LD_LIBRARY_PATH", ""):
    os.environ["HIDE_LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH"]
    del os.environ["LD_LIBRARY_PATH"]
    os.execv(sys.argv[0], sys.argv)

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(os.path.join(PREFIX, "lib"))
from tracing import as_span, log_host_time
import get_parser
import pool
from submit_support import (
    get_env_list,
    jobsub_submit_dag,
    jobsub_submit_dataset_definition,
    jobsub_submit_maxconcurrent,
    jobsub_submit_simple,
)

from utils import (
    cleanup,
    sanitize_lines,
    backslash_escape_layer,
    set_extras_n_fix_units,
)
import version
import tarfiles
import creds
import skip_checks

from .common import VERBOSE

# pylint: disable=too-many-branches,too-many-statements,dangerous-default-value
@as_span("jobsub_submit", is_main=True)
def jobsub_submit_main(argv: List[str] = sys.argv) -> None:
    """script mainline:
    - parse args
    - get credentials
    - handle tarfile options
    - set added values from environment, etc.
    - convert/render template files to submission files
    - launch
    """
    global VERBOSE  # pylint: disable=global-statement,invalid-name

    parser = argparse.ArgumentParser(
        epilog=get_parser.get_condor_epilog("condor_submit")
    )
    parser = get_parser.get_parser(parser)

    # Argument-checking code
    # old jobsub_client commands got run through a shell that replaced \x with x
    # so we do that here for backwards compatability
    backslash_escape_layer(argv)

    args = parser.parse_args(argv[1:])

    print("in jobsub_submit_main: args = ", args)

    VERBOSE = args.verbose
    jobsub_submit_args(args)


def jobsub_submit_args(
    args: argparse.Namespace, passthru: Optional[List[str]] = None
) -> None:

    global VERBOSE  # pylint: disable=global-statement

    if passthru:
        raise argparse.ArgumentError(None, f"unknown arguments: {repr(passthru)}")

    if not args.global_pool and os.environ.get("JOBSUB_GLOBAL_POOL", ""):
        pool.set_pool(os.environ["JOBSUB_GLOBAL_POOL"])

    # Allow environment variables to append to some command lists to get rid of
    # need for poms_jobsub_wrapper to get in front of us on the path -- we will
    # just set these and have a job-info script report the job id, etc.
    args.environment.extend(get_env_list("JOBSUB_EXTRA_ENVIRONMENT"))
    args.lines.extend(get_env_list("JOBSUB_EXTRA_LINES"))
    args.job_info.extend(get_env_list("JOBSUB_EXTRA_JOB_INFO"))

    sanitize_lines(args.lines)

    VERBOSE = args.verbose

    log_host_time(VERBOSE)

    # if they were trying to pass LD_LIBRARY_PATH to the job, get it from HIDE_LD_LIBRARY_PATH
    if "LD_LIBRARY_PATH" in args.environment and os.environ.get(
        "HIDE_LD_LIBRARY_PATH", ""
    ):
        args.environment = [
            f"{x}={os.environ['HIDE_LD_LIBRARY_PATH']}" if x == "LD_LIBRARY_PATH" else x
            for x in args.environment
        ]

    if args.version:
        version.print_version()
        return

    if args.support_email:
        version.print_support_email()
        return

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

    tarfiles.do_tarballs(args)

    if args.maxConcurrent and int(args.maxConcurrent) >= args.N and not args.dag:
        if args.verbose:
            sys.stderr.write(
                f"Note: ignoring --maxConcurrent {args.maxConcurrent} for {args.N} jobs\n"
            )
        args.maxConcurrent = None

    varg = vars(args)

    cred_set = creds.get_creds(varg)
    if args.verbose:
        creds.print_cred_paths_from_credset(cred_set)

    if args.verbose:
        sys.stderr.write(f"varg: {repr(varg)}\n")

    schedd_add = condor.get_schedd(varg)
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
