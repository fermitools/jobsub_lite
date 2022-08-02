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
""" replacement for jobsub_wrapper for POMS"""
import os
import sys
from typing import Dict

from packages import pkg_find

pkg_find("poms_client", "-g poms41")
#pylint: disable-next=wrong-import-position,wrong-import-order,import-error
import poms_client

# translation of jobub_submit wrapper in poms_jobsub_wrapper...


def poms_wrap(args: Dict[str, str]) -> None:
    """
       pass assorted POMS bookeeping into job submission and
       back to monitoring and POMS
    """

    if os.environ.get("POMS_TASK_ID", None) is None:
        # poms launch env not set, so skip...
        return

    if args["environment"] and "POMS_TASK_ID" in args["environment"]:
        # -e POMS_TASK_ID set, so already using poms_jobsub_wrapper
        return

    if os.environ.get('POMS_TEST', None):
        dest = os.environ["POMS_TEST"]

    os.environ["POMS_TASK_ID"] = str(
        poms_client.get_task_id_for(
            test=dest,
            experiment=args["group"],
            task_id=os.environ["POMS_TASK_ID"],
            command_executed=f"jobsub_submit {' '.join(sys.argv)}",
            campaign=os.environ["POMS_CAMPAIGN"],
            parent_task_id=os.environ["POMS_PARENT_TASK_ID"],
        )
    )

    for estr in ("POMS_CAMPAIGN_ID", "POMS_TASK_ID"):
        args["environment"].append(estr)

    args["lines"].append(
        f"FIFE_CATEGORIES=\"POMS_TASK_ID_{os.environ['POMS_TASK_ID']},"
        f"POMS_CAMPAIGN_ID_{os.environ['POMS_CAMPAIGN_ID']}"
        f"{os.environ['POMS_CAMPAIGN_TAGS']}\""
    )

    for lstr in (
        "POMS_TASK_ID",
        "POMS_CAMPAIGN_ID",
        "POMS_LAUNCHER",
        "POMS_CAMPAIGN_NAME",
        "POMS4_CAMPAIGN_STAGE_ID",
        "POMS4_CAMPAIGN_STAGE_NAME",
        "POMS4_CAMPAIGN_ID",
        "POMS4_CAMPAIGN_NAME",
        "POMS4_SUBMISSION_ID",
        "POMS4_CAMPAIGN_TYPE",
        "POMS4_TEST_LAUNCH",
    ):
        args["lines"].append(f"+{lstr}={os.environ[lstr]}")

    return
