import argparse
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tempfile
import time
from typing import List, NamedTuple, Optional

import htcondor  # type: ignore

EXPIRATION_CUTOFF_SECONDS = 3600
AGE_CUTOFF_SECONDS = 10800
CREDS_DIR = pathlib.Path("/var/lib/jobsub_lite/creds/proxies")
MYPROXY_SERVER = "myproxy-int.fnal.gov"
OWN_VOMS_INSTANCES = ["dune", "des"]  # VOs with their own VOMS instance

REQUIRED_EXECUTABLES = {
    "voms-proxy-info": "",
    "voms-proxy-init": "",
    "myproxy-logon": "",
}
DN_SPLIT_REGEXP = re.compile("(.+)/CN=\d+")
ROLE_FROM_FQAN_REGEXP = re.compile(".*\/Role\=(\w+)\/Capability\=NULL")
NOW = time.time()


# Utilities


def check_for_required_executables() -> None:
    for exe in REQUIRED_EXECUTABLES:
        exe_path = shutil.which(exe)
        if exe_path:
            REQUIRED_EXECUTABLES[exe] = exe_path
        else:
            raise OSError(
                f"Required executable {exe} was not found in $PATH.  Exiting."
            )


class JobCredentialInfo(NamedTuple):
    """Class that holds the information needed to refresh a user's X509 proxy"""

    owner: str
    group: str
    role: str
    x509userproxy: pathlib.Path
    dn: str


def get_job_classads(*classad_attributes: str) -> List[htcondor.ClassAd]:
    """Query condor schedd to get a list of classads for all idle, running, and held jobs"""
    DEFAULT_ATTRIBUTES = [
        "Owner",
        "Jobsub_Group",
        "x509userproxy",
        "JobsubClientDN",
        "x509UserProxyFirstFQAN",
    ]
    schedd = htcondor.Schedd()
    wanted_attributes = (
        classad_attributes if len(classad_attributes) != 0 else DEFAULT_ATTRIBUTES
    )
    classads = [
        classad
        for classad in schedd.query(
            constraint="JobStatus =?= 1 || JobStatus =?= 2 || JobStatus =?= 5 || JobStatus =?= 4",
            projection=wanted_attributes,
        )
    ]
    return classads


def classad_to_JobCredentialInfo(
    classad: htcondor.ClassAd,
) -> Optional[JobCredentialInfo]:
    """Convert an htcondor.ClassAd to a JobCredentialInfo object"""
    try:
        role = get_role_from_fqan(classad["x509UserProxyFirstFQAN"])
    except KeyError:
        print(
            "Could not get role from FQAN because x509UserProxyFirstFQAN is not defined in the classad"
        )
        return None

    try:
        jc = JobCredentialInfo(
            classad["Owner"],
            classad["Jobsub_Group"],
            role,
            pathlib.Path(classad["x509useproxy"]).resolve(),
            trim_dn(classad["JobsubClientDN"]),
        )
    except KeyError as e:
        print(f"Missing key to create JobCredentialInfo object: {e}")
        return None

    expected_x509userproxy_path = CREDS_DIR / jc.group / f"x509cc_{jc.owner}_{role}"
    try:
        assert jc.x509userproxy == expected_x509userproxy_path.resolve()
    except AssertionError:
        print(
            "JobCredentialInfo failed validation:  x509userproxy is set incorrectly.  "
            f"Expected {expected_x509userproxy_path}, got {jc.x509userproxy}"
        )
    return jc


def trim_dn(dn: str) -> str:
    """Split dn by looking for a CN=#### string at the end of the DN.  If we find that, trim it off and return
    the remaining part.
    e.g. "/DC=org/DC=issuer/C=US/O=Organization/OU=People/CN=User Name/CN=UID:user/CN=123456"
    should become "/DC=org/DC=issuer/C=US/O=Organization/OU=People/CN=User Name/CN=UID:user"
    """
    matches = DN_SPLIT_REGEXP.match(dn)
    if matches is not None:
        return matches.group(1)
    return dn


def get_role_from_fqan(fqan: str) -> str:
    """Parse FQAN to extract role"""
    matches = ROLE_FROM_FQAN_REGEXP.match(fqan)
    if matches is not None:
        return matches.group(1)
    return fqan


def check_proxy_timeleft(job_credential_info: JobCredentialInfo) -> int:
    """Check how many seconds a proxy has left until expiration"""
    result = subprocess.run(
        [
            REQUIRED_EXECUTABLES["voms-proxy-info"],
            "-file",
            str(job_credential_info.x509userproxy.resolve()),
            "-timeleft",
        ],
        stdout=subprocess.PIPE,
        encoding="UTF-8",
    )
    timeleft_string = result.stdout.strip()
    return int(timeleft_string)


def get_fqan_from_voms_proxy(path: pathlib.Path) -> str:
    """Extract the FQAN from a VOMS proxy"""
    result = subprocess.run(
        [
            REQUIRED_EXECUTABLES["voms-proxy-info"],
            "-file",
            str(path.resolve()),
            "-fqan",
        ],
        stdout=subprocess.PIPE,
        encoding="UTF-8",
    )
    attributes = result.stdout.split("\n")
    return attributes[0]


def get_voms_attribute(group: str, role: str) -> str:
    """Given the group and role, return the appropriate voms attribute"""
    if group in OWN_VOMS_INSTANCES:
        voms_root = f"{group}:/{group}"
    else:
        voms_root = f"fermilab:/fermilab/{group}"
    return f"{voms_root}/Role={role}"


def needs_refresh(
    job_credential_info: JobCredentialInfo,
    expiration_cutoff: int = EXPIRATION_CUTOFF_SECONDS,
    age_cutoff: int = AGE_CUTOFF_SECONDS,
) -> bool:
    """Determine if the proxy file within the job_credential_info object needs to be refreshed.
    Refresh proxy if:
        - Proxy file does not exist
        - Proxy expires before expiration cutoff
        - Proxy file is older than expiration cutoff
    """
    if not job_credential_info.x509userproxy.exists():
        return True
    if check_proxy_timeleft(job_credential_info) < expiration_cutoff:
        return True
    if NOW - job_credential_info.x509userproxy.stat().st_ctime > age_cutoff:
        return True
    return False


def refresh_proxy(job_credential_info: JobCredentialInfo) -> None:
    # First, pull down the proxy from myproxy server
    myproxy_env = os.environ.copy()
    # TODO
    myproxy_env["X509_USER_CERT"] = "TODOCHANGETHIS"
    myproxy_env["X509_USER_KEY"] = "TODOCHANGETHIS"
    with tempfile.NamedTemporaryFile() as myproxy_tempfile:
        myproxy_result = subprocess.run(
            [
                REQUIRED_EXECUTABLES["myproxy-logon"],
                "-l",
                job_credential_info.dn,
                "-s",
                MYPROXY_SERVER,
                "-t",
                "24",
                "-o",
                myproxy_tempfile.name,
            ],
            env=myproxy_env,
        )
        myproxy_result.check_returncode()
        print(
            f"Successfully retrieved proxy from myproxy, {job_credential_info.x509userproxy}"
        )

        # voms-proxy-init to add voms extensions
        voms_attribute = get_voms_attribute(
            job_credential_info.group, job_credential_info.role
        )
        with tempfile.NamedTemporaryFile() as voms_proxy_tempfile:
            voms_proxy_init_result = subprocess.run(
                [
                    REQUIRED_EXECUTABLES["voms-proxy-init"],
                    "-noregen",
                    "-rfc",
                    "-ignorewarn",
                    "-valid",
                    "168:0",
                    "-bits",
                    "1024",
                    "-voms",
                    voms_attribute,
                    "-out",
                    voms_proxy_tempfile.name,
                    "-cert",
                    myproxy_tempfile.name,
                    "-key",
                    myproxy_tempfile.name,
                ]
            )
            voms_proxy_init_result.check_returncode()
            proxy_fqan = get_fqan_from_voms_proxy(
                pathlib.Path(voms_proxy_tempfile.name)
            )
            check_role = get_role_from_fqan(proxy_fqan)
            try:
                assert job_credential_info.role == check_role
            except AssertionError:
                print(
                    f"Verification of refreshed proxy failed:  Roles do not match.  Expected {job_credential_info.role}, got {check_role}"
                )
                raise

            shutil.copy(voms_proxy_tempfile, job_credential_info.x509userproxy)

    # chmod proxy files to 600, chown to job owner, fnalgrid group
    job_credential_info.x509userproxy.chmod(stat.S_IRUSR | stat.S_IWUSR)
    shutil.chown(
        job_credential_info.x509userproxy, job_credential_info.owner, "fnalgrid"
    )
    print(f"Refreshed proxy at f{job_credential_info.x509userproxy}")


def main() -> None:
    """
    Note - TO BE DELETED AT FINAL COMMIT:
        Ask rexbatch to be put into condor group so we can write into /var/lib/condor/oauth_credentials
        - To test, write in any file called userproxy_test.use, see if that gets forwarded
        - Then, if that does work, we have this script do that

    Order of operations:

    0.  Jobs submitted with x509useproxy set to /var/lib/creds/proxies/<Jobsub_Group>/<Owner>,
    cigetcert run with options from config to allow jobsubdev/jobsub01 to retrieve jobs.  Might have to store creds locally too

    Submit job with x509userproxy set as the /var/lib/whatever location, hope that it works

    Verify:
    Submit job that runs for 12 hours.  Have it run voms-proxy-info on credential file to make sure it's refreshed, ls -l on the file to make sure it's actually new

    """
    check_for_required_executables()

    # Collect args
    parser = argparse.ArgumentParser(
        description="Refresh all proxies in use by running, idle, and held jobs"
    )
    parser.add_argument(
        "-e",
        "--expiration-cutoff",
        help="Refresh proxies that will expire before this cutoff duration (in seconds)",
        default=EXPIRATION_CUTOFF_SECONDS,
    )
    parser.add_argument(
        "-a",
        "--age-cutoff",
        help="Refresh proxies that live in files older than this cutoff (in seconds)",
        default=AGE_CUTOFF_SECONDS,
    )
    args = parser.parse_args()

    # Get list of all running and idle, and held jobs, store into JobCredentialInfo namedtuples
    classads = get_job_classads()
    _job_credential_infos = [
        classad_to_JobCredentialInfo(classad) for classad in classads
    ]
    job_credential_infos = [jc for jc in _job_credential_infos if jc is not None]

    # Check to see which proxies need to be renewed, and renew them
    for jc in job_credential_infos:
        if needs_refresh(jc, args.expiration_cutoff, args.age_cutoff):
            try:
                refresh_proxy(jc)  # TODO
            except Exception as e:
                print(
                    f"Proxy refresh failed for {jc.x509userproxy}.  Continuing to the next proxy"
                )
        else:
            print(
                f"Reviewed proxy at f{jc.x509userproxy}.  Does not need to be renewed"
            )


if __name__ == "__main__":
    main()
