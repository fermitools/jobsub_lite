from collections import namedtuple
import grp
import os
import pathlib
import pwd
import shutil
import sys
import tempfile

import pytest
import jwt
import scitokens

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

import fake_ifdh


@pytest.fixture
def clear_token():
    if os.environ.get("BEARER_TOKEN_FILE", None):
        if os.path.exists(os.environ["BEARER_TOKEN_FILE"]):
            try:
                os.unlink(os.environ["BEARER_TOKEN_FILE"])
            except:
                pass
        del os.environ["BEARER_TOKEN_FILE"]


@pytest.fixture
def fermilab_token(clear_token, set_group_fermilab):
    # Get a standard fermilab token for tests
    return fake_ifdh.getToken("Analysis")


@pytest.fixture
def fake_proxy_path(tmp_path):
    fake_path = tmp_path / "test_proxy"
    if os.path.exists(fake_path):
        try:
            os.unlink(fake_path)
        except:
            pass
    return fake_path


@pytest.fixture
def switch_to_invalid_kerb_cache(monkeypatch, tmp_path):
    # Set the environment variable to an invalid path
    fakefile = tmp_path / "invalid_kerb_cache"
    fakefile.touch()
    monkeypatch.setenv("KRB5CCNAME", f"FILE:{fakefile}")
    yield


class TestGetTmp:
    @pytest.mark.unit
    def test_getTmp(self):
        if os.environ.get("TMPDIR", None):
            del os.environ["TMPDIR"]
        res = fake_ifdh.getTmp()
        assert res == "/tmp"

    @pytest.mark.unit
    def test_getTmp_override(self, monkeypatch):
        monkeypatch.setenv("TMPDIR", "/var/tmp")
        res = fake_ifdh.getTmp()
        assert res == "/var/tmp"


class TestGetExp:
    @pytest.mark.unit
    def test_getExp_GROUP(self, monkeypatch):
        monkeypatch.setenv("GROUP", "samdev")
        res = fake_ifdh.getExp()
        assert res == "samdev"

    @pytest.mark.unit
    def test_getExp_no_GROUP(self, monkeypatch):
        monkeypatch.delenv("GROUP", raising=False)
        # Adapted from https://stackoverflow.com/a/9324811
        user = pwd.getpwuid(os.getuid()).pw_name
        gid = pwd.getpwnam(user).pw_gid
        expected_group = grp.getgrgid(gid).gr_name
        assert fake_ifdh.getExp() == expected_group


# getRole and derived function test fixtures
default_role_file_dirs = ("/tmp", f'{os.environ.get("HOME")}/.config')


@pytest.fixture
def stage_existing_default_role_files(set_group_fermilab):
    # If we already have a default role file, stage it somewhere else
    staged_temp_files = {}

    uid = os.getuid()
    group = os.environ.get("GROUP")
    filename = f"jobsub_default_role_{group}_{uid}"
    try:
        for file_location in default_role_file_dirs:
            file_dir = pathlib.Path(file_location)
            filepath = file_dir / filename

            if os.path.exists(filepath):
                old_file_temp = tempfile.NamedTemporaryFile(delete=False)
                os.rename(filepath, old_file_temp.name)
                staged_temp_files[filepath] = old_file_temp.name

        yield

    finally:
        # Put any staged files back
        for filepath, staged_file in staged_temp_files.items():
            os.rename(staged_file, filepath)


@pytest.fixture(params=default_role_file_dirs)
def default_role_file_location(request):
    return request.param


class TestGetRole:
    @pytest.mark.unit
    def test_getRole_from_default_role_file(
        self, default_role_file_location, stage_existing_default_role_files
    ):
        uid = os.getuid()
        group = os.environ.get("GROUP")
        filename = f"jobsub_default_role_{group}_{uid}"
        file_dir = pathlib.Path(default_role_file_location)
        file_dir.mkdir(exist_ok=True)
        filepath = file_dir / filename
        try:
            filepath.write_text("testrole")
            assert fake_ifdh.getRole_from_default_role_file() == "testrole"
        finally:
            os.unlink(filepath)

    @pytest.mark.unit
    def test_getRole_from_default_role_file_none(
        self, stage_existing_default_role_files
    ):
        assert not fake_ifdh.getRole_from_default_role_file()

    @pytest.mark.unit
    def test_getRole_from_valid_token(self, monkeypatch):
        monkeypatch.setenv(
            "BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab_production.token"
        )
        assert fake_ifdh.getRole_from_valid_token() == "Production"

    @pytest.mark.unit
    def test_getRole_from_valid_token_invalid(self, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/malformed.token")
        with pytest.raises(TypeError, match="malformed.*list"):
            fake_ifdh.getRole_from_valid_token()

    @pytest.mark.unit
    def test_getRole_from_valid_token_none(self, monkeypatch):
        monkeypatch.delenv("BEARER_TOKEN_FILE", raising=False)
        assert not fake_ifdh.getRole_from_valid_token()

    @pytest.mark.unit
    def test_getRole(self, set_group_fermilab):
        res = fake_ifdh.getRole()
        assert res == fake_ifdh.DEFAULT_ROLE

    @pytest.mark.unit
    def test_getRole_override(self):
        override_role = "Hamburgler"
        res = fake_ifdh.getRole(override_role)
        assert res == override_role


# checkToken test fixtures
_TokenLocationAndReverser = namedtuple(
    "_TokenLocationAndReverser", ["token_location", "preserve_or_reverse_func"]
)
_token_locations_and_reversers = (
    _TokenLocationAndReverser("fake_ifdh_tokens/fermilab.token", lambda x: x),
    _TokenLocationAndReverser("thispathdoesntexist", lambda x: not x),
    _TokenLocationAndReverser("fake_ifdh_tokens/expired.token", lambda x: not x),
)


@pytest.fixture(params=_token_locations_and_reversers)
def token_locations_and_reverser(request):
    return request.param


class TestCheckToken:
    @pytest.mark.unit
    def test_checkToken_bool(
        self,
        token_locations_and_reverser,
        monkeypatch,
        clear_bearer_token_file,
    ):
        monkeypatch.setenv(
            "BEARER_TOKEN_FILE", token_locations_and_reverser.token_location
        )
        group = "fermilab"
        # If we want to assert False in one of these cases, flip the result using preserve_or_reverse_func
        assert token_locations_and_reverser.preserve_or_reverse_func(
            fake_ifdh.checkToken(group)
        )

    @pytest.mark.unit
    def test_checkToken_wrong_group_raises(self, monkeypatch, clear_bearer_token_file):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab.token")
        group = "fakegroup"
        with pytest.raises(ValueError, match="wrong group"):
            fake_ifdh.checkToken(group)


class TestCheckTokenNotExpired:
    @pytest.mark.unit
    def test_fail(self, clear_bearer_token_file, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/expired.token")
        try:
            token = scitokens.SciToken.discover(insecure=True)
            assert not fake_ifdh.checkToken_not_expired(token)
        except jwt.ExpiredSignatureError:
            pass

    @pytest.mark.unit
    def test_success(self, clear_bearer_token_file, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab.token")
        token = scitokens.SciToken.discover(insecure=True)
        assert fake_ifdh.checkToken_not_expired(token)


# checkToken_right_group_and_role test cases and fixtures
_BadCheckTokenTestCase = namedtuple(
    "_BadCheckTokenTestCase",
    ["token_location", "group", "raised_error", "match_expr", "role"],
)
_bad_checkToken_test_cases = (
    _BadCheckTokenTestCase(
        "fake_ifdh_tokens/no_groups.token", "fermilab", TypeError, r"wlcg\.groups", None
    ),
    _BadCheckTokenTestCase(
        "fake_ifdh_tokens/malformed.token",
        "fermilab",
        TypeError,
        "malformed.*list",
        None,
    ),
    _BadCheckTokenTestCase(
        "fake_ifdh_tokens/fermilab.token", "badgroup", ValueError, "wrong group", None
    ),
    _BadCheckTokenTestCase(
        "fake_ifdh_tokens/fermilab.token",
        "fermilab",
        ValueError,
        "wrong group or role",
        "badrole",
    ),
)


@pytest.fixture(params=_bad_checkToken_test_cases)
def bad_checkToken_test_case(request):
    return request.param


class TestCheckTokenRightGroupAndRole:
    @pytest.mark.unit
    def test_good(self, clear_bearer_token_file, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab.token")
        group = "fermilab"
        token = scitokens.SciToken.discover(insecure=True)
        fake_ifdh.checkToken_right_group_and_role(token, group)

    @pytest.mark.unit
    def test_good_with_role(self, clear_bearer_token_file, monkeypatch):
        monkeypatch.setenv(
            "BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab_production.token"
        )
        group = "fermilab"
        role = "production"
        token = scitokens.SciToken.discover(insecure=True)
        fake_ifdh.checkToken_right_group_and_role(token, group, role)

    @pytest.mark.unit
    def test_good_with_role_different_case(self, clear_bearer_token_file, monkeypatch):
        """Should still pass because we should be case-insensitive"""
        monkeypatch.setenv(
            "BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab_production.token"
        )
        group = "fermilab"
        role = "Production"
        token = scitokens.SciToken.discover(insecure=True)
        fake_ifdh.checkToken_right_group_and_role(token, group, role)

    @pytest.mark.unit
    def test_bad(self, bad_checkToken_test_case, clear_bearer_token_file, monkeypatch):
        monkeypatch.setenv("BEARER_TOKEN_FILE", bad_checkToken_test_case.token_location)
        group = bad_checkToken_test_case.group
        token = scitokens.SciToken.discover(insecure=True)
        with pytest.raises(
            bad_checkToken_test_case.raised_error,
            match=bad_checkToken_test_case.match_expr,
        ):
            args = (
                (token, group, bad_checkToken_test_case.role)
                if bad_checkToken_test_case.role
                else (token, group)
            )
            fake_ifdh.checkToken_right_group_and_role(*args)


class TestGetToken:
    @pytest.mark.unit
    def test_good(self, clear_token, fermilab_token):
        assert os.path.exists(fermilab_token)

    @pytest.mark.unit
    def test_fail(self, monkeypatch, clear_token):
        monkeypatch.setenv("GROUP", "bozo")
        with pytest.raises(PermissionError):
            fake_ifdh.getToken("Analysis")

    @pytest.mark.unit
    def test_bearer_token_file_good(
        self, monkeypatch, clear_bearer_token_file, set_group_fermilab
    ):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab.token")
        assert fake_ifdh.getToken() == os.environ["BEARER_TOKEN_FILE"]

    @pytest.mark.unit
    def test_bearer_token_file_expired(
        self, monkeypatch, tmp_path, clear_bearer_token_file
    ):
        # Since the token is expired, a new, valid token should show up at BEARER_TOKEN_FILE
        token_path = tmp_path / "expired.token"
        shutil.copy("fake_ifdh_tokens/expired.token", token_path)
        monkeypatch.setenv("BEARER_TOKEN_FILE", str(token_path))
        monkeypatch.setenv("GROUP", "fermilab")
        assert fake_ifdh.getToken()

    @pytest.mark.unit
    def test_bearer_token_file_wrong_group(self, monkeypatch, clear_bearer_token_file):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/fermilab.token")
        monkeypatch.setenv("GROUP", "bogus")
        with pytest.raises(ValueError, match="wrong group"):
            fake_ifdh.getToken()

    @pytest.mark.unit
    def test_bearer_token_file_malformed(self, monkeypatch, clear_bearer_token_file):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "fake_ifdh_tokens/malformed.token")
        monkeypatch.setenv("GROUP", "fermilab")
        with pytest.raises(TypeError, match="malformed"):
            fake_ifdh.getToken()

    @pytest.mark.unit
    def test_bearer_token_file_not_exist(self, monkeypatch, clear_bearer_token_file):
        monkeypatch.setenv("BEARER_TOKEN_FILE", "thisfiledoesnotexist")
        monkeypatch.setenv("GROUP", "fermilab")
        token_file = fake_ifdh.getToken()
        assert os.path.exists(token_file)


class TestGetProxy:
    @pytest.mark.unit
    def x_test_getProxy_good(
        self, check_user_kerberos_creds, clear_token, set_group_fermilab
    ):
        proxy = fake_ifdh.getProxy("Analysis")
        assert os.path.exists(proxy)

    @pytest.mark.unit
    def x_test_getProxy_override(
        self,
        check_user_kerberos_creds,
        clear_x509_user_proxy,
        clear_token,
        set_group_fermilab,
        fake_proxy_path,
        monkeypatch,
        tmp_path,
    ):
        fake_path = fake_proxy_path
        monkeypatch.setenv("X509_USER_PROXY", str(fake_path))
        proxy = fake_ifdh.getProxy("Analysis")
        assert proxy == str(fake_path)

    @pytest.mark.unit
    def x_test_getProxy_fail(
        self,
        check_user_kerberos_creds,
        clear_x509_user_proxy,
        clear_token,
        fake_proxy_path,
        monkeypatch,
        tmp_path,
    ):
        fake_path = fake_proxy_path
        monkeypatch.setenv("X509_USER_PROXY", str(fake_path))
        monkeypatch.setenv("GROUP", "bozo")
        with pytest.raises(PermissionError):
            fake_ifdh.getProxy("Analysis")

    @pytest.mark.unit
    def x_test_getProxy_fail_cigetcert_kerberos(
        self,
        switch_to_invalid_kerb_cache,
        clear_x509_user_proxy,
        clear_token,
        fake_proxy_path,
        monkeypatch,
        tmp_path,
    ):
        fake_path = fake_proxy_path
        monkeypatch.setenv("X509_USER_PROXY", str(fake_path))
        monkeypatch.setenv("GROUP", "bozo")

        # Should fail because cigetcert fails for kerberos issue
        with pytest.raises(Exception, match="kerberos issue"):
            fake_ifdh.getProxy("Analysis")

    @pytest.mark.unit
    def x_test_getProxy_fail_cigetcert_other(
        self,
        clear_x509_user_proxy,
        clear_token,
        monkeypatch,
        tmp_path,
    ):
        # We're trying to force a permission-denied error here.  So try to write to /dev/null/fake_file, which can never exist since /dev/null isn't a directory
        monkeypatch.setenv("X509_USER_PROXY", "/dev/null/fake_file")
        monkeypatch.setenv("GROUP", "bozo")

        # Should fail because cigetcert fails for kerberos issue
        with pytest.raises(
            PermissionError,
            match="Cigetcert failed to get a proxy due to an unspecified issue",
        ):
            fake_ifdh.getProxy("Analysis")


@pytest.mark.unit
def test_cp():
    dest = __file__ + ".copy"
    if os.path.exists(dest):
        os.unlink(dest)
    fake_ifdh.cp(__file__, dest)
    assert os.path.exists(dest)
    os.unlink(dest)


@pytest.mark.parametrize(
    "input, expected, raised_error, match_expr",
    [
        (["/fermilab"], ("fermilab", "Analysis"), None, None),
        (["/fermilab/production", "/fermilab"], ("fermilab", "production"), None, None),
        (["/hypot"], ("hypot", "Analysis"), None, None),
        (["hypot"], None, ValueError, r"wlcg\.groups.*token.*malformed"),
    ],
)
@pytest.mark.unit
def test_get_group_and_role_from_token_claim(input, expected, raised_error, match_expr):
    if not raised_error:
        assert fake_ifdh.get_group_and_role_from_token_claim(input) == expected
    else:
        with pytest.raises(raised_error, match=match_expr):
            fake_ifdh.get_group_and_role_from_token_claim(input)
