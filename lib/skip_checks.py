# COPYRIGHT 2023 FERMI NATIONAL ACCELERATOR LABORATORY
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

"""Note:  This file really serves to hold all the checks that users can
skip.  It doesn't make much sense to define skipping-check behavior here,
far away from where the skips should be implemented, so the original intent
of this module is to serve as both a definitive list of checks users can
skip, and to control the warning messages users get when they elect to skip
a check.

To add a check, simply add it to the dict supported_skip_checks.

Optionally create a setup function to call for that check, and register it in
the skip_check_setup_functions dictionary at the bottom of this file.
Most of these "setup functions" will simply print a warning explaining to the user
the consequences of skipping the check.
"""

from typing import Dict, Callable, Any, List

__all__ = ["get_supported_checks_to_skip", "skip_check_setup"]

supported_skip_checks: List[str] = ["rcds"]


def get_supported_checks_to_skip() -> List[str]:
    """Returns supported checks that can be skipped.  Mainly
    for outside callers"""
    return supported_skip_checks


def skip_check_setup(check_name: str) -> Any:
    """This function calls the mapped setup function in supported_skip_checks_setup_functions"""
    if check_name not in supported_skip_checks:
        raise TypeError(
            f'Invalid check to skip: "{check_name}". Supported checks to skip '
            f"are: {supported_skip_checks}"
        )
    # If we've registered a setup function, use that.  Otherwise, default to a no-op.
    setup_func = skip_check_setup_functions.get(check_name, lambda *args: None)
    return setup_func()


"""Internal functions to handle any presteps for each supported check to skip"""


def _print_rcds_warning() -> None:
    """This function prints out the warning for skipping the RCDS tarball upload check."""
    print(
        "WARNING:  You have elected to skip the RCDS tarball publish check. "
        "This check ensures that if you are uploading a tarball or "
        "directory using RCDS/CVMFS, the uploaded tarball is published "
        "on CVMFS before the job is submitted.  Skipping this check "
        "may result in jobs running on the worker nodes that cannot "
        "find the intended uploaded files."
    )


# Registration of skipped check setup functions

skip_check_setup_functions: Dict[str, Callable] = {  # type: ignore
    "rcds": _print_rcds_warning,
}
