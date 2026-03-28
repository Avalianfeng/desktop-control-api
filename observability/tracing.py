from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

try:
    from opentelemetry import trace  # type: ignore
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore
    from opentelemetry.trace import Tracer  # type: ignore
except Exception:  # pragma: no cover
    trace = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    Resource = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    Tracer = object  # type: ignore


_configured = False


def configure_tracing(*, service_name: str = "desktop-control-api") -> None:
    global _configured
    if _configured:
        return
    if trace is None or Resource is None or TracerProvider is None:
        _configured = True
        return

    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME") or service_name,
        }
    )
    provider = TracerProvider(resource=resource)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and OTLPSpanExporter is not None and BatchSpanProcessor is not None:
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer(name: str = "desktop-control-api") -> Tracer:
    if trace is None:
        return Tracer()  # type: ignore[call-arg]
    return trace.get_tracer(name)


def set_span_attributes(**attrs: object) -> None:
    if trace is None:
        return
    span = trace.get_current_span()
    if not span:
        return
    for k, v in attrs.items():
        if v is None:
            continue
        span.set_attribute(k, v)


def start_span(name: str, *, tracer: Optional[Tracer] = None):
    if trace is None:
        @contextmanager
        def _noop():
            yield None
        return _noop()
    tr = tracer or get_tracer()
    return tr.start_as_current_span(name)

