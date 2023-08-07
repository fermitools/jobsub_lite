#!/usr/bin/python3 -I

# fake_ifdh -- get rid of ifdhc dependency by providing a few
#              bits of ifdh behavior
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
"""ifdh replacemnents to remove dependency"""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from typing import Union, Optional, List, Dict, Any
from typing import Union, Optional, List
from tracing import as_span, add_event

import htcondor  # type: ignore

VAULT_OPTS = htcondor.param.get("SEC_CREDENTIAL_GETTOKEN_OPTS", "")
DEFAULT_ROLE = "Analysis"


def getTmp() -> str:
    """return temp directory path"""
    return os.environ.get("TMPDIR", "/tmp")


@as_span("getExp")
def getExp() -> Union[str, None]:
    """return current experiment name"""
    if os.environ.get("GROUP", None):
        return os.environ.get("GROUP")
    # otherwise guess primary group...
    exp = None
    with os.popen("id -gn", "r") as f:
        exp = f.read()
    return exp


@as_span("getRole")
def getRole(role_override: Optional[str] = None, verbose: int = 0) -> str:
    """get current role"""

    if role_override:
        return role_override

    # if we have a default role pushed with a vault token, or $HOME/.jobsub_default... use that
    uid = os.getuid()
    group = os.environ["GROUP"]

    for prefix in ["/tmp/", f"{os.environ['HOME']}/.config/"]:

        fname = f"{prefix}jobsub_default_role_{group}_{uid}"

        if os.path.exists(fname) and os.stat(fname).st_uid == uid:
            with open(fname, "r") as f:
                role = f.read().strip()
            return role

    # if there's a role in the wlcg.groups of the token, pick that
    if os.environ.get("BEARER_TOKEN_FILE", False):
        with os.popen("decode_token.sh $BEARER_TOKEN_FILE", "r") as f:
            token_s = f.read()
            token = json.loads(token_s)
            groups: List[str] = token.get("wlcg.groups", [])
            for g in groups:
                m = re.match(r"/.*/(.*)", g)
                if m:
                    role = m.group(1)
                    return role.capitalize()

    return DEFAULT_ROLE


@as_span("checkToken", arg_attrs=["*"])
def checkToken(tokenfile: str) -> bool:
    """check if token is (almost) expired"""
    if not os.path.exists(tokenfile):
        return False
    exp_time = None
    cmd = f"decode_token.sh -e exp {tokenfile} 2>/dev/null"
    with os.popen(cmd, "r") as f:
        exp_time = f.read()
    try:
        add_event(f"expiration: {exp_time}")
        return int(exp_time) - time.time() > 60
    except ValueError as e:
        print(
            "decode_token.sh could not successfully extract the "
            f"expiration time from token file {tokenfile}. Please open "
            "a ticket to Distributed Computing Support if you need further "
            "assistance."
        )
        raise


@as_span("getToken")
def getToken(role: str = DEFAULT_ROLE, verbose: int = 0) -> str:
    """get path to token file"""
    pid = os.getuid()
    tmp = getTmp()
    exp = getExp()
    if exp == "samdev":
        issuer: Optional[str] = "fermilab"
    else:
        issuer = exp

    if os.environ.get("BEARER_TOKEN_FILE", None) and os.path.exists(
        os.environ["BEARER_TOKEN_FILE"]
    ):
        # if we have a bearer token file set already, keep that one
        tokenfile = os.environ["BEARER_TOKEN_FILE"]
    else:
        tokenfile = f"{tmp}/bt_token_{issuer}_{role}_{pid}"
        os.environ["BEARER_TOKEN_FILE"] = tokenfile

    if not checkToken(tokenfile):
        cmd = f"htgettoken {VAULT_OPTS} -i {issuer}"

        if role != DEFAULT_ROLE:
            cmd = f"{cmd} -r {role.lower()}"  # Token-world wants all-lower

        if verbose > 0:
            sys.stderr.write(f"Running: {cmd}")

        res = os.system(cmd)
        if res != 0:
            raise PermissionError(f"Failed attempting '{cmd}'")
        if checkToken(tokenfile):
            return tokenfile
        raise PermissionError(f"Failed validating token from '{cmd}'")
    return tokenfile


@as_span("getProxy")
def getProxy(
    role: str = DEFAULT_ROLE, verbose: int = 0, force_proxy: bool = False
) -> str:
    """get path to proxy certificate file and regenerate proxy if needed.
    Setting force_proxy=True will force regeneration of the proxy"""

    def generate_proxy_command_verbose_args(cmd_str: str) -> Dict[str, Any]:
        # Helper function to handle verbose and regular mode
        if verbose > 0:
            # Caller that sets up command will write stdout to stderr
            # Equivalent of >&2
            sys.stderr.write(f"Running: {cmd_str}\n")
            return {"stdout": sys.stderr}
        else:
            # Caller that sets up command will write stdout to /dev/null, stderr to stdout
            # Equivalent of >/dev/null 2>&1
            return {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.STDOUT,
            }

    pid = os.getuid()
    tmp = getTmp()
    exp = getExp()
    if exp == "samdev":
        issuer = "fermilab"
        igroup = "fermilab"
    elif exp in ("lsst", "dune", "fermilab", "des"):
        issuer = exp
        igroup = exp
    else:
        issuer = "fermilab"
        igroup = f"fermilab/{exp}"
    vomsfile = os.environ.get("X509_USER_PROXY", f"{tmp}/x509up_{exp}_{role}_{pid}")

    # If this is a read-only proxy, like managed proxies or POMS-uploaded proxy, don't touch it!
    if os.path.exists(vomsfile) and (not os.access(vomsfile, os.W_OK)):
        return vomsfile

    certfile = os.environ.get("X509_USER_PROXY", f"{tmp}/x509up_u{pid}")

    invalid_proxy = False
    if not force_proxy:
        chk_cmd_str = f"voms-proxy-info -exists -valid 0:10 -file {vomsfile}"
        extra_check_args = generate_proxy_command_verbose_args(chk_cmd_str)
        try:
            subprocess.run(shlex.split(chk_cmd_str), check=True, **extra_check_args)
        except subprocess.CalledProcessError:
            invalid_proxy = True

    if force_proxy or invalid_proxy:
        cigetcert_cmd_str = f"cigetcert -i 'Fermi National Accelerator Laboratory' -n --proxyhours 168 --minhours 167 -o {certfile}"
        cigetcert_cmd = subprocess.run(
            shlex.split(cigetcert_cmd_str),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="UTF-8",
            env=os.environ,
        )
        if cigetcert_cmd.returncode != 0:
            if "Kerberos initialization failed" in cigetcert_cmd.stdout:
                raise Exception(
                    "Cigetcert failed to get proxy due to kerberos issue.  Please ensure "
                    "you have valid kerberos credentials."
                )
        voms_proxy_init_cmd_str = (
            f"voms-proxy-init -dont-verify-ac -valid 167:00 -rfc -noregen"
            f" -debug -cert {certfile} -key {certfile} -out {vomsfile} -vomslife 167:0"
            f" -voms {issuer}:/{igroup}/Role={role}"
        )
        extra_check_args = generate_proxy_command_verbose_args(voms_proxy_init_cmd_str)
        try:
            subprocess.run(
                shlex.split(voms_proxy_init_cmd_str),
                check=True,
                env=os.environ,
                **extra_check_args,
            )
        except subprocess.CalledProcessError:
            raise PermissionError(f"Failed attempting '{voms_proxy_init_cmd_str}'")
        else:
            return vomsfile

    return vomsfile


gfal_clean_env = (
    "unset PYTHONHOME PYTHONPATH LD_LIBRARY_PATH GFAL_PLUGIN_DIR GFAL_CONFIG_DIR"
)


def fix_pnfs(path: str) -> str:

    if path[0] == "/":
        path = os.path.realpath(path)

    # use nfs4 mount if present
    mountpoint_end = path.find("/", 7)
    if os.path.isdir(path[:mountpoint_end]):
        return path

    # otherwise make an https/webdav path for it
    m = re.match(r"/pnfs/(.*)", path)
    if m:
        path = f"https://fndcadoor.fnal.gov:2880/{m.group(1)}"
    return path


def chmod(dest: str, mode: int) -> None:
    # can't really chmod over https, but can over nfs mount, so
    # just try with the raw path, and ignore it if it doesn't work
    try:
        os.chmod(dest, mode)
    except FileNotFoundError as e:
        pass
    except PermissionError as e:
        pass


def mkdir_p(dest: str) -> None:
    """make possibly multiple directories"""
    dest = fix_pnfs(dest)
    if 0 != os.system(f"{gfal_clean_env}; gfal-mkdir -p {dest}"):
        raise PermissionError(f"Error: Unable to make directory {dest}")


def ls(dest: str) -> List[str]:
    """make possibly multiple directories"""
    dest = fix_pnfs(dest)
    with os.popen(f"{gfal_clean_env}; gfal-ls {dest} 2>/dev/null") as f:
        files = [x.strip() for x in f.readlines()]
    return files


@as_span("cp", arg_attrs=["*"])
def cp(src: str, dest: str) -> None:
    """copy a (remote) file with gfal-copy"""
    src = fix_pnfs(src)
    dest = fix_pnfs(dest)
    if 0 != os.system(f"{gfal_clean_env}; gfal-copy {src} {dest}"):
        raise PermissionError(f"Error: Unable to copy {src} to {dest}")


if __name__ == "__main__":
    commands = {
        "getProxy": getProxy,
        "getToken": getToken,
        "cp": cp,
        "ls": ls,
        "mkdir_p": mkdir_p,
        "getRole": getRole,
    }
    parser = argparse.ArgumentParser(description="ifdh subset replacement")
    parser.add_argument(
        "--experiment", help="experiment name", default=os.environ.get("GROUP", None)
    )
    parser.add_argument("--role", help="role name", default=None)
    parser.add_argument("command", action="store", nargs=1, help="command")
    parser.add_argument(
        "cpargs", default=None, action="append", nargs="*", help="copy arguments"
    )

    opts = parser.parse_args()
    myrole = getRole(opts.role)

    try:
        if opts.command[0] in ("cp", "ls", "mkdir_p"):
            print(commands[opts.command[0]](*opts.cpargs[0]))  # type: ignore
        else:
            result = commands[opts.command[0]](myrole, verbose=1)  # type: ignore
            if result is not None:
                print(result)
    except PermissionError as pe:
        sys.stderr.write(str(pe) + "\n")
        print("")
    except KeyError:
        print(
            "An invalid command to fake_ifdh was given.  Please select from "
            f'one of the following: {", ".join(commands.keys())}'
        )
