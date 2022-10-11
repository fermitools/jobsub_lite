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
""" credential related routines """
import os
from typing import Any, Dict, Tuple

import fake_ifdh

# pylint: disable-next=dangerous-default-value
def get_creds(args: Dict[str, Any] = {}) -> Tuple[str, str]:
    """get credentials -- Note this does not currently push to
    myproxy, nor does it yet deal with tokens, but those should
    be done here as needed.
    """

    role = fake_ifdh.getRole(args.get("role", None))
    p = fake_ifdh.getProxy(role, args.get("debug", 0))
    t = fake_ifdh.getToken(role, args.get("debug", 0))

    p = p.strip()
    t = t.strip()
    os.environ["X509_USER_PROXY"] = p
    os.environ["BEARER_TOKEN_FILE"] = t

    if role.lower() == "production":
        with os.popen(f"decode_token.sh -e sub {t}", "r") as f:
            sub = f.read().strip().strip('"')
            os.environ["USER"] = sub

    return p, t
