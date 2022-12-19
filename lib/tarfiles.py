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
""" tarfile upload related code """
import argparse
import hashlib
import itertools
import os
import os.path
import random
import re
import sys
import time
import traceback as tb
from typing import Union, Dict, Tuple, Callable, List, Any, Iterator, Optional
from urllib.parse import quote as _quote

import requests  # type: ignore

import fake_ifdh
from creds import get_creds

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


def tar_up(directory: str, excludes: str, file: str = ".") -> str:
    """build path/to/directory.tar from path/to/directory"""
    tarfile = os.path.basename(f"{directory}.tar.gz")
    if not excludes:
        excludes = os.path.dirname(__file__) + "/../etc/excludes"
    excludes = f"--exclude-from {excludes}"
    os.system(f"GZIP=-n tar czvf {tarfile} {excludes} --directory {directory} {file}")
    return tarfile


def slurp_file(fname: str) -> Tuple[str, bytes]:
    """pull in a tarfile while computing its hash"""
    h = hashlib.sha256()
    tfl = []
    with open(fname, "rb") as f:
        tff = f.read(4096)
        h.update(tff)
        tfl.append(tff)
        while tff:
            tff = f.read(4096)
            h.update(tff)
            tfl.append(tff)
    return h.hexdigest(), bytes().join(tfl)


def dcache_persistent_path(exp: str, filename: str) -> str:
    """pick the reslient dcache path for a tarfile"""
    bf = os.path.basename(filename)

    with os.popen(f"sha256sum {filename}", "r") as f:
        sha256_hash = f.read().strip().split(" ")[0]
    res = f"/pnfs/{exp}/resilient/jobsub_stage/{sha256_hash}/{bf}"
    # for testing, we don't have a resilient area for "fermilab", so...
    if exp == "fermilab":
        res = res.replace("fermilab/resilient", "fermilab/volatile")
    sys.stdout.flush()
    return res


def do_tarballs(args: argparse.Namespace) -> None:
    """handle tarfile argument;  we could have:
       a directory with tardir: prefix to tar up and upload
       a tarfile with dropbox: prefix to upload
       a plain path to just use
    we convert the argument to the next type as we go...
    """
    # pylint: disable=too-many-nested-blocks,too-many-branches
    clean_up: List[str] = []
    res: List[str] = []
    path: Optional[str] = None
    for fn in args.input_file:
        if fn.startswith("dropbox:"):
            pfn = fn.replace("dropbox:", "")
            if args.use_dropbox == "cvmfs" or args.use_dropbox is None:
                tarfile = tar_up(
                    os.path.dirname(pfn), "/dev/null", os.path.basename(pfn)
                )
                clean_up.append(tarfile)
                path = tarfile_in_dropbox(args, tarfile)
                if path:
                    res.append(os.path.join(path, os.path.basename(fn)))
                else:
                    res.append(pfn)

            elif args.use_dropbox == "pnfs":
                location = dcache_persistent_path(args.group, pfn)
                fake_ifdh.cp(pfn, location)
                res.append(location)
            else:

                res.append(pfn)
        else:
            res.append(fn)

    args.input_file = res

    res = []
    for tfn in args.tar_file_name:
        if tfn.startswith("tardir:"):
            # tar it up, pretend they gave us dropbox:
            tarfile = tar_up(tfn[7:], args.tarball_exclusion_file)
            tfn = f"dropbox:{tarfile}"
            clean_up.append(tarfile)

        if tfn.startswith("dropbox:"):
            # move it to dropbox area, pretend they gave us plain path
            path = tarfile_in_dropbox(args, tfn[8:])
            if path:
                tfn = path
            else:
                tfn = tfn.replace("dropbox:", "")

        res.append(tfn)
    args.tar_file_name = res

    # clean up tarfiles we made...
    for tarfile in clean_up:
        try:
            os.unlink(tarfile)
        except:  # pylint: disable=bare-except
            print(f"Notice: unable to remove generated tarfile {tarfile}")


def tarfile_in_dropbox(args: argparse.Namespace, tfn: str) -> Optional[str]:
    """
    upload a tarfile to the dropbox, return its path there
    """
    location: Optional[str] = ""
    if args.use_dropbox == "cvmfs" or args.use_dropbox is None:
        digest, tf = slurp_file(tfn)
        proxy, token = get_creds(vars(args))

        if not args.group:
            raise ValueError("No --group specified!")

        # cid looks something like dune/bf6a15b4238b72f82...(long hash)
        cid = f"{args.group}/{digest}"
        if args.verbose:
            print(f"Using RCDS to publish tarball\ncid: {cid}")

        publisher = TarfilePublisherHandler(cid, proxy, token)
        location = publisher.cid_exists()
        if location is None:
            publisher.publish(tf)
            # pylint: disable-next=unused-variable
            for i in range(NUM_RETRIES):
                time.sleep(RETRY_INTERVAL_SEC)
                location = publisher.cid_exists()
                if location is not None:
                    break
        else:
            # tag it so it stays around
            publisher.update_cid()

    elif args.use_dropbox == "pnfs":
        location = dcache_persistent_path(args.group, tfn[8:])
        fake_ifdh.cp(tfn[8:], location)
    else:
        raise (
            NotImplementedError(f"unknown tar distribution method: {args.use_dropbox}")
        )
    return location


class TarfilePublisherHandler:
    """Handler to publish tarballs via HTTP to RCDS (or future dropbox server)

    Args:
        object (_type_): _description_
        cid (str): unique group/hash combination that RCDS uses to locate tarballs
        proxy (str): Location of X509 Proxy file to authenticate to RCDS
        token (str): Location of JWT/Sci-token to authenticate to RCDS
    """

    dropbox_server_string = os.getenv("JOBSUB_DROPBOX_SERVER_LIST", "")
    check_tarball_present_re = re.compile(
        "^PRESENT:(.+)$"
    )  # RCDS returns this if a tarball represented by cid is present

    def __init__(
        self, cid: str, proxy: Union[None, str] = None, token: Union[None, str] = None
    ):
        self.cid_url = _quote(cid, safe="")  # Encode CID for passing to URL
        self.proxy = proxy
        self.token = token
        if token is not None:
            self.request_headers = self.__make_request_token_headers()
            print(f"Using bearer token located at {self.token} to authenticate to RCDS")
        else:
            print(f"Using X509 proxy located at {self.proxy} to authenticate to RCDS")
        self.dropbox_servers = tuple(self.dropbox_server_string.split())
        self.pubapi_base_url_formatter_full = (
            f"https://{{dropbox_server}}/pubapi/{{endpoint}}?cid={self.cid_url}"
        )
        self.pubapi_base_url_formatter = self.pubapi_base_url_formatter_full

    # pylint: disable-next=no-self-argument
    def pubapi_operation(func: Callable) -> Callable:  # type: ignore
        """Wrap various PubAPI operations, return path if we get it from response"""

        class SafeDict(dict):  # type: ignore
            """Use this object to allow us to not need all keys of dict when
            running str.format_map method to do string interpolation.
            Taken from https://stackoverflow.com/a/17215533"""

            def __missing__(self, key: str) -> str:
                """missing item handler"""
                return f"{{{key}}}"  # "{<key>}"

        def wrapper(self, *args, **kwargs):  # type: ignore
            """wrapper function for decorator"""
            # pylint: disable-next=protected-access
            _dropbox_server_selector = self.__select_dropbox_server()
            retry_count = itertools.count()
            while True:
                try:
                    _dropbox_server = next(_dropbox_server_selector)
                    self.pubapi_base_url_formatter = (
                        self.pubapi_base_url_formatter_full.format_map(
                            SafeDict(dropbox_server=_dropbox_server)
                        )
                    )
                    # pylint: disable-next=not-callable
                    response = func(self, *args, **kwargs)
                except:  # pylint: disable=bare-except
                    tb.print_exc()
                    if next(retry_count) == NUM_RETRIES:
                        print(f"Max retries {NUM_RETRIES} exceeded.  Exiting now.")
                        raise
                    print(f"Will retry in {RETRY_INTERVAL_SEC} seconds")
                    time.sleep(RETRY_INTERVAL_SEC)
                else:
                    break
            _match = self.check_tarball_present_re.match(response.text)
            if _match is not None:
                return _match.group(1)
            return None

        return wrapper

    @pubapi_operation
    def update_cid(self) -> requests.Response:
        """Make PubAPI update call to check if we already have this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="update")
        if self.token:
            return requests.get(url, headers=self.request_headers)
        return requests.get(url, cert=(self.proxy, self.proxy))

    @pubapi_operation
    def publish(self, tarfile: str) -> requests.Response:
        """Make PubAPI publish call to upload this tarfile

        Args:
            tarfile (bytes): Byte-string of tarfile #TODO CHECK THIS

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="publish")
        if self.token:
            return requests.post(url, headers=self.request_headers, data=tarfile)
        return requests.post(url, cert=(self.proxy, self.proxy), data=tarfile)

    @pubapi_operation
    def cid_exists(self) -> requests.Response:
        """Make PubAPI update call to check if we already have this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="exists")
        if self.token:
            return requests.get(url, headers=self.request_headers)
        return requests.get(url, cert=(self.proxy, self.proxy))

    def __make_request_token_headers(self) -> Dict[str, str]:
        """Create headers for token auth to dropbox server"""
        with open(self.token, "r", encoding="UTF-8") as f:  # type: ignore
            token_string = f.read()
        token_string = token_string.strip()  # Drop \n at end of token_string
        header = {"Authorization": f"Bearer {token_string}"}
        return header

    def __select_dropbox_server(self) -> Iterator[str]:
        """Yield a dropbox server for client to upload tarball to"""
        dropbox_servers_working_list: List[str] = []
        while True:
            if len(dropbox_servers_working_list) == 0:
                dropbox_servers_working_list = list(self.dropbox_servers)
                random.shuffle(dropbox_servers_working_list)
            yield dropbox_servers_working_list.pop()
