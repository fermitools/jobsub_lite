import os
import os.path
from creds import get_creds
import requests
import ifdh

def tar_up(directory, excludes):
    """ build path/to/directory.tar from path/to/directory """
    tarfile = "%s.tar.gz" % directory
    if not excludes:
        excludes = os.path.dirname(__FILE__) + "/../etc/default_excludes"
    excludes = "--exclude-from %s" % excludes
    os.system("tar czvf %s %s %s" % (tarfile, excludes, directory))
    return tarfile


def slurp_file(fname):
    """ pull in a tarfile while computing its hash """
    h = hashlib.sha256()
    tfl = []
    with open(fname, "r") as f:
        tff = f.read(4096)
        h.update(tff)
        tfl.append(tff)
        while tff:
            tff = f.read(4096)
            h.update(tff)
            tfl.append(tff)
    return h.hexdigest(), "".join(tfl)

def dcache_path(filename):
    """ pick the reslient dcache path for a tarfile """
    bf = os.path.basename(filename)
    sha1_hash = backquote("sha1sum %s" % filename)
    return "/pnfs/%s/resilient/%s/%s" % (exp, sha1_hash, bf)

def do_tarballs(args):
    """ handle tarfile argument;  we could have: 
           a directory with tardir: prefix to tar up and upload
           a tarfile with dropbox: prefix to upload
           a plain path to just use
        we convert the argument to the next type as we go...
    """

    res = []
    for tfn in args.tar_file_name:
        if tfn.startswith("tardir:"):
            # tar it up, pretend they gave us dropbox:
            tarfile = tar_up(tfn[7:], args.tarball_exclusion_file)
            tfn = "dropbox:%s" % tarfile

        if tfn.startswith("dropbox:"):
            # move it to dropbox area, pretend they gave us plain path

            if args.tarmethod=="cvmfs":
                digest, tf = slurp_file(tfn[8:])
                proxy = get_creds()

                cid = "".join((args.group, "%2F", digest))
                location = pubapi_update(cid, proxy)
                if not location:
                    location = pubapi_publish(cid, tf, proxy)
            elif args.tarmethod=="persistent":
                location = dcache_persistent_path(tfn[8:])
                ih = ifdh.ifdh()
                ih.cp([tfn[8:],location])
            else:
                raise(NotImplementedError("unknown tar distribution method: %s" % tarmethod))

            tfn = location
        res.append(tfn)
    args.tar_file_name = res


def pubapi_update(cid, proxy):
    """ make pubapi update call to check if we already have this tarfile,
        return path.
    """
    dropbox_server = "rdcs.fnal.gov"
    url = "https://%s/pubapi/update?cid=%s" % (dropbox_server, cid)
    res = requests.get(url, cert=(proxy, proxy))
    if res.text[:8] == "PRESENT:":
        return res.text[8:]
    else:
        return None


def pubapi_publish(cid, tf, proxy):
    """ make pubapi publish call to upload this tarfile, return path"""
    dropbox_server = random.choice(DROPBOX_SERVERS)
    url = "https://%s/pubapi/publish?cid=%s" % (dropbox_server, cid)
    res = requests.post(url, cert=(proxy, proxy), data=tf)
    if res.text[:8] == "PRESENT:":
        return res.text[8:]
    else:
        return None

