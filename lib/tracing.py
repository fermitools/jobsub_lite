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
"""
   Make an as_span decorator to help us log traces with a jaeger trace service
"""

from functools import wraps
import os
import sys
import logging
from typing import Dict, Any, Callable, TypeVar

# at the moment jaeger_client is installed with pip --user...
sys.path.append(f"{os.environ['HOME']}/.local/lib/python3.6/site-packages")

# pylint: disable-next=wrong-import-position
from jaeger_client import Config  # type: ignore


def init_tracer(service: str) -> Any:
    """get the initial trace context"""
    logging.getLogger("").handlers = []
    logging.basicConfig(format="%(message)s", level=logging.ERROR)

    config = Config(
        config={
            "sampler": {
                "type": "const",
                "param": 1,
            },
            "logging": True,
        },
        service_name=service,
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()


tracer = init_tracer("jobsub_lite")

F = TypeVar("F", bound=Callable[..., Any])


def as_span(name: str, is_main: bool = False) -> Callable[[F], F]:
    """outer function returning the decorator, binds the name and is_main symbols"""
    logging.getLogger("").handlers = []

    def as_span_inner(func: F) -> F:
        """
        all purpose tracing decorator. Calls function f in an opentelemetry span,
        and if we have the is_main flag set, closes out the tracer at the end.
        One should of course only use the is_main flag once on the main routine.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore
            """wrapper that does the span around the call to the original function."""
            # pylint: disable-next=unused-variable
            with tracer.start_active_span(name) as scope:
                res = func(*args, **kwargs)
            if is_main:
                tracer.close()
            return res

        return wrapper  # type: ignore

    return as_span_inner
