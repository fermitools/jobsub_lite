from collections import namedtuple
import json
import os
import sys
import tempfile
import time
import pytest

#
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

import utils

from test_unit import TestUnit

DATADIR = f"{os.path.abspath(os.path.dirname(__file__))}/data"


def fill_in(dir):
    open(f"{dir}/simple.sh", "w").close()
    open(f"{dir}/simple.cmd", "w").close()


@pytest.fixture
def test_job_dir():
    d = tempfile.mkdtemp()
    d = f"{d}/js_testdir"
    os.mkdir(d)
    fill_in(d)
    return d


@pytest.fixture
def test_old_dir(test_job_dir):
    d = f"{test_job_dir}/../js_newstuff"
    os.mkdir(d)
    fill_in(d)
    d = f"{test_job_dir}/../js_oldstuff"
    os.mkdir(d)
    fill_in(d)
    eightdaysago = time.time() - 691200
    os.utime(d, times=(eightdaysago, eightdaysago))
    return test_job_dir


def site_and_usage_model_test_data():
    """Pull in site and usage model test data from data file and
    return a list of test data for use in test"""
    SiteAndUsageModelTestCase = namedtuple(
        "SiteAndUsageModelTestCase",
        [
            "sites",
            "usage_model",
            "resource_provides_quoted",
            "expected_result",
            "helptext",
        ],
    )
    DATA_FILENAME = "site_and_usagemodel.json"
    with open(f"{DATADIR}/{DATA_FILENAME}", "r") as datafile:
        tests_json = json.load(datafile)

    return [
        SiteAndUsageModelTestCase(
            sites=test_json["sites"],
            usage_model=test_json["usage_model"],
            resource_provides_quoted=test_json["resource_provides_quoted"],
            expected_result=(
                utils.SiteAndUsageModel(
                    **test_json["expected_result"]["site_and_usage_model"]
                ),
                test_json["expected_result"]["resource_provides_remainder"],
            ),
            helptext=test_json["helptext"],
        )
        for test_json in tests_json
    ]


def singularity_test_data():
    """Pull in singularity test data from data file and return a list of
    test cases"""
    SingularityTestCase = namedtuple(
        "SingularityTestCase",
        [
            "singularity_image_arg",
            "lines_arg",
            "expected_singularity_image",
            "expected_lines",
            "helptext",
        ],
    )

    DATA_FILENAME = "singularity_image.json"
    with open(f"{DATADIR}/{DATA_FILENAME}", "r") as datafile:
        tests_json = json.load(datafile)

    return [SingularityTestCase(**test_json) for test_json in tests_json]


def site_blocklist_test_data(good=True):
    """Pull in site/blocklist test data from data file and return a list of
    test cases"""
    SiteAndBlocklistTestData = namedtuple(
        "SiteAndBlocklistTestData", ["helptext", "site_arg", "blocklist_arg"]
    )
    good_or_bad = "good" if good else "bad"
    DATA_FILENAME = f"site_blocklist_{good_or_bad}.json"
    with open(f"{DATADIR}/{DATA_FILENAME}", "r") as datafile:
        tests_json = json.load(datafile)

    return [SiteAndBlocklistTestData(**test_json) for test_json in tests_json]


def create_id_for_test_case(value) -> str:
    """Creates test IDs for our TestCase classes (namedtuples).  Will return
    the "helptext" attribute of the TestCase if it exists"""
    try:
        return value.helptext
    except AttributeError:
        pass


class TestUtilsUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    #
    # utils.py routines...
    #

    @pytest.mark.unit
    def test_fixquote_1(self):
        """check the fixquote routine"""
        assert utils.fixquote("test1") == "test1"
        assert utils.fixquote("test2=test3") == 'test2="test3"'
        assert utils.fixquote("test2=test3=test4") == 'test2="test3=test4"'

    @pytest.mark.unit
    def test_grep_n_1(self):
        """check the grep_n routine on us"""
        assert utils.grep_n(r"class (\w*):", 1, __file__) == "TestUtilsUnit"
        assert utils.grep_n(r"import (\w*)", 1, __file__) == "json"

    @pytest.mark.unit
    def test_fix_unit_1(self):
        """test fixing units on '64gb' memory"""
        args = TestUnit.test_vargs.copy()
        memtable = {"k": 1.0 / 1024, "m": 1, "g": 1024, "t": 1024 * 1024}
        utils.fix_unit(args, "memory", memtable, -1, "b", -2)
        assert args["memory"] == 64 * 1024

    @pytest.mark.unit
    def test_get_principal_1(self):
        """make sure get_principal returns a string starting with $USER"""
        # blatantly assumes you have a valid principal...
        res = utils.get_principal()
        assert res.split("@")[0] == os.environ["USER"]

    @pytest.mark.unit
    def test_set_extras_1(self, needs_credentials):
        """call set_extras_n_fix_units, verify one thing from environment
        and one unit conversion..."""
        cred_set = needs_credentials
        args = TestUnit.test_vargs.copy()
        utils.set_extras_n_fix_units(args, TestUnit.test_schedd, cred_set)
        assert args["user"] == os.environ["USER"]
        assert args["memory"] == 64 * 1024

    @pytest.mark.unit
    def x_test_get_client_dn_valid_proxy_provided(
        self, needs_credentials, clear_x509_user_proxy
    ):
        """Call get_client_dn with proxy specified"""
        cred_set = needs_credentials
        clear_x509_user_proxy
        client_dn = utils.get_client_dn(proxy=cred_set.proxy)
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def x_test_get_client_dn_env_plus_proxy_provided(self, needs_credentials):
        """Call get_client_dn with proxy specified, env set.  Should grab
        proxy from passed-in arg"""
        cred_set = needs_credentials
        old_x509_user_proxy_value = os.environ.pop("X509_USER_PROXY", None)
        os.environ[
            "X509_USER_PROXY"
        ] = "foobar"  # Break the environment so that this test won't accidentally pass
        client_dn = utils.get_client_dn(proxy=cred_set.proxy)
        assert os.environ["USER"] in client_dn
        os.environ["X509_USER_PROXY"] = old_x509_user_proxy_value

    @pytest.mark.unit
    def x_test_get_client_dn_no_proxy_provided(self, needs_credentials):
        """Call get_client_dn with no proxy specified.  Should grab proxy from
        env"""
        client_dn = utils.get_client_dn()
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def x_test_get_client_dn_no_proxy_provided_no_env(
        self, needs_credentials, clear_x509_user_proxy
    ):
        """Call get_client_dn with no proxy specified, environment not set.
        Should get proxy from standard grid location"""
        clear_x509_user_proxy
        client_dn = utils.get_client_dn()
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def x_test_get_client_dn_bad_proxy(self):
        """If we give a bad proxy file, or there's some other problem, we
        should get "" as the return value"""
        client_dn = utils.get_client_dn("bad_path")
        assert client_dn == ""

    @pytest.mark.unit
    def test_cleanup_simple(self, test_job_dir):
        assert os.path.exists(f"{test_job_dir}/simple.cmd")
        utils.cleanup({"submitdir": test_job_dir, "verbose": 1})
        assert not os.path.exists(f"{test_job_dir}/simple.cmd")
        assert not os.path.exists(test_job_dir)

    @pytest.mark.unit
    def test_cleanup_old(self, test_old_dir):
        oldd = f"{os.path.dirname(test_old_dir)}/js_oldstuff"
        newd = f"{os.path.dirname(test_old_dir)}/js_newstuff"
        assert os.path.exists(f"{test_old_dir}/simple.cmd")
        assert os.path.exists(f"{oldd}/simple.cmd")
        assert os.path.exists(f"{newd}/simple.cmd")
        utils.cleanup({"submitdir": test_old_dir, "verbose": 1})
        assert not os.path.exists(f"{test_old_dir}/simple.cmd")
        assert not os.path.exists(f"{oldd}/simple.cmd")
        assert os.path.exists(f"{newd}/simple.cmd")

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "site_and_usage_model_test_case",
        site_and_usage_model_test_data(),
        ids=create_id_for_test_case,
    )
    def test_resolve_site_and_usage_model(self, site_and_usage_model_test_case):
        """Check that site, usage model, and resource provides inputs are resolved
        correctly"""
        assert (
            utils.resolve_site_and_usage_model(
                site_and_usage_model_test_case.sites,
                site_and_usage_model_test_case.usage_model,
                site_and_usage_model_test_case.resource_provides_quoted,
            )
            == site_and_usage_model_test_case.expected_result
        )

    @pytest.mark.unit
    def test_resolve_site_and_usage_model_invalid(self):
        # I honestly can't think of any combos that don't work/won't get corrected before we get to validation,
        # but I'm leaving this here unless I missed something
        _should_not_work = []
        for sites, usage_model, resource_provides_quoted in _should_not_work:
            with pytest.raises(
                utils.SiteAndUsageModelConflictError, match="are in conflict"
            ):
                utils.resolve_site_and_usage_model(
                    sites, usage_model, resource_provides_quoted
                )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "singularity_test_case",
        singularity_test_data(),
        ids=create_id_for_test_case,
    )
    def test_resolve_singularity_image(self, singularity_test_case):
        """Test to make sure that given simgularity image and lines arguments are handled
        correctly"""
        assert (
            singularity_test_case.expected_singularity_image,
            singularity_test_case.expected_lines,
        ) == utils.resolve_singularity_image(
            singularity_test_case.singularity_image_arg,
            singularity_test_case.lines_arg,
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "site_blocklist_test_case",
        site_blocklist_test_data(good=True),
        ids=create_id_for_test_case,
    )
    def test_check_site_and_blocklist_good(self, site_blocklist_test_case):
        """Test to make sure that a given comma-separated site list string
        and blocklist string are handled correctly"""
        assert (
            utils.check_site_and_blocklist(
                site_blocklist_test_case.site_arg,
                site_blocklist_test_case.blocklist_arg,
            )
            is None
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "site_blocklist_test_case",
        site_blocklist_test_data(good=False),
        ids=create_id_for_test_case,
    )
    def test_check_site_and_blocklist_bad(self, site_blocklist_test_case):
        """Test to make sure that a given comma-separated site list string
        and blocklist string are handled correctly"""
        with pytest.raises(utils.SiteAndBlocklistConflictError):
            utils.check_site_and_blocklist(
                site_blocklist_test_case.site_arg,
                site_blocklist_test_case.blocklist_arg,
            )
