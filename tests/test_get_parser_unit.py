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
#
sys.path.append("../lib")
import get_parser

from test_unit import TestUnit


@pytest.fixture
def find_all_arguments():
    # try to extract all the --foo arguments from the source
    # and track which ones are flags
    # we assume
    # * there are mostly calls to add_argument in the source file
    # * the add_argument lines may span multiple lines, but
    # * we don't have more than one add_argument call per line
    # so we look for various parts of the add_argument calls
    # separately on each line
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
            if arg.find("_") == -1:
                allargs.append(arg)
                dest[arg] = arg  # destination starts off as flag name
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
        "--blacklist",
        "xxblacklistxx",
        "--cmtconfig",
        "xxcmtconfigxx",
        "--cpu",
        "xxcpuxx",
        "--dag",
        "xxdagxx",
        "--dataset-definition",
        "xxdataset-definitionxx",
        "--debug",
        "1",
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
        "--group",
        "xxgroupxx",
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
        "--no-singularity",
        "--no-submit",
        "--OS",
        "xxOSxx",
        "--overwrite-condor-requirements",
        "xxoverwrite-condor-requirementsxx",
        "--resource-provides",
        "xxresource-providesxx",
        "--role",
        "xxrolexx",
        "--singularity-image",
        "xxsingularity-imagexx",
        "--site",
        "xxsitexx",
        "--subgroup",
        "xxsubgroupxx",
        "--tar-file-name",
        "xxtar-file-namexx",
        "--tarball-exclusion-file",
        "xxtarball-exclusion-filexx",
        "--timeout",
        "xxtimeoutxx",
        "--use-cvmfs-dropbox",
        "--use-pnfs-dropbox",
        "--verbose",
        "--devserver",
        "file:///bin/true",
        "xx_executable_arg_0_xx",
        "xx_executable_arg_1_xx",
        "xx_executable_arg_2_xx",
        "xx_executable_arg_3_xx",
    ]


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
        args_exclude_list = ["--no-singularity"]

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

            if arg in flagargs:
                # its a flag, just assert it
                assert vres[uarg]
            elif arg == "d":
                # -d special case -- makes list of *pairs* of args
                assert vres["d"] == [["dtag", "dpath"]]
            elif arg == "debug":
                assert vres["debug"] == 1
            elif arg == "dataset":
                assert vres["dataset_definition"] == "xxdataset-definitionxx"
            elif arg in listargs:
                # args are in a list, so look for list containing xxflagxx
                if arg in ["resource-provides", "lines"]:
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
