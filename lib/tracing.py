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

# at the moment opentelemetry is installed with pip --user...
sys.path.append(f"{os.environ['HOME']}/.local/lib/python3.6/site-packages")

# opentelemetry makes this obnoxious warning about nanosecond accuracy in python 3.6
# squelch it before we import the modules
class nanosecond_warning_filter(logging.Filter):
    def filter(self, lr: logging.LogRecord) -> bool:
        if str(lr).find("millisecond precision") > 0:
            return False
        return True

logging.getLogger("opentelemetry.util._time").addFilter(nanosecond_warning_filter())

# pylint: disable-next=wrong-import-position
from opentelemetry import trace  # type: ignore

# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter # type: ignore
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter # type: ignore
from opentelemetry.exporter.jaeger.thrift import JaegerExporter  # type: ignore
from opentelemetry.sdk.resources import Resource  # type: ignore
from opentelemetry.sdk.trace import TracerProvider  # type: ignore
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

resource = Resource(attributes={"service.name": "kretzke-test"})

trace.set_tracer_provider(TracerProvider(resource=resource))

# otlp_exporter = OTLPSpanExporter(
#    endpoint="https://landscape.fnal.gov/jaeger-collector/api/traces"
# )
# span_processor = BatchSpanProcessor(otlp_exporter)

jaeger_exporter = JaegerExporter(
    collector_endpoint="https://landscape.fnal.gov/jaeger-collector/api/traces"
)
span_processor = BatchSpanProcessor(jaeger_exporter)

trace.get_tracer_provider().add_span_processor(span_processor)

tracer = trace.get_tracer("jobsub_lite")

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
            with tracer.start_as_current_span(name) as scope:
                res = func(*args, **kwargs)
            return res

        return wrapper  # type: ignore

    return as_span_inner
