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
def getRole(role_override: Optional[str] = None, debug: int = 0) -> str:
    """get current role"""

    if role_override:
        return role_override

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
def getToken(role: str = DEFAULT_ROLE, debug: int = 0) -> str:
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

        if debug > 0:
            sys.stderr.write(f"Running: {cmd}")

        res = os.system(cmd)
        if res != 0:
            raise PermissionError(f"Failed attempting '{cmd}'")
        if checkToken(tokenfile):
            return tokenfile
        raise PermissionError(f"Failed attempting '{cmd}'")
    return tokenfile


@as_span("getProxy")
def getProxy(role: str = DEFAULT_ROLE, debug: int = 0) -> str:
    """get path to proxy certificate file"""
    pid = os.getuid()
    tmp = getTmp()
    exp = getExp()
    certfile = f"{tmp}/x509up_u{pid}"
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
    chk_cmd = f"voms-proxy-info -exists -valid 0:10 -file {vomsfile}"

    if debug > 0:
        # send output to stderr because invokers read stdout
        sys.stderr.write(f"Running: {chk_cmd}")
        chk_cmd += " >&2"
    else:
        chk_cmd += " >/dev/null 2>&1"

    if 0 != os.system(chk_cmd):
        cmd = f"cigetcert -i 'Fermi National Accelerator Laboratory' -n -o {certfile}"
        completed_cmd = subprocess.run(
            shlex.split(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="UTF-8",
        )
        if completed_cmd.returncode != 0:
            if "Kerberos initialization failed" in completed_cmd.stdout:
                raise Exception(
                    "Cigetcert failed to get proxy due to kerberos issue.  Please ensure "
                    "you have valid kerberos credentials."
                )
        cmd = (
            f"voms-proxy-init -dont-verify-ac -valid 120:00 -rfc -noregen"
            f" -debug -cert {certfile} -key {certfile} -out {vomsfile}"
            f" -voms {issuer}:/{igroup}/Role={role}"
        )

        if debug > 0:
            # send output to stderr because invokers read stdout
            sys.stderr.write("Running: {cmd}")
            cmd = f"{cmd} >&2"
        else:
            cmd = f"{cmd} > /dev/null 2>&1"

        os.system(cmd)

        if 0 == os.system(chk_cmd):
            return vomsfile
        raise PermissionError(f"Failed attempting '{cmd}'")
    return vomsfile


@as_span("cp", arg_attrs=["*"])
def cp(src: str, dest: str) -> None:
    """copy a (remote) file with gfal-copy"""
    os.system(f"gfal-copy {src} {dest}")


if __name__ == "__main__":
    commands = {
        "getProxy": getProxy,
        "getToken": getToken,
        "cp": cp,
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
        if opts.command[0] == "cp":
            commands[opts.command[0]](*opts.cpargs[0])  # type: ignore
        else:
            result = commands[opts.command[0]](myrole, debug=1)  # type: ignore
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
