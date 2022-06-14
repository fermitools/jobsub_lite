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
import get_parser

from test_unit import TestUnit 

@pytest.fixture
def find_all_arguments():
    # try to extract all the --foo arguments from the source
    # and track which ones are flags
    f = open("../lib/get_parser.py","r")
    flagargs = set()
    listargs = set()
    allargs = []
    dest = {}
    for line in f.readlines():
        p = line.find('"--')
        if p > 0:
            arg = line[p+3:]
            arg = arg[0:arg.find('"')]
            allargs.append(arg)
            dest[arg] = arg
        if line.find('dest="') > 0:
            dest[arg] = line[line.find('dest="')+6:]
            dest[arg] = dest[arg][0:dest[arg].find('"')]
        if line.find('"-d"') > 0:
            arg = "d"
            allargs.append(arg)
            dest[arg] = arg
        if line.find('"-f"') > 0:
            arg = "f"
            allargs.append(arg)
            dest[arg] = arg
        if line.find('action="store') > 0:
            flagargs.add(arg)
        if line.find('action="append') > 0:
            listargs.add(arg)

    f.close()
    # now make a filled argument list
    return allargs, flagargs, listargs, dest 

@pytest.fixture
def all_test_args():
    return [
         '--append_condor_requirements', 'xxappend_condor_requirementsxx',
         '--blacklist', 'xxblacklistxx',
         '--cmtconfig', 'xxcmtconfigxx',
         '--cpu', 'xxcpuxx',
         '--dag', 'xxdagxx',
         '--dataset_definition', 'xxdataset_definitionxx',
         '--debug', 'xxdebugxx',
         '--disk', 'xxdiskxx',
         '-d', 'dtag', 'dpath',
         '--email-to', 'xxemail-toxx',
         '--environment', 'xxenvironmentxx',
         '--expected-lifetime', 'xxexpected-lifetimexx',
         '-f', 'xxfxx',
         '--generate-email-summary',
         '--group', 'xxgroupxx',
         '--log_file', 'xxlog_filexx',
         '--lines', 'xxlinesxx',
         '--mail_never',
         '--mail_on_error',
         '--mail_always',
         '--maxConcurrent', 'xxmaxConcurrentxx',
         '--memory', 'xxmemoryxx',
         '--no_submit',
         '--OS', 'xxOSxx',
         '--overwrite_condor_requirements', 'xxoverwrite_condor_requirementsxx',
         '--resource-provides', 'xxresource-providesxx',
         '--role', 'xxrolexx',
         '--site', 'xxsitexx',
         '--subgroup', 'xxsubgroupxx',
         '--tar_file_name', 'xxtar_file_namexx',
         '--tarball-exclusion-file', 'xxtarball-exclusion-filexx',
         '--timeout', 'xxtimeoutxx',
         '--use-cvmfs-dropbox',
         '--use-pnfs-dropbox',
         '--verbose',
         '--devserver',
         'file:///bin/true',
         'xx_executable_arg_0_xx',
         'xx_executable_arg_1_xx',
         'xx_executable_arg_2_xx',
         'xx_executable_arg_3_xx',
    ]

class TestGetParserUnit:
    """
        Use with pytest... unit tests for ../lib/*.py
    """


    # lib/get_parser.py routines...

    def test_get_parser_small(self):
        """
            Try a few common arguments on a get_parser() generated parser
        """
        parser = get_parser.get_parser()
        line = "jobsub_submit --devserver -e SAM_EXPERIMENT -G {0} --resource-provides=usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE file://`pwd`/lookaround.sh".format(TestUnit.test_group)
        line_argv = line.strip().split()[1:]
        res = parser.parse_args(line_argv)
        assert res.devserver
        assert 'SAM_EXPERIMENT' in res.environment
        assert res.group == TestUnit.test_group


    def test_check_all_test_args(self,find_all_arguments, all_test_args):
        # make sure we have a test argument for all the arguments in 
        # the source, and that we find all the arguments in the source
        # we think we should
        allargs, flagargs, listargs, dest = find_all_arguments
        for arg in allargs:
            if len(arg) > 1:
               arg = "--"+arg
            else:
               arg = "-"+arg
            assert arg in all_test_args 
        for arg in all_test_args:
            if arg[0] == "-":
                arg = arg.lstrip("-")
                assert arg in allargs

    def test_get_parser_all(self,find_all_arguments, all_test_args):
        """
            Make an argument list 
        """

        allargs, flagargs, listargs, dest = find_all_arguments

        print("trying command flags: ", all_test_args)
        
        parser = get_parser.get_parser()
        res = parser.parse_args(all_test_args)
        vres = vars(res)  
        print("vres is ", vres)

        for arg in allargs:
            uarg = dest[arg].replace('-','_')
            if arg in flagargs:
                assert vres[uarg]
            elif arg == "d":
                assert vres['d'] == [['dtag','dpath']]
            elif arg == "f":
                assert vres['input_file'] == ['xxfxx']
            elif arg in listargs:
                if arg in ['resource-provides', 'lines']:
                    assert vres[uarg] == ['', "xx%sxx" % arg,]
                else:
                    assert vres[uarg] == ["xx%sxx" % arg,]
            else:
                assert vres[uarg] == "xx%sxx" % arg

        # also make sure we got the executable and arguments...

        assert 'file:///bin/true' == vres['executable']
        for i in range(4):
            assert 'xx_executable_arg_%s_xx' % i in vres['exe_arguments']
