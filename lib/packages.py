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
from typing import Union, Any, Dict

SAVED_ENV = None


def orig_env() -> None:
    global SAVED_ENV
    if SAVED_ENV:
        os.environ.clear()
        os.environ.update(SAVED_ENV)


def pkg_find(p: str, qual: str = "") -> None:
    """
    Use Spack or UPS to find the package mentioned and stuff its
    various subdirectories on sys.path so we can 'import' from it.
    """
    global SAVED_ENV
    if not SAVED_ENV:
        SAVED_ENV = os.environ.copy()
    path = None
    if not path and os.environ.get("SPACK_ROOT", None):
        cmd = f"spack find --paths --variants '{p} os=fe' 'py-{p} os=fe'" 
        f = os.popen(cmd, "r")
        for line in f:
            if line[0] == "-":
                continue
            path = line.split()[1]
            break
        f.close()

    if not path and os.environ.get("PRODUCTS", None):
        cmd = (
            f"ups list -a4 -Kproduct:@prod_dir {p} {qual}, -a0 -Kproduct:@prod_dir {p} {qual}"
        )
        f = os.popen(cmd, "r")
        for line in f:
            path = line.split()[1].strip('"')
            break
        f.close()

    if path:
        os.environ[f"{p.upper()}_DIR"] = path
        for fmt in [
            f"{path}/lib/python*/site-packages/*.egg",
            f"{path}/lib/python*/site-packages",
            f"{path}/lib/python*",
            f"{path}/python*",
        ]:

            gl = glob(fmt)
            if gl:
                sys.path = sys.path + gl
                return
