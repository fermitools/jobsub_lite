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
import render_files


@pytest.mark.unit
def test_render_files_disk_full(fakefs, monkeypatch):
    _prefix = os.path.dirname(
        os.path.abspath(__file__)
    )  # /path/to/jobsub_lite_repo/tests/
    template_source_dir = os.path.join(_prefix, "data", "fake_templates")

    # Figure out how large fakefs has to be
    fakefs.pause()
    template_file = os.path.join(template_source_dir, "fake_basic_template")
    template_stat = os.stat(template_file)
    fakefs.set_disk_usage(template_stat.st_size)
    fakefs.resume()

    # Set up our fake fs source and destination directories
    fakefs.create_dir("/src")
    fakefs.add_real_file(
        f"{template_source_dir}/fake_basic_template", True, "/src/fake_basic_template"
    )
    fakefs.create_dir("/dest")

    values = {"argument": "value_of_argument"}
    with pytest.raises(OSError, match="No space left on device"):
        render_files._render_files(
            "/src",
            values,
            "/dest",
            None,
            False,
        )
