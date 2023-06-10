import os.path


def getschedd(s):
    """obfuscated way to get development schedd -- works onsite"""
    hn = os.environ["HOSTNAME"]
    dom = hn[hn.find(".") :]
    js = os.path.basename(os.path.dirname(os.path.dirname(__file__)))[:6]
    n = dom.find(".", 1) - 4
    return f"{js}{s}0{n}{dom}"


class TestUnit:
    """
    strings/parameters common to unit tests
    """

    test_group = "fermilab"
    test_role = "Analysis"
    # test_group = "dune"
    test_schedd = getschedd("devgpvm")
    test_vargs = {
        "debug": False,
        "verbose": 0,
        "executable": "file:///bin/true",
        "exe_arguments": [],
        "memory": "64gb",
        "disk": "100mb",
        "expected_lifetime": "8h",
        "timeout": "8h",
        "devserver": True,
        "environment": ["USER"],
        "group": test_group,
        "role": test_role,
        "N": 1,
        "maxConcurrent": None,
        "resource_provides": ["usage_model=OPPORTUNISTIC,DEDICATED,OFFSITE"],
        "job_scope": "storage.create:/foo storage:modify:/foo compute.create compute.modify compute.read",
        "oauth_handle": "0a1b2c3d4e5f",
        "project_name": "",
        "job_info": [],
        "generate_email_summary": False,
        "dd_percentage": 100,
        "dd_extra_dataset": [],
    }
    test_extra_template_args = {
        "role": test_role,
        "clientdn": "test_client_dn",
        "ipaddr": "TEST.IP.ADDRESS",
        "user": "test_user",
        "jobsub_version": "jobsub_test_version",
        "kerberos_principal": "test@FNAL.GOV",
        "lines": [],
        "subgroup": "test_subgroup",
        "schedd": "test_schedd",
        "date": "test_date",
        "uuid": "test_FERRY_uuid",
        "dir": "test_dir",
        "email_to": "test_user@fnal.gov",
        "version": "test_version",
        "resource_provides_quoted": "usage_model=TEST",
        "outurl": "https://www.fnal.gov",
    }
