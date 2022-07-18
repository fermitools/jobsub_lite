import os
import sys
import time
import pytest

#
# we assume everwhere our current directory is in the package 
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))


#
# import modules we need to test, since we chdir()ed, can use relative path 
#
sys.path.append("../lib")

import fake_ifdh

def test_getTmp():
    if os.environ.get('TMPDIR',None):
        del os.environ['TMPDIR']
    res = fake_ifdh.getTmp()
    assert res == "/tmp"

def test_getTmp_override():
    os.environ['TMPDIR'] = '/var/tmp'
    res = fake_ifdh.getTmp()
    assert res == "/var/tmp"

def test_getExp_GROUP():
    os.environ['GROUP'] = 'samdev'
    res = fake_ifdh.getExp()
    assert res == 'samdev'

def test_getExp_GROUP():
    os.environ['GROUP'] = ''
    os.environ['EXPERIMENT'] = 'samdev'
    res = fake_ifdh.getExp()
    assert res == 'samdev'

def test_getRole():
    res = fake_ifdh.getRole()
    assert res == fake_ifdh.DEFAULT_ROLE

def test_getRole_override():
    override_role = 'Hamburgler'
    res = fake_ifdh.getRole(override_role)
    assert res == override_role

def test_checkToken_fail():
    tokenfile = '/dev/null'
    res = fake_ifdh.checkToken(tokenfile)
    assert res


@pytest.fixture
def clear_token():
    if os.environ.get('BEARER_TOKEN_FILE', None):
        del os.environ['BEARER_TOKEN_FILE']

@pytest.fixture
def fermilab_token(clear_token):
    os.environ['GROUP'] = 'fermilab'
    return fake_ifdh.getToken('Analysis')
    
def test_checkToken_fail():
    tokenfile = '/dev/null'
    res = fake_ifdh.checkToken(tokenfile)
    assert not res

def test_checkToken_success(fermilab_token):
    res = fake_ifdh.checkToken(fermilab_token)
    assert res

def test_getToken_good(clear_token, fermilab_token):
    assert os.path.exists(fermilab_token)

def test_getToken_fail(clear_token):
    try:
        os.environ['GROUP'] = 'bozo'
        fake_ifdh.getToken('Analysis')
    except PermissionError:
        assert True
    else:
        assert False
   
def test_getProxy_good(clear_token):
     
    os.environ['GROUP'] = 'fermilab'
    proxy = fake_ifdh.getProxy('Analysis')
    assert os.path.exists(proxy)

def test_getProxy_fail(clear_token):
    try:
        os.environ['GROUP'] = 'bozo'
        proxy = fake_ifdh.getProxy('Analysis')
    except PermissionError:
        assert True
    else:
        assert False

def test_cp():
    dest = __file__+'.copy'
    fake_ifdh.cp( __file__, dest )
    assert os.path.exists( dest )
    os.unlink(dest)
