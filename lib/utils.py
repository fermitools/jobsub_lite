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
""" misc. utility functions """
from collections import OrderedDict
import datetime
import os
import os.path
import re
import socket
import sys
import subprocess
import uuid
import shutil
from typing import Union, Dict, Any


def fixquote(s: str) -> str:
    """utility to put double quotes on value in string 'name=value'"""
    parts = s.split("=", 1)
    if len(parts) == 2:
        return f'{parts[0]}="{parts[1]}"'
    return s


def grep_n(regex: str, n: int, file: str) -> str:
    """return n-th sub expression of first regex match in file"""
    rre = re.compile(regex)
    with open(file, "r", encoding="UTF-8") as fd:
        for line in fd:
            m = rre.match(line)
            if m:
                return m.group(n)
    return ""


def set_extras_n_fix_units(
    args: Dict[str, Any],
    schedd_name: str,
    proxy: Union[None, str],
    token: Union[None, str],
) -> None:
    """
    add items to our args dictionary that are not given on the
    command line, but that are needed to render the condor submit
    file templates.
    Also convert units on memory, disk, and times
    Note: this has gotten excessively long, probably should be split up?
    """
    # pylint: disable=too-many-branches,too-many-statements

    #
    # outbase needs to be an area shared with schedd servers.
    #
    if args["debug"]>1:
        sys.stderr.write(f"entering set_extras... args: {repr(args)}\n")

    args["outbase"] = os.environ.get(
        "JOBSUB_SPOOL", f"{os.environ.get('HOME')}/.jobsub_lite"
    )
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
    args["uid"] = str(os.getuid())

    if not "uuid" in args:
        args["uuid"] = str(uuid.uuid4())
    if not "date" in args:
        args["date"] = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    if args["debug"]>1:
        sys.stderr.write(
            f"checking args[executable]: {repr(args.get('executable', None))}\n"
        )
    if not args["executable"] and args["exe_arguments"]:
        args["executable"] = args["exe_arguments"][-1]
        args["exe_arguments"] = args["exe_arguments"][:-1]

    if args["executable"]:
        args["full_executable"] = args["executable"]
        args["full_executable"] = args["full_executable"].replace("file://", "")
        if args["full_executable"][0] != "/":
            args["full_executable"] = os.path.join(os.getcwd(), args["full_executable"])
    else:
        if not args["dag"]:
            sys.stderr.write("Warning: No executable given to job launch\n")

    args["resource_provides_quoted"] = [fixquote(x) for x in args["resource_provides"]]

    # if the user defined the usage_model on the command line,
    # we need to use their definition of usage_model, not ours
    # also, we define the site as 'Fermigrid' if they have not requested OFFSITE
    add_site = ""
    for r in args["resource_provides_quoted"]:
        if "usage_model" in r:
            args["usage_model"] = ""
            if "OFFSITE" not in r:
                add_site = "Fermigrid"

    # if the user chooses 'onsite' from the runtime params
    # we need to define the sites as 'Fermigrid'
    if args["usage_model"] != "" and "OFFSITE" not in args["usage_model"]:
        add_site = "Fermigrid"

    if args.get("site", None):
        args["site"] += ", " + add_site
    else:
        args["site"] = add_site

    if not "outdir" in args:
        args["outdir"] = (
            f"{args['outbase']}/{args['group']}/"
            f"{args['user']}/{args['date']}.{args['uuid']}"
        )
        args["submitdir"] = args["outdir"]

    if not os.path.exists(args["outdir"]):
        os.makedirs(args["outdir"])

    # copy executable to submit dir so schedd can see it
    if args["debug"]>1:
        sys.stderr.write(
            f"checking full_executable: {repr(args.get('full_executable', None))}\n"
        )

    if args.get("full_executable", False):
        dest = os.path.join(args["submitdir"], os.path.basename(args["executable"]))
        if args["debug"]>1:
            sys.stderr.write(
                f"copying  {repr(args.get('full_executable', None))} to {repr(dest)}\n"
            )
        shutil.copyfile(args["full_executable"], dest, follow_symlinks=True)
        args["full_executable"] = dest

    #
    # conversion factors for memory suffixes
    #
    dsktable: Dict[str, float] = {
        "k": 1.0,
        "m": 1024.0,
        "g": 1024 * 1024.0,
        "t": 1024 * 1024 * 1024.0,
    }
    memtable: Dict[str, float] = {
        "k": 1.0 / 1024,
        "m": 1.0,
        "g": 1024.0,
        "t": 1024 * 1024.0,
    }
    timtable: Dict[str, float] = {
        "s": 1.0,
        "m": 60.0,
        "h": 60 * 60.0,
        "d": 60 * 60 * 24.0,
    }

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
                    f"--environment {e} was given but no value was in the environment"
                )
            e = f"{e}={v}"
        newe.append(e)
    args["environment"] = newe
    if args["debug"]>1:
        sys.stderr.write(f"leaving set_extras... args: {repr(args)}\n")
    args["jobsub_command"] = " ".join(sys.argv)


# pylint: disable-next=too-many-arguments
def fix_unit(
    args: Dict[str, Any],
    name: str,
    table: Dict[str, float],
    s_offset: int,
    s_list: str,
    c_offset: int,
) -> None:
    """
    unit conversions using appropriate conversion table
    """
    # print(f"fix_unit: {name}, {args[name]}, {repr(table)},{s_offset},{repr(s_list)},{c_offset}")
    if isinstance(args[name], float):
        # already converted...
        return
    if args[name] and args[name][s_offset].lower() in s_list:
        cf = table[args[name][c_offset].lower()]
        args[name] = float(args[name][:c_offset]) * cf
        # print(f"converted to {args[name]}")
    elif args[name]:
        args[name] = float(args[name])


def get_principal() -> str:
    """get our kerberos principal name"""
    princ = None
    with subprocess.Popen(
        ["/usr/bin/klist"], stdout=subprocess.PIPE, encoding="UTF-8"
    ) as p:
        line = p.stdout.readline()  # type: ignore
        line = p.stdout.readline()  # type: ignore
        princ = line[line.find(":") + 2 : -1]
    return princ


def get_client_dn(proxy: Union[None, str] = None) -> Union[str, Any]:
    """Get our proxy's DN if the proxy exists"""
    if proxy is None:
        proxy = os.getenv("X509_USER_PROXY")
        if proxy is None:
            uid = str(os.getuid())
            proxy = f"/tmp/x509up_u{uid}"

    executables: OrderedDict[str, Dict[str, Any]] = OrderedDict(
        (
            (
                "voms-proxy-info",
                {
                    "args": ["-file", proxy, "-subject"],
                    "parse_output": re.compile("(.+)"),
                },
            ),
            (
                "openssl",
                {
                    "args": ["x509", "-in", proxy, "-noout", "-subject"],
                    "parse_output": re.compile("subject= (.+)"),
                },
            ),
        )
    )

    for executable in executables:
        exe_path = shutil.which(executable)
        if exe_path is not None:
            try:
                proc = subprocess.run(
                    [exe_path, *executables[executable]["args"]],
                    stdout=subprocess.PIPE,
                    encoding="utf-8",
                    check=False,
                )
                assert proc.returncode == 0
            # pylint: disable-next=broad-except
            except Exception as e:
                print(
                    "Warning:  There was an issue getting the client DN from"
                    " the user proxy.  Please open a"
                    " ticket to the Service Desk and paste the entire error"
                    " message in the ticket."
                )
                print(e)
                continue
            else:
                raw_out = proc.stdout.strip()

            out_match = executables[executable]["parse_output"].match(raw_out)
            if out_match is not None:
                return out_match.group(1)

    return ""
