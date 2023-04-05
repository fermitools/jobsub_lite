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
def needs_credentials(check_user_kerberos_creds):
    os.environ["GROUP"] = TestUnit.test_group
    return creds.get_creds({"role": "Analysis"})


@pytest.fixture
def clear_x509_user_proxy():
    """Clear environment variable X509_USER_PROXY to test credentials overrides"""
    old_x509_user_proxy_value = os.environ.pop("X509_USER_PROXY", None)
    yield

    if old_x509_user_proxy_value is not None:
        os.environ["X509_USER_PROXY"] = old_x509_user_proxy_value


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
