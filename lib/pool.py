"""
pools:
    Info about what condor pools we know about.  However we don't actually store the info here,
    we just parse it out of the environment.
"""
import argparse
import json
import functools
import os
import utils
import condor
import packages
from typing import Dict, Any, Union


@functools.lru_cache(1)
def get_poolmap() -> Any:
    return json.loads(os.environ.get("JOBSUB_POOL_MAP", "{}"))


# so we can reset later for tests
SAVE_COLLECTOR_HOST = ""
SAVE_ONSITE_SITE_NAME = ""


def set_pool(name: str) -> None:
    global SAVE_COLLECTOR_HOST, SAVE_ONSITE_SITE_NAME

    poolmap = get_poolmap()
    if not name in poolmap:
        raise KeyError(
            f"--global-pool value must be one of ({', '.join(poolmap.keys())})"
        )
    os.environ["_condor_COLLECTOR_HOST"] = poolmap[name]["collector"]
    packages.SAVED_ENV["_condor_COLLECTOR_HOST"] = poolmap[name]["collector"]
    if not SAVE_COLLECTOR_HOST:
        SAVE_COLLECTOR_HOST = condor.COLLECTOR_HOST
        SAVE_ONSITE_SITE_NAME = utils.ONSITE_SITE_NAME
    condor.COLLECTOR_HOST = poolmap[name]["collector"]
    utils.ONSITE_SITE_NAME = poolmap[name]["onsite"]


def reset_pool() -> None:
    global SAVE_COLLECTOR_HOST, SAVE_ONSITE_SITE_NAME
    if "_condor_COLLECTOR_HOST" in os.environ:
        del os.environ["_condor_COLLECTOR_HOST"]
    if "_condor_COLLECTOR_HOST" in packages.SAVED_ENV:
        del packages.SAVED_ENV["_condor_COLLECTOR_HOST"]
    if SAVE_COLLECTOR_HOST:
        condor.COLLECTOR_HOST = SAVE_COLLECTOR_HOST
        utils.ONSITE_SITE_NAME = SAVE_ONSITE_SITE_NAME


class SetPool(argparse.Action):
    """Action to store the pool info for the given pool"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Union[None, str] = None,
    ) -> None:
        set_pool(values)
        setattr(namespace, self.dest, values)
