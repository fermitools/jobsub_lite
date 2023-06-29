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

from condor import get_schedd_names
import get_parser
import pool

from test_unit import TestUnit
from test_submit_wait_int import get_collector


def set_pool_map():
    """we need a pool map set to test the --global-pool option"""
    os.environ["GROUP"] = "dune"
    os.environ["JOBSUB_POOL_MAP"] = (
        '{"dune":{"collector":"' + get_collector() + '","onsite":"FNAL_GPGRID"}}'
    )
    del os.environ["GROUP"]


# we need to set the pool map when we're imported...
set_pool_map()


@pytest.fixture
def paired_arguments():
    """
    Tuple of all paired arguments aside from those that are dash-underscore-differentiated.
    This is for those like "--singularity-image" and "apptainer-image", which point to the same
    argument.  We are mapping the alternate option back to the primary option - the option that
    will drive the destination variable name.
    """
    return {
        "apptainer-image": "singularity-image",
        "no-apptainer": "no-singularity",
        "onsite-only": "onsite",
        "offsite-only": "offsite",
    }


@pytest.fixture
def find_all_arguments(paired_arguments):
    # try to extract all the --foo arguments from the source
    # and track which ones are flags
    # we assume
    # * there are mostly calls to add_argument in the source file
    # * the add_argument lines may span multiple lines, but
    # * we don't have more than one add_argument call per line
    # so we look for various parts of the add_argument calls
    # separately on each line
    if os.environ.get("JOBSUB_TEST_INSTALLED", "0") == "1":
        f = open("/opt/jobsub_lite/lib/get_parser.py", "r")
    else:
        f = open("../lib/get_parser.py", "r")
    flagargs = set()
    listargs = set()
    allargs = []
    dest = {}
    for line in f.readlines():
        p = line.find('"--')
        mq = '"'
        if p < 0:
            p = line.find("'--")
            mq = "'"

        if p > 0:
            # we saw a '"--...' or "'--..." which we assume is a parameter
            # to add_argument (or similar), so pull the argument name
            # and mark that as "arg" -- the argument we're currently
            # working on
            arg = line[p + 3 :]
            p2 = arg.find(mq)
            arg = arg[0:p2]
            # sometimes we find '--arg=whatever' in a help message
            # just prune it back down to --arg and it shouldn't hurt
            # assuming its still talking about the current argument, or last
            p2 = arg.find("=")
            if p2 >= 0:
                arg = arg[0:p2]
            # all of our old args with underscores have dashed versions now
            # so ignore the underscore versions.
            if arg.find("_") == -1 and arg:
                allargs.append(arg)
                dest[arg] = arg  # destination starts off as flag name
            if arg in paired_arguments.keys():
                # Handle paired arguments - switch to the primary option key of the argument
                allargs.append(arg)
                arg = paired_arguments[arg]
        if line.find('dest="') > 0 or line.find("dest='") > 0:
            # add_argument may take a dest= parameter, so if we see
            # one make a note about the last argument we saw
            dest[arg] = line[line.find("dest=") + 6 :]
            p2 = dest[arg].find('"')
            if p2 < 0:
                p2 = dest[arg].find("'")
            dest[arg] = dest[arg][0:p2]
        if line.find('"-d"') > 0 or line.find("'-d'") > 0:
            # special case for -d -- make it current argument
            arg = "d"
            allargs.append(arg)
            dest[arg] = arg
        if line.find('"-f"') > 0 or line.find("'-f'") > 0:
            # special case for -f -- make it current argument
            arg = "f"
            allargs.append(arg)
            dest[arg] = arg
        if line.find('action="store') > 0 or line.find("action='store") > 0:
            # if we see an action="store.. then this argument is a flag
            # and doesn't consume a value
            flagargs.add(arg)
        if line.find('action="append') > 0 or line.find("action='append") > 0:
            # if we see an action="append.. then this argument adds to a list
            listargs.add(arg)

    f.close()
    print("flagargs:", repr(flagargs))
    return allargs, flagargs, listargs, dest


@pytest.fixture
def all_test_args():
    return [
        "--append-condor-requirements",
        "xxappend-condor-requirementsxx",
        "--blocklist",
        "xxblocklistxx",
        "--cmtconfig",
        "xxcmtconfigxx",
        "--constraint",
        "--cpu",
        "xxcpuxx",
        "--dag",
        "--dataset-definition",
        "xxdataset-definitionxx",
        "--dd-percentage",
        "50",
        "--dd-extra-dataset",
        "xxdd-extra-datasetxx",
        "--debug",
        "--disk",
        "xxdiskxx",
        "-d",
        "dtag",
        "dpath",
        "--email-to",
        "xxemail-toxx",
        "--environment",
        "xxenvironmentxx",
        "--expected-lifetime",
        "xxexpected-lifetimexx",
        "-f",
        "xxfxx",
        "--generate-email-summary",
        "--global-pool",
        "dune",
        "--group",
        "xxgroupxx",
        "--job-info",
        "xxjob-infoxx",
        "--jobid",
        "--log-file",
        "xxlog-filexx",
        "--lines",
        "xxlinesxx",
        "--mail-never",
        "--mail-on-error",
        "--mail-always",
        "--maxConcurrent",
        "xxmaxConcurrentxx",
        "--memory",
        "xxmemoryxx",
        "--need-storage-modify",
        "xxneed-storage-modifyxx",
        "--need-scope",
        "xxneed-scopexx",
        "--no-env-cleanup",
        "--no-singularity",
        "--no-apptainer",
        "--no-submit",
        "--OS",
        "xxOSxx",
        "--overwrite-condor-requirements",
        "xxoverwrite-condor-requirementsxx",
        "--project-name",
        "xxproject-namexx",
        "--resource-provides",
        "xxresource-providesxx",
        "--role",
        "xxrolexx",
        "--singularity-image",
        "xxsingularity-imagexx",
        "--apptainer-image",
        "--schedd-for-testing",
        "--site",
        "xxsitexx",
        "--skip-check",
        "--subgroup",
        "xxsubgroupxx",
        "--support-email",
        "--tar-file-name",
        "xxtar-file-namexx",
        "--tarball-exclusion-file",
        "xxtarball-exclusion-filexx",
        "--timeout",
        "xxtimeoutxx",
        "--use-cvmfs-dropbox",
        "--use-pnfs-dropbox",
        "--verbose",
        "1",
        "--version",
        "--devserver",
        "--onsite",
        "--onsite-only",
        "--offsite",
        "--offsite-only",
        "file:///bin/true",
        "xx_executable_arg_0_xx",
        "xx_executable_arg_1_xx",
        "xx_executable_arg_2_xx",
        "xx_executable_arg_3_xx",
    ]


@pytest.fixture
def clear_group_from_environment():
    """This fixture clears out the group environment variable"""
    old_group = os.environ.get("GROUP", None)
    if old_group:
        del os.environ["GROUP"]
    yield
    os.environ["GROUP"] = old_group


@pytest.fixture
def skip_check_arg_parser():
    """This fixture sets up a lightweight ArgumentParser to test the --skip-check flag"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-check", type=str, default=[], action=get_parser.VerifyAndAddSkipCheck
    )
    return parser


@pytest.fixture
def get_single_valid_check_to_skip():
    """This fixture gets a valid check from the skip_checks module to set up for tests"""
    from skip_checks import SupportedSkipChecks

    valid_check: str = ""
    valid_checks = SupportedSkipChecks.get_all_checks()
    if len(valid_checks) > 0:
        valid_check = valid_checks[0]
    return valid_check


@pytest.fixture
def schedd_for_testing_arg_parser():
    """This fixture sets up a lightweight ArgumentParser to test the --schedd-for-testing flag"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schedd-for-testing", type=str, action=get_parser.CheckIfValidSchedd
    )
    return parser


class TestGetParserUnit:
    """
    Use with pytest... unit tests for ../lib/*.py
    """

    # lib/get_parser.py routines...

    @pytest.mark.unit
    def test_get_parser_small(self):
        """
        Try a few common arguments on a get_parser() generated parser
        """
        parser = get_parser.get_parser()
        line = "jobsub_submit --devserver -e SAM_EXPERIMENT -G {0} --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE file://`pwd`/lookaround.sh".format(
            TestUnit.test_group
        )
        line_argv = line.strip().split()[1:]
        res = parser.parse_args(line_argv)
        assert res.devserver
        assert "SAM_EXPERIMENT" in res.environment
        assert res.group == TestUnit.test_group

    @pytest.mark.unit
    def test_check_all_test_args(self, find_all_arguments, all_test_args):
        # make sure we have a test argument for all the arguments in
        # the source, and that we find all the arguments in the source
        # we think we should.  This way we maintain a list here in
        # the test code, but check it against the source...
        allargs, flagargs, listargs, dest = find_all_arguments
        for arg in allargs:
            if len(arg) > 1:
                arg = "--" + arg
            else:
                arg = "-" + arg

            if arg == "--dataset":
                continue

            assert arg in all_test_args

        for arg in all_test_args:
            if arg[0] == "-":
                arg = arg.lstrip("-")
                assert arg in allargs

    @pytest.mark.unit
    def test_get_parser_all(self, find_all_arguments, all_test_args):
        """
        Validate an all arguments list
        """

        allargs, flagargs, listargs, dest = find_all_arguments

        # Args to exclude from checks below.  We need to do this due to,
        # for example, mutually exclusive groups defined in the parser.
        # Currently, the testing code here tries to parse all args, which
        # works until you have a mutually exclusive group.  So the
        # variable args_exclude_list should contain all the args in a
        # mutually exclusive group, except for one
        # e.g. For the mutually exclusive group (--singularity-image,
        # --no-singularity), we pick one and enter it into args_exclude_list
        args_exclude_list = [
            "--no-singularity",
            "--apptainer-image",
            "--no-apptainer",
            "--onsite",
            "--onsite-only",
            "--offsite-only",
            "--offsite",
            "--jobid",
            "--constraint",
            "--skip-check",  # Skipping this one because we do a special test later on for this
            "--schedd-for-testing",  # Skipping this one because we do a special test later on for this
        ]

        def filter_excluded(arg_list):
            _stripped_args_exclude_list = [arg.strip("-") for arg in args_exclude_list]

            def is_arg_excluded(arg):
                return arg in args_exclude_list or arg in _stripped_args_exclude_list

            return [arg for arg in arg_list if not is_arg_excluded(arg)]

        allargs = filter_excluded(allargs)
        flagargs = filter_excluded(flagargs)
        listargs = filter_excluded(listargs)
        all_test_args = filter_excluded(all_test_args)

        print("trying command flags: ", all_test_args)

        parser = get_parser.get_parser()
        res = parser.parse_args(all_test_args)
        vres = vars(res)
        for arg in args_exclude_list:
            remove_key = arg.strip("-").replace("-", "_")
            vres.pop(remove_key, None)

        print("vres is ", vres)

        #
        # do a suitable assertion for all the arguments
        # slightly more cases here than seem obvious
        #
        for arg in allargs:
            # figure out what arg is called in the result
            # using dest table and fixing dashes
            uarg = dest[arg].replace("-", "_")

            print(f"arg '{arg}' uarg '{uarg}'")

            if arg in flagargs:
                # its a flag, just assert it
                assert vres[uarg]
            elif arg == "d":
                # -d special case -- makes list of *pairs* of args
                assert vres["d"] == [["dtag", "dpath"]]
            elif arg == "debug" or arg == "verbose":
                assert vres["verbose"] == 1
            elif arg == "dataset":
                assert vres["dataset_definition"] == "xxdataset-definitionxx"
            elif arg == "global-pool":
                assert vres["global_pool"] == "dune"
            elif arg == "dd-percentage":
                assert vres["dd_percentage"] == 50
            elif arg in listargs:
                # args are in a list, so look for list containing xxflagxx
                if arg in ["lines"]:
                    # some of our arguments start with blank in the list
                    # so a "\nprefix:".join(list) prefixes the useful items
                    assert vres[uarg] == [
                        "",
                        "xx%sxx" % arg,
                    ]
                else:
                    assert vres[uarg] == [
                        "xx%sxx" % arg,
                    ]
            else:
                # general string argument, look for xxflagxx
                assert vres[uarg] == "xx%sxx" % arg

        # also make sure we got the executable and arguments...
        assert "file:///bin/true" == vres["executable"]
        for i in range(4):
            assert "xx_executable_arg_%s_xx" % i in vres["exe_arguments"]

    @pytest.mark.unit
    def test_get_condor_epilog(self):
        """make sure we get the condor_q help epilog if we are jobsub_q"""
        sys.argv[0] = "/blah/blah/jobsub_q"
        epilog = get_parser.get_condor_epilog()
        assert epilog.find("also condor_q arguments") == 0
        assert epilog.find("-better-analyze") > 0

    @pytest.mark.unit
    def test_verify_and_add_skip_check_valid(
        self, skip_check_arg_parser, get_single_valid_check_to_skip
    ):
        """This test checks that when we pass a valid check to --skip-check,
        the attributes are set correctly in the ArgumentParser namespace
        """
        valid_check = get_single_valid_check_to_skip
        if not valid_check:
            return

        args = skip_check_arg_parser.parse_args(["--skip-check", valid_check])
        assert valid_check in args.skip_check
        assert getattr(args, f"skip_check_{valid_check}", False)

    @pytest.mark.unit
    def test_verify_and_add_skip_check_duplicate(
        self, skip_check_arg_parser, get_single_valid_check_to_skip
    ):
        """This test checks that if we pass a duplicate valid check to --skip-check,
        the ArgumentParser namespace attributes are set correctly, and we only see
        the check once in the ArgumentParser namespace"""
        valid_check = get_single_valid_check_to_skip
        if not valid_check:
            return

        args = skip_check_arg_parser.parse_args(
            ["--skip-check", valid_check, "--skip-check", valid_check]
        )
        assert valid_check in args.skip_check
        assert len(args.skip_check) == 1
        assert getattr(args, f"skip_check_{valid_check}", False)

    @pytest.mark.unit
    def test_verify_and_add_skip_check_single_invalid(self, skip_check_arg_parser):
        """This test makes sure that if we pass an invalid check to --skip-check, we
        get a TypeError"""
        with pytest.raises(TypeError, match="Invalid argument to flag --skip-check:"):
            skip_check_arg_parser.parse_args(["--skip-check", "ThisIsAFakeCheck"])

    @pytest.mark.unit
    def test_verify_and_add_skip_check_mixed_invalid(
        self, skip_check_arg_parser, get_single_valid_check_to_skip
    ):
        """This test makes sure that if we pass a mix of valid and invalid checks
        to --skip-check, we still get a TypeError"""
        valid_check = get_single_valid_check_to_skip
        if not valid_check:
            return

        with pytest.raises(TypeError, match="Invalid argument to flag --skip-check:"):
            skip_check_arg_parser.parse_args(
                ["--skip-check", valid_check, "--skip-check", "ThisIsAFakeCheck"]
            )

    @pytest.mark.unit
    def test_put_back_pool(self):
        pool.reset_pool()

    @pytest.mark.unit
    def test_schedd_for_testing_valid(
        self, clear_group_from_environment, schedd_for_testing_arg_parser
    ):
        """This test ensures that if we give a valid schedd to --schedd-for-testing,
        we are allowed to proceed"""
        schedds = get_schedd_names({})
        valid_schedd = schedds[0]

        args = schedd_for_testing_arg_parser.parse_args(
            ["--schedd-for-testing", valid_schedd]
        )
        assert args.schedd_for_testing == valid_schedd

    @pytest.mark.unit
    def test_schedd_for_testing_invalid(self, schedd_for_testing_arg_parser):
        """This test makes sure that if we give an invalid schedd to --schedd-for-testing,
        we get a TypeError"""
        with pytest.raises(TypeError, match="Invalid schedd specified"):
            schedd_for_testing_arg_parser.parse_args(
                ["--schedd-for-testing", "this_is_an_invalid_schedd.domain"]
            )
