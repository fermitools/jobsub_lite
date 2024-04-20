"""
    Routines to deal with token scopes (permissions) which
    are stored in the "scope": entry of the Scitoken, and
    are generally a space-separated list of group.property:path
    style entries, with the group and path optional
"""

import os
import os.path
import shutil
import sys
from typing import List, Set

import scitokens  # type: ignore # pylint: disable=import-error
import packages


def get_job_scopes(
    tokenfile: str, need_modify: List[str], need_scopes: List[str]
) -> List[str]:
    """
    get the scope for this job submission
    * start with the original broad token scope
    * filter out tokens we don't want by default (currently storage.modify)
    * add any weaker-or-equal storage.modify items requested in need_modify
    * add any scopes listed in need_scopes
    and return that revised list
    """
    # clean_tokens: scope entries we scrub by default, currently just storage.modify
    #   if we were doing a config file this should probably be a config item...
    clean_tokens = set(["storage.modify"])

    orig_scope = get_token_scope(tokenfile)
    job_scope = scope_without(clean_tokens, orig_scope)
    for dpath in need_modify:
        job_scope = add_subpath_scope("storage.modify", dpath, job_scope, orig_scope)

    for sc in need_scopes:
        # do not know how to check if these are allowed...
        job_scope.append(sc)

    job_scope.sort(key=len)
    # order matters to condor(?) this seems to work

    return job_scope


def use_token_copy(tokenfile: str) -> str:
    """copy our submit scitoken file and point BEARER_TOKEN_FILE there, so when
    condor stomps on it we don't lose our original permissions for next time"""
    pid = os.getpid()
    copyto = f"{tokenfile}.{pid}"
    shutil.copy(tokenfile, copyto)
    os.environ["BEARER_TOKEN_FILE"] = copyto
    # This needs to be added so that any credential we set stays in both the environment
    # modified before use_token_copy() is called (such as the POMS pkg_find case) and the
    # environment in which this function is called.  So far, that seems to only be the case
    # for submissions that use the poms_client, so when that is moved to POMS, this can be removed.
    packages.add_to_SAVED_ENV_if_not_empty("BEARER_TOKEN_FILE", copyto)
    return copyto


def is_copied_token(tokenfile: str) -> bool:
    """check if the tokenfile is a copy we made."""
    return tokenfile.endswith(str(os.getpid()))


def get_token_scope(tokenfilename: str) -> List[str]:
    """get the list of scopes from our token file"""

    with open(tokenfilename) as f:  # pylint: disable=unspecified-encoding
        token_encoded = f.read().strip()
        token = scitokens.SciToken.deserialize(token_encoded, insecure=True)
        scopelist = str(token.get("scope")).split(" ")

    return scopelist


def scope_without(sctypeset: Set[str], orig_scopelist: List[str]) -> List[str]:
    """
    get the scope minus any components in sctypelist
    so scope_without( set(["a","b"]), ["a:/x"'"b:/y","c:/z","d:/w"])
    gives ["c:/z","d:/w"]...
    For now we use it to strip out storage.modify items, but we could
    need to do others, later.
    """
    res = []
    for s in orig_scopelist:
        if s.find(":") > 0:
            sctype = s[0 : s.find(":")]
        else:
            sctype = s

        if sctype and sctype not in sctypeset:
            res.append(s)

    return res


def add_subpath_scope(
    add_sctype: str, add_path: str, scopelist: List[str], orig_scopelist: List[str]
) -> List[str]:
    """check if given scope type and path can be added given orig_scopelist,
    and if it can, return the new scopelist appending it to scopelist"""

    add_path = os.path.normpath(add_path)  # don't be fooled by /a/b/../../c/d

    if add_path.startswith("/pnfs/") or add_path.startswith("/eos/"):
        # common user mistake, giving mounted path /pnfs/experiment/...
        # instead of /experiment/...
        new_path = add_path[add_path.find("/", 1) :]
        msg = "warning: detected wrong --need-storage-modify path:\n"
        msg = f"{msg} converting from {add_path}\n            to {new_path}\n"

        sys.stderr.write(msg)
        add_path = new_path

    for s in orig_scopelist:
        if s.find(":") > 0:
            s_sctype, s_path = s.split(":", 1)

            if (
                s_sctype == add_sctype
                and os.path.commonpath([s_path, add_path]) == s_path
            ):
                return scopelist + [f"{add_sctype}:{add_path}"]
    raise PermissionError(
        f"Unable to add '{add_sctype}:{add_path}' scope given initial scope '{orig_scopelist}'"
    )
