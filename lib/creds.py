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
import argparse
import os
from enum import Enum
from typing import Any, Dict, Union, Optional, List, NamedTuple
from collections import namedtuple

import fake_ifdh


DEFAULT_AUTH_METHODS = "token,proxy"


class CredentialSet:
    """Class to hold credential paths for supported auth methods.  The __init__ method
    here defines what credentials we support"""

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
            self_key = f"{cred_type.upper}_ENV"
            environ_key = getattr(self, self_key, None)
            if environ_key:
                os.environ[environ_key] = cred_path


SUPPORTED_AUTH_METHODS = [
    cred_type for cred_type in vars(CredentialSet())
]  # Dynamically populate our SUPPORTED_AUTH_METHODS

# pylint: disable-next=dangerous-default-value
def get_creds(args: Dict[str, Any] = {}) -> CredentialSet:
    """get credentials for job operations"""
    role = fake_ifdh.getRole(args.get("role", None))
    args["role"] = role

    auth_methods: List[str] = SUPPORTED_AUTH_METHODS
    if args.get("auth_methods", None):
        auth_methods = str(args.get("auth_methods")).split(",")

    creds_to_return: Dict[str, Optional[str]] = {
        cred_type: None for cred_type in SUPPORTED_AUTH_METHODS
    }
    # TODO Templates should also support token or proxy not existing
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


class CheckIfValidAuthMethod(argparse.Action):
    """Argparse Action to check if the caller has requested a valid auth method"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Union[None, str] = None,
    ) -> None:
        check_values = [value.strip() for value in values.split()]
        for value in check_values:
            if value not in SUPPORTED_AUTH_METHODS:
                raise TypeError(
                    f"Invalid auth method {value}.  Supported auth methods are {SUPPORTED_AUTH_METHODS}"
                )
        setattr(namespace, self.dest, ",".join(check_values))
