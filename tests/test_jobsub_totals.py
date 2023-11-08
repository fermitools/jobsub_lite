import pytest
import os

if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
    os.environ["PATH"] = "/opt/jobsub_lite/bin:" + os.environ["PATH"]
else:
    os.environ["PATH"] = (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        + "/bin:"
        + os.environ["PATH"]
    )


class TestJobsubTotals:
    """
    test our totals script
    """

    @pytest.mark.unit
    def test_jobsub_totals(self):
        count = 0
        last = ""
        with os.popen("jobsub_totals < data/jq_out.txt", "r") as jqout:
            for l in jqout.readlines():
                print(l, end="")
                count = count + 1
                last = l
        assert (
            last
            == "1862 total; 15 completed, 0 removed, 64 idle, 1748 running, 35 held, 0 suspended\n"
        )
        assert count == 1863
