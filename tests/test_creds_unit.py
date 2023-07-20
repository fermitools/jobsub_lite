from collections import namedtuple
import json
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

DATADIR = f"{os.path.abspath(os.path.dirname(__file__))}/data"


@pytest.fixture
def check_valid_auth_method_arg_parser():
    """This fixture sets up a lightweight ArgumentParser to test the --auth-methods flag"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--auth-methods",
        action=creds.CheckIfValidAuthMethod,
        default=os.environ.get(
            "JOBSUB_AUTH_METHODS", ",".join(creds.SUPPORTED_AUTH_METHODS)
        ),
    )
    return parser


def get_auth_methods_test_data_good():
    """Pull in test data from data file and return a list of
    test cases"""
    AuthMethodsArgsTestCase = namedtuple(
        "AuthMethodsArgsTestCase",
        ["cmdline_args", "auth_methods_result"],
    )

    DATA_FILENAME = "auth_methods_args_good.json"
    with open(f"{DATADIR}/{DATA_FILENAME}", "r") as datafile:
        tests_json = json.load(datafile)

    return [AuthMethodsArgsTestCase(**test_json) for test_json in tests_json]


def get_auth_methods_test_data_bad():
    """Pull in test data from data file and return a list of
    test cases"""
    AuthMethodsArgsTestCase = namedtuple(
        "AuthMethodsArgsTestCase",
        ["cmdline_args", "bad_auth_method"],
    )

    DATA_FILENAME = "auth_methods_args_bad.json"
    with open(f"{DATADIR}/{DATA_FILENAME}", "r") as datafile:
        tests_json = json.load(datafile)

    return [AuthMethodsArgsTestCase(**test_json) for test_json in tests_json]


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
        assert os.path.exists(os.environ["X509_USER_PROXY"])
        assert os.path.exists(os.environ["BEARER_TOKEN_FILE"])
        assert os.path.exists(cred_set.proxy)
        assert os.path.exists(cred_set.token)

    @pytest.mark.unit
    def test_get_creds_default_role(self):
        """get credentials, make sure the credentials files returned
        exist"""
        args = {}
        os.environ["GROUP"] = TestUnit.test_group
        _ = creds.get_creds(args)
        assert args["role"] == "Analysis"

    @pytest.mark.unit
    def test_get_creds_token_only(self, clear_x509_user_proxy, clear_bearer_token_file):
        """Get only a token"""
        args = {"auth_methods": "token"}
        os.environ["GROUP"] = TestUnit.test_group
        cred_set = creds.get_creds(args)
        # Make sure we have a token and the env is set
        assert os.path.exists(os.environ["BEARER_TOKEN_FILE"])
        assert os.path.exists(cred_set.token)
        # Make sure the X509_USER_PROXY is not set
        assert os.environ.get("X509_USER_PROXY", None) is None

    @pytest.mark.unit
    def test_get_creds_proxy_only(self, clear_x509_user_proxy, clear_bearer_token_file):
        """Get only a proxy"""
        args = {"auth_methods": "proxy"}
        os.environ["GROUP"] = TestUnit.test_group
        cred_set = creds.get_creds(args)
        # Make sure we have a proxy and the env is set
        assert os.path.exists(os.environ["X509_USER_PROXY"])
        assert os.path.exists(cred_set.proxy)
        # Make sure the BEARER_TOKEN_FILE is not set
        assert os.environ.get("BEARER_TOKEN_FILE", None) is None

    @pytest.mark.unit
    def test_get_creds_invalid_auth(
        self, clear_x509_user_proxy, clear_bearer_token_file
    ):
        """This should never happen as the get_parser custom action should catch this and
        raise an Exception, but just in case we get past it"""
        args = {"auth_methods": "fakeauth"}
        os.environ["GROUP"] = TestUnit.test_group
        cred_set = creds.get_creds(args)
        assert cred_set.token is None
        assert cred_set.proxy is None
        # Make sure BEARER_TOKEN_FILE, X509_USER_PROXY are not set
        assert os.environ.get("BEARER_TOKEN_FILE", None) is None
        assert os.environ.get("X509_USER_PROXY", None) is None

    @pytest.mark.unit
    def test_print_cred_paths_from_credset(self, capsys):
        cred_set = creds.CredentialSet(token="tokenlocation", proxy="proxylocation")
        creds.print_cred_paths_from_credset(cred_set)
        out, _ = capsys.readouterr()
        assert out == (
            "token location: tokenlocation\n" "proxy location: proxylocation\n"
        )

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "auth_methods_args_test_case",
        get_auth_methods_test_data_good(),
    )
    def test_CheckIfValidAuthMethod_good(
        self, auth_methods_args_test_case, check_valid_auth_method_arg_parser
    ):
        args = check_valid_auth_method_arg_parser.parse_args(
            ["--auth-methods", auth_methods_args_test_case.cmdline_args]
        )
        assert args.auth_methods == auth_methods_args_test_case.auth_methods_result

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "auth_methods_args_test_case",
        get_auth_methods_test_data_bad(),
    )
    def test_CheckIfValidAuthMethod_bad(
        self, auth_methods_args_test_case, check_valid_auth_method_arg_parser
    ):
        with pytest.raises(
            TypeError, match=auth_methods_args_test_case.bad_auth_method
        ):
            args = check_valid_auth_method_arg_parser.parse_args(
                ["--auth-methods", auth_methods_args_test_case.cmdline_args]
            )
