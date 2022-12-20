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
""" argument parser, used multiple places, so defined here"""
# pylint: disable=too-few-public-methods
import argparse
import os
import re
import sys
from typing import Union, Any


def verify_executable_starts_with_file_colon(s: str) -> str:
    """routine to give argparse to verify the executable parameter,
    which is supposed to be given as a file:///path URL
    -- note we could check the file exists here, too.
    """
    if s.startswith("file://"):
        return s
    raise TypeError("executable must start with file://")


class StoreGroupinEnvironment(argparse.Action):
    """Action to store the given group in the GROUP environment variable"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Union[None, str] = None,
    ) -> None:
        os.environ["GROUP"] = values
        setattr(namespace, self.dest, values)


class ConvertDebugToVerbose(argparse.Action):
    """Action to convert the --debug flag to --verbose 1"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Union[None, str] = None,
    ) -> None:
        setattr(namespace, self.dest, True)
        setattr(namespace, "verbose", 1)


def get_base_parser(add_condor_epilog: bool = False) -> argparse.ArgumentParser:
    """build the general jobsub command argument parser and return it"""

    if add_condor_epilog:
        apargs = {
            "formatter_class": argparse.RawDescriptionHelpFormatter,
            "epilog": get_condor_epilog(),
        }
    else:
        apargs = {}

    parser = argparse.ArgumentParser(**apargs)  # type: ignore
    group = parser.add_argument_group("general arguments")

    # default to JOBSUB_GROUP rather than GROUP if set
    if os.environ.get("JOBSUB_GROUP", ""):
        os.environ["GROUP"] = os.environ["JOBSUB_GROUP"]

    group.add_argument(
        "-G",
        "--group",
        help="Group/Experiment/Subgroup for priorities and accounting",
        action=StoreGroupinEnvironment,
        default=os.environ.get("GROUP", None),
    )
    group.add_argument(
        "--role", help="VOMS Role for priorities and accounting", default="Analysis"
    )
    group.add_argument(
        "--subgroup",
        help=" Subgroup for priorities and accounting. See https://cdcvs.fnal.gov/redmine/projects/jobsub/wiki/ Jobsub_submit#Groups-Subgroups-Quotas-Priorities for more documentation on using --subgroup to set job quotas and priorities",
    )
    group.add_argument(
        "--verbose",
        type=int,
        default=0,
        help="Turn on more information on internal state of program. --verbose 1 is the same as --debug",
    )
    group.add_argument(
        "--debug",
        action=ConvertDebugToVerbose,
        nargs=0,
        help="dump internal state of program (useful for debugging)",
    )
    return parser


def get_jobid_parser(add_condor_epilog: bool = False) -> argparse.ArgumentParser:
    parser = get_base_parser(add_condor_epilog=add_condor_epilog)
    parser.add_argument("-J", "--jobid", dest="jobid", help="job/submission ID")
    return parser


def get_parser() -> argparse.ArgumentParser:
    """build the jobsub_submit argument parser and return it"""
    parser = get_base_parser()
    parser.add_argument(
        "-c",
        "--append-condor-requirements",
        "--append_condor_requirements",
        help="append condor requirements",
    )
    parser.add_argument(
        "--blacklist", help="enusure that jobs do not land at these sites"
    )
    parser.add_argument("-r", help="Experiment release version")
    parser.add_argument("-i", help="Experiment release dir")
    parser.add_argument("-t", help="Experiment test release dir")
    parser.add_argument(
        "--cmtconfig",
        help=" Set up minervasoft release built with cmt configuration. default is $CMTCONFIG",
    )
    parser.add_argument("--cpu", help="request worker nodes have at least NUMBER cpus")
    parser.add_argument(
        "--dag",
        help="submit and run a dagNabbit input file",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "--dataset-definition",
        "--dataset_definition",
        "--dataset",
        help="SAM dataset definition used in a Directed Acyclic Graph (DAG)",
    )
    parser.add_argument(
        "--disk",
        help="Request worker nodes have at least NUMBER[UNITS] of disk space."
        " If UNITS is not specified default is 'KB' (a typo in earlier"
        " versions said that default was 'MB', this was wrong)."
        " Allowed values for UNITS are 'KB','MB','GB', and 'TB'",
        default="100MB",
    )
    parser.add_argument(
        "-d",
        nargs=2,
        action="append",
        default=[],
        metavar=("tag", "dir"),
        help="-d <tag> <dir> Writable directory $CONDOR_DIR_<tag> will exist"
        " on the execution node. After job completion, its contents will"
        " be moved to <dir> automatically."
        " Specify as many <tag>/<dir> pairs as you need.",
    )
    parser.add_argument(
        "--email-to",
        default=f"{os.environ['USER']}@fnal.gov",
        help="email address to send job reports/summaries"
        " (default is $USER@fnal.gov)",
    )
    parser.add_argument(
        "-e",
        "--environment",
        default=[],
        action="append",
        help=" -e ADDED_ENVIRONMENT exports this variable with its local value"
        " to worker node environment. For example export FOO='BAR';"
        " jobsub -e FOO <more stuff> guarantees that the value of $FOO"
        " on the worker node is 'BAR' . Alternate format which does not"
        " require setting the env var first is the -e VAR=VAL idiom,"
        " which sets the value of $VAR to 'VAL' in the worker environment."
        " The -e option can be used as many times in one jobsub_submit"
        " invocation as desired.",
    )
    parser.add_argument(
        "--expected-lifetime",
        help=" 'short'|'medium'|'long'|NUMBER[UNITS] Expected lifetime of the"
        " job. Used to match against resources advertising that they have"
        " REMAINING_LIFETIME seconds left. The shorter your EXPECTED_LIFTIME"
        " is, the more resources (aka slots, cpus) your job can potentially"
        " match against and the quicker it should start. If your job runs"
        " longer than EXPECTED_LIFETIME it *may* be killed by the batch"
        " system."
        " If your specified EXPECTED_LIFETIME is too long your job may"
        " take a long time to match against a resource a sufficiently long"
        " REMAINING_LIFETIME. Valid inputs for this parameter are:"
        " 'short', 'medium', 'long' IF [UNITS] is omitted, value is NUMBER"
        " seconds. Allowed values for UNITS are 's', 'm', 'h', 'd'"
        " representing seconds, minutes, etc.The values for"
        " 'short','medium',and 'long' are configurable by Grid Operations,"
        " they currently are '3h' , '8h' , and '85200s' but this may"
        " change in the future.",
        default="8h",
    )
    parser.add_argument(
        "-f",
        dest="input_file",
        default=[],
        action="append",
        help="INPUT_FILE at runtime, INPUT_FILE will be copied to directory"
        " $CONDOR_DIR_INPUT on the execution node. Example :"
        " -f /grid/data/minerva/my/input/file.xxx will be copied to"
        " $CONDOR_DIR_INPUT/file.xxx Specify as many"
        " -f INPUT_FILE_1 -f INPUT_FILE_2 args as you need. To copy file at"
        " submission time instead of run time, use -f dropbox://INPUT_FILE"
        " to copy the file.",
    )
    parser.add_argument(
        "--generate-email-summary",
        action="store_true",
        default=False,
        help="generate and mail a summary report of completed/failed/removed"
        " jobs in a DAG",
    )
    parser.add_argument(
        "-L", "--log-file", "--log_file", help="Log file to hold log output from job."
    )
    parser.add_argument(
        "-l",
        "--lines",
        action="append",
        default=[""],
        help="Lines to append to the job file.",
    )
    parser.add_argument(
        "--need-modify",
        action="append",
        default=[],
        help="directories needing storage.modify scope in job tokens",
    )
    parser.add_argument(
        "--need-scope",
        action="append",
        default=[],
        help="scopes needed in job tokens",
    )
    parser.add_argument(
        "-Q",
        "--mail_never",
        "--mail-never",
        dest="mail",
        action="store_const",
        const="never",
        default="never",
        help="never send mail about job results (default)",
    )

    parser.add_argument(
        "--mail_on_error",
        "--mail-on-error",
        dest="mail",
        action="store_const",
        const="on_error",
        help="never send mail about job results (default)",
    )
    parser.add_argument(
        "--mail_always",
        "--mail-always",
        dest="mail",
        action="store_const",
        const="always",
        help="never send mail about job results (default)",
    )

    parser.add_argument(
        "--maxConcurrent",
        help="max number of jobs running concurrently at given time.  Use in"
        " conjunction with -N option to protect a shared resource. Example:"
        " jobsub -N 1000 -maxConcurrent 20 will only run 20 jobs at a time"
        " until all 1000 have completed. This is implemented by running the"
        " jobs in a DAG. Normally when jobs are run with the -N option, they"
        " all have the same $CLUSTER number and differing, sequential"
        " $PROCESS numbers, and many submission scripts take advantage of this."
        " When jobs are run with this option in a DAG each job has a different"
        " $CLUSTER number and a $PROCESS number of 0, which may break scripts"
        " that rely on the normal -N numbering scheme for $CLUSTER and $PROCESS."
        " Groups of jobs run with this option will have the same"
        " $JOBSUBPARENTJOBID, each individual job will have a unique and"
        " sequential $JOBSUBJOBSECTION. Scripts may need modification to take"
        " this into account",
    )
    parser.add_argument(
        "--memory",
        default="2GB",
        help="Request worker nodes have at least NUMBER[UNITS] of memory."
        " If UNITS is not specified default is 'MB'.  Allowed values "
        " for UNITS are 'KB','MB','GB', and 'TB'",
    )
    parser.add_argument(
        "-N",
        default=1,
        type=int,
        help="submit N copies of this job. Each job will have access to the"
        " environment variable $PROCESS that provides the job number"
        " (0 to NUM-1), equivalent to the number following the decimal"
        " point in the job ID (the '2' in 134567.2).",
    )
    parser.add_argument(
        "-n",
        "--no_submit",
        "--no-submit",
        default=False,
        action="store_true",
        help="generate condor_command file but do not submit",
    )
    parser.add_argument(
        "--no-env-cleanup",
        default=False,
        action="store_true",
        help="do not clean environment in wrapper script",
    )
    parser.add_argument(
        "--OS",
        default=None,
        help="specify OS version of worker node. Example --OS=SL5 Comma"
        " separated list '--OS=SL4,SL5,SL6' works as well. Default is any"
        " available OS",
    )
    parser.add_argument(
        "--overwrite-condor-requirements",
        "--overwrite_condor_requirements",
        help="overwrite default condor requirements with supplied requirements",
    )
    parser.add_argument(
        "--resource-provides",
        action="append",
        default=[""],
        help="request specific resources by changing condor jdf file. For"
        " example: --resource-provides=CVMFS=OSG will add"
        ' +DESIRED_CVMFS="OSG" to the job classad attributes and'
        " '&&(CVMFS==\"OSG\")' to the job requirements",
    )
    parser.add_argument("--site", help="submit jobs to these (comma-separated) sites")
    parser.add_argument(
        "--tar_file_name",
        "--tar-file-name",
        default=[],
        action="append",
        help="    dropbox://PATH/TO/TAR_FILE\n     tardir://PATH/TO/DIRECTORY\n"
        "specify TAR_FILE or DIRECTORY to be transferred to worker node."
        " TAR_FILE will be copied with RCDS/cvmfs (or /pnfs),"
        " transferred to the job and unpacked there."
        " TAR_FILE will be accessible to the user job on the worker node"
        " via the environment variable $INPUT_TAR_FILE. The unpacked"
        " contents will be in the same directory as $INPUT_TAR_FILE."
        " Successive --tar_file_name options will be in"
        " $INPUT_TAR_FILE_1, $INPUT_TAR_FILE_2, etc.",
    )
    parser.add_argument(
        "--tarball-exclusion-file",
        default=None,
        help="File with patterns to exclude from tarffile creation",
    )
    parser.add_argument(
        "--timeout",
        help="kill user job if still running after NUMBER[UNITS] of time."
        " UNITS may be `s' for seconds (the default), `m' for minutes,"
        " `h' for hours or `d' h for days.",
    )
    parser.add_argument(
        "--use-cvmfs-dropbox",
        dest="use_dropbox",
        action="store_const",
        const="cvmfs",
        help="use cvmfs for dropbox (default is cvmfs)",
        default=None,
    )
    parser.add_argument(
        "--use-pnfs-dropbox",
        dest="use_dropbox",
        action="store_const",
        const="pnfs",
        help="use pnfs resilient for dropbox (default is cvmfs)",
        default=None,
    )
    parser.add_argument(
        "--devserver",
        default=False,
        action="store_true",
        help="Use jobsubdevgpvm01 etc. to submit",
    )
    parser.add_argument(
        "executable",
        type=verify_executable_starts_with_file_colon,
        default=None,
        nargs="?",
        help="executable for job to run",
    )

    usage_model_group = parser.add_mutually_exclusive_group()
    usage_model_group.add_argument(
        "--onsite",
        "--onsite-only",
        dest="usage_model",
        action="store_const",
        const="OPPORTUNISTIC,DEDICATED",
        default="OPPORTUNISTIC,DEDICATED,OFFSITE",
        help="run jobs locally only; usage_model=OPPORTUNISTIC,DEDICATED",
    )
    usage_model_group.add_argument(
        "--offsite",
        "--offsite-only",
        dest="usage_model",
        action="store_const",
        const="OFFSITE",
        default="OPPORTUNISTIC,DEDICATED,OFFSITE",
        help="run jobs offsite; usage_model=OFFSITE",
    )

    singularity_group = parser.add_mutually_exclusive_group()
    singularity_group.add_argument(
        "--singularity-image",
        "--apptainer-image",
        default="/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest",
        help="Singularity image to run jobs in.  Default is "
        "/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest",
    )
    singularity_group.add_argument(
        "--no-singularity",
        "--no-apptainer",
        action="store_true",
        help="Don't request a singularity container.  If the site your job "
        "lands on runs all jobs in singularity containers, your job will "
        "also run in one.  If the site does not run all jobs in "
        "singularity containers, your job will run outside a singularity "
        "container.",
    )

    parser.add_argument(
        "exe_arguments", nargs=argparse.REMAINDER, help="arguments to executable"
    )

    return parser


def get_condor_epilog() -> str:
    condor_cmd = os.path.basename(sys.argv[0]).replace("jobsub_", "condor_")
    epilog_l = []

    with os.popen(f"/usr/bin/{condor_cmd} -h 2>&1", "r") as fd:
        epilog_l = fd.readlines()

    epilog_l[0] = re.sub(
        f"Usage:.*{condor_cmd}", f"also {condor_cmd} arguments:", epilog_l[0]
    )
    epilog_l[0] += "(with single '-' or double '--' dashes)\n"

    if condor_cmd == "condor_q":
        # condor_q's help says that it defaults to jobs for the current user,
        # but jobsub_q's default is jobs for the current group, so we adjust it here
        for i in range(len(epilog_l)):
            epilog_l[i] = epilog_l[i].replace(
                "jobs owned by the current user",
                "jobs owned by the current jobsub group",
            )
    return "".join(epilog_l)
