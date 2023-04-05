import os
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
def needs_credentials():
    os.environ["GROUP"] = TestUnit.test_group
    return creds.get_creds({"role": "Analysis"})


@pytest.fixture
def clear_x509_user_proxy():
    """Clear environment variable X509_USER_PROXY to test credentials overrides"""
    old_x509_user_proxy_value = os.environ.pop("X509_USER_PROXY", None)
    yield

    if old_x509_user_proxy_value is not None:
        os.environ["X509_USER_PROXY"] = old_x509_user_proxy_value
