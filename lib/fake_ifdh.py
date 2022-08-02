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

import sys

import os
import time
import argparse
from typing import Union, Any, Dict

VAULT_HOST = "fermicloud543.fnal.gov"
DEFAULT_ROLE = "Analysis"


def getTmp() -> str:
    """ return temp directory path """
    return os.environ.get("TMPDIR", "/tmp")


def getExp() -> str:
    """ return current experiment name """
    for ev in ["GROUP", "EXPERIMENT", "SAM_EXPERIMENT"]:
        if os.environ.get(ev, None):
            return os.environ.get(ev)
    # otherwise guess primary group...
    exp = None
    with os.popen("id -gn", "r", encoding="UTF-8") as f:
        exp = f.read()
    return exp


def getRole(role_override: Union[str, None] = None) -> str:
    """ get current role """
    if role_override:
        return role_override
    elif os.environ["USER"][-3:] == "pro":
        return "Production"
    else:
        return DEFAULT_ROLE


def checkToken(tokenfile: str) -> bool:
    """ check if token is (almost) expired """
    exp_time = None
    cmd = f"decode_token.sh -e exp {tokenfile} 2>/dev/null"
    with os.popen(cmd, "r", encoding="UTF-8") as f:
        exp_time = f.read()
    return exp_time and ((int(exp_time) - time.time()) > 60)


def getToken(role: str = DEFAULT_ROLE) -> str:
    """ get path to token file """
    pid = os.getuid()
    tmp = getTmp()
    exp = getExp()
    if exp == "samdev":
        issuer = "fermilab"
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
        cmd = f"htgettoken -a {VAULT_HOST} -i {issuer}"
        if role != DEFAULT_ROLE:
            cmd = f"{cmd} -r {role.lower()}"  # Token-world wants all-lower
        # send htgettoken output to stderr because invokers read stdout
        res = os.system(f"{cmd} >&2")
        if res != 0:
            raise PermissionError(f"Failed attempting '{cmd}'")
        if checkToken(tokenfile):
            return tokenfile
        else:
            raise PermissionError(f"Failed attempting '{cmd}'")
    else:
        return tokenfile


def getProxy(role: str = DEFAULT_ROLE) -> str:
    """ get path to proxy certificate file"""
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
        igroup = "fermilab/" + exp
    vomsfile = f"{tmp}/x509up_{exp}_{role}_{pid}"
    chk_cmd = f"voms-proxy-info -exists -valid 0:10 -file {vomsfile}"
    if 0 != os.system(chk_cmd):
        cmd = f"cigetcert -i 'Fermi National Accelerator Laboratory' -n -o {certfile}"
        # send htgettoken output to stderr because invokers read stdout
        os.system(f"{cmd} >&2")
        cmd = (
            f"voms-proxy-init -dont-verify-ac -valid 120:00 -rfc -noregen -debug -cert {certfile} -key {certfile} -out {vomsfile} -voms {issuer}:/{igroup}/Role={role}"
        )

        # send htgettoken output to stderr because invokers read stdout
        os.system(f"{cmd} >&2")
        if 0 == os.system(chk_cmd):
            return vomsfile
        else:
            raise PermissionError(f"Failed attempting '{cmd}'")
    else:
        return vomsfile


def cp(src: str, dest: str) -> None:
    """ copy a (remote) file with gfal-copy """
    os.system(f"gfal-copy {src} {dest}")


if __name__ == "__main__":
    commands = {"getProxy": getProxy, "getToken": getToken, "cp": cp}
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
    role = getRole(opts.role)

    try:
        if opts.command[0] == "cp":
            commands[opts.command[0]](*opts.cpargs[0])
        else:
            res = commands[opts.command[0]](role)
            if res != None:
                print(res)
    except PermissionError as pe:
        sys.stderr.write(str(pe) + "\n")
        print("")
    except KeyError:
        print(
            "An invalid command to fake_ifdh was given.  Please select from "
            f'one of the following: {", ".join(commands.keys())}'
        )
