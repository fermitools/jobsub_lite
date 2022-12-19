import os
import sys
import time
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
import tarfiles
import get_parser

from test_unit import TestUnit
from test_creds_unit import needs_credentials


class TestTarfilesUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    # lib/tarfiles.py routines...

    @pytest.mark.unit
    def test_tar_up_1(self):
        """make sure tar up makes a tarfile"""
        tarfile = tarfiles.tar_up(os.path.dirname(__file__), None)
        assert os.path.exists(tarfile)
        os.unlink(tarfile)

    @pytest.mark.unit
    def test_slurp_file_1(self):
        """make sure tar slurp_file makes a digest"""
        digest, tf = tarfiles.slurp_file(__file__)
        assert len(digest) == 64

    @pytest.mark.unit
    def test_repeated_tar_same_hash(self):
        """make sure if we tar up the same data twice we get the same
        hash for the tarball (i.e. no GZIP -n silliness)"""
        t1 = tarfiles.tar_up(
            os.path.dirname(__file__), "/dev/null", os.path.basename(__file__)
        )
        h1, b1 = tarfiles.slurp_file(t1)
        print(f"h1: {h1}")
        os.system(f"md5sum {t1}")
        os.unlink(t1)
        # wait to get a different timestamp
        time.sleep(2)
        t2 = tarfiles.tar_up(
            os.path.dirname(__file__), "/dev/null", os.path.basename(__file__)
        )
        h2, b2 = tarfiles.slurp_file(t2)
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
        proxy, token = needs_credentials
        # need something to publish...
        tarfile = tarfiles.tar_up(os.path.dirname(__file__), None)
        digest, tf = tarfiles.slurp_file(tarfile)
        cid = f"{TestUnit.test_group}/{digest}"

        publisher = tarfiles.TarfilePublisherHandler(cid, proxy, token)
        location = publisher.cid_exists()

        #
        # code cloned from do_tarballs... this logic should
        # probably be a callable method..
        #
        if location is None:
            publisher.publish(tf)
            for i in range(20):
                time.sleep(30)
                location = publisher.cid_exists()
                if location is not None:
                    break
        else:
            publisher.update_cid()

        assert location is not None

    @pytest.mark.unit
    def test_do_tarballs_1(self, needs_credentials):
        """test that the do_tarballs method does a dropbox:path
        processing"""
        tdir = os.path.dirname(__file__)
        for dropbox_type in ["cvmfs", "pnfs"]:
            argv = [
                "--tar_file_name",
                "tardir:{0}".format(tdir),
                "--use-{0}-dropbox".format(dropbox_type),
                "--group",
                TestUnit.test_group,
                "file:///bin/true",
            ]
            parser = get_parser.get_parser()
            args = parser.parse_args(argv)
            before_len = len(args.tar_file_name)
            tarfiles.do_tarballs(args)
            assert args.tar_file_name[0][:6] == "/{0}/".format(dropbox_type)[:6]
            assert before_len == len(args.tar_file_name)

    def x_test_do_tarballs_2(self):
        # should have another one here to test dropbox:xxx
        pass

    def x_test_do_tarballs_3(self):
        # should have another one here to test existing /cvmfs path
        pass
