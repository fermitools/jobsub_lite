import os
import sys
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
import utils

from test_unit import TestUnit
from test_creds_unit import needs_credentials  # pylint: disable=unused-import
from test_creds_unit import clear_x509_user_proxy  # pylint: disable=unused-import


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
        assert utils.grep_n(r"import (\w*)", 1, __file__) == "os"

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
        proxy, token = needs_credentials
        args = TestUnit.test_vargs.copy()
        utils.set_extras_n_fix_units(args, TestUnit.test_schedd, proxy, token)
        assert args["user"] == os.environ["USER"]
        assert args["memory"] == 64 * 1024

    @pytest.mark.unit
    def test_get_client_dn_valid_proxy_provided(
        self, needs_credentials, clear_x509_user_proxy
    ):
        """Call get_client_dn with proxy specified"""
        _proxy, _ = needs_credentials
        clear_x509_user_proxy
        client_dn = utils.get_client_dn(proxy=_proxy)
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def test_get_client_dn_env_plus_proxy_provided(self, needs_credentials):
        """Call get_client_dn with proxy specified, env set.  Should grab
        proxy from passed-in arg"""
        _proxy, _ = needs_credentials
        old_x509_user_proxy_value = os.environ.pop("X509_USER_PROXY", None)
        os.environ[
            "X509_USER_PROXY"
        ] = "foobar"  # Break the environment so that this test won't accidentally pass
        client_dn = utils.get_client_dn(proxy=_proxy)
        assert os.environ["USER"] in client_dn
        os.environ["X509_USER_PROXY"] = old_x509_user_proxy_value

    @pytest.mark.unit
    def test_get_client_dn_no_proxy_provided(self, needs_credentials):
        """Call get_client_dn with no proxy specified.  Should grab proxy from
        env"""
        _proxy, _ = needs_credentials  # Sets $X509_USER_PROXY
        client_dn = utils.get_client_dn()
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def test_get_client_dn_no_proxy_provided_no_env(
        self, needs_credentials, clear_x509_user_proxy
    ):
        """Call get_client_dn with no proxy specified, environment not set.
        Should get proxy from standard grid location"""
        _proxy, _ = needs_credentials
        clear_x509_user_proxy
        client_dn = utils.get_client_dn()
        assert os.environ["USER"] in client_dn

    @pytest.mark.unit
    def test_get_client_dn_bad_proxy(self):
        """If we give a bad proxy file, or there's some other problem, we
        should get "" as the return value"""
        client_dn = utils.get_client_dn("bad_path")
        assert client_dn == ""
