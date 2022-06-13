import os
import sys
import time

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
        res = parser.parse_args(line.strip().split()[1:])
        assert res.devserver
        assert 'SAM_EXPERIMENT' in res.environment
        assert res.group == TestUnit.test_group

    def test_get_parser_all(self):
        """
            Try to find *all* the arguments in the get_parser code, 
            make an argument list with them all and see if we get
            values back in the parsed arguments.
            Arguably this should have such a list and validate it
            rather than always generate it, so the test doesn't
            just always work...
       """
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
        filledargs = []
        for arg in allargs:
            if arg in flagargs:
                filledargs.append("--%s" % arg)
            elif arg == "f":
                filledargs.append("-f")
                filledargs.append("xxfxx")
            elif arg == "d":
                filledargs.append("-d")
                filledargs.append("dtag")
                filledargs.append("dpath")
            else:
                filledargs.append("--%s=xx%sxx" % (arg, arg))

        filledargs.append("file://bin/true")

        print("trying command flags: ", filledargs)
        
        parser = get_parser.get_parser()
        res = parser.parse_args(filledargs)
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

