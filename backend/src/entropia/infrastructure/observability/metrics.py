"""Per-process metrics registry (Module 20 §11, Stage 8b).

Golden signals for the API process, rendered in the Prometheus text exposition
format with zero external dependencies. In-process only by design: each process
exposes its own ``/metrics``; aggregation is the scraper's job. DB-backed
gauges (queue depth, outbox lag, lease age) are computed at scrape time by the
metrics route, not stored here.
"""

from __future__ import annotations

import threading
from collections import defaultdict

_BUCKETS: tuple[float, ...] = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)

_lock = threading.Lock()
_requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
_duration_bucket_counts: dict[tuple[str, str], list[int]] = {}
_duration_sum: dict[tuple[str, str], float] = defaultdict(float)
_duration_count: dict[tuple[str, str], int] = defaultdict(int)
_in_flight = 0


def request_started() -> None:
    global _in_flight
    with _lock:
        _in_flight += 1


def request_finished(method: str, path_template: str, status: int, duration_seconds: float) -> None:
    global _in_flight
    key = (method, path_template)
    with _lock:
        _in_flight = max(0, _in_flight - 1)
        _requests_total[(method, path_template, status)] += 1
        counts = _duration_bucket_counts.setdefault(key, [0] * len(_BUCKETS))
        for index, upper in enumerate(_BUCKETS):
            if duration_seconds <= upper:
                counts[index] += 1
        _duration_sum[key] += duration_seconds
        _duration_count[key] += 1


def reset() -> None:
    """Test hook: clear all process counters."""
    global _in_flight
    with _lock:
        _requests_total.clear()
        _duration_bucket_counts.clear()
        _duration_sum.clear()
        _duration_count.clear()
        _in_flight = 0


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def render_process_metrics() -> str:
    """The process-local slice of the exposition (counters + histogram + gauge)."""
    lines: list[str] = []
    with _lock:
        lines.append("# TYPE entropia_http_requests_total counter")
        for (method, path, status), count in sorted(_requests_total.items()):
            lines.append(
                f'entropia_http_requests_total{{method="{_escape(method)}",'
                f'path="{_escape(path)}",status="{status}"}} {count}'
            )
        lines.append("# TYPE entropia_http_request_duration_seconds histogram")
        for (method, path), counts in sorted(_duration_bucket_counts.items()):
            cumulative = 0
            for index, upper in enumerate(_BUCKETS):
                cumulative += counts[index]
                lines.append(
                    f'entropia_http_request_duration_seconds_bucket{{method="{_escape(method)}",'
                    f'path="{_escape(path)}",le="{upper}"}} {cumulative}'
                )
            total = _duration_count[(method, path)]
            lines.append(
                f'entropia_http_request_duration_seconds_bucket{{method="{_escape(method)}",'
                f'path="{_escape(path)}",le="+Inf"}} {total}'
            )
            lines.append(
                f'entropia_http_request_duration_seconds_sum{{method="{_escape(method)}",'
                f'path="{_escape(path)}"}} {_duration_sum[(method, path)]:.6f}'
            )
            lines.append(
                f'entropia_http_request_duration_seconds_count{{method="{_escape(method)}",'
                f'path="{_escape(path)}"}} {total}'
            )
        lines.append("# TYPE entropia_http_requests_in_flight gauge")
        lines.append(f"entropia_http_requests_in_flight {_in_flight}")
    return "\n".join(lines) + "\n"


__all__ = [
    "render_process_metrics",
    "request_finished",
    "request_started",
    "reset",
]
