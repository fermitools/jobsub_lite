import os
import glob
import json
import pytest
import sys
import time

sys.path.append("../lib")
import fake_ifdh

# make sure we are cd-ed in the test directorectory
os.chdir(os.path.dirname(__file__))


def do_decode_token_sh(filename: str, extract: str = ""):
    """run deocde_token.sh from our bin with optional -e flag
    and collect all the lines of output"""
    if extract:
        estr = f" -e {extract} "
    else:
        estr = ""
    cmd = f"../bin/decode_token.sh {estr}{filename}"
    lines = []
    with os.popen(cmd, "r") as f:
        lines = f.readlines()
    return lines


# need a token for varioust test
@pytest.fixture
def token():
    """get a token with default options"""
    os.environ["GROUP"] = "fermilab"
    return fake_ifdh.getToken()


def test_decode_token_fresh(token):
    """Make sure token dump is at least several lines"""
    lines = do_decode_token_sh(token)
    assert len(lines) > 5


def test_decode_token_fresh_json(token):
    """Make sure fresh token dump is parsable json"""
    lines = do_decode_token_sh(token)
    td = json.loads("".join(lines))
    assert "aud" in td
    assert "sub" in td


def test_decode_token_ext_aud(token):
    """make sure we can extract audience"""
    lines = do_decode_token_sh(token, "aud")
    assert lines[0] == '"https://wlcg.cern.ch/jwt/v1/any"'


def test_decode_token_ext_exp(token):
    """make sure we can extract expiration, and it is in future"""
    lines = do_decode_token_sh(token, "exp")
    assert int(lines[0]) > time.time()


def test_decode_token_ext_group():
    """make sure we can extract wlcg.groups and get whole list"""
    lines = do_decode_token_sh("decode_token_tests/dp1", "wlcg.groups")
    assert lines[0] == '["/dune","/dune/production"]\n'


def test_decode_token_past_bugs(token):
    """go through list of tokens  that caused trouble in past and
    make sure they generate good json, etc."""
    list = glob.glob("decode_token_tests/*")
    for f in list:
        lines = do_decode_token_sh(f)
        td = json.loads("".join(lines))
        assert "aud" in td
        assert "sub" in td
