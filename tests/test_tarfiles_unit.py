import importlib
import os
import sys
import tarfile as tarfile_mod
import time
import tempfile
import pathlib
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

from creds import CredentialSet
import tarfiles
import get_parser

from test_unit import TestUnit


@pytest.fixture
def tarfiles_mod_end_reloader():
    """Use this fixture to make sure we tarfiles module is reloaded after the test"""
    yield
    importlib.reload(tarfiles)


@pytest.fixture
def del_jobsub_dropbox_server_list(tarfiles_mod_end_reloader, monkeypatch):
    monkeypatch.delenv("JOBSUB_DROPBOX_SERVER_LIST", raising=False)
    importlib.reload(tarfiles)
    yield


@pytest.fixture
def set_jobsub_dropbox_server_list(tarfiles_mod_end_reloader, monkeypatch):
    monkeypatch.setenv("JOBSUB_DROPBOX_SERVER_LIST", "server1 server2")
    importlib.reload(tarfiles)
    yield


@pytest.fixture
def set_fake_args_to_tarfile_publisher_handler_test(tmp_path):
    """Get a set of fake cid, fake credentials argument to use in invocation to tarfiles.TarfilePublisherHandler"""
    fake_cid = f"{TestUnit.test_group}/12345abcde"
    fake_location = tmp_path / "fake_location"
    fake_location.touch()
    fake_creds = CredentialSet(token=str(fake_location))
    return fake_cid, fake_creds


class TestTarfilesUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    dir_to_tar: tempfile.TemporaryDirectory = None

    @classmethod
    def setup_class(cls):
        """Create our tar directory to tar up"""
        cls.dir_to_tar = tempfile.TemporaryDirectory()
        temp_path = pathlib.Path(cls.dir_to_tar.name)
        subdir = temp_path / "subdir"
        subdir.mkdir()
        # Create test files to put in dir
        for i in range(5):
            filename = f"file_{i}"
            writefile = temp_path / filename
            writefile.write_text(f"This is file {i}")
        subdir_file = subdir / "test_file"
        subdir_file.write_text("This is a file in a subdirectory")
        subdir_link = subdir / "test_link"
        subdir_link.symlink_to(subdir_file)
        subdir_hlink = subdir / "test_hlink"
        os.link(str(subdir_file), str(subdir_hlink))

    @classmethod
    def teardown_class(cls):
        """Delete any test remnants"""
        cls.dir_to_tar.cleanup()

    # lib/tarfiles.py routines...
    @pytest.mark.unit
    def test_tar_up_1(self):
        """make sure tar up makes a tarfile"""
        tarfile = tarfiles.tar_up(self.dir_to_tar.name, None)
        assert os.path.exists(tarfile)
        os.unlink(tarfile)

    @pytest.mark.unit
    def test_checksum_file_1(self):
        """make sure tar checksum_file makes a digest"""
        digest = tarfiles.checksum_file(__file__)
        assert len(digest) == 64

    @pytest.mark.unit
    def test_repeated_tar_same_hash(self):
        """make sure if we tar up the same data twice we get the same
        hash for the tarball (i.e. no GZIP -n silliness)"""
        t1 = tarfiles.tar_up(
            os.path.dirname(__file__), "/dev/null", os.path.basename(__file__)
        )
        h1 = tarfiles.checksum_file(t1)
        print(f"h1: {h1}")
        os.system(f"md5sum {t1}")
        os.unlink(t1)
        # wait to get a different timestamp
        time.sleep(2)
        t2 = tarfiles.tar_up(
            os.path.dirname(__file__), "/dev/null", os.path.basename(__file__)
        )
        h2 = tarfiles.checksum_file(t2)
        print(f"h2: {h2}")
        os.system(f"md5sum {t2}")
        os.unlink(t2)
        assert h1 == h2

    @pytest.mark.unit
    def test_dcache_persistent_path_1(self):
        """make sure persistent path gives /pnfs/ path digest"""
        path = tarfiles.dcache_persistent_path(TestUnit.test_group, __file__)
        assert path[:6] == "/pnfs/"

    @pytest.mark.unit
    def test_tarfile_publisher_1(self, needs_credentials):
        """test the tarfile publisher object"""
        cred_set = needs_credentials
        # need something to publish...
        tarfile = tarfiles.tar_up(self.dir_to_tar.name, None)
        digest = tarfiles.checksum_file(tarfile)
        cid = f"{TestUnit.test_group}/{digest}"

        publisher = tarfiles.TarfilePublisherHandler(cid, cred_set)
        location = publisher.cid_exists()

        #
        # code cloned from do_tarballs... this logic should
        # probably be a callable method..
        #
        if location is None:
            publisher.publish(tarfile)
            for i in range(20):
                time.sleep(30)
                location = publisher.cid_exists()
                if location is not None:
                    break
        else:
            publisher.update_cid()

        os.unlink(tarfile)
        assert location is not None

    @pytest.mark.unit
    def test_do_tarballs_1(self, needs_credentials):
        """test that the do_tarballs method does a dropbox:path
        processing"""
        for dropbox_type in ["cvmfs", "pnfs"]:
            argv = [
                "--tar_file_name",
                "tardir:{0}".format(self.dir_to_tar.name),
                "--use-{0}-dropbox".format(dropbox_type),
                "--group",
                TestUnit.test_group,
                "file:///bin/true",
            ]
            parser = get_parser.get_parser()
            args = parser.parse_args(argv)
            print(f"b: args.tar_file_name: {args.tar_file_name}")
            before_len = len(args.tar_file_name)
            tarfiles.do_tarballs(args)
            print(f"a: args.tar_file_name: {args.tar_file_name}")
            assert args.tar_file_name[0][:6] == "/{0}/".format(dropbox_type)[:6]
            assert before_len == len(args.tar_file_name)

    @pytest.mark.unit
    def test_do_tarballs_2(self, needs_credentials):
        """test that the do_tarballs method does a dropbox:path
        processing"""
        for dropbox_type in ["cvmfs", "pnfs"]:
            print(f"dropbox type: {dropbox_type}\n===============")
            argv = [
                "--tar_file_name",
                "tardir://{0}".format(self.dir_to_tar.name),
                "--use-{0}-dropbox".format(dropbox_type),
                "--group",
                TestUnit.test_group,
                "file:///bin/true",
            ]
            parser = get_parser.get_parser()
            args = parser.parse_args(argv)
            print(f"b: args.tar_file_name: {args.tar_file_name}")
            before_len = len(args.tar_file_name)
            tarfiles.do_tarballs(args)
            print(f"a: args.tar_file_name: {args.tar_file_name}")
            assert args.tar_file_name[0][:6] == "/{0}/".format(dropbox_type)[:6]
            assert before_len == len(args.tar_file_name)

    @pytest.mark.unit
    def test_do_tarballs_3(self, needs_credentials):
        """test that the do_tarballs method does a dropbox:path
        processing"""
        for dropbox_type in ["cvmfs", "pnfs"]:
            print(f"dropbox type: {dropbox_type}\n===============")
            argv = [
                "-f",
                "dropbox://{0}".format(__file__),
                "--use-{0}-dropbox".format(dropbox_type),
                "--group",
                TestUnit.test_group,
                "file:///bin/true",
            ]
            parser = get_parser.get_parser()
            args = parser.parse_args(argv)
            print(f"b: args.input_file: {args.tar_file_name}")
            before_len = len(args.tar_file_name)
            tarfiles.do_tarballs(args)
            print(f"a: args.input_file: {args.tar_file_name}")
            assert args.input_file[0][:6] == "/{0}/".format(dropbox_type)[:6]
            assert before_len == len(args.tar_file_name)

    def x_test_do_tarballs_4(self):
        # should have another one here to test dropbox:xxx
        pass

    def x_test_do_tarballs_5(self):
        # should have another one here to test existing /cvmfs path
        pass

    @pytest.mark.unit
    def test_tarfile_publisher_glob_path(self, needs_credentials):
        """Tests that the TarfilePublisherHandler glob path generator
        returns the expected glob for the CID given"""
        import re

        cred_set = needs_credentials
        fake_cid = f"{TestUnit.test_group}/12345abcde"
        tfh = tarfiles.TarfilePublisherHandler(fake_cid, cred_set)
        expected_pattern = r"/cvmfs/{(.+)}/sw/" + fake_cid
        assert re.match(expected_pattern, tfh.get_glob_path_for_cid())

    @pytest.mark.unit
    def test_tarfile_publisher_cid_operation(
        self, set_fake_args_to_tarfile_publisher_handler_test
    ):
        """Test the cid_operation decorator of the TarfilePublisherHandler."""
        from collections import namedtuple

        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        fake_location = fake_creds.token

        # We have to use this fake object to mimic a requests.Response's structure:
        # specifically, we need to return an object which has a "text"
        # attribute from our test functions wrapped with the cid_operation
        # handler, since the cid_operation decorator inspects the text
        # attribute of the return value of the function it wraps
        FakeTextContainer = namedtuple("FakeTextContainer", ["text"])

        class FakePublisherHandler(tarfiles.TarfilePublisherHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)

            @tarfiles.TarfilePublisherHandler.cid_operation
            def fail_function(self):
                return FakeTextContainer("thiswillnotmatch")

            @tarfiles.TarfilePublisherHandler.cid_operation
            def present_function(self):
                return FakeTextContainer(f"PRESENT:{fake_location}")

        f = FakePublisherHandler(cid=fake_cid, cred_set=fake_creds)
        assert f.fail_function() is None
        assert f.present_function() == str(fake_location)
        del os.environ["BEARER_TOKEN_FILE"]

    @pytest.mark.unit
    def test_tarchmod_not_tarfile(self, tmp_path):
        """Test that if we give tarchmod a file that is not a tarfile to
        operate on, it raises the appropriate error"""
        # Make a temp file with some content in it that is not a tarball
        CONTENT = "This is a fake temp file, not a tar archive"
        tmp_file = tmp_path / "test_file.txt"
        tmp_file.write_text(CONTENT)
        assert tmp_file.read_text() == CONTENT

        # The actual test
        with pytest.raises(tarfile_mod.TarError):
            tarfiles.tarchmod(str(tmp_file))

    @pytest.mark.unit
    def test_setup_fixed_server_no_server_set(
        self,
        del_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        with pytest.raises(tarfiles.NoPublisherHandlerServerError):
            _ = tarfiles.TarfilePublisherHandler(
                cid=fake_cid, cred_set=fake_creds, fixed_server=True
            )

    @pytest.mark.unit
    def test_setup_fixed_server(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(
            cid=fake_cid, cred_set=fake_creds, fixed_server=True
        )
        assert server_is_fixed(tfh)

    @pytest.mark.unit
    def test_setup_dropbox_server_selector_no_server_set(
        self,
        del_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        with pytest.raises(tarfiles.NoPublisherHandlerServerError):
            _ = tarfiles.TarfilePublisherHandler(cid=fake_cid, cred_set=fake_creds)

    @pytest.mark.unit
    def test_setup_dropbox_server_selector(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(cid=fake_cid, cred_set=fake_creds)
        assert server_switches(tfh)

    @pytest.mark.unit
    def test_activate_server_switcher_noop(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(cid=fake_cid, cred_set=fake_creds)
        assert server_switches(tfh)
        tfh.activate_server_switcher()
        assert server_switches(tfh)

    @pytest.mark.unit
    def test_activate_server_switcher(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(
            cid=fake_cid, cred_set=fake_creds, fixed_server=True
        )
        assert server_is_fixed(tfh)
        tfh.activate_server_switcher()
        assert server_switches(tfh)

    @pytest.mark.unit
    def test_deactivate_server_switcher_noop(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(
            cid=fake_cid, cred_set=fake_creds, fixed_server=True
        )
        assert server_is_fixed(tfh)
        tfh.deactivate_server_switcher()
        assert server_is_fixed(tfh)

    @pytest.mark.unit
    def test_deactivate_server_switcher(
        self,
        set_jobsub_dropbox_server_list,
        set_fake_args_to_tarfile_publisher_handler_test,
    ):
        fake_cid, fake_creds = set_fake_args_to_tarfile_publisher_handler_test
        tfh = tarfiles.TarfilePublisherHandler(cid=fake_cid, cred_set=fake_creds)
        assert server_switches(tfh)
        tfh.deactivate_server_switcher()
        assert server_is_fixed(tfh)


# Utility functions to use in tests


def server_switches(tfh: tarfiles.TarfilePublisherHandler) -> bool:
    """Function that checks if a TarfilePublisherHandler's server selector is switching
    servers.  Returns True if switching is happening, False otherwise"""
    dropbox_servers_env_dict = {
        server: None for server in os.getenv("JOBSUB_DROPBOX_SERVER_LIST").split()
    }
    results = {}
    for _ in range(len(dropbox_servers_env_dict)):
        result_server = next(tfh._dropbox_server_selector)
        results[result_server] = None
    return results == dropbox_servers_env_dict


def server_is_fixed(tfh: tarfiles.TarfilePublisherHandler) -> bool:
    """Function that checks if a TarfilePublisherHandler's server selector always yields
    the same server.  Returns True if server stays constant, False otherwise"""
    picked_server = next(tfh._dropbox_server_selector)
    if picked_server not in os.getenv("JOBSUB_DROPBOX_SERVER_LIST").split():
        return False
    for _ in range(10):
        if next(tfh._dropbox_server_selector) != picked_server:
            return False
    return True
