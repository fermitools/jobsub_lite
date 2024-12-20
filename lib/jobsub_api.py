from typing import List, Optional, Generator
import re
import sys
import contextlib
from io import StringIO
from mains import jobsub_submit_main, jobsub_fetchlog_main, jobsub_cmd_main


@contextlib.contextmanager
def output_saver(should_i: bool) -> Generator[StringIO, StringIO, StringIO]:
    """
    context manager that optionally puts sys.stdio and sys.stderr into
    a StringIO() so you can look at them...
    """

    output = StringIO()
    if should_i:
        # save initial stdout, stderr
        save_out = sys.stdout
        save_err = sys.stderr
        # point them at our StringIO
        sys.stdout = output
        sys.stderr = output
    yield output
    if should_i:
        # put them back
        sys.stderr = save_err
        sys.stdout = save_out
    return output


# so clients can easily parse the result strings
jobsub_submit_re = re.compile(r"Use job id (?P<jobid>[0-9.]+\@[^ ]+) to retrieve")

jobsub_q_re = re.compile(
    r"(?P<jobid>\S+)\s+"
    r"(?P<owner>\S+)\s+"
    r"(?P<submitted>\S+\s\S+)\s+"
    r"(?P<runtime>\S+)\s+"
    r"(?P<status>\S+)\s+"
    r"(?P<prio>\S+)\s+"
    r"(?P<size>\S+)\s+"
    r"(?P<command>.*)"
)


def jobsub_call(argv: List[str], return_output: bool = False) -> Optional[str]:
    print("here: jobsub_call")
    res = None
    if argv[0].find("_submit") > 0:
        func = jobsub_submit_main
    elif argv[0].find("_fetchlog") > 0:
        func = jobsub_fetchlog_main
    else:
        func = jobsub_cmd_main
    print("here: picked ", func)
    try:
        with output_saver(return_output) as output:
            func(argv)
            res = output.getvalue()
    except:
        print(f"Excepion in jobsub_call({argv})")
        raise
    print("... and back:")
    return res
