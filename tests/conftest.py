import os
import subprocess
import sys

import pytest

#
# we assume everwhere our current directory is in the package
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))

from test_unit import TestUnit

#
# import modules we need to test, since we chdir()ed, can use relative path
#
sys.path.append("../lib")

import creds


@pytest.fixture
def set_creds_dir(tmp_path):
    """
    Set the credentials directory to a temporary path for testing.
    """
    creds_dir = tmp_path / "creds"
    creds_dir.mkdir()
    yield creds_dir


@pytest.fixture
def set_temp_bearer_token_file(monkeypatch, set_creds_dir):
    """
    Set the BEARER_TOKEN_FILE env to a temporary path for testing.
    """
    monkeypatch.setenv("BEARER_TOKEN_FILE", str(set_creds_dir / "test_bearer_token"))
    yield


@pytest.fixture
def set_temp_x509_user_proxy(monkeypatch, set_creds_dir):
    """
    Set the X509_USER_PROXY env to a temporary path for testing.
    """
    monkeypatch.setenv("X509_USER_PROXY", str(set_creds_dir / "test_x509_user_proxy"))
    yield


@pytest.fixture
def needs_x509_user_proxy(
    monkeypatch,
    set_temp_x509_user_proxy,
    check_user_kerberos_creds,
):
    """
    Fixture to ensure that the X509_USER_PROXY is set and valid.
    """
    monkeypatch.setenv("GROUP", TestUnit.test_group)
    yield creds.get_creds({"role": "Analysis", "auth_methods": "proxy"})


@pytest.fixture
def needs_token(
    monkeypatch,
    set_temp_bearer_token_file,
    check_user_kerberos_creds,
):
    """
    Fixture to ensure that the BEARER_TOKEN_FILE is set and valid.
    """
    monkeypatch.setenv("GROUP", TestUnit.test_group)
    yield creds.get_creds({"role": "Analysis", "auth_methods": "token"})


@pytest.fixture
def needs_credentials(
    monkeypatch,
    needs_token,
    needs_x509_user_proxy,
    check_user_kerberos_creds,
):
    monkeypatch.setenv("GROUP", TestUnit.test_group)
    yield creds.get_creds({"role": "Analysis"})
    cred_set_token = needs_token
    cred_set_proxy = needs_x509_user_proxy
    yield creds.CredentialSet(token=cred_set_token.token, proxy=cred_set_proxy.proxy)


@pytest.fixture
def clear_x509_user_proxy():
    """Clear environment variable X509_USER_PROXY to test credentials overrides"""
    old_x509_user_proxy_value = os.environ.pop("X509_USER_PROXY", None)
    yield

    if old_x509_user_proxy_value is not None:
        os.environ["X509_USER_PROXY"] = old_x509_user_proxy_value


@pytest.fixture
def clear_bearer_token_file():
    """Clear environment variable BEARER_TOKEN_FILE to test credentials overrides"""
    old_bearer_token_file_value = os.environ.pop("BEARER_TOKEN_FILE", None)
    yield

    if old_bearer_token_file_value is not None:
        os.environ["BEARER_TOKEN_FILE"] = old_bearer_token_file_value


@pytest.fixture
def check_user_kerberos_creds():
    """Make sure we have kerberos credentials before starting the test"""
    proc = subprocess.run(
        ["klist"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8"
    )
    if proc.returncode or ("No credentials cache found" in proc.stdout):
        raise Exception(
            f"No kerberos credentials found.  Please run kinit and try again.  Error: {proc.stdout}"
        )


@pytest.fixture
def set_group_fermilab(monkeypatch):
    monkeypatch.setenv("GROUP", "fermilab")


# fs here is referring to a pyfakefs fake file system.  pyfakefs is a pytest plugin.
# By running "pip install pyfakefs", we can use the "fs" fixture in pytest tests and fixtures
@pytest.fixture
def fakefs(fs):
    yield fs
