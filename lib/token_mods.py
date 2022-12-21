import os
import os.path
import shutil
from typing import List, Set


def get_job_scopes(
    tokenfile: str, need_modify: List[str], need_scopes: List[str]
) -> List[str]:
    clean_tokens = set(["storage.modify"])
    orig_scope = get_token_scope(tokenfile)
    job_scope = scope_without(clean_tokens, orig_scope)
    for dpath in need_modify:
        job_scope = add_subpath_scope("storage.modify", dpath, job_scope, orig_scope)

    for sc in need_scopes:
        # do not know how to check if these are allowed...
        job_scope.append(sc)

    job_scope.sort(key=len)
    # order matters to condor(?)

    return job_scope


def use_token_copy(tokenfile: str) -> str:
    pid = os.getpid()
    copyto = f"{tokenfile}.{pid}"
    shutil.copy(tokenfile, copyto)
    os.environ["BEARER_TOKEN_FILE"] = copyto
    return copyto


def get_token_scope(tokenfilename: str) -> List[str]:
    """get the list of scopes from our token file"""

    with os.popen(f"decode_token.sh -e scope {tokenfilename}", "r") as sf:
        data = sf.read()
        scopelist = data.strip().strip('"').split(" ")

    return scopelist


def scope_without(sctypeset: Set[str], orig_scopelist: List[str]) -> List[str]:
    """
    get the scope minus any components in sctypelist
    so scope_withot( set(["a","b"]), ["a:/x"'"b:/y","c:/z","d:/w"])
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
