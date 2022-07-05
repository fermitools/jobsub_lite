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
from collections import OrderedDict
import os
import re
import os.path
import socket
import sys
import subprocess
import uuid
import datetime
import shutil


def fixquote(s):
    """utility to put double quotes on value in string 'name=value'"""
    parts = s.split("=", 1)
    if len(parts) == 2:
        return '%s="%s"' % (parts[0], parts[1])
    else:
        return s


def grep_n(regex, n, file):
    rre = re.compile(regex)
    with open(file, "r") as fd:
        for line in fd:
            m = rre.match(line)
            if m:
                return m.group(n)


def set_extras_n_fix_units(args, schedd_name, proxy, token):
    """add items to our args dictionary that are not given on the
    command line, but that are needed to render the condor submit
    file templates.
    Also convert units on memory, disk, and times
    Note: this has gotten excessively long, probably should be split up?
    """
    #
    # outbase needs to be an area shared with schedd servers.
    #
    if args["debug"]:
        sys.stderr.write("entering set_extras... args: %s\n" % repr(args))

    args["outbase"] = os.environ.get("JOBSUB_SPOOL", "%s/.jobsub_lite" % os.environ.get("HOME"))
    args["user"] = os.environ["USER"]
    args["schedd"] = schedd_name
    ai = socket.getaddrinfo(socket.gethostname(), 80)
    args["clientdn"] = get_client_dn(proxy)
    if ai:
        args["ipaddr"] = ai[-1][-1][0]
    else:
        args["ipaddr"] = "unknown"
    args["proxy"] = proxy
    args["token"] = token
    args["jobsub_version"] = "lite_v1_0"
    args["kerberos_principal"] = get_principal()
    args["usage_model"] = "ONSITE"
    args["uid"] = str(os.getuid())
    if not "uuid" in args:
        args["uuid"] = str(uuid.uuid4())
    args["date"] = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    if args["debug"]:
        sys.stderr.write("checking args[executable]: %s\n" % repr(args.get("executable",None)))
    if not args["executable"] and args["exe_arguments"]:
        args["executable"] = args["exe_arguments"][-1]
        args["exe_arguments"] = args["exe_arguments"][:-1]

    if args["executable"]:
        args["full_executable"] = args["executable"]
        args["full_executable"] = args["full_executable"].replace("file://", "")
    else:
        sys.stderr.write("Ouch! no executable?\n")
        args["full_executable"] = "/bin/false"
    if args["full_executable"][0] != "/":
        args["full_executable"] = os.path.join(os.getcwd(), args["full_executable"])

    args["resource_provides_quoted"] = [fixquote(x) for x in args["resource_provides"]]

    args["outdir"] = "%(outbase)s/%(group)s/%(user)s/%(date)s.%(uuid)s" % args
    args["submitdir"] = args["outdir"]

    if not os.path.exists(args["outdir"]):
        os.makedirs(args["outdir"])

    # copy executable to submit dir so schedd can see it
    if args["debug"]:
        sys.stderr.write("checking full_executable: %s\n" % repr(args.get("full_executable",None)))

    if args.get("full_executable",False):
        dest = os.path.join(args["submitdir"], os.path.basename(args["executable"]))
        if args["debug"]:
            sys.stderr.write("copying  %s to %s\n" % (repr(args.get("full_executable",None)),repr(dest)))
        shutil.copyfile(args["full_executable"], dest, follow_symlinks=True)
        args["full_executable"] = dest

    #
    # conversion factors for memory suffixes
    #
    dsktable = {"k": 1, "m": 1024, "g": 1024 * 1024, "t": 1024 * 1024 * 1024}
    memtable = {"k": 1.0 / 1024, "m": 1, "g": 1024, "t": 1024 * 1024}
    timtable = {"s": 1, "m": 60, "h": 60 * 60, "d": 60 * 60 * 24}

    fix_unit(args, "disk", dsktable, -1, "b", -2)
    fix_unit(args, "memory", memtable, -1, "b", -2)
    fix_unit(args, "expected_lifetime", timtable, -1, "smhd", -1)
    fix_unit(args, "timeout", timtable, -1, "smhd", -1)
    newe = []
    for e in args["environment"]:
        pos = e.find("=")
        if pos < 0:
            v = os.environ.get(e, None)
            if not v:
                raise RuntimeError(
                    "--environment %s was given but no value was in the environment"
                )
            e = "%s=%s" % (e, v)
        newe.append(e)
    args["environment"] = newe
    if args["debug"]:
        sys.stderr.write("leaving set_extras... args: %s\n" % repr(args))


def fix_unit(args, name, table, s_offset, s_list, c_offset):
    """
    unit conversions using appropriate conversion table
    """
    # print("fix_unit: %s %s %s %d %s %d" % (name, args[name], repr(table),s_offset,s_list,c_offset))
    if args[name] and args[name][s_offset].lower() in s_list:
        cf = table[args[name][c_offset].lower()]
        args[name] = float(args[name][:c_offset]) * cf
        # print("converted to %f" % args[name])
    elif args[name]:
        args[name] = float(args[name])


def get_principal():
    """get our kerberos principal name"""
    princ = None
    if sys.version_info.major >= 3:
        enc = {"encoding": "UTF-8"}
    else:
        enc = {}
    p = subprocess.Popen(["/usr/bin/klist"], stdout=subprocess.PIPE, **enc)
    line = p.stdout.readline()
    line = p.stdout.readline()
    princ = line[line.find(":") + 2 : -1]
    p.stdout.close()
    p.wait()
    return princ


def get_client_dn(proxy=None):
    """Get our proxy's DN if the proxy exists"""
    if proxy is None:
        proxy = os.getenv('X509_USER_PROXY')    
        if proxy is None:
            uid = str(os.getuid())
            proxy = f"/tmp/x509up_u{uid}"

    executables = OrderedDict(
        ( 
            (
                "voms-proxy-info",
                {
                    "args": ["-file", proxy, "-subject"],
                    "parse_output": re.compile("(.+)")
                },
            ),
            (
                "openssl",
                {
                    "args": ["x509", "-in", proxy, "-noout", "-subject"],
                    "parse_output": re.compile("subject= (.+)")
                },
            )
        )
    )

    for executable in executables:
        exe_path = shutil.which(executable)
        if exe_path is not None:
            try:
                proc = subprocess.run([exe_path, *executables[executable]["args"]], stdout=subprocess.PIPE, encoding="utf-8")
                assert proc.returncode == 0
            except Exception as e:
                print("Warning:  There was an issue getting the client DN from the user proxy.  Please open a "
                "ticket to the Service Desk and paste the entire error message in the ticket.")
                print(e)
                continue
            else:
                raw_out = proc.stdout.strip()

            out_match = executables[executable]["parse_output"].match(raw_out)            
            if out_match is not None:
                return out_match.group(1)

    return ""
