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
from typing import Any, Dict, Union

import fake_ifdh


DEFAULT_AUTH_METHODS = "token,proxy"
SUPPORTED_AUTH_METHOD_ENV_MAPPING = {
    "token": "BEARER_TOKEN_FILE",
    "proxy": "X509_USER_PROXY",
}
SUPPORTED_AUTH_METHODS = list(SUPPORTED_AUTH_METHOD_ENV_MAPPING.keys())


class CredentialSet(object):
    """Class that holds the paths to the supported credential types given in
    SUPPORTED_AUTH_METHODS"""

    def __init__(self) -> None:
        for cred_type in SUPPORTED_AUTH_METHODS:
            setattr(self, cred_type, None)

    def __setattr__(self, cred_type: str, cred_path: Any) -> None:
        """Make sure we can't set a value here for an unsupported auth method,
        and also set the correct environment variable"""
        if not hasattr(self, cred_type):
            print(
                f"Invalid credential type.  Not setting {cred_type} to {cred_path} for this CredentialSet"
            )
            return
        os.environ[SUPPORTED_AUTH_METHOD_ENV_MAPPING[cred_type]] = cred_path
        setattr(self, cred_type, cred_path)

    def get_all_credentials(self) -> Dict[str, str]:
        """Get the stored credentials in the CredentialSet that are not None"""
        return {key: value for key, value in vars(self).items() if value is not None}


# pylint: disable-next=dangerous-default-value
def get_creds(args: Dict[str, Any] = {}) -> CredentialSet:
    """get credentials -- Note this does not currently push to
    myproxy, nor does it yet deal with tokens, but those should
    be done here as needed.
    """
    role = fake_ifdh.getRole(args.get("role", None))
    args["role"] = role

    auth_methods = args.get("auth_methods", SUPPORTED_AUTH_METHODS)

    obtained_creds = CredentialSet()
    # TODO Callers should support either of token or proxy or both being returned
    # TODO Templates should also support token or proxy not existing
    if "token" in auth_methods:
        t = fake_ifdh.getToken(role, args.get("verbose", 0))
        t = t.strip()
        obtained_creds.token = t
    if "proxy" in auth_methods:
        p = fake_ifdh.getProxy(
            role, args.get("verbose", 0), args.get("force_proxy", False)
        )
        p = p.strip()
        obtained_creds.proxy = p

    return obtained_creds


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
