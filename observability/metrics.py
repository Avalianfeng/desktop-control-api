from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

try:
    from prometheus_client import Counter, Gauge, Histogram  # type: ignore
except Exception:  # pragma: no cover
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore


class _NoopMetric:
    def labels(self, **_labels):  # type: ignore[no-untyped-def]
        return self

    def inc(self, _amount: float = 1.0) -> None:
        return None

    def dec(self, _amount: float = 1.0) -> None:
        return None

    def observe(self, _value: float) -> None:
        return None


def _counter(*args, **kwargs):  # type: ignore[no-untyped-def]
    if Counter is None:
        return _NoopMetric()
    return Counter(*args, **kwargs)


def _gauge(*args, **kwargs):  # type: ignore[no-untyped-def]
    if Gauge is None:
        return _NoopMetric()
    return Gauge(*args, **kwargs)


def _histogram(*args, **kwargs):  # type: ignore[no-untyped-def]
    if Histogram is None:
        return _NoopMetric()
    return Histogram(*args, **kwargs)


HTTP_IN_FLIGHT = _gauge(
    "http_in_flight_requests",
    "Number of in-flight HTTP requests.",
    labelnames=("method", "route"),
)
HTTP_REQUESTS_TOTAL = _counter(
    "http_requests_total",
    "Count of HTTP requests.",
    labelnames=("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_MS = _histogram(
    "http_request_duration_ms",
    "HTTP request latency in milliseconds.",
    labelnames=("method", "route", "status_code"),
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
)


DESKTOP_ACTION_ATTEMPTS_TOTAL = _counter(
    "desktop_action_attempts_total",
    "Count of desktop actions.",
    labelnames=("endpoint", "success"),
)
DESKTOP_ACTION_DURATION_MS = _histogram(
    "desktop_action_duration_ms",
    "Desktop action latency in milliseconds.",
    labelnames=("endpoint", "success"),
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000),
)


DOM_BUILD_DURATION_MS = _histogram(
    "dom_build_duration_ms",
    "Desktop DOM build duration in milliseconds.",
    labelnames=("truncated", "truncated_reason"),
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
)


@dataclass(frozen=True)
class Timer:
    start: float

    @staticmethod
    def start_now() -> "Timer":
        return Timer(start=time.perf_counter())

    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)


def safe_route_label(route: Optional[str], path: str) -> str:
    if route:
        return route
    return path

