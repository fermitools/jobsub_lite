import os
import re
import glob
import inspect
import pytest
import sys
import time
import subprocess
import tempfile
import shutil

#
# we assume everwhere our current directory is in the package
# test area, so go ahead and cd there
#
os.chdir(os.path.dirname(__file__))

#
# add to path what we eed to test
# unless we're testing installed, then use /opt/jobsub_lite/...
#
if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    sys.path.append("/opt/jobsub_lite/lib")
else:
    sys.path.append("../lib")

import fake_ifdh

if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    os.environ["PATH"] = "/opt/jobsub_lite/bin:" + os.environ["PATH"]
else:
    os.environ["PATH"] = (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        + "/bin:"
        + os.environ["PATH"]
    )

if 0 != os.system("ksu -e /bin/true"):
    pytest.skip("cannot ksu to make test filesystem here", allow_module_level=True)


@pytest.fixture
def tiny_home():
    # setup a $HOME which has just a few MB in it...
    tinyfile = f"{os.environ.get('TMPDIR', '/tmp')}/fsfile{os.getpid()}"
    tinymount = f"/media/tiny_{os.getpid()}"
    print("Setting up {tinymount} as full 3M $HOME area")
    print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
    os.system(f"dd if=/dev/zero of={tinyfile} bs=1M count=3 ")
    os.system(f"echo y | mkfs -t ext3 {tinyfile}")
    os.system(f"ksu -e /bin/mkdir -p {tinymount}")
    os.system(f"ksu -e /bin/mount -o loop,nodev {tinyfile} {tinymount}")
    os.system(f"ksu -e /bin/chown $USER {tinymount}")
    os.system(f"cp -r $HOME/.config/htgettoken {tinymount}/.config")
    save_home = os.environ["HOME"]
    os.environ["HOME"] = tinymount
    os.system(f"dd if=/dev/zero of={tinymount}/f3k bs=1k count=3")
    os.system(f"dd if=/dev/zero of={tinymount}/f16k bs=1k count=16")
    os.system(f"dd if=/dev/zero of={tinymount}/fillit")
    yield tinymount
    os.system(f"ksu -e /bin/umount {tinymount}")
    os.system(f"ksu -e rm {tinyfile}")
    os.environ["HOME"] = save_home
    print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
    return ""


def check_for(cmd, string):
    with os.popen(f"{cmd} 2>&1", "r") as fout:
        out = fout.read()
        sys.stdout.write(out)
        assert string in out


@pytest.mark.integration
def test_1(tiny_home):
    # TODO:  These should be split out into a series of tests in the future.
    # When tarfiles.tar_up transitions from using os.system to subprocess.run/call,
    # We need to change the expected text for the --tar_file_name tardir:// test cases
    # to "No space left on device"
    os.system(f"ls -la $HOME")
    os.system(f"df -h $HOME")
    print("With disk totally full:")
    print("===================")
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab file:///bin/true",
        "No space left on device",
    )
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab --tar_file_name {os.path.dirname(__file__)}/data/tiny.tar file:///bin/true",
        "No space left on device",
    )
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab --tar_file_name tardir://{os.path.dirname(__file__)}/dagnabbit file:///bin/true",
        # "No space left on device",
        "Tarring up the directory",
    )
    os.system(f"rm $HOME/f3k")
    print("===================")
    print("With 3k free:")
    print("===================")
    os.system(f"df -h $HOME")
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab file:///bin/true",
        "No space left on device",
    )
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab --tar_file_name {os.path.dirname(__file__)}/data/tiny.tar file:///bin/true",
        "No space left on device",
    )
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab --tar_file_name tardir://{os.path.dirname(__file__)}/dagnabbit file:///bin/true",
        # "No space left on device",
        "Tarring up the directory",
    )
    os.system(f"rm $HOME/f16k")
    print("===================")
    print("With 18k free:")
    print("===================")
    os.system(f"df -h $HOME")
    # Note:  Here, the tarball creation will work, but there won't be space to copy in the submit files
    check_for(
        f"cd $HOME; jobsub_submit -G fermilab --tar_file_name tardir://{os.path.dirname(__file__)}/dagnabbit file:///bin/true",
        "No space left on device",
    )
    print("===================")
