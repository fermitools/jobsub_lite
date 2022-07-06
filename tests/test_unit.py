

class TestUnit:
    """
        strings/parameters common to unit tests
    """

    test_group = "fermilab"
    #test_group = "dune"
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
            "resource_provides": "usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE" ,
        }
    test_extra_template_args = {
            "role":              "Analysis",
            "clientdn":          "test_client_dn",
            "ipaddr":            "TEST.IP.ADDRESS",
            "user":              "test_user",
            "jobsub_version":    "jobsub_test_version" ,
            "kerberos_principal": "test@FNAL.GOV",
            "lines":             [],
            "subgroup":          "test_subgroup",
            "schedd":            "test_schedd",
            "date":              "test_date",
            "uuid":              "test_FERRY_uuid",
            "dir":               "test_dir",
            "email_to":          "test_user@fnal.gov",
            "version":           "test_version",
            "resource_provides_quoted": "usage_model=TEST",
    }

