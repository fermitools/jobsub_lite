import sys
sys.path.append("../lib")

import condor
class TestCondor:
    test_schedd = "jobsubtestgpvm01.fnal.gov"
    test_vargs = { 
            "devserver":          True,
            "environment":       "SAM_EXPERIMENT",
            "group":             "fermilab",
            "resource-provides": "usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE" 
        }

    def get_submit_file():
        filename="/tmp/tst{0}.sub".format(os.getpid())
        f = open(filename, "w")
        f.write("""
        """)
        f.close()
        return filename

    def get_dag_file():
        filename="/tmp/tst{0}.dag".format(os.getpid())
        f = open(filename, "w")
        f.write("""
        """)
        f.close()
        return filename

    def test_get_schedd_1(self):
        schedd =  condor.get_schedd(TestCondor.test_vargs)
        assert schedd == TestCondor.test_schedd

    def test_load_submit_file_1(self):
        res = condor.load_submit_file(TestCondor.get_submit_file())

    def test_submit_1(self):
        res = condor.submit(get_submit_file(), TestCondor.test_vargs, TestCondor.test_schedd )

    def test_submit_dag_1(self):
        res = condor.submit_dag(get_dag_file, vargs, schedd_name, cmd_args=[])

