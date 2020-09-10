
import os
import sys
from glob import glob

def pkg_find(p,qual=''):
    path = None
    if not path and  os.environ.get("SPACK_ROOT",None):
        print("checking Spack:")
        cmd = "spack find --paths --variants '%s os=fe' 'py-%s os=fe'" % p
        print("running: %s" % cmd)
        f = os.popen(cmd, "r")
        for line in f:
            if line[0] == '-':
                 continue
            path = line.split()[1]
            break
        f.close()
         
    if not path and os.environ.get("PRODUCTS",None):
        print("checking UPS:")
        cmd = "ups list -a4 -Kproduct:@prod_dir %s %s, -a0 -Kproduct:@prod_dir %s %s" % (p,qual, p,qual)
        print("running: %s" % cmd)
        f = os.popen(cmd, "r")
        for line in f:
            print("line: %s" % line)
            path = line.split()[1].strip('"')
            break
        f.close()
   
    if path:
        print("found packge %s at %s" % (p, path))
        gl = glob('%s/lib/python*/site-packages' % path)
        if gl:
            print("globbed %s" % gl)
            sys.path.append(gl[0])
            return
        gl = glob('%s/lib/python*' % path)
        if gl:
            print("globbed %s" % gl)
            sys.path.append(gl[0])
            return
