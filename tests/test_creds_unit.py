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
# unless we're testing installed, then use /opt/jobsub_lite/...
#
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    sys.path.append("/opt/jobsub_lite/lib")
else:
    sys.path.append("../lib")
import creds
from test_unit import TestUnit


class TestCredUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    # lib/creds.py routines...

    @pytest.mark.unit
    def test_get_creds_1(self):
        """get credentials, make sure the credentials files returned
        exist"""
        os.environ["GROUP"] = TestUnit.test_group
        cred_set = creds.get_creds()
        # assert os.path.exists(os.environ["X509_USER_PROXY"])
        assert os.path.exists(os.environ["BEARER_TOKEN_FILE"])
        # assert os.path.exists(cred_set.proxy)
        assert os.path.exists(cred_set.token)
        # del os.environ["X509_USER_PROXY"]

    @pytest.mark.unit
    def test_get_creds_default_role(self):
        """get credentials, make sure the credentials files returned
        exist"""
        args = {"auth_methods": os.environ.get("JOBSUB_AUTH_METHODS", "token")}
        os.environ["GROUP"] = TestUnit.test_group
        _ = creds.get_creds(args)
        assert args["role"] == "Analysis"

    @pytest.mark.unit
    def test_get_creds_token_only(self, clear_x509_user_proxy, clear_bearer_token_file):
        """Get only a token"""
        args = {"auth_methods": os.environ.get("JOBSUB_AUTH_METHODS", "token")}
        os.environ["GROUP"] = TestUnit.test_group
        cred_set = creds.get_creds(args)
        # Make sure we have a token and the env is set
        assert os.path.exists(os.environ["BEARER_TOKEN_FILE"])
        assert os.path.exists(cred_set.token)
        # Make sure the X509_USER_PROXY is not set
        assert os.environ.get("X509_USER_PROXY", None) is None

    @pytest.mark.unit
    def x_test_get_creds_proxy_only(
        self, clear_x509_user_proxy, clear_bearer_token_file
    ):
        """Get only a proxy"""
        args = {"auth_methods": "proxy"}
        os.environ["GROUP"] = TestUnit.test_group
        with pytest.raises(TypeError, match="Missing required authorization method"):
            creds.get_creds(args)

    @pytest.mark.unit
    def test_get_creds_invalid_auth(
        self, clear_x509_user_proxy, clear_bearer_token_file
    ):
        """This should never happen as the get_parser custom action should catch this and
        raise an Exception, but just in case we get past it"""
        args = {"auth_methods": "fakeauth"}
        os.environ["GROUP"] = TestUnit.test_group
        with pytest.raises(TypeError, match="Missing required authorization method"):
            creds.get_creds(args)

    @pytest.mark.unit
    def test_print_cred_paths_from_credset(self, capsys):
        cred_set = creds.CredentialSet(token="tokenlocation", proxy="proxylocation")
        creds.print_cred_paths_from_credset(cred_set)
        out, _ = capsys.readouterr()
        assert out == (
            "token location: tokenlocation\n" "proxy location: proxylocation\n"
        )
        del os.environ["X509_USER_PROXY"]
