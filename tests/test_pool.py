import os
import sys

import pytest

# we assume everwhere our current directory is in the package
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))


#
# import modules we need to test, since we chdir()ed, can use relative path
# unless we're testing installed, then use /opt/jobsub_lite/...
#
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    sys.path.append("/opt/jobsub_lite/lib")
else:
    sys.path.append("../lib")

import condor
import importlib
import packages
import pool
import utils


@pytest.mark.unit
def test_set_pool(monkeypatch):
    # TODO This needs to have a few more test cases, but this will do for now
    monkeypatch.setenv(
        "JOBSUB_POOL_MAP",
        '{"global-pool-one": {"collector":"hostname.domain","onsite":"MY_ONSITE"}}',
    )
    monkeypatch.setenv("RANDOM_ENV", "RANDOM_VALUE")
    importlib.reload(pool)
    pool.set_pool("global-pool-one")
    assert packages.SAVED_ENV["RANDOM_ENV"] == "RANDOM_VALUE"
    assert packages.SAVED_ENV["_condor_COLLECTOR_HOST"] == "hostname.domain"
    assert condor.COLLECTOR_HOST == "hostname.domain"
    assert utils.ONSITE_SITE_NAME == "MY_ONSITE"
    pool.reset_pool()
