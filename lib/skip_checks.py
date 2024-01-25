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

To add a check, simply add it to the Enum class SupportedSkipChecks, setting
its value to an optional setup function to call for that check.
Most of these "setup functions" will simply print a warning explaining to the user
the consequences of skipping the check.
"""

from enum import Enum
from functools import partial
from typing import Any, List

__all__ = ["SupportedSkipChecks", "skip_check_setup"]

# Internal functions to handle any presteps for each supported check to skip


def _print_rcds_warning() -> None:
    """This function prints out the warning for skipping the RCDS tarball upload check."""
    print(
        "WARNING:  You have elected to skip the RCDS tarball publish check. "
        "This check ensures that if you are uploading a tarball or "
        "directory using RCDS/CVMFS, the uploaded tarball is published "
        "on CVMFS before the job is submitted.  Skipping this check "
        "may result in jobs running on the worker nodes that cannot "
        "find the intended uploaded files.\n"
    )


def _print_disk_space_warning() -> None:
    """This function prints out the warning for skipping disk quota checks"""
    print(
        "WARNING: You have elected to skip the disk quota check. "
        "This check ensures that there are available disk space and file "
        "handles in the locations jobsub needs to submit your jobs as "
        "specified.  Skipping this check may result in failed job submissions.\n"
    )


# Supported Checks to Skip
class SupportedSkipChecks(Enum):
    """Add checks to skip here, with the setup function they should call when skipped
    Example:
        foo = partial(setup_func)
    No-op example:
        blah = partial(lambda *args: None)

    Need to use the functools.partial as explained here:
    https://stackoverflow.com/a/40339397
    because functions in Enums are not considered attributes

    This changes in  3.11, where you can specify if a function is a member using the
    Enum.member() function.  But for now, we need to have this workaround
    """

    rcds = partial(_print_rcds_warning)  # pylint: disable=invalid-name
    disk_space = partial(_print_disk_space_warning)  # pylint: disable=invalid-name

    # pylint: disable=consider-iterating-dictionary
    @classmethod
    def get_all_checks(cls) -> List[str]:
        """Returns supported checks that can be skipped.  Mainly
        for outside callers"""
        return list(cls.__members__.keys())


def skip_check_setup(check_name: str, *args: Any, **kwargs: Any) -> Any:
    """This function calls the mapped setup function in supported_skip_checks_setup_functions"""
    try:
        return getattr(SupportedSkipChecks, check_name).value(*args, **kwargs)
    except AttributeError:
        raise AttributeError(
            f'Invalid check to skip: "{check_name}". Supported checks to skip '
            f"are: {SupportedSkipChecks.get_all_checks()}"
        )
