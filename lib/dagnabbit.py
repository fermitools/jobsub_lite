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
    debug_comments: bool = True,
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
    with open(values["dag"], "r", encoding="UTF-8") as df, open(
        os.path.join(dest, "dag.dag"), "w", encoding="UTF-8"
    ) as of:
        of.write(f"DOT dag.dot UPDATE\n")
        in_parallel = False
        in_serial = False
        last_serial = None
        parallel_l: List[str] = []
        for line in df:
            line = line.strip()
            line = os.path.expandvars(line)
            linenum = linenum + 1
            if debug_comments:
                of.write(f"# line: {line}\n")
                of.write(
                    f"# in_parallel: {in_parallel} in_serial: {in_serial}"
                    f" last_serial: {last_serial} parallel_l: {parallel_l}\n"
                )

            if line.find("<parallel>") >= 0:
                if debug_comments:
                    of.write("# saw <parallel>\n")
                in_parallel = True
                parallel_l = []
            elif line.find("</parallel>") >= 0:
                if debug_comments:
                    of.write("# saw </parallel>\n")
                in_parallel = False
                parallels = " ".join(parallel_l)
                of.write(f"PARENT {last_serial} CHILD {parallels}\n")
                last_serial = parallels
            elif line.find("<serial>") >= 0:
                if debug_comments:
                    of.write("# saw <serial>\n")
                in_serial = True
                if in_parallel:
                    # to make this work we need a stack to remember we were
                    # in a parallel, and our parallel_l would need a start
                    # and end for each chain...
                    sys.stderr.write(
                        f"Error: file {values['dag']} line {linenum}: <serial>"
                        f" inside <parallel> not currently supported\n"
                    )
                    sys.exit(1)
            elif line.find("</serial>") >= 0:
                if debug_comments:
                    of.write("# saw </serial>\n")
                in_serial = False
            elif line.find("jobsub") >= 0:
                if not in_serial and not in_parallel:
                    sys.stderr.write(
                        f"Syntax Error: job not in <serial> or <parallel block> at line {linenum}\n"
                    )
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
                print(f"vars(res): {repr(vars(res))}")
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
                with open(
                    os.path.join(dest, f"{name}.cmd"), "w", encoding="UTF-8"
                ) as cf:
                    cf.write(jinja_env.get_template("simple.cmd").render(**thesevalues))
                with open(
                    os.path.join(dest, f"{name}.sh"), "w", encoding="UTF-8"
                ) as csf:
                    csf.write(jinja_env.get_template("simple.sh").render(**thesevalues))
                of.write(f"JOB {name} {name}.cmd\n")
                of.write(f'VARS {name} +JOBSUBJOBSECTION={count} nodename="$(JOB)"')

                if in_serial:
                    if last_serial:
                        of.write(f"PARENT {last_serial} CHILD {name}\n")
                    last_serial = name
                if in_parallel:
                    parallel_l.append(name)
            elif not line:
                # blank lines are fine
                pass
            else:
                sys.stderr.write(f"Syntax Error: ignoring {line} at line {linenum}\n")

        if values["maxConcurrent"]:
            of.write("CONFIG dagmax.config\n")
