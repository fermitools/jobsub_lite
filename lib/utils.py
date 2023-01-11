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
import time
from typing import Union, Dict, Any, NamedTuple, Tuple, List

ONSITE_SITE_NAME = "Fermigrid"
DEFAULT_USAGE_MODELS = ["DEDICATED", "OPPORTUNISTIC", "OFFSITE"]


def cleandir(d: str) -> None:
    with os.scandir(d) as it:
        for entry in it:
            os.unlink(f"{d}/{entry.name}")
    os.rmdir(d)


def cleanup(varg: Dict[str, Any]) -> None:
    """cleanup submit directory etc."""
    os.chdir(f'{varg["submitdir"]}/..')
    cleandir(varg["submitdir"])
    # now clean up old submit directories that weren't
    # cleaned up by jobsub_submit at the time
    with os.scandir(".") as it:
        for entry in it:
            sb = os.stat(entry.name)
            if entry.name.startswith("js_") and time.time() - sb.st_mtime > 604800:
                cleandir(entry.name)


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
    if args["verbose"] > 1:
        sys.stderr.write(f"entering set_extras... args: {repr(args)}\n")

    args["outbase"] = (
        os.environ.get("XDG_CACHE_HOME", f"{os.environ.get('HOME')}/.cache")
        + "/jobsub_lite"
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

    for i in range(len(args["line"])):
        # do 1 layer of \x -> x to be compatible with jobsub_client
        args["line"][i] = re.sub(r"\\(.)", "\\1", args["line"][i])

    if not "uuid" in args:
        args["uuid"] = str(uuid.uuid4())
    if not "date" in args:
        args["date"] = datetime.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    if args["verbose"] > 1:
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

    # Setting usage_model and site keys correctly in args dict
    (site_and_usage_model, new_resource_provides) = resolve_site_and_usage_model(
        args.get("site", ""),
        args.get("usage_model", ""),
        args["resource_provides_quoted"],
    )
    args["site"] = site_and_usage_model.sites
    args["usage_model"] = site_and_usage_model.usage_models
    args["resource_provides_quoted"] = new_resource_provides

    if not "outdir" in args:
        args["outdir"] = f"{args['outbase']}/js_{args['date']}_{args['uuid']}"
        args["submitdir"] = args["outdir"]

    if not os.path.exists(args["outdir"]):
        os.makedirs(args["outdir"])

    # copy executable to submit dir so schedd can see it
    if args["verbose"] > 1:
        sys.stderr.write(
            f"checking full_executable: {repr(args.get('full_executable', None))}\n"
        )

    if args.get("full_executable", False):
        dest = os.path.join(args["submitdir"], os.path.basename(args["executable"]))
        if args["verbose"] > 1:
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
    if args["verbose"] > 1:
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
        try:
            args[name] = float(args[name])
        except ValueError:
            cmd = os.path.basename(sys.argv[0])
            if len(s_list) == 1:
                suff = s_list
            else:
                suff = ""
            ulist = [f"{a}{suff}" for a in table]
            raise SystemExit(
                f"{cmd}: error: unable to convert units on argument '{args[name]}', expected units from {repr(ulist)}"
            )


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


class SiteAndUsageModel(NamedTuple):
    # A simple namedtuple subclass that is meant to encapsulate the sites and usage_model pairing
    sites: str = ""
    usage_models: str = ""


def resolve_site_and_usage_model(
    given_sites: str = "",
    given_usage_model: str = "",
    resource_provides_quoted: List[str] = [""],
) -> Tuple[SiteAndUsageModel, List[str]]:
    # resolve_site_and_usage_model parses through the given sites, usage model,
    # and resource_provides arguments to determine the final site designation
    # for the job.  It also checks the usage model against the site to ensure
    # that we aren't requesting onsite and offsite at the same time, for example
    #
    # Order of operations:
    #
    # 1) If --site is provided, set usage_model accordingly
    # 2) If --onsite/--offsite is different than the default, then set usage_model and possibly site accordingly
    # 3) Check to see if resource_provides has usage_model
    # 4) If (1) or (2), make sure we remove the usage_model bit from resource-provides.
    #
    # Return values:  (SiteAndUsageModel, list[str])
    # The list is simply the modified or unmodified resource_provides_quoted
    # list, depending on whether or not we want to strip out the usage_model bit

    def _check_valid_site_usage_model_pair(
        sites: List[str], usage_models: List[str]
    ) -> None:
        # Sanity-check the site-usage_model combination
        # Check 1:  If usage_models are only onsite, make sure sites is ONSITE_SITE_NAME, or sites is empty
        if "OFFSITE" not in usage_models and sites not in ([ONSITE_SITE_NAME], [""]):
            raise SiteAndUsageModelConflictError(
                ",".join(sites), ",".join(usage_models)
            )

        # Check 2:  If usage_models are only offsite, make sure sites does not include ONSITE_SITE_NAME
        if usage_models == ["OFFSITE"] and ONSITE_SITE_NAME in sites:
            raise SiteAndUsageModelConflictError(
                ",".join(sites), ",".join(usage_models)
            )
        return None

    def _strip_usage_model_from_resource_provides(
        resource_provides: List[str],
    ) -> List[str]:
        return_resource_provides = []
        for request in resource_provides:
            if usage_model_regex.match(request):
                msg = (
                    "Warning:  As --site or --onsite/--offsite were provided, we will "
                    "ignore this usage_model designation in --resource-provides: "
                    f"{request}."
                )
                print(msg)
            else:
                return_resource_provides.append(request)
        return return_resource_provides

    def _sanitize_sites_and_usage_models(
        sites: str, usage_models: str
    ) -> Tuple[str, str]:
        return (
            sites.strip(", "),
            usage_models.strip(", "),
        )

    usage_model_regex = re.compile("usage\_model\=(.+)")
    derived_sites: str = ""
    derived_sites_list = given_sites.split(",")
    # Case 1: --site provided on the command line.  Set usage model accordingly
    if given_sites != "":
        derived_usage_model_string = ""
        if len(derived_sites_list) == 1 and derived_sites_list[0] == ONSITE_SITE_NAME:
            # Just asking for ONSITE_SITE_NAME
            derived_usage_model_string = "DEDICATED,OPPORTUNISTIC"
        else:
            if ONSITE_SITE_NAME in derived_sites_list:
                # Asking for ONSITE_SITE_NAME and other sites
                derived_usage_model_string = "DEDICATED,OPPORTUNISTIC,OFFSITE"
            else:
                # Asking for sites other than ONSITE_SITE_NAME
                derived_usage_model_string = "OFFSITE"
        derived_usage_models = derived_usage_model_string.split(",")
        _check_valid_site_usage_model_pair(derived_sites_list, derived_usage_models)
        return (
            SiteAndUsageModel(
                *_sanitize_sites_and_usage_models(
                    given_sites, derived_usage_model_string
                )
            ),
            _strip_usage_model_from_resource_provides(resource_provides_quoted),
        )

    # Case 2: If --onsite/--offsite is different than the default, then set it accordingly
    derived_usage_models = given_usage_model.split(",")
    if (given_usage_model != "") and (
        sorted(derived_usage_models) != sorted(DEFAULT_USAGE_MODELS)
    ):
        if "OFFSITE" not in derived_usage_models and given_sites == "":
            # If they've only asked for onsite, add Fermigrid in the sites list.  Not entirely necessary,
            # but it makes explicit what the user has asked for
            derived_sites = ONSITE_SITE_NAME
            derived_sites_list = derived_sites.split(",")
        _check_valid_site_usage_model_pair(derived_sites_list, derived_usage_models)
        return (
            SiteAndUsageModel(
                *_sanitize_sites_and_usage_models(derived_sites, given_usage_model)
            ),
            _strip_usage_model_from_resource_provides(resource_provides_quoted),
        )

    # Case 3: At this point, the user hasn't specified --site or a non-default --usage_model, so we check
    # --resource-provides for the usage_model
    for request in resource_provides_quoted:
        usage_model_matches = usage_model_regex.match(request)
        if usage_model_matches:
            # Found usage_model in --resource-provides.  Don't set usage_model. Template will read it from --resource-provides
            # Note that when resource_provides_quoted is created, something like:
            #     --resource-provides=usage_model=DEDICATED,OPPORTUNISTIC
            # is stored in resource_provides_quoted as:
            #     ['usage_model="DEDICATED,OPPORTUNISTIC"']
            # We need to remove those extra quotes around the "DEDICATED,OPPORTUNISTIC" to properly parse the usage models
            derived_usage_models = usage_model_matches.group(1).strip('"').split(",")
            if ("OFFSITE" not in derived_usage_models) and given_sites == "":
                # If they've only asked for onsite, add Fermigrid in the sites list.  Not entirely necessary,
                # but it makes explicit what the user has asked for
                derived_sites = ONSITE_SITE_NAME
                derived_sites_list = derived_sites.split(",")
            _check_valid_site_usage_model_pair(derived_sites_list, derived_usage_models)
            return (
                SiteAndUsageModel(*_sanitize_sites_and_usage_models(derived_sites, "")),
                resource_provides_quoted,
            )

    # Default case:  Nothing was provided.  Don't return any preferred sites, but just the default usage model.
    return (
        SiteAndUsageModel("", ",".join(DEFAULT_USAGE_MODELS)),
        _strip_usage_model_from_resource_provides(resource_provides_quoted),
    )


class SiteAndUsageModelConflictError(Exception):
    # Exception to raise if a site/usage model are in conflict
    def __init__(self, site: str, usage_model: str):
        self.site = site
        self.usage_model = usage_model
        self.message = (
            f"Site {self.site} and usage_model {self.usage_model} are in "
            "conflict.  Please ensure that you are not attempting to submit "
            f"jobs that request to run at {ONSITE_SITE_NAME} while also "
            "requesting to run only OFFSITE, or that you are not requesting to "
            "run with OPPORTUNISTIC or DEDICATED usage_models while specifying "
            f"a site list that does not include {ONSITE_SITE_NAME}."
        )
        super().__init__(self.message)
