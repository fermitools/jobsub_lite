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
from typing import Any, Dict, Optional, List

import fake_ifdh
from tracing import as_span


DEFAULT_AUTH_METHODS = ["token", "proxy"]
REQUIRED_AUTH_METHODS = [
    value.strip()
    for value in os.environ.get("JOBSUB_REQUIRED_AUTH_METHODS", "token").split(",")
]


class CredentialSet:
    """Class to hold credential paths for supported auth methods.  The __init__ method
    here defines what credentials we support"""

    # TODO Add __iter__ method so that we can explicitly return the credentials in an iterator
    # rather than relying on the magic of vars()?

    # Environment Variables corresponding to each supported auth method
    TOKEN_ENV = "BEARER_TOKEN_FILE"
    PROXY_ENV = "X509_USER_PROXY"

    def __init__(self, token: Optional[str] = None, proxy: Optional[str] = None):
        self.token: Optional[str] = token
        self.proxy: Optional[str] = proxy
        self._set_environment_for_credentials()

    def _set_environment_for_credentials(self) -> None:
        """Set environment variables for credentials"""
        for cred_type, cred_path in vars(self).items():
            if not cred_path:
                continue
            self_key = f"{cred_type.upper()}_ENV"
            environ_key = getattr(self, self_key, None)
            if environ_key:
                os.environ[environ_key] = cred_path


SUPPORTED_AUTH_METHODS = list(
    set([cred_type for cred_type in vars(CredentialSet())] + REQUIRED_AUTH_METHODS)
)  # Dynamically populate our SUPPORTED_AUTH_METHODS, and make sure it includes REQUIRED_AUTH_METHODS

# pylint: disable-next=dangerous-default-value
@as_span("get_creds")
def get_creds(args: Dict[str, Any] = {}) -> CredentialSet:
    """get credentials for job operations"""
    role = fake_ifdh.getRole(args.get("role", None))
    args["role"] = role

    auth_methods: List[str] = SUPPORTED_AUTH_METHODS
    if args.get("auth_methods", None):
        auth_methods = str(args.get("auth_methods")).split(",")

    # One last check to make sure we have the required auth methods
    if len(set(REQUIRED_AUTH_METHODS).intersection(set(auth_methods))) == 0:
        raise TypeError(
            f"Missing required authorization method(s) {list(set(REQUIRED_AUTH_METHODS).difference(set(auth_methods)))} "
            f"in requested authorization methods {auth_methods}"
        )

    if args.get("verbose", 0) > 0:
        print(f"Requested auth methods are: {auth_methods}")

    creds_to_return: Dict[str, Optional[str]] = {
        cred_type: None for cred_type in SUPPORTED_AUTH_METHODS
    }
    if "token" in auth_methods:
        t = fake_ifdh.getToken(role, args.get("verbose", 0))
        t = t.strip()
        creds_to_return["token"] = t
    if "proxy" in auth_methods:
        p = fake_ifdh.getProxy(
            role, args.get("verbose", 0), args.get("force_proxy", False)
        )
        p = p.strip()
        creds_to_return["proxy"] = p
    obtained_creds = CredentialSet(**creds_to_return)
    return obtained_creds


def print_cred_paths_from_credset(cred_set: CredentialSet) -> None:
    """Print out the locations of the various credentials in the credential set"""
    for cred_type, cred_path in vars(cred_set).items():
        print(f"{cred_type} location: {cred_path}")
