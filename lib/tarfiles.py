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
from creds import get_creds
from functools import wraps
import hashlib
import os
import os.path
import re
import sys
import time
from urllib.parse import quote as _quote

import requests


def tar_up(directory, excludes):
    """build path/to/directory.tar from path/to/directory"""
    tarfile = "%s.tar.gz" % directory
    if not excludes:
        excludes = os.path.dirname(__file__) + "/../etc/excludes"
    excludes = "--exclude-from %s" % excludes
    os.system("tar czvf %s %s --directory %s ." % (tarfile, excludes, directory))
    return tarfile


def slurp_file(fname):
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


def dcache_persistent_path(exp, filename):
    """pick the reslient dcache path for a tarfile"""
    bf = os.path.basename(filename)
    f = os.popen("sha256sum %s" % filename, "r")
    sha256_hash = f.read().strip().split(" ")[0]
    f.close()
    res = "/pnfs/%s/resilient/jobsub_stage/%s/%s" % (exp, sha256_hash, bf)
    # for testing, we don't have a resilient area for "fermilab", so...
    if exp == "fermilab":
        res = res.replace("fermilab/resilient", "fermilab/volatile")
    sys.stdout.flush()
    return res


def do_tarballs(args):
    """handle tarfile argument;  we could have:
       a directory with tardir: prefix to tar up and upload
       a tarfile with dropbox: prefix to upload
       a plain path to just use
    we convert the argument to the next type as we go...
    """

    NUM_RETRIES_UPLOAD = 20
    RETRY_INTERVAL_SEC = 30

    res = []
    clean_up = []
    for tfn in args.tar_file_name:
        if tfn.startswith("tardir:"):
            # tar it up, pretend they gave us dropbox:
            tarfile = tar_up(tfn[7:], args.tarball_exclusion_file)
            tfn = "dropbox:%s" % tarfile
            clean_up.append(tarfile)

        if tfn.startswith("dropbox:"):
            # move it to dropbox area, pretend they gave us plain path

            if args.use_dropbox == "cvmfs" or args.use_dropbox is None:
                digest, tf = slurp_file(tfn[8:])
                proxy, token = get_creds()

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
                    for i in range(NUM_RETRIES_UPLOAD):
                        time.sleep(RETRY_INTERVAL_SEC)
                        location = publisher.cid_exists()
                        if location is not None:
                            break
                else:
                    # tag it so it stays around
                    publisher.update_cid()

            elif args.use_dropbox == "pnfs":
                location = dcache_persistent_path(args.group, tfn[8:])
                os.system("fake_ifdh cp %s %s" % (tfn[8:], location))
            else:
                raise (
                    NotImplementedError(
                        "unknown tar distribution method: %s" % args.use_dropbox
                    )
                )
            tfn = location
        res.append(tfn)
    # clean up tarfiles we made...
    for tf in clean_up:
        try:
            os.unlink(tf)
        except:
            print("Notice: unable to remove generated tarfile %s" % tf)
            pass

    args.tar_file_name = res


class TarfilePublisherHandler(object):
    """Handler to publish tarballs via HTTP to RCDS (or future dropbox server)

    Args:
        object (_type_): _description_
        cid (str): unique group/hash combination that RCDS uses to locate tarballs
        proxy (str): Location of X509 Proxy file to authenticate to RCDS
        token (str): Location of JWT/Sci-token to authenticate to RCDS
    """

    dropbox_server = "rcds.fnal.gov"
    pubapi_base_url = f"https://{dropbox_server}/pubapi"
    check_tarball_present_re = re.compile(
        "^PRESENT\:(.+)$"
    )  # RCDS returns this if a tarball represented by cid is present

    def __init__(self, cid, proxy=None, token=None):
        self.cid_url = _quote(cid, safe="")  # Encode CID for passing to URL
        self.proxy = proxy
        self.token = token
        self.pubapi_base_url_formatter = (
            f"{self.pubapi_base_url}/{{endpoint}}?cid={self.cid_url}"
        )
        if token is not None:
            self.request_headers = self.__make_request_token_headers()

    # Some sort of wrapper to wrap the above three
    def pubapi_operation(func):
        """Wrap various PubAPI operations, return path if we get it from response"""

        def wrapper(self, *args, **kwargs):
            response = func(self, *args, **kwargs)
            _match = self.check_tarball_present_re.match(response.text)
            if _match is not None:
                return _match.group(1)
            return None

        return wrapper

    @pubapi_operation
    def update_cid(self):
        """Make PubAPI update call to check if we already have this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="update")
        if self.token:
            print(f"Using bearer token located at {self.token} to authenticate to RCDS")
            return requests.get(url, headers=self.request_headers, verify=False)
        else:
            print(f"Using X509 proxy located at {self.proxy} to authenticate to RCDS")
            return requests.get(url, cert=(self.proxy, self.proxy), verify=False)

    @pubapi_operation
    def publish(self, tarfile):
        """Make PubAPI publish call to upload this tarfile

        Args:
            tarfile (bytes): Byte-string of tarfile #TODO CHECK THIS

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="publish")
        if self.token:
            return requests.post(
                url, headers=self.request_headers, data=tarfile, verify=False
            )
        else:
            return requests.post(
                url, cert=(self.proxy, self.proxy), data=tarfile, verify=False
            )

    @pubapi_operation
    def cid_exists(self):
        """Make PubAPI update call to check if we already have this tarfile

        Returns:
            requests.Response: Response from PubAPI call indicating if tarball
            represented by self.cid is present
        """
        url = self.pubapi_base_url_formatter.format(endpoint="exists")
        if self.token:
            return requests.get(url, headers=self.request_headers, verify=False)
        else:
            return requests.get(url, cert=(self.proxy, self.proxy), verify=False)

    def __make_request_token_headers(self):
        with open(self.token, "r") as f:
            token_string = f.read()
        token_string = token_string.strip()  # Drop \n at end of token_string
        header = {"Authorization": f"Bearer {token_string}"}
        return header
