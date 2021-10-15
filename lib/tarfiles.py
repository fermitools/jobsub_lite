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
import ifdh
import os
import os.path
import requests
import sys
import time


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

            if args.use_dropbox == "cvmfs" or args.use_dropbox == None:
                digest, tf = slurp_file(tfn[8:])
                proxy, token = get_creds()

                if not args.group:
                    raise ValueError("No --group specified!")
                cid = "".join((args.group, "%2F", digest))
                location = pubapi_exists(cid, proxy)
                if not location:
                    pubapi_publish(cid, tf, proxy)
                    for i in range(20):
                        time.sleep(30)
                        location = pubapi_exists(cid, proxy)
                        if location:
                            break
                else:
                    # tag it so it stays around
                    pubapi_update(cid, proxy)

            elif args.use_dropbox == "pnfs":
                location = dcache_persistent_path(args.group, tfn[8:])
                ih = ifdh.ifdh()
                ih.mkdir_p(os.path.dirname(location))
                ih.cp([tfn[8:], location])
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


def pubapi_update(cid, proxy):
    """make pubapi update call to check if we already have this tarfile,
    return path.
    """
    dropbox_server = "rcds.fnal.gov"
    url = "https://%s/pubapi/update?cid=%s" % (dropbox_server, cid)
    res = requests.get(url, cert=(proxy, proxy), verify=False)
    if res.text[:8] == "PRESENT:":
        return res.text[8:]
    else:
        return None


def pubapi_publish(cid, tf, proxy):
    """make pubapi publish call to upload this tarfile, return path"""
    dropbox_server = "rcds.fnal.gov"
    url = "https://%s/pubapi/publish?cid=%s" % (dropbox_server, cid)
    res = requests.post(url, cert=(proxy, proxy), data=tf, verify=False)
    if res.text[:8] == "PRESENT:":
        return res.text[8:]
    else:
        return None


def pubapi_exists(cid, proxy):
    """make pubapi update call to check if we already have this tarfile,
    return path.
    """
    dropbox_server = "rcds.fnal.gov"
    url = "https://%s/pubapi/exists?cid=%s" % (dropbox_server, cid)
    res = requests.get(url, cert=(proxy, proxy), verify=False)
    if res.text[:8] == "PRESENT:":
        return res.text[8:]
    else:
        return None
