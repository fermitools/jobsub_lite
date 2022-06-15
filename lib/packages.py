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


import os
import sys
from glob import glob

SAVED_ENV = None


def orig_env():
    global SAVED_ENV
    if SAVED_ENV:
        os.environ.clear()
        os.environ.update(SAVED_ENV)


def pkg_find(p, qual=""):
    """
    Use Spack or UPS to find the package mentioned and stuff its
    various subdirectories on sys.path so we can 'import' from it.
    """
    global SAVED_ENV
    if not SAVED_ENV:
        SAVED_ENV = os.environ.copy()
    path = None
    if not path and os.environ.get("SPACK_ROOT", None):
        cmd = "spack find --paths --variants '%s os=fe' 'py-%s os=fe'" % p
        f = os.popen(cmd, "r")
        for line in f:
            if line[0] == "-":
                continue
            path = line.split()[1]
            break
        f.close()

    if not path and os.environ.get("PRODUCTS", None):
        cmd = (
            "ups list -a4 -Kproduct:@prod_dir %s %s, -a0 -Kproduct:@prod_dir %s %s"
            % (p, qual, p, qual)
        )
        f = os.popen(cmd, "r")
        for line in f:
            path = line.split()[1].strip('"')
            break
        f.close()


    if path:
        os.environ["%s_DIR" % p.upper()] = path
        for fmt in [
            "%s/lib/python*/site-packages/*.egg",
            "%s/lib/python*/site-packages",
            "%s/lib/python*",
            "%s/python*",
        ]:

            gl = glob(fmt % path)
            if gl:
                sys.path = sys.path + gl
                return
