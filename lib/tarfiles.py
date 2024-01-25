#
# COPYRIGHT 2021 FERMI NATIONAL ACCELERATOR LABORATORY
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=fixme
""" tarfile upload related code """
import argparse
import hashlib
import http.client
import itertools
import os
import os.path
import random
import re
import sys
import tarfile as tarfile_mod
import time
import traceback as tb
from typing import Dict, Callable, List, Any, Iterator, Optional
from urllib.parse import quote as _quote


import requests  # type: ignore # pylint: disable=import-error
from requests.auth import AuthBase  # type: ignore # pylint: disable=import-error

import fake_ifdh
from creds import get_creds, CredentialSet
from tracing import as_span, add_event
import utils

try:
    _NUM_RETRIES_ENV = os.getenv("JOBSUB_UPLOAD_NUM_RETRIES", "20")
    NUM_RETRIES = int(_NUM_RETRIES_ENV)
    _RETRY_INTERVAL_SEC_ENV = os.getenv("JOBSUB_UPLOAD_RETRY_INTERVAL_SEC", "30")
    RETRY_INTERVAL_SEC = int(_RETRY_INTERVAL_SEC_ENV)
except ValueError:
    print(
        "Retry variables JOBSUB_UPLOAD_NUM_RETRIES and "
        "JOBSUB_UPLOAD_RETRY_INTERVAL_SEC must be either unset or integers"
    )
    raise

RCDS_MAX_FILE_SIZE = 1073741824


class TokenAuth(AuthBase):  # type: ignore
    # auth class for token authentication
    # see https://requests.readthedocs.io/en/latest/user/advanced/
    # under Custom Authentication / PizzaAuth
    def __init__(self, token: str) -> None:
        self.token = token
        with open(self.token, "r", encoding="UTF-8") as f:
            self.token_string = f.read()
        self.token_string = self.token_string.strip()  # Drop \n at end of token_string

    # pylint: disable=invalid-name
    def __call__(self, r: requests.Request) -> requests.Request:
        r.headers["Authorization"] = f"Bearer {self.token_string}"
        return r


def check_we_can_write() -> None:
    if not os.access(".", os.W_OK):
        print(
            "jobsub_lite needs to create the tarball, or copy of the tarball you are attempting to upload"
            " in the current working directory, \nbut this directory is read-only."
        )
        sys.exit(1)


def tarchmod(tfn: str) -> str:
    """
    copy a tarfile to a compressed tarfile, while:
    * changing modes of contents to 755
    * bailing if tarfile has files too large for RCDS
    """
    ofn = os.path.basename(f"{tfn}{os.getpid()}.tbz2")
    check_we_can_write()

    # also make sure there is enough space...
    statinfo = os.stat(tfn)
    if statinfo:
        need_blocks = int(statinfo.st_size / 1024) + 1
        if not utils.check_space(".", need_blocks):
            raise RuntimeError(
                f"Not enough disk space / quota in current directory to rewrite {tfn}."
            )
    else:
        raise RuntimeError(f"Cannot stat() tarfile {tfn}, does it exist?")

    try:
        with tarfile_mod.open(tfn, "r|*") as fin, tarfile_mod.open(
            ofn, "w|bz2"
        ) as fout:
            ti = fin.next()
            while ti:
                if ti.type in (tarfile_mod.SYMTYPE, tarfile_mod.LNKTYPE):
                    # dont mess with symlinks, and cannot extract them
                    st = None
                else:
                    st = fin.extractfile(ti)
                ti.mode = ti.mode | 0o755
                if ti.size > RCDS_MAX_FILE_SIZE:
                    raise ValueError(
                        f"file '{ti.name}' in your tarfile {tfn}\n"
                        f"  size {ti.size/1024}k is over RCDS 1G limit\n"
                    )
                fout.addfile(ti, st)
                ti = fin.next()
    except tarfile_mod.TarError:
        if not tarfile_mod.is_tarfile(tfn):
            print(
                f"ERROR: Argument to --tar-file-name {tfn} must be a tarfile.  If you would like to upload a file that is not a tarfile, "
                "please use the -f option.\n"
            )
        raise
    return ofn


@as_span("tar_up", arg_attrs=["*"])
def tar_up(directory: str, excludes: str, file: str = ".") -> str:
    """build directory.tar from path/to/directory"""
    if not directory:
        directory = "."

    if file != ".":
        # the --mtime reduces repeated uploads to rcds for the same file
        # with different dates
        mtime = "--mtime='1970-01-01 00:00:01'"
    else:
        mtime = ""

    tarfile = os.path.basename(f"{directory}{os.getpid()}.tgz")
    check_we_can_write()

    # check for space for tarfile
    with os.popen(f"du -sk {directory}/{file}", "r") as fdu:
        s = fdu.read()
        m = re.match(r"(\d+)", s)
        if m:
            blocks = int(m.group(1))
        else:
            blocks = 1
    if not utils.check_space(
        ".", int(blocks / 2) + 1
    ):  # assuming gzip gets 50% compression...
        raise RuntimeError(
            f"Not enough disk space / quota in current directory to create tarfile of {directory}/{file}."
        )

    if not excludes:
        excludes = os.path.dirname(__file__) + "/../etc/excludes"
    excludes = f"--exclude-from {excludes} --exclude {tarfile}"
    # note: the TZ=UTC stops tar from whining about the date format
    # if we are doing the --mtime flag, above...
    os.system(
        f"TZ=UTC GZIP=-n tar czvf {tarfile} {excludes} {mtime} --directory {directory} {file}"
    )
    return tarfile


@as_span("checksum_file", arg_attrs=["*"], return_attr=False)
def checksum_file(fname: str) -> str:
    """pull in a tarfile while computing its hash"""
    h = hashlib.sha256()
    with open(fname, "rb") as f:
        tff = f.read(4096)
        h.update(tff)
        while tff:
            tff = f.read(4096)
            h.update(tff)
    add_event("computed digest", {"digest": h.hexdigest()})
    return h.hexdigest()


@as_span("dcache_persistent_path", arg_attrs=["*"])
def dcache_persistent_path(exp: str, filename: str) -> str:
    """pick the reslient dcache path for a tarfile"""
    bf = os.path.basename(filename)

    with os.popen(f"sha256sum {filename}", "r") as f:
        sha256_hash = f.read().strip().split(" ")[0]

    # gm2 has upper cased the experiment name in DCache for some reason...
    if exp == "gm2":
        exp = "GM2"

    res = f"/pnfs/{exp}/resilient/jobsub_stage/{sha256_hash}/{bf}"

    # for testing, we don't have a resilient area for "fermilab", so...
    if exp == "fermilab":
        user = os.environ["USER"]
        res = res.replace("fermilab/resilient", f"fermilab/users/{user}", 1)

    sys.stdout.flush()
    return res


# TODO:  I've disabled too-many-statements, but it's a good indicator that this could be
# cleaned up in the future
# pylint: disable=too-many-statements
@as_span("do_tarballs", arg_attrs=["*"])
def do_tarballs(args: argparse.Namespace) -> None:
    """handle tarfile argument;  we could have:
       a directory with tardir: or tardir:// prefix to tar up and upload
       a tarfile with dropbox: or drobpox:// prefix to upload
       a plain path to just use
    we convert the argument to the next type as we go...
    """
    # pylint: disable=too-many-nested-blocks,too-many-branches
    clean_up: List[str] = []
    res: List[str] = []
    path: Optional[str] = None

    args.orig_input_file = args.input_file.copy()
    args.orig_tar_file_name = args.tar_file_name.copy()

    pnfs_classad_line: List[str] = []

    try:
        for fn in args.input_file:
            if fn.startswith("dropbox:"):
                if fn.startswith("dropbox://"):
                    fn = fn.replace("//", "", 1)

                pfn = fn.replace("dropbox:", "", 1)

                # backwards incompatability warning
                if tarfile_mod.is_tarfile(pfn):
                    sys.stderr.write(
                        "Notice: with jobsub_lite, -f dropbox:... "
                        "does not unpack tarfiles, use --tar_file_name instead\n"
                    )

                if args.use_dropbox == "cvmfs" or args.use_dropbox is None:
                    # make sure they'll be able to read it, etc.
                    savemode = os.stat(pfn).st_mode
                    try:
                        os.chmod(pfn, 0o755)
                    except OSError:
                        pass
                    tarfile = tar_up(
                        os.path.dirname(pfn), "/dev/null", os.path.basename(pfn)
                    )
                    try:
                        os.chmod(pfn, savemode)
                    except OSError:
                        pass
                    clean_up.append(tarfile)
                    path = tarfile_in_dropbox(args, tarfile)
                    if path:
                        res.append(os.path.join(path, os.path.basename(pfn)))
                    else:
                        res.append(pfn)

                elif args.use_dropbox == "pnfs":
                    location = dcache_persistent_path(args.group, pfn)
                    existing = fake_ifdh.ls(location)
                    if existing:
                        print(f"file {pfn} already copied to resilient area")
                    else:
                        fake_ifdh.mkdir_p(os.path.dirname(location))
                        fake_ifdh.chmod(os.path.dirname(location), 0o775)
                        fake_ifdh.cp(pfn, location)
                        fake_ifdh.chmod(location, 0o775)
                        existing = fake_ifdh.ls(location)
                        if not existing:
                            raise PermissionError(f"Error: Unable to create {location}")
                    res.append(location)
                    pnfs_classad_line.append(location)
                else:
                    res.append(pfn)
            else:
                res.append(fn)

        args.input_file = res

        res = []
        orig_basenames = []
        for tfn in args.tar_file_name:
            orig_basenames.append(
                os.path.basename(tfn)
                .replace(".tbz2", "")
                .replace(".tar", "")
                .replace(".tgz", "")
            )

            if tfn.startswith("tardir://"):
                tfn = tfn.replace("//", "", 1)

            if tfn.startswith("tardir:"):
                # tar it up, pretend they gave us dropbox:
                tarfile = tar_up(tfn[7:], args.tarball_exclusion_file)
                tfn = f"dropbox:{tarfile}"
                clean_up.append(tarfile)

            if tfn.startswith("dropbox:"):
                # move it to dropbox area, pretend they gave us plain path
                if tfn.startswith("dropbox://"):
                    tfn = tfn.replace("//", "", 1)
                path = tarfile_in_dropbox(args, tfn[8:])
                if path:
                    tfn = path
                else:
                    tfn = tfn.replace("dropbox:", "", 1)

                if args.use_dropbox == "pnfs":
                    pnfs_classad_line.append(tfn)

            res.append(tfn)
        args.tar_file_name = res
        args.tar_file_orig_basenames = orig_basenames
    finally:
        # clean up any tarfiles we made...
        for tarfile in clean_up:
            try:
                os.unlink(tarfile)
            except:  # pylint: disable=bare-except
                print(f"Notice: unable to remove generated tarfile {tarfile}")

    if pnfs_classad_line:
        args.lines.append(f'+PNFS_INPUT_FILES="{",".join(pnfs_classad_line)}"')


# TODO:  I've disabled too-many-statements and too-many-branches, but it's a good indicator that this could be
# cleaned up in the future
# pylint: disable=too-many-statements,too-many-branches
def tarfile_in_dropbox(args: argparse.Namespace, origtfn: str) -> Optional[str]:
    """
    upload a tarfile to the dropbox, return its path there
    """

    if args.verbose > 3:
        # if we're *really* debugging, dump the http connections...
        http.client.HTTPConnection.debuglevel = 5

    # redo tarfile to have contents with world read perms before publishing
    tfn = tarchmod(origtfn)

    location: Optional[str] = ""
    if args.use_dropbox == "cvmfs" or args.use_dropbox is None:
        digest = checksum_file(tfn)
        cred_set = get_creds(vars(args))

        if not args.group:
            raise ValueError("No --group specified!")

        # cid looks something like dune/bf6a15b4238b72f82...(long hash)
        cid = f"{args.group}/{digest}"

        publisher = TarfilePublisherHandler(
            cid=cid, cred_set=cred_set, fixed_server=True, verbose=args.verbose
        )
        location = publisher.cid_exists()
        if location is None:
            if args.verbose:
                print(f"\n\nUsing RCDS to publish tarball\ncid: {cid}")
            publisher.publish(tfn)
            publisher.activate_server_switcher()
            if not getattr(args, "skip_check_rcds", False):
                msg = "Checking to see if uploaded file is published on RCDS"
                if args.verbose:
                    msg = msg + f" for CID {cid}"
                print(msg)

                # pylint: disable-next=unused-variable
                for i in range(NUM_RETRIES):
                    location = publisher.cid_exists()
                    if location is not None:
                        print("Found uploaded file on RCDS.")
                        break
                    if i < (NUM_RETRIES - 1):
                        _retry_interval_sec = 0 if i == 0 else RETRY_INTERVAL_SEC
                        print(
                            f"Could not locate uploaded file on RCDS.  Will retry in {_retry_interval_sec} seconds."
                        )
                        time.sleep(_retry_interval_sec)
                else:
                    print(
                        f"Max retries {NUM_RETRIES} to find RCDS tarball at {cid} exceeded.  Exiting now."
                    )
                    sys.exit(1)
            else:
                # Here, we don't wait for publish to happen, so we don't know the exact location of the tarball.
                # We instead set the location to a glob that the wrapper has to handle later
                if args.verbose:
                    print("Requested to publish uploaded file on RCDS.")
                    if args.verbose > 1:
                        print(
                            "skip_check_rcds is set to True, so will not wait on confirmation of publish to proceed"
                        )
                    print("\n")
                location = publisher.get_glob_path_for_cid()
        else:
            if args.verbose:
                print("Found uploaded file on RCDS.")
            # tag it so it stays around
            publisher.update_cid()

    elif args.use_dropbox == "pnfs":
        cred_set = get_creds(vars(args))
        location = dcache_persistent_path(args.group, tfn)
        existing = fake_ifdh.ls(location)
        if existing:
            print(f"file {tfn} already copied to resilient area")
        else:
            fake_ifdh.mkdir_p(os.path.dirname(location))
            fake_ifdh.chmod(os.path.dirname(location), 0o775)
            fake_ifdh.cp(tfn, location)
            fake_ifdh.chmod(location, 0o775)
            existing = fake_ifdh.ls(location)
            if not existing:
                raise PermissionError(f"Error: Unable to create {location}")
    else:
        raise (
            NotImplementedError(f"unknown tar distribution method: {args.use_dropbox}")
        )
    os.unlink(tfn)
    return location


# pylint: disable=too-many-instance-attributes
class TarfilePublisherHandler:
    """Handler to publish tarballs via HTTP to RCDS (or future dropbox server).  By default, TarfilePublisherHandler will
    cycle between different RCDS servers to run operations.  Disable this by setting fixed_server=True

    Args:
        object (_type_): _description_
        cid (str): unique group/hash combination that RCDS uses to locate tarballs
        cred_set (CredentialSet): Paths to various supported credentials to authenticate to RCDS
        fixed_server (bool): Determines whether TarfilePublisherHandler should cycle between RCDS
            servers or use a fixed server.  Defaults to False.
        verbose (int): Verbosity level
    """

    dropbox_server_string = os.getenv("JOBSUB_DROPBOX_SERVER_LIST", "")
    check_tarball_present_re = re.compile(
        "^PRESENT:(.+)$"
    )  # RCDS returns this if a tarball represented by cid is present

    def __init__(
        self,
        cid: str,
        cred_set: CredentialSet,
        fixed_server: bool = False,
        verbose: int = 0,
    ):
        self.cid = cid
        self.cid_url = _quote(cid, safe="")  # Encode CID for passing to URL
        self.verbose = verbose
        self.__auth_kwargs: Dict[str, Any]
        print(f"Publishing hash {cid} to RCDS:")
        if cred_set.token is not None:
            print(
                f"Using bearer token located at {cred_set.token} to authenticate to RCDS"
            )
            self.__auth_kwargs = {"auth": TokenAuth(cred_set.token)}
        elif cred_set.proxy is not None:
            print(
                f"Using X509 proxy located at {cred_set.proxy} to authenticate to RCDS"
            )
            self.__auth_kwargs = {"cert": (cred_set.proxy, cred_set.proxy)}
        else:
            raise ValueError("No proxy or token provided to authenticate to RCDS.")

        self.pubapi_base_url_formatter_full = f"https://{{dropbox_server}}/pubapi/{{endpoint}}"  # pylint: disable=f-string-without-interpolation
        self.pubapi_base_url_formatter = self.pubapi_base_url_formatter_full
        self.pubapi_cid_url_formatter = (
            self.pubapi_base_url_formatter + f"?cid={self.cid_url}"
        )
        self._fixed_server = fixed_server
        self._dropbox_server_selector = (
            self.__setup_dropbox_server_selector()
            if not self._fixed_server
            else self.__setup_fixed_dropbox_server()
        )
        self.__last_server = next(self._dropbox_server_selector)

    # pylint: disable-next=no-self-argument
    def pubapi_operation(always_switch_servers: bool = False) -> Callable:  # type: ignore
        # pylint: disable-next=no-self-argument
        def _pubapi_operation(func: Callable) -> Callable:  # type: ignore
            """Wrap various PubAPI operations, setting dropbox server and handling retries"""

            class SafeDict(dict):  # type: ignore
                """Use this object to allow us to not need all keys of dict when
                running str.format_map method to do string interpolation.
                Taken from https://stackoverflow.com/a/17215533"""

                def __missing__(self, key: str) -> str:
                    """missing item handler"""
                    return f"{{{key}}}"  # "{<key>}"

            def wrapper(self, *args: Any, **kwargs: Any) -> requests.Response:  # type: ignore
                """wrapper function for decorator"""

                # After this request, restore the appropriate fixed_server behavior
                # pylint: disable=protected-access
                # Logic here:
                # 1. If self._fixed_server and always_switch_servers, we want to switch servers for only this request, and we should restore the behavior afterwards
                # 2. If not self._fixed_server and always_switch_servers, everything is already set correctly.  Do nothing, restore nothing.
                # 3. If self._fixed_server and not always_switch_servers, everything else already set correctly.  Do nothing, restore nothing.
                # 4. If not self._fixed_server and not always_switch_servers, then we respect the self._fixed_server setting, and do nothing and restore nothing.
                should_change_selector_behavior = (
                    self._fixed_server and always_switch_servers
                )

                # Default value for restore_func.  In reality we won't use this value at all if should_change_selector_behavior is False
                restore_func: Callable[
                    ..., Iterator[str]
                ] = lambda: self._dropbox_server_selector  # type: ignore

                if should_change_selector_behavior:
                    restore_func = (
                        self.__restore_fixed_server_behavior_func()
                    )  # Evaluate this now so that when we restore the dropbox_server_selector, the resultant iterator is giving us the correct server
                    if self.verbose:
                        print(
                            "TarfilePublisherHandler is configured to use a fixed RCDS server, however this is being overridden "
                            "for the duration of the current request."
                        )

                _retry_interval_sec = 0  # First retry immediately, and then we can wait the retry interval
                # pylint: disable-next=protected-access
                retry_count = itertools.count(1)

                while True:
                    try:
                        # pylint: disable=protected-access
                        _dropbox_server = next(self._dropbox_server_selector)

                        # If we're supposed to be switching servers, make sure we are actually switching servers
                        if (
                            len(self.dropbox_server_string.split()) > 1
                            and not self._fixed_server
                            and _dropbox_server == self.__last_server
                        ):
                            _dropbox_server = next(self._dropbox_server_selector)

                        self.__last_server = _dropbox_server

                        if self.verbose > 0:
                            print(f"Using PubAPI server {_dropbox_server}")
                        self.pubapi_base_url_formatter = (
                            self.pubapi_base_url_formatter_full.format_map(
                                SafeDict(dropbox_server=_dropbox_server)
                            )
                        )
                        self.pubapi_cid_url_formatter = (
                            self.pubapi_base_url_formatter + f"?cid={self.cid_url}"
                        )
                        # pylint: disable-next=not-callable
                        response = func(self, *args, **kwargs)
                        response.raise_for_status()
                    except:  # pylint: disable=bare-except
                        # Note:  This retry loop is in case the request itself fails.  Not
                        # if we couldn't find the tarball!
                        tb.print_exc()
                        next_retry_count = next(retry_count)
                        if next_retry_count == NUM_RETRIES:
                            print(f"Max retries {NUM_RETRIES} exceeded.  Exiting now.")
                            raise

                        # If always_switch_servers is True, we should override the fixed_server setting for the duration of this request
                        if next_retry_count == 1 and should_change_selector_behavior:
                            self.activate_server_switcher()

                        print(f"Will retry in {_retry_interval_sec} seconds")
                        time.sleep(_retry_interval_sec)
                        _retry_interval_sec = RETRY_INTERVAL_SEC
                    else:
                        if should_change_selector_behavior:
                            if self.verbose:
                                print(
                                    "Restoring fixed server behavior of TarfilePublisherHandler"
                                )
                            self._dropbox_server_selector = restore_func()
                        break
                return response

            return wrapper

        return _pubapi_operation

    # pylint: disable-next=no-self-argument
    def cid_operation(func: Callable) -> Callable:  # type: ignore
        """Decorator to call PubAPI operations, and return location of tarball
        locations if known"""

        def wrapper(self, *args: Any, **kwargs: Any) -> Optional[str]:  # type: ignore
            response = func(self, *args, **kwargs)  # pylint: disable=not-callable
            _match = self.check_tarball_present_re.match(response.text)
            if _match is not None:
                return str(_match.group(1))
            return None

        return wrapper

    @cid_operation
    @pubapi_operation()
    def update_cid(self) -> requests.Response:
        """Make PubAPI update call to update the last-accessed timestamp on
        this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_cid_url_formatter.format(endpoint="update")
        if self.verbose:
            print(f"Calling URL {url}")
        return requests.get(url, **self.__auth_kwargs)

    # pylint: disable=redundant-keyword-arg
    @cid_operation
    @as_span("publish", arg_attrs=["*"])
    @pubapi_operation(always_switch_servers=True)
    def publish(self, tarfilename: str) -> requests.Response:
        """Make PubAPI publish call to upload this tarfile.  In the case of failure, if there are multiple
        dropbox servers, we will always retry with a different server

        Args:
            tarfilename: filename to open for tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_cid_url_formatter.format(endpoint="publish")
        if self.verbose:
            print(f"Calling URL {url}")

        with open(tarfilename, "rb") as tarfile:
            return requests.post(url, data=tarfile, **self.__auth_kwargs)

    @cid_operation
    @as_span("cid_exists")
    @pubapi_operation()
    def cid_exists(self) -> requests.Response:
        """Make PubAPI update call to check if we already have this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_cid_url_formatter.format(endpoint="exists")
        if self.verbose:
            print(f"Calling URL {url}")
        return requests.get(url, **self.__auth_kwargs)

    def get_glob_path_for_cid(self) -> Optional[str]:
        """Return a glob path where a tarball given by self.cid can be found"""
        DEFAULT_REPOS: str = "fifeuser1.opensciencegrid.org,fifeuser2.opensciencegrid.org,fifeuser3.opensciencegrid.org,fifeuser4.opensciencegrid.org"
        response = self._get_configured_pubapi_repos()
        _match = re.match("repos:(.+)", response.text)
        repos = _match.group(1) if _match is not None else DEFAULT_REPOS
        return f"/cvmfs/{{{repos}}}/sw/{self.cid}"

    def activate_server_switcher(self) -> None:
        """Change TarfilePublisherHandler so that it will try different PubAPI servers"""
        self._fixed_server = False
        self._dropbox_server_selector = self.__setup_dropbox_server_selector()

    def deactivate_server_switcher(self) -> None:
        """Change TarfilePublisherHandler so that it will try a single PubAPI server repeatedly"""
        self._fixed_server = True
        self._dropbox_server_selector = self.__setup_fixed_dropbox_server()

    @pubapi_operation()
    def _get_configured_pubapi_repos(self) -> requests.Response:
        url = self.pubapi_base_url_formatter.format(endpoint="config")
        return requests.get(url, **self.__auth_kwargs)

    def __setup_dropbox_server_selector(self) -> Iterator[str]:
        """Return an infinite iterator of dropbox servers for client to upload tarball to"""
        dropbox_servers_working_list = self.dropbox_server_string.split()
        random.shuffle(dropbox_servers_working_list)
        if len(dropbox_servers_working_list) == 0:
            raise NoPublisherHandlerServerError(
                "No server was specified to publish the tarball.  Please check to ensure that JOBSUB_DROPBOX_SERVER_LIST is set in the environment"
            )
        return itertools.cycle(dropbox_servers_working_list)

    def __setup_fixed_dropbox_server(self) -> Iterator[str]:
        """Return an infinite iterator of a random selection of dropbox servers for client to upload tarball to.
        e.g. if the possible dropbox servers are "server1,server2", then one will get selected at random (e.g. "server2")
        and the iterator returned will look like ["server2", "server2", "server2", ...]
        """
        dropbox_servers_working_list = self.dropbox_server_string.split()
        random.shuffle(dropbox_servers_working_list)
        try:
            _server_to_use = dropbox_servers_working_list.pop()
            return itertools.repeat(_server_to_use)
        except IndexError:
            raise NoPublisherHandlerServerError(
                "No server was specified to publish the tarball.  Please check to ensure that JOBSUB_DROPBOX_SERVER_LIST is set in the environment"
            )

    def __restore_fixed_server_behavior_func(self) -> Callable[..., Iterator[str]]:
        """This function is meant to be used when restoring the behavior
        of yielding a fixed dropbox server after activating the dropbox server switcher.

        It returns a function that will set self._fixed_server to True and will
        return an infinite iterator that repeatedly generates the value given by
        self._dropbox_server_selector at the time this function is called,
        mimicking the behavior of __setup_fixed_dropbox_server, but ensuring
        that the yielded values are the same value as before the dropbox
        server switcher was activated.

        The following is how it should generally be used within the class:

            def func(self):
                restore_func = self.__restore_fixed_server_behavior_func() # Evaluate this now so that the correct server is saved
                self.activate_server_switcher()
                do_stuff()
                restore_func()
        """
        __fixed_server = next(self._dropbox_server_selector)

        def return_func() -> Iterator[str]:
            self._fixed_server = True
            return itertools.repeat(__fixed_server)

        return return_func


class NoPublisherHandlerServerError(Exception):
    """Exception to be raised when there are no servers available for the TarfilePublisherHandler to communicate with to either
    query or publish tarballs"""
