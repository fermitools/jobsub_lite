import os
import sys
import pytest

os.chdir(os.path.dirname(__file__))


#
# import modules we need to test, since we chdir()ed, can use relative path
#
sys.path.append("../lib")
import token_mods

# change path to get our decode_token.sh
os.environ["PATH"] = (
    os.path.dirname(os.path.dirname(__file__)) + "/bin:" + os.environ["PATH"]
)


@pytest.fixture
def sample_sl():
    """scope that should be in decode_token_tests/da1"""
    return [
        "storage.create:/dune/scratch/users/username",
        "compute.create",
        "compute.read",
        "compute.cancel",
        "compute.modify",
        "storage.read:/dune",
    ]


def test_get_job_scopes(sample_sl):
    """layer jobsub_submit calls to get desired job scope..."""

    tokenf = "decode_token_tests/mp1"  # sample mu2e token with modify
    need_modify = [
        "/mu2e/scratch/users/username/out1/d1",
        "/mu2e/scratch/users/username/out2/d2",
    ]
    need_scope = ["foo", "bar"]

    job_scopes = token_mods.get_job_scopes(tokenf, need_modify, need_scope)
    print(f"got job scopes: {repr(job_scopes)}")
    # check things we added
    assert "storage.modify:/mu2e/scratch/users/username/out1/d1" in job_scopes
    assert "storage.modify:/mu2e/scratch/users/username/out2/d2" in job_scopes
    assert "foo" in job_scopes
    assert "bar" in job_scopes
    # check things that should still be there from original
    assert "storage.create:/mu2e/scratch/users/username" in job_scopes
    assert "compute.modify" in job_scopes
    # check things that should NOT still be there from original
    assert "storage.modify:/mu2e/scratch/users/username" not in job_scopes


def test_get_token_scope_1(sample_sl):
    """check that get_token_scope finds the scope"""
    sl = token_mods.get_token_scope("decode_token_tests/da1")
    assert sl == sample_sl


def test_scope_without_1(sample_sl):
    """make sure scope_without can clean out scope types"""
    cleanout = set(["storage.read", "compute.cancel"])
    sl = token_mods.scope_without(cleanout, sample_sl)
    assert "compute.create" in sl
    assert "compute.modify" in sl
    assert "compute.cancel" not in sl
    assert "storage.read:/dune" not in sl


def test_add_subpath_scope_1(sample_sl):
    """test adding allowed weaker storage scopes"""
    sctyp = "storage.modify"
    scpath = "/dune/scratch/users/username"
    scsubdir1 = scpath + "/sub/directory"
    scsubdir2 = scpath + "/other/directory"
    orig_scl = sample_sl + ["{sctyp}:{scpath}"]

    nscl = token_mods.add_subpath_scope(sctyp, scsubdir1, sample_sl, orig_scl)
    nscl = token_mods.add_subpath_scope(sctyp, scsubdir2, nscl, orig_scl)

    assert "{sctyp}:{scsubdir1}" in nscl
    assert "{sctyp}:{scsubdir2}" in nscl


def test_add_subpath_scope_1(sample_sl):
    sctyp = "storage.modify"
    scpath = "/dune/scratch/users/username"
    scsubdir = scpath + "/sub/directory"
    orig_scl = sample_sl + ["{sctyp}:{scpath}"]

    with pytest.raises(PermissionError):
        nscl = token_mods.add_subpath_scope(sctyp, scpath, sample_sl, orig_scl)
