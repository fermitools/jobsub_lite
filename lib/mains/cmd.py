#!/usr/bin/python3 -I

#
# api -- calls for apis
#

""" python command  apis for jobsub """
# pylint: disable=wrong-import-position,wrong-import-order,import-error
import argparse
import io
import os
import os.path
import sys
import subprocess
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

import version
import creds
import re
from collections import defaultdict
from .common import VERBOSE


class StoreGroupinEnvironment(argparse.Action):
    """Action to store the given group in the GROUP environment variable"""

    # pylint: disable=too-few-public-methods

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore
        os.environ["GROUP"] = values
        setattr(namespace, self.dest, values)


def jobsub_cmd_parser(
    jobsub_q_flag: bool, parser: Optional[argparse.ArgumentParser]
) -> argparse.ArgumentParser:
    parser = get_parser.get_jobid_parser(parser=parser)
    parser.add_argument("-name", help="Set schedd name", default=None)
    parser.add_argument(
        "--jobsub_server", help="backwards compatability; ignored", default=None
    )

    # combine jobsub_q as well
    if jobsub_q_flag:
        parser.add_argument("--user", help="username to query", default=None)
    return parser


# pylint: disable=dangerous-default-value
@as_span("jobsub_cmd", is_main=True)
def jobsub_cmd_main(argv: List[str] = sys.argv) -> None:

    """main line of code, proces args, etc."""
    condor_cmd = os.path.basename(argv[0]).replace("jobsub_", "condor_")
    parser = argparse.ArgumentParser(epilog=get_parser.get_condor_epilog(condor_cmd))
    parser = jobsub_cmd_parser(argv[0].find("jobsub_q") >= 0, parser=parser)

    parser.set_defaults(command=os.path.basename(argv[0]))
    arglist, passthru = parser.parse_known_args(argv[1:])
    jobsub_cmd_args(arglist, passthru)


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def jobsub_cmd_args(arglist: argparse.Namespace, passthru: List[str]) -> None:
    global VERBOSE  # pylint: disable=invalid-name,global-statement

    VERBOSE = arglist.verbose

    log_host_time(VERBOSE)
    totalsf = None

    if arglist.version:
        version.print_version()
        return

    if arglist.support_email:
        version.print_support_email()
        return

    # Re-insert --debug/--VERBOSE if it was given
    if arglist.verbose:
        passthru.append("-debug")
    # if they gave us --jobid or --user put in the value plain, condor figures it out
    if arglist.jobid:
        for jid in arglist.jobid.split(","):
            passthru.append(jid)
    if hasattr(arglist, "user") and arglist.user:
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
    cmd = arglist.command

    # TODO:  This patch is to fix a small bug when condor_q is used directly. #pylint: disable=fixme
    # We're trying to combine totals because of the clause at the end of this
    # function that calculates totals.  So this is a patch until we can figure
    # out how we want to handle it properly
    # combine jobsub_q as well
    if cmd == "jobsub_q":

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
                    "-format",  # JOBSUBJOBID
                    "%-40s",
                    'strcat(split(GlobalJobId,"#")[1],"@",split(GlobalJobId,"#")[0])',
                    "-format",  # OWNER
                    "%-10s\t",
                    """(DAGNodeName=!=''?strcat(" |-",DAGNodeName):Owner)""",
                    "-format",  # SUBMITTED
                    "%-11s ",
                    'formatTime(QDate,"%m/%d %H:%M")',
                    "-format",  # RUNTIME
                    # For running jobs, use ServerTime - ShadowBday, and add it to the accumulated RemoteWallClockTime for previous executions
                    # of the job.  Otherwise, use RemoteWallClockTime
                    # This is because RemoteWallClockTime is only updated when jobs stop running - either through
                    # completion, removal, or being held.
                    "%T ",
                    "IfThenElse(JobStatus == 2, (ServerTime - ShadowBday) + RemoteWallClockTime, RemoteWallClockTime)",
                    "-format",  # ST
                    " %s ",
                    'substr("UIRXCHE",JobStatus,1)',
                    "-format",  # PRIO
                    " %3d ",
                    "JobPrio",
                    "-format",  # SIZE
                    "%6.1f ",
                    "ImageSize/1024.0",
                    "-format",  # COMMAND
                    "%s",
                    "JobsubCmd=!=''?JobsubCmd:Cmd",
                    "-format",  # arguments after COMMAND
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

            if not isinstance(sys.stdout, io.StringIO):
                # pipe our remaining output through sort (by date) and jobsub_totals next to us
                # ... if we're not collecting output for the API.
                jobsub_totals_path = os.path.join(
                    os.path.dirname(__file__), "../bin/jobsub_totals"
                )
                totalsf = os.popen(f"sort -k 3,4 | {jobsub_totals_path}", "w")
                savout = os.dup(1)
                os.close(1)
                os.dup2(totalsf.fileno(), 1)

    cmd = cmd.replace("jobsub_", "condor_")

    if not schedd_list:
        # if no specific schedds given, get list of all...
        schedd_list = set(condor.get_schedd_names(vars(arglist)))

    if VERBOSE:
        print("schedd list:", schedd_list)

    cmd = f"/usr/bin/{cmd}"
    for schedd in schedd_list:
        os.environ["_condor_CREDD_HOST"] = schedd
        these_args = [cmd, "-name", schedd] + execargs + args_for_schedd.get(schedd, [])
        if VERBOSE:
            print("running:", these_args)

        sys.stderr.flush()
        sys.stdout.flush()
        # pylint: disable=consider-using-with
        p = subprocess.Popen(
            these_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf8"
        )
        if p.stdout:
            for line in p.stdout.readlines():
                sys.stdout.write(line)
            p.stdout.close()
        if p.stderr:
            for line in p.stderr.readlines():
                sys.stderr.write(line)
            p.stderr.close()
        p.wait()

    if totalsf:
        os.close(1)
        totalsf.close()
        os.dup2(savout, 1)
