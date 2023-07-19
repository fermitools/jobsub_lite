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
from typing import Any, Dict, Union, Optional, List
from collections import namedtuple

import fake_ifdh


DEFAULT_AUTH_METHODS = "token,proxy"


class CredentialEnvMapping(Enum):
    """All supported authorization methods and the corresponding environment variables
    pointing to their credential's location"""

    TOKEN = "BEARER_TOKEN_FILE"
    PROXY = "X509_USER_PROXY"


SUPPORTED_AUTH_METHODS = [mapping.name.lower() for mapping in CredentialEnvMapping]
CredentialSet = namedtuple("CredentialSet", SUPPORTED_AUTH_METHODS)  # type: ignore

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
    set_environment_for_credentials(obtained_creds)
    return obtained_creds


def set_environment_for_credentials(cred_set: CredentialSet) -> None:
    """Set environment variables for a CredentialSet according to the
    SUPPORTED_AUTH_METHOD_ENV_MAPPING"""
    for cred_type, cred_path in cred_set._asdict().items():
        try:
            cred_env = getattr(CredentialEnvMapping, cred_type.upper()).value
            os.environ[cred_env] = cred_path
        except AttributeError:
            print(
                f"Unsupported auth method {cred_type}.  Supported auth methods are {','.join(SUPPORTED_AUTH_METHODS)}"
            )


def print_cred_paths_from_credset(cred_set: CredentialSet) -> None:
    """Print out the locations of the various credentials in the credential set"""
    for cred_type, cred_path in cred_set._asdict().items():
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
