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
import classad  # type: ignore
import datetime
import os
import os.path
import re
import socket
import subprocess
import sys
import uuid
import shutil
import time
from typing import Union, Dict, Any, NamedTuple, Tuple, List, Optional
from tracing import get_propagator_carrier

from creds import CredentialSet
import version

ONSITE_SITE_NAME = "FermiGrid"
DEFAULT_USAGE_MODELS = ["DEDICATED", "OPPORTUNISTIC", "OFFSITE"]
DEFAULT_SINGULARITY_IMAGE = (
    "/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest"
)


def cleandir(d: str, verbose: int) -> None:

    if not os.path.exists(d):
        return

    if verbose > 0:
        sys.stderr.write(f"cleaning directory:{d}\n")

    with os.scandir(d) as it:
        for entry in it:
            os.unlink(f"{d}/{entry.name}")
    os.rmdir(d)


def cleanup(varg: Dict[str, Any]) -> None:
    """cleanup submit directory etc."""
    os.chdir(os.path.dirname(f'{varg["submitdir"]}'))
    cleandir(varg["submitdir"], verbose=varg["verbose"])
    # now clean up old submit directories that weren't
    # cleaned up by jobsub_submit at the time
    with os.scandir(".") as it:
        for entry in it:
            sb = os.stat(entry.name)
            if entry.name.startswith("js_") and time.time() - sb.st_mtime > 604800:
                cleandir(entry.name, verbose=varg["verbose"])


def sanitize_lines(linelist: List[str]) -> None:
    """check all the items in the linelist to see if they are a valid htcondor classad entries"""
    for line in linelist:
        try:
            res = classad.parseOne(line)
        except classad.ClassAdParseError as err:
            raise SyntaxError(f"in --lines '{line}'")


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


def backslash_escape_layer(argv: List[str]) -> None:
    r"""do 1 layer of \x -> x
    as well as eating a layer of single quotes
    to be compatible with jobsub_client
    """

    for i in range(len(argv)):
        argv[i] = re.sub(r"(?!\\)'(.*[^\\])'", "\\1", argv[i])
        argv[i] = re.sub(r"\\(.)", "\\1", argv[i])


def set_some_extras(
    args: Dict[str, Any],
    schedd_name: str,
    cred_set: CredentialSet,
) -> None:
    """common items needed for condor_submit_dag to make the dagman file"""
    #
    # outbase needs to be where we make scratch files
    #
    args["prefix"] = os.path.dirname(os.path.dirname(__file__))
    args["outbase"] = (
        os.environ.get("XDG_CACHE_HOME", f"{os.environ.get('HOME')}/.cache")
        + "/jobsub_lite"
    )
    args["user"] = os.environ["USER"]
    args["schedd"] = schedd_name
    ai = socket.getaddrinfo(socket.gethostname(), 80)
    if ai:
        args["ipaddr"] = ai[-1][-1][0]
    else:
        args["ipaddr"] = "unknown"

    if not "uuid" in args:
        args["uuid"] = str(uuid.uuid4())
    if not "date" in args:
        now = datetime.datetime.now()
        args["date"] = now.strftime("%Y_%m_%d")
        args["datetime"] = now.strftime("%Y_%m_%d_%H%M%S")

    if not "outdir" in args:
        args["outdir"] = f"{args['outbase']}/js_{args['datetime']}_{args['uuid']}"
        args["submitdir"] = args["outdir"]

    if not os.path.exists(args["outdir"]):
        os.makedirs(args["outdir"])

    args["jobsub_version"] = f"{version.__title__}-v{version.__version__}"
    args["kerberos_principal"] = get_principal()

    if not "outurl" in args:
        args["outurl"] = ""
        if "JOBSUB_OUTPUT_URL" in os.environ:
            # the path included in the output url needs to be included in users'
            # tokens with storage.create scope (only!)
            base = os.environ["JOBSUB_OUTPUT_URL"]
            # this path is sanity-checked when fetching logs, so we can't change
            # it here without also changing the check in jobview (or whatever
            # comes after it).
            args["outurl"] = "/".join((base, args["date"], args["uuid"]))
        else:
            sys.stderr.write(
                "warning: JOBSUB_OUTPUT_URL not defined, web logs will not be available for this submission\n"
            )


def set_extras_n_fix_units(
    args: Dict[str, Any],
    schedd_name: str,
    cred_set: CredentialSet,
) -> None:
    """
    add items to our args dictionary that are not given on the
    command line, but that are needed to render the condor submit
    file templates.
    Also convert units on memory, disk, and times
    Note: this has gotten excessively long, probably should be split up?
    """
    # pylint: disable=too-many-branches,too-many-statements

    if args["verbose"] > 1:
        sys.stderr.write(f"entering set_extras... args: {repr(args)}\n")

    set_some_extras(args, schedd_name, cred_set)

    #
    # get tracing propagator traceparent id so we can use it in templates, etc.
    #
    carrier = get_propagator_carrier()
    if carrier and "traceparent" in carrier:
        args["traceparent"] = carrier["traceparent"]
    else:
        args["traceparent"] = ""

    if args["verbose"] > 0:
        sys.stderr.write(f"Setting traceparent: {args['traceparent']}\n")

    # Read in credentials
    for cred_type, cred_path in vars(cred_set).items():
        args[cred_type] = cred_path
    if getattr(cred_set, "proxy", None) is not None:
        args["clientdn"] = get_client_dn(cred_set.proxy)

    args["jobsub_version"] = f"{version.__title__}-v{version.__version__}"
    args["kerberos_principal"] = get_principal()
    args["uid"] = str(os.getuid())

    if args["verbose"] > 1:
        sys.stderr.write(
            f"checking args[executable]: {repr(args.get('executable', None))}\n"
        )

    if not args["executable"] and args["exe_arguments"]:
        args["executable"] = args["exe_arguments"][-1]
        args["exe_arguments"] = args["exe_arguments"][:-1]

    # fixup collapsed DAG arguments.
    args["exe_arguments"] = [
        x.replace("$(CM1)", "${CM1}").replace("$(CM2)", "${CM2}")
        for x in args["exe_arguments"]
    ]

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

    # Check site and blocklist to ensure there are no conflicts
    check_site_and_blocklist(args.get("site", ""), args.get("blocklist", ""))

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

    if args.get("prescript", False):
        dest = os.path.join(args["submitdir"], os.path.basename(args["prescript"]))
        if args["verbose"] > 1:
            sys.stderr.write(
                f"copying  {repr(args.get('prescript', None))} to {repr(dest)}\n"
            )
        # do not copy prescript if it is already at its destination
        # its path has been updated to be the final destination in a previous step
        if args["prescript"] != dest:
            shutil.copyfile(args["prescript"], dest, follow_symlinks=True)
            args["prescript"] = dest
            os.chmod(dest, 0o755)

    if args.get("postscript", False):
        dest = os.path.join(args["submitdir"], os.path.basename(args["postscript"]))
        if args["verbose"] > 1:
            sys.stderr.write(
                f"copying  {repr(args.get('postscript', None))} to {repr(dest)}\n"
            )
        # do not copy postscript if it is already at its destination
        # its path has been updated to be the final destination in a previous step
        if args["postscript"] != dest:
            shutil.copyfile(args["postscript"], dest, follow_symlinks=True)
            args["postscript"] = dest
            os.chmod(dest, 0o755)

    # Sanitize --lines input.  There's the unfortunate possibility of "--lines '""'" being passed
    # in, so guard against those kinds of things
    if args.get("lines"):
        args["lines"] = [line for line in args["lines"] if line not in ('""', "''")]
        # Check --lines for SingularityImage, resolve the possible case where that AND --singularity-image
        # are specified, as long as --no-singularity is not set
        if not args.get("no_singularity", False):
            args["singularity_image"], args["lines"] = resolve_singularity_image(
                args.get("singularity_image", DEFAULT_SINGULARITY_IMAGE), args["lines"]
            )
        else:
            # Strip out any line with "SingularityImage=" in it, since --no-singularity is specified
            _lines = [line for line in args["lines"] if "SingularityImage=" not in line]
            if len(_lines) != args["lines"]:
                print(
                    "Warning:  --lines contains a SingularityImage specification "
                    "but --no-singularity was also passed on command line. "
                    "jobsub_lite will remove the --lines parameter that contains "
                    "SingularityImage."
                )
            args["lines"] = _lines

    #
    # allow short, medium, and long for duration values (--expected_lifetime, --timeout)
    #
    time_aliases: Dict[str, str] = {
        "short": "3h",
        "medium": "8h",
        "long": "85200s",
    }
    for k in ("expected_lifetime", "timeout"):
        if args[k] in time_aliases:
            args[k] = time_aliases[args[k]]
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
    envnames = set()  # set of environment variable names with -e for below
    for e in args["environment"]:
        pos = e.find("=")
        if pos < 0:
            envnames.add(e)
            v = os.environ.get(e, None)
            if not v:
                raise RuntimeError(
                    f"--environment {e} was given but no value was in the environment"
                )
            e = f"{e}={v}"
        else:
            envnames.add(e[0:pos])

        newe.append(e)

    args["environment"] = newe

    #
    # build list of environment variables for wrapper script to clear:
    # -- this is our default list, below, minus anything passed in a -e/--environment argument
    #
    full_clean_env_list = set(["LC_CTYPE", "CPATH", "LIBRARY_PATH"])
    args["clean_env_vars"] = " ".join(full_clean_env_list.difference(envnames))
    args["not_clean_env_vars"] = " ".join(full_clean_env_list.intersection(envnames))

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
                    f" the user proxy using {executable}."
                )
                print(e)
                continue
            else:
                raw_out = proc.stdout.strip()

            out_match = executables[executable]["parse_output"].match(raw_out)
            if out_match is not None:
                return out_match.group(1)

    print(
        "Warning:  There was an issue getting the client DN from the user "
        "proxy.  Please open a ticket to the Service Desk if your requested proxy "
        "as an auth method and paste the entire error "
        "message in the ticket."
    )
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
        lower_sites = [s.lower() for s in sites]
        # Sanity-check the site-usage_model combination
        # Check 1:  If usage_models are only onsite, make sure sites is ONSITE_SITE_NAME, or sites is empty
        if "OFFSITE" not in usage_models and lower_sites not in (
            [ONSITE_SITE_NAME.lower()],
            [""],
        ):
            raise SiteAndUsageModelConflictError(
                ",".join(sites), ",".join(usage_models)
            )

        # Check 2:  If usage_models are only offsite, make sure sites does not include ONSITE_SITE_NAME
        if usage_models == ["OFFSITE"] and ONSITE_SITE_NAME.lower() in lower_sites:
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

    usage_model_regex = re.compile("usage_model=(.+)")

    # Correct case of onsite site if it's given
    split_given = given_sites.split(",")
    corrected_given_split = [
        ONSITE_SITE_NAME if s.lower() == ONSITE_SITE_NAME.lower() else s
        for s in split_given
    ]  # If the wrong case was given for the onsite site, correct it.
    given_sites_corrected = ",".join(corrected_given_split)

    derived_sites: str = ""
    derived_sites_list = given_sites_corrected.split(",")
    # Case 1: --site provided on the command line.  Set usage model accordingly
    if given_sites_corrected != "":
        derived_usage_model_string = ""
        if (
            len(derived_sites_list) == 1
            and derived_sites_list[0].lower() == ONSITE_SITE_NAME.lower()
        ):
            # Just asking for ONSITE_SITE_NAME
            derived_usage_model_string = "DEDICATED,OPPORTUNISTIC"
        else:
            derived_sites_list_lower = [d.lower() for d in derived_sites_list]
            if ONSITE_SITE_NAME.lower() in derived_sites_list_lower:
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
                    given_sites_corrected, derived_usage_model_string
                )
            ),
            _strip_usage_model_from_resource_provides(resource_provides_quoted),
        )

    # Case 2: If --onsite/--offsite is different than the default, then set it accordingly
    derived_usage_models = given_usage_model.split(",")
    if (given_usage_model != "") and (
        sorted(derived_usage_models) != sorted(DEFAULT_USAGE_MODELS)
    ):
        if "OFFSITE" not in derived_usage_models and given_sites_corrected == "":
            # If they've only asked for onsite, add FermiGrid in the sites list.  Not entirely necessary,
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


def resolve_singularity_image(
    singularity_image_from_args: str, lines: List[str]
) -> Tuple[str, List[str]]:
    """
    Determine what the proper --singularity-image flag should be, parsing both that flag and the --lines
    arguments.  If --lines has a SingularityImage flag specified, we should remove that from --lines and
    put it in the return value of singularity_image.

    Order of precedence:
    1. Non-default singularity-image argument
    2. --lines SingularityImage argument
    3. Default singularity-image argument

    Returns a tuple of (singularity_image, lines (modified or not))
    """
    lines_singularity_re = re.compile(".+SingularityImage=(.+)")
    lines_singularity_image: Optional[str] = None
    return_lines: List[str] = []

    # Parse lines.
    # Look for something like:
    #     '+SingularityImage=\\\"/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest\\\"'
    # in lines and remove it while setting lines_singularity_image
    # In the above example, if there were such a line, lines_singularity_image would be set to
    # "/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest"
    for line in lines:
        m = lines_singularity_re.match(line)
        if m:
            raw_singularity_image = m.group(1)
            # Since most of the time the SingularityImage here is heavily-escaped, we need to strip out all double-quotes and backslashes
            lines_singularity_image = raw_singularity_image.strip('"\\')
            msg = (
                f"Warning: SingularityImage {lines_singularity_image} specified in "
                "--lines.  A non-default --singularity-image value takes precedence, "
                "but a non-default SingularityImage may be specified here for backward-compatibility. "
                "--lines SingularityImage ONLY takes precedence over --singularity-image if "
                "--singularity-image value is not the default and --no-singularity is not given "
                "on the command line."
            )
            print(msg)
        else:
            return_lines.append(line)

    # If we have a non-default --singularity-image given on the command line, use that
    if singularity_image_from_args != DEFAULT_SINGULARITY_IMAGE:
        return (singularity_image_from_args, return_lines)

    # If SingularityImage is specified in lines, use that
    if lines_singularity_image:
        return (lines_singularity_image, return_lines)

    return (DEFAULT_SINGULARITY_IMAGE, return_lines)


def check_site_and_blocklist(site: str, blocklist: str) -> None:
    """Check list of sites and blocklist to make sure there are no
    conflicting options.  If there are conflicts, raise a SiteAndBlocklistConflictError.
    Otherwise, return None.
    """
    # If we have empty --site and --blocklist, this is fine.
    if (not site) or (not blocklist):
        return None
    site_set = set(site.split(","))
    blocklist_set = set(blocklist.split(","))
    common_sites = site_set.intersection(blocklist_set)
    if common_sites:
        raise SiteAndBlocklistConflictError(list(common_sites))
    return None


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


class SiteAndBlocklistConflictError(Exception):
    """Exception to raise if any of the sites the user passed in are also in the user-passed
    blocklist"""

    def __init__(self, common_sites: List[str]):
        self.common_sites = common_sites
        self.message = (
            "The following site(s) are both in the --site and --blocklist "
            f"argument: {self.common_sites}. If your job tries to "
            "run at one of these sites, it will never start.  Please adjust "
            "either the --site list or the --blocklist list."
        )
        super().__init__(self.message)
