# pylint: disable=wrong-import-position,wrong-import-order,import-error
import argparse
import glob
import hashlib
import os
import os.path
import sys
from typing import Union, List, Dict, Any

import jinja2 as jinja  # type: ignore
from get_parser import get_parser
from condor import get_schedd, submit, submit_dag
from dagnabbit import parse_dagnabbit
from tarfiles import do_tarballs
from tracing import as_span
from utils import (
    set_extras_n_fix_units,
    cleanup,
    backslash_escape_layer,
    sanitize_lines,
)
from creds import get_creds
from token_mods import get_job_scopes, use_token_copy
from version import print_version, print_support_email
from fake_ifdh import mkdir_p, cp
import pool
import skip_checks
from render_files import render_files, get_basefiles

""" Code factored out of jobsub_submit """

PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def do_dataset_defaults(varg: Dict[str, Any]) -> None:
    """
    make sure to pass appropriate SAM_* environment variables if we
    are doing datasets.  Pick a SAM_PROJECT name if we don't have one.
    """
    have_project = False
    have_dataset = False
    have_station = False
    have_user = False
    have_group = False
    experiment = varg["group"]

    if varg["project_name"]:
        varg["environment"].append(f"SAM_PROJECT={varg['project_name']}")
        varg["environment"].append(f"SAM_PROJECT_NAME={varg['project_name']}")

    for e in varg["environment"]:
        pos = e.find("=")
        if e[:pos] == "SAM_PROJECT":
            have_project = True
        if e[:pos] == "SAM_DATASET":
            have_dataset = True
        if e[:pos] == "SAM_STATION":
            have_station = True
        if e[:pos] == "SAM_USER":
            have_user = True
        if e[:pos] == "SAM_GROUP":
            have_group = True
        if e[:pos] == "SAM_EXPERIMENT":
            experiment = e[pos + 1 :]

    if not have_project:
        # if not, grab from the environment, or use dataset_$USER_$uuid
        projname = os.environ.get(
            "SAM_PROJECT",
            f'{varg["dataset_definition"]}_{os.environ.get("USER", "")}_{varg["uuid"]}',
        )
        varg["environment"].append(f"SAM_PROJECT={projname}")
        varg["environment"].append(f"SAM_PROJECT_NAME={projname}")
    if not have_dataset:
        varg["environment"].append(f"SAM_DATASET={varg['dataset_definition']}")
    if not have_station:
        varg["environment"].append(f"SAM_STATION={experiment}")
    if not have_user:
        varg["environment"].append(f"SAM_USER={os.environ['USER']}")
    if not have_group:
        varg["environment"].append(f"SAM_GROUP={experiment}")


@as_span("transfer_sandbox")
def transfer_sandbox(src_dir: str, dest_url: str) -> None:
    """Transfer files from src_dir to sandbox with fake_ifdh (gfal-copy).
    Nothing failing here is considered fatal, since it doesn't affect the job
    itself, just log availability.

    """
    print("Transferring files to web sandbox...")
    try:
        mkdir_p(dest_url)
    except Exception as e:
        print(
            f"warning: error creating sandbox, web logs will not be available for this submission: {e}"
        )
        return
    for f in os.listdir(src_dir):
        try:
            cp(os.path.join(src_dir, f), os.path.join(dest_url, f))
        except Exception as e:
            print(
                f"warning: error copying {f} to sandbox, will not be available through web logs: {e}"
            )


def get_env_list(name: str) -> List[str]:
    """get a split comma separated list of strings from an environment variable"""
    return [x for x in os.environ.get(name, "").split(",") if x]


def jobsub_submit_dag(varg: Dict[str, Any], schedd_name: str) -> None:
    """do a submission to schedd with --dag using the dagnabbit parser"""
    submitdir = varg["outdir"]
    varg["is_dag"] = True
    d1 = os.path.join(PREFIX, "templates", "simple")
    d2 = os.path.join(PREFIX, "templates", "dag")
    parse_dagnabbit(d1, varg, submitdir, schedd_name, varg["verbose"] > 1)
    render_files(d2, varg, submitdir, dlist=[d2, submitdir])
    if not varg.get("no_submit", False):
        if varg["outurl"]:
            transfer_sandbox(submitdir, varg["outurl"])
        os.chdir(varg["submitdir"])
        submit_dag(os.path.join(submitdir, "dag.dag"), varg, schedd_name)


def jobsub_submit_dataset_definition(varg: Dict[str, Any], schedd_name: str) -> None:
    """do a submission to schedd with --dataset-definition  and a 3-stage dag"""
    submitdir = varg["outdir"]
    varg["is_dag"] = True
    do_dataset_defaults(varg)
    d1 = os.path.join(PREFIX, "templates", "dataset_dag")
    d2 = f"{PREFIX}/templates/simple"
    # so we render the simple area (d2) with -N 1 because
    # we are making a loop of 1..N in th dataset_dag area
    # otherwise we get N submissions of N jobs -> N^2 jobs...
    saveN = varg["N"]
    varg["N"] = "1"
    render_files(d2, varg, submitdir, dlist=[d1, d2])
    varg["N"] = saveN
    render_files(d1, varg, submitdir, dlist=[d1, d2, submitdir])
    if not varg.get("no_submit", False):
        if varg["outurl"]:
            transfer_sandbox(submitdir, varg["outurl"])
        os.chdir(varg["submitdir"])
        submit_dag(os.path.join(submitdir, "dataset.dag"), varg, schedd_name)


def jobsub_submit_maxconcurrent(varg: Dict[str, Any], schedd_name: str) -> None:
    """do a --maxConcurrent dag job submission to schedd"""
    submitdir = varg["outdir"]
    varg["is_dag"] = True
    d1 = os.path.join(PREFIX, "templates", "maxconcurrent_dag")
    d2 = os.path.join(PREFIX, "templates", "simple")
    # see above bit about -N 1
    saveN = varg["N"]
    varg["N"] = "1"
    render_files(d2, varg, submitdir, dlist=[d1, d2])
    varg["N"] = saveN
    render_files(d1, varg, submitdir, dlist=[d1, d2, submitdir])
    if not varg.get("no_submit", False):
        if varg["outurl"]:
            transfer_sandbox(submitdir, varg["outurl"])
        os.chdir(varg["submitdir"])
        submit_dag(os.path.join(submitdir, "maxconcurrent.dag"), varg, schedd_name)


def jobsub_submit_simple(varg: Dict[str, Any], schedd_name: str) -> None:
    """a  simple (non-DAG) submission"""
    submitdir = varg["outdir"]
    varg["is_dag"] = False
    d = f"{PREFIX}/templates/simple"
    render_files(d, varg, submitdir)
    if not varg.get("no_submit", False):
        os.chdir(varg["submitdir"])
        if varg["outurl"]:
            transfer_sandbox(submitdir, varg["outurl"])
        submit(os.path.join(submitdir, "simple.cmd"), varg, schedd_name)
