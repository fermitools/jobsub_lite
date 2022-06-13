

class TestUnit:
    """
        strings/parameters common to unit tests
    """

    #test_group = "fermilab"
    test_group = "dune"
    test_schedd = "jobsubdevgpvm01.fnal.gov"
    test_vargs = { 
            "debug":             False,
            "executable":         "file:///bin/true",
            "exe_arguments":     [],
            "memory":            "64gb",
            "disk":              "100mb",
            "expected_lifetime": "8h",
            "timeout":           "8h",
            "devserver":         True,
            "environment":       ["USER"],
            "group":             test_group,
            "N":                 1,
            "maxConcurrent":     None,
            "resource_provides": "usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE" 
        }

