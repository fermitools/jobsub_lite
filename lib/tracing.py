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
import datetime
import os
import sys
import socket
import logging
from typing import Dict, Any, Callable, TypeVar, Optional, List

# opentelemetry makes this obnoxious warning about nanosecond accuracy in python 3.6
# squelch it before we import the modules
class nanosecond_warning_filter(logging.Filter):
    def filter(self, lr: logging.LogRecord) -> bool:
        if str(lr).find("millisecond precision") > 0:
            return False
        return True


logging.getLogger("opentelemetry.util._time").addFilter(nanosecond_warning_filter())

try:
    # from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter # type: ignore
    # from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter # type: ignore
    # pylint: disable-next=wrong-import-position
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
    from opentelemetry import trace  # type: ignore
    from opentelemetry.context import Context  # type: ignore
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator  # type: ignore

    resource = Resource(attributes={"service.name": "fife"})

    trace.set_tracer_provider(TracerProvider(resource=resource))

    # otlp_exporter = OTLPSpanExporter(
    #    endpoint="https://landscape.fnal.gov/jaeger-collector/api/traces"
    # )
    # span_processor = BatchSpanProcessor(otlp_exporter)

    jaeger_exporter = JaegerExporter(
        collector_endpoint=os.environ["OTEL_EXPORTER_JAEGER_ENDPOINT"]
    )
    span_processor = BatchSpanProcessor(jaeger_exporter)

    trace.get_tracer_provider().add_span_processor(span_processor)

    tracer = trace.get_tracer("jobsub_lite")

    def get_current_span():  # type: ignore
        return trace.get_current_span()

    def get_propagator_carrier() -> Dict[str, str]:
        carrier: Dict[str, str] = {}
        TraceContextTextMapPropagator().inject(carrier)
        return carrier

except:
    # if we can't import the stuff, here's a little mock so we don't crash
    print("Note: tracing not available here.")
    logging.exception("importing tracing")
    print("")
    print("Continuing without tracing...")

    class Context:  # type: ignore
        def __init__(self):  # type: ignore
            pass

        def __enter__(self):  # type: ignore
            pass

        def __exit__(self, *args):  # type: ignore
            pass

    class Tracer:
        def start_as_current_span(self, name: str) -> Context:
            return Context()

        def add_event(
            self, name: str, attributes: Optional[Dict[str, str]] = None
        ) -> None:
            return

    def get_current_span():  # type: ignore
        return Tracer()

    tracer = Tracer()

    def get_propagator_carrier() -> Dict[str, str]:
        return {"traceparent": ""}


F = TypeVar("F", bound=Callable[..., Any])


def add_event(name: str, attributes: Optional[Dict[str, str]] = None) -> None:
    span = get_current_span()  # type: ignore
    span.add_event(name, attributes)


def start_as_current_span(name: str) -> Context:
    return tracer.start_as_current_span(name)


def as_span(
    name: str,
    arg_attrs: List[str] = [],
    is_main: bool = False,
    return_attr: bool = True,
) -> Callable[[F], F]:

    """outer function returning the decorator,
    binds the name,is_main,arg_attrs,return_attr symbols"""

    logging.getLogger("").handlers = []

    def as_span_inner(func: F) -> F:
        """
        all purpose tracing decorator. Calls function f in an opentelemetry span,
        and if we have the is_main flag set, closes out the tracer at the end.
        The is_main was added 'cause gthe g
        """

        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore
            """wrapper that does the span around the call to the original function."""
            # pylint: disable-next=unused-variable
            with tracer.start_as_current_span(name) as scope:
                if scope:
                    if is_main:
                        scope.set_attribute("argv", sys.argv)

                    if bool(arg_attrs):
                        scope.set_attribute("args", repr(args))

                    if bool(arg_attrs) and arg_attrs[0] == "*":
                        attrlist = kwargs.keys()
                    else:
                        attrlist = arg_attrs  # type: ignore

                    for kw in attrlist:
                        scope.set_attribute(kw, repr(kwargs[kw]))

                res = func(*args, **kwargs)

                if return_attr and scope:
                    scope.set_attribute("returns", repr(res))

            return res

        return wrapper  # type: ignore

    return as_span_inner


#
# log the current time and hostname in a way that also shows up in the
# Jaeger trace...
#


@as_span("log_host_time")
def log_host_time(verbose: int) -> None:
    datestr = str(datetime.datetime.now())
    fqdn = socket.getfqdn()
    msg = f"running on hostname {fqdn} at {datestr}\n"
    add_event("log_host_time", {"host": fqdn, "date": datestr})
    if verbose != 0:
        sys.stderr.write(msg)
