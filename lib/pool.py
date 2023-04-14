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
from typing import Dict, Any, Union


@functools.lru_cache(1)
def get_poolmap() -> Any:
    return json.loads(os.environ.get("JOBSUB_POOL_MAP", "{}"))


class SetPool(argparse.Action):
    """Action to store the pool info for the given pool"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Union[None, str] = None,
    ) -> None:
        poolmap = get_poolmap()
        if not values in poolmap:
            raise KeyError(f"--global-pool value must be one of {poolmap.keys()}")
        os.environ["_condor_COLLECTOR_HOST"] = poolmap[values]["collector"]
        condor.COLLECTOR_HOST = poolmap[values]["collector"]
        utils.ONSITE_SITE_NAME = poolmap[values]["onsite"]
        print(
            f'settting _condor_COLLECTOR_HOST to {os.environ["_condor_COLLECTOR_HOST"]}'
        )
        print(f"settting ONSITE_SITE_NAME to {utils.ONSITE_SITE_NAME}")
        setattr(namespace, self.dest, values)
