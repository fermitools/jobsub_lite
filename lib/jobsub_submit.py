#!/usr/bin/env python3

#
# jobsub_submit -- wrapper for condor_submit
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

import sys
import os
import os.path
import re
import glob
import requests
import subprocess
import datetime
import uuid
import socket
import shutil

import jinja2 as jinja

#
# import our local parts
#
from get_parser import get_parser
from condor import get_schedd, submit, submit_dag
from dagnabbit import parse_dagnabbit
from creds import get_creds
from tarfiles import do_tarballs
from utils import fixquote, set_extras_n_fix_units

#
# we are in prefix/bin/jobsub_submit, so find our prefix for the templates
#
PREFIX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_basefiles(dlist):
    res = []
    for d in dlist:
        flist = glob.glob("%s/*" % d)
        for f in flist:
            res.append(os.path.basename(f))
    return res

def render_files(srcdir, values, dest, dlist=None):
    """use jinja to render the templates from srcdir into the dest directory
    using values dict for substitutions
    """
    print("trying to render files from %s\n" % srcdir)

    if dlist == None:
        dlist = [ srcdir ]
    values["transfer_files"] = get_basefiles(dlist)

    jinja_env = jinja.Environment(loader=jinja.FileSystemLoader(srcdir))
    jinja_env.filters["basename"] = os.path.basename
    flist = glob.glob("%s/*" % srcdir)

    # add destination dir to values for template
    values["cwd"] = dest

    for f in flist:
        print("rendering: %s" % f)
        bf = os.path.basename(f)
        ff = os.path.join(dest, bf)
        of = open(ff, "w")
        of.write(jinja_env.get_template(bf).render(**values))
        of.close()
        if ff.endswith(".sh"):
            os.chmod(ff, 0o755)


def cleanup(tmp):
    """cleanup /tmp etc."""
    # we actually leave everything in the sandbox right now..
    pass


def do_dataset_defaults(varg):
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
        varg["environment"].append(
            "SAM_PROJECT=%s"
            % os.environ.get(
                "SAM_PROJECT",
                "%s_%s_%s"
                % (
                    varg["dataset_definition"],
                    os.environ.get("USER", ""),
                    varg["uuid"],
                ),
            )
        )
    if not have_dataset:
        varg["environment"].append("SAM_DATASET=%s" % varg["dataset_definition"])
    if not have_station:
        varg["environment"].append("SAM_STATION=%s" % experiment)
    if not have_user:
        varg["environment"].append("SAM_USER=%s" % os.environ["USER"])
    if not have_group:
        varg["environment"].append("SAM_GROUP=%s" % experiment)


def main():
    """script mainline:
    - parse args
    - get credentials
    - handle tarfile options
    - set added values from environment, etc.
    - convert/render template files to submission files
    - launch
    """
    parser = get_parser()
    args = parser.parse_args()


    proxy, token = get_creds()
    if args.verbose:
        print("proxy is : %s" % proxy)
        print("token is : %s" % token)

    do_tarballs(args)

    varg = vars(args)
    if args.debug:
        sys.stderr.write("varg: %s" % repr(varg))
    schedd_add = get_schedd(varg)
    schedd_name = schedd_add.eval("Machine")
    set_extras_n_fix_units(varg, schedd_name, proxy, token)
    submitdir = varg["outdir"]

    # if proxy:
    #    proxy_dest=os.path.join(submitdir,os.path.basename(proxy))
    #    shutil.copyfile(proxy, proxy_dest)
    #    varg["proxy"] = proxy_dest
    # if token:
    #    token_dest=os.path.join(submitdir,os.path.basename(token))
    #    shutil.copyfile(token, token_dest)
    #    varg["token"] = token_dest

    if args.dag:
        d1 = os.path.join(PREFIX, "templates", "simple")
        d2 = os.path.join(PREFIX, "templates", "dag")
        parse_dagnabbit(d1, varg, submitdir, schedd_name)
        varg["N"] = 1
        render_files(d2, varg, submitdir, dlist=[d1,d2,varg["dest"]])
        if not varg.get("no_submit",False):
            os.chdir(varg["submitdir"])
            submit_dag(os.path.join(submitdir, "*.dag"), varg, schedd_name)
    elif args.dataset_definition:
        do_dataset_defaults(varg)
        d1 = os.path.join(PREFIX, "templates", "dataset_dag")
        d2 = "%s/templates/simple" % PREFIX
        render_files(d1, varg, submitdir, dlist=[d1,d2])
        varg["N"] = 1
        render_files(d2, varg, submitdir, dlist=[d1,d2])
        if not varg.get("no_submit",False):
            os.chdir(varg["submitdir"])
            submit_dag(os.path.join(submitdir, "*.dag"), varg, schedd_name)
    elif args.maxConcurrent:
        d1 = os.path.join(PREFIX, "templates", "maxconcurrent_dag")
        d2 = os.path.join(PREFIX, "templates", "simple")
        render_files(d1, varg, submitdir, dlist=[d1,d2])
        varg["N"] = 1
        render_files(d2, varg, submitdir, dlist=[d1,d2])
        if not varg.get("no_submit",False):
            os.chdir(varg["submitdir"])
            submit_dag(os.path.join(submitdir, "*.dag"), varg, schedd_name)
    else:
        d = "%s/templates/simple" % PREFIX
        render_files(d, varg, submitdir)
        if not varg.get("no_submit",False):
            os.chdir(varg["submitdir"])
            submit(os.path.join(submitdir, "*.cmd"), varg, schedd_name)


if __name__ == "__main__":
    main()
