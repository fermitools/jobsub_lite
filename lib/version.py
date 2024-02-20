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

import sys

__title__ = "jobsub_lite"
__summary__ = "The local HTCondor job submission software for Fermilab users to submit jobs to local FermiGrid resources and to the Open Science Grid."
__uri__ = "https://fifewiki.fnal.gov/wiki/Jobsub_Lite"

__version__ = "1.6"
__email__ = "jobsub-support@fnal.gov"

__license__ = "Apache License, Version 2.0"
__author__ = "Fermi National Accelerator Laboratory"
__copyright__ = f"2023 {__author__}"


def print_version() -> None:
    print(f"{__title__} version {__version__}")
    sys.exit()


def print_support_email() -> None:
    print(f"Email {__email__} for help.")
    sys.exit()
