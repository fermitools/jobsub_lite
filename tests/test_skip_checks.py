import os
import sys
import pytest

os.chdir(os.path.dirname(__file__))


#
# import modules we need to test, since we chdir()ed, can use relative path
#
sys.path.append("../lib")
import skip_checks


def test_skip_check_setup_fake():
    """Pass a fake check, make sure we get a TypeError"""
    with pytest.raises(TypeError, match="Invalid check to skip"):
        skip_checks.skip_check_setup("thisisafakechecktoskip")


def test_skip_check_setup():
    """Get our list of supported checks to skip, make sure they all
    can run the registered setup functions"""
    checks = skip_checks.get_supported_checks_to_skip()
    for check in checks:
        skip_checks.skip_check_setup(check)
