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
import jinja2 as jinja
import os
import sys
import creds
import os.path
from get_parser import get_parser
from utils import fixquote, set_extras_n_fix_units


def parse_dagnabbit(srcdir, values, dest, schedd_name, debug_comments=True):
    """
    parse a dagnabbit dag file generating a .dag file and .cmd files
    in the dest directory, using global cmdline options from values
    along with ones parsed from dagnabbit file
    """
    jinja_env = jinja.Environment(loader=jinja.FileSystemLoader(srcdir))
    jinja_env.filters["basename"] = os.path.basename
    proxy, token = creds.get_creds()
    count = 0
    linenum = 0
    df = open(values["dag"], "r")
    of = open(os.path.join(dest, "dag.dag"), "w")
    of.write("DOT %s/dag.dot UPDATE\n" % dest)
    in_parallel = False
    in_serial = False
    last_serial = None
    parallel_l = []
    for line in df:
        line = line.strip()
        line = os.path.expandvars(line)
        linenum = linenum + 1
        if debug_comments:
            of.write("# line: %s\n" % line)
            of.write(
                "# in_parallel: %s in_serial: %s last_serial: %s parallel_l: %s\n"
                % (in_parallel, in_serial, last_serial, parallel_l)
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
            of.write("PARENT %s CHILD %s\n" % (last_serial, parallels))
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
                    "Error: file %s line %d: <serial> inside <parallel> not currently supported\n"
                    % (values[dag], linenum)
                )
                sys.exit(1)
        elif line.find("</serial>") >= 0:
            if debug_comments:
                of.write("# saw </serial>\n")
            in_serial = False
        elif line.find("jobsub") >= 0:
            if not in_serial and not in_parallel:
                sys.stderr.write(
                    "Syntax Error: job not in <serial> or <parallel block> at line %d\n"
                    % linenum
                )
            count = count + 1
            name = "stage_%d" % count
            parser = get_parser()
            try:
                res = parser.parse_args(line.strip().split()[1:])
            except:
                sys.stderr.write(
                    "Error at file %s line %s\n" % (values["dag"], linenum)
                )
                sys.stderr.write("parsing: %s\n" % line.strip().split())
                sys.stderr.flush()
                raise
            print("vars(res): %s" % repr(vars(res)))
            thesevalues = values.copy()
            thesevalues["N"] = 1
            thesevalues["dag"] = None
            thesevalues.update(vars(res))
            cf = open(os.path.join(dest, "%s.cmd" % name), "w")
            csf = open(os.path.join(dest, "%s.sh" % name), "w")
            set_extras_n_fix_units(thesevalues, schedd_name, proxy, token)
            thesevalues["script_name"] = "%s.sh" % name
            cf.write(jinja_env.get_template("simple.cmd").render(**thesevalues))
            csf.write(jinja_env.get_template("simple.sh").render(**thesevalues))
            cf.close()
            of.write("JOB %s %s/%s.cmd\n" % (name, dest, name))
            if in_serial:
                if last_serial:
                    of.write("PARENT %s CHILD %s\n" % (last_serial, name))
                last_serial = name
            if in_parallel:
                parallel_l.append(name)
        elif not line:
            # blank lines are fine
            pass
        else:
            sys.stderr.write("Syntax Error: ignoring %s at line %d\n" % (line, linenum))

    if values["maxConcurrent"]:
        of.write("CONFIG dagmax.config\n")

    of.close()
