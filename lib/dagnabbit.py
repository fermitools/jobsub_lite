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
""" dagnabbit DAG parser """
import sys
import os
import os.path
from typing import Dict, List, Any

import jinja2 as jinja  # type: ignore

import creds
from get_parser import get_parser
from tarfiles import do_tarballs
from utils import set_extras_n_fix_units


def parse_dagnabbit(
    srcdir: str,
    values: Dict[str, Any],
    dest: str,
    schedd_name: str,
    debug_comments: bool = False,
) -> None:
    """
    parse a dagnabbit dag file generating a .dag file and .cmd files
    in the dest directory, using global cmdline options from values
    along with ones parsed from dagnabbit file
    """
    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    jinja_env = jinja.Environment(loader=jinja.FileSystemLoader(srcdir))
    jinja_env.filters["basename"] = os.path.basename
    proxy, token = creds.get_creds(values)
    count = 0
    linenum = 0
    pstack: List[List[List[str]]] = []
    dagfile = values["executable"].replace("file://", "")
    with open(dagfile, "r", encoding="UTF-8") as df, open(
        os.path.join(dest, "dag.dag"), "w", encoding="UTF-8"
    ) as of:
        of.write(f"DOT dag.dot UPDATE\n")
        in_parallel = False
        in_serial = False
        in_prescript = False
        in_postscript = False
        last_serial = ""
        last_serial_in = ""
        parallel_l_in: List[str] = []
        parallel_l_out: List[str] = []
        for line in df:
            line = line.strip()
            line = os.path.expandvars(line)
            linenum = linenum + 1
            if debug_comments:
                of.write(f"# line: {line}\n")
                of.write(
                    f"# in_parallel: {in_parallel} in_serial: {in_serial}"
                    f" last_serial: {last_serial} parallel_l_in: {parallel_l_in}parallel_l_out: {parallel_l_out}\n"
                )

            if line.find("<parallel>") >= 0:
                if in_parallel:
                    sys.stderr.write(
                        f"Error: file {values['dag']} line {linenum}: <parallel>"
                        f" inside <parallel> not currently supported\n"
                    )
                    sys.exit(1)
                if debug_comments:
                    of.write("# saw <parallel>\n")
                in_parallel = True
                in_serial = False
                parallel_l_in = []
                parallel_l_out = []
            elif line.find("</parallel>") >= 0:
                if debug_comments:
                    of.write("# saw </parallel>\n")
                in_parallel = False
                of.write(f"PARENT {last_serial} CHILD {' '.join(parallel_l_in)}\n")
                last_serial = " ".join(parallel_l_out)
                in_serial = True
            elif line.find("<serial>") >= 0:
                last_serial_in = ""
                if debug_comments:
                    of.write("# saw <serial>\n")
                in_serial = True
                if in_parallel:
                    if debug_comments:
                        of.write(
                            f"# pushing {repr([parallel_l_in, parallel_l_out, [last_serial]])}\n"
                        )

                    pstack.append([parallel_l_in, parallel_l_out, [last_serial]])
                    last_serial = ""
                    parallel_l_in = []
                    parallel_l_out = []
                    in_parallel = False
            elif line.find("</serial>") >= 0:
                if debug_comments:
                    of.write("# saw </serial>\n")
                in_serial = False
                if pstack:
                    # we just ended a serial within a parallel...
                    # our end is the tag for that chain, so add it to
                    # the list of parallel branches
                    parallel_l_in, parallel_l_out, last_serial_l = pstack.pop()
                    in_parallel = True
                    parallel_l_in.append(last_serial_in)
                    parallel_l_out.append(last_serial)
                    # now put last serial back to the one that led into
                    # the chain...
                    last_serial = last_serial_l[0]
                    in_parallel = True
            elif line.find("jobsub") >= 0:
                if not in_serial and not in_parallel:
                    sys.stderr.write(
                        f"Syntax Error: job not in <serial> or <parallel block> at line {linenum}\n"
                    )
                # we want at most 1 prescript and 1 postscript after jobsub line
                in_prescript = False
                in_postscript = False
                count = count + 1
                name = f"stage_{count}"
                parser = get_parser()
                try:
                    res = parser.parse_args(line.strip().split()[1:])
                except:
                    sys.stderr.write(f"Error at file {values['dag']} line {linenum}\n")
                    sys.stderr.write(f"parsing: {line.strip().split()}\n")
                    sys.stderr.flush()
                    raise
                # print(f"vars(res): {repr(vars(res))}")
                # handle -f drobpox: etc. in dag stages
                do_tarballs(res)
                thesevalues = values.copy()
                thesevalues["N"] = 1
                thesevalues["dag"] = None
                # don't take executable from command line, only from DAG file
                if "full_executable" in thesevalues:
                    del thesevalues["full_executable"]
                if "executable" in thesevalues:
                    del thesevalues["executable"]

                # we get a bunch of defaults from the command line parser that
                # we don't want to override from the initial command line
                update_with: Dict[str, Any] = vars(res)
                kl = list(update_with.keys())
                for k in kl:
                    if update_with[k] is parser.get_default(k):
                        del update_with[k]

                thesevalues.update(update_with)
                set_extras_n_fix_units(thesevalues, schedd_name, proxy, token)
                thesevalues["script_name"] = f"{name}.sh"
                thesevalues["cmd_name"] = f"{name}.cmd"
                with open(
                    os.path.join(dest, f"{name}.cmd"), "w", encoding="UTF-8"
                ) as cf:
                    cf.write(jinja_env.get_template("simple.cmd").render(**thesevalues))
                with open(
                    os.path.join(dest, f"{name}.sh"), "w", encoding="UTF-8"
                ) as csf:
                    csf.write(jinja_env.get_template("simple.sh").render(**thesevalues))
                of.write(f"\nJOB {name} {name}.cmd\n")
                of.write(f'VARS {name} JOBSUBJOBSECTION="{count}" nodename="$(JOB)"\n')

                if in_serial:
                    if not last_serial_in:
                        last_serial_in = name

                    if last_serial:
                        of.write(f"PARENT {last_serial} CHILD {name}\n")

                    last_serial = name

                if in_parallel:
                    parallel_l_in.append(name)
                    parallel_l_out.append(name)

            elif line.startswith("prescript "):
                if debug_comments:
                    of.write("# saw prescript\n")
                if in_prescript:
                    sys.stderr.write(
                        f"Error: file {dagfile} line {linenum}\n"
                        f" only 1 prescript line per jobsub line is allowed\n"
                    )
                    sys.exit(1)
                in_prescript = True
                name = f"stage_{count}"
                parser = get_parser()
                try:
                    res = parser.parse_args(line.strip().split()[1:])
                except:
                    sys.stderr.write(f"Error at file {dagfile} line {linenum}\n")
                    sys.stderr.write(f"parsing: {line.strip().split()}\n")
                    sys.stderr.flush()
                    raise
                prescript = line.split()[1].replace("file://", "")
                prescript_base = os.path.basename(prescript)
                prescript_args = " ".join(line.split()[2:])
                of.write(f"SCRIPT PRE {name} {prescript_base} {prescript_args}\n")
                thesevalues["prescript"] = prescript
                thesevalues.update(update_with)
                set_extras_n_fix_units(thesevalues, schedd_name, proxy, token)

            elif line.startswith("postscript "):
                if debug_comments:
                    of.write("# saw postscript\n")
                if in_postscript:
                    sys.stderr.write(
                        f"Error: file {dagfile} line {linenum}\n"
                        f" only 1 postscript line per jobsub line is allowed\n"
                    )
                    sys.exit(1)
                in_postscript = True
                name = f"stage_{count}"
                parser = get_parser()
                try:
                    res = parser.parse_args(line.strip().split()[1:])
                except:
                    sys.stderr.write(f"Error at file {dagfile} line {linenum}\n")
                    sys.stderr.write(f"parsing: {line.strip().split()}\n")
                    sys.stderr.flush()
                    raise
                postscript = line.split()[1].replace("file://", "")
                postscript_base = os.path.basename(postscript)
                postscript_args = " ".join(line.split()[2:])
                of.write(f"SCRIPT POST {name} {postscript_base} {postscript_args}\n")
                thesevalues["postscript"] = postscript
                thesevalues.update(update_with)
                set_extras_n_fix_units(thesevalues, schedd_name, proxy, token)

            elif not line:
                # blank lines are fine
                pass
            else:
                sys.stderr.write(f"Syntax Error: ignoring {line} at line {linenum}\n")

        if values["maxConcurrent"]:
            of.write("CONFIG dagmax.config\n")
