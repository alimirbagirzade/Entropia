"""API hardening middleware: security headers, rate limiting, metrics timing
(Module 20 §11, Stage 8b).

- Security headers ride EVERY response (API-appropriate CSP; HSTS only in
  production where TLS terminates in front of the process).
- Rate limiting is an in-process fixed 60s window keyed by the dev-mode actor
  header (``X-Actor-Id``) or the client address, with a separate (stricter)
  budget for write methods. Opt-in via ``RATE_LIMIT_ENABLED`` — the durable
  authorization line stays in the application commands; this only sheds load.
- Metrics timing feeds the per-process golden signals.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from entropia.apps.api.deps import ACTOR_ID_HEADER
from entropia.config import get_settings
from entropia.infrastructure.observability import metrics
from entropia.shared.responses import ErrorBody, ErrorResponse

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_EXEMPT_SUFFIXES = ("/health/live", "/health/ready", "/metrics")
_WINDOW_SECONDS = 60


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'")
        if get_settings().is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response


class FixedWindowRateLimiter:
    """Fixed 60s window per (key, class). In-process by design (Module 20 §11):
    each API replica sheds its own load; the durable guarantees live below."""

    _MAX_TRACKED_KEYS = 10_000

    def __init__(self) -> None:
        self._windows: dict[tuple[str, str], tuple[int, int]] = {}

    def check(self, key: str, limit_class: str, limit: int) -> tuple[bool, int, int]:
        """-> (allowed, remaining, reset_epoch_seconds)."""
        # Bounded memory under key churn (X-Actor-Id is client-supplied in
        # dev-mode): drop expired windows first; under a same-window flood,
        # evict oldest entries — resetting a flooding key's counter is an
        # acceptable trade for a hard memory cap.
        if len(self._windows) >= self._MAX_TRACKED_KEYS:
            self.prune()
            while len(self._windows) >= self._MAX_TRACKED_KEYS:
                self._windows.pop(next(iter(self._windows)))
        now = int(time.time())
        window_start = now - (now % _WINDOW_SECONDS)
        reset_at = window_start + _WINDOW_SECONDS
        bucket = (key, limit_class)
        start, count = self._windows.get(bucket, (window_start, 0))
        if start != window_start:
            count = 0
        if count >= limit:
            self._windows[bucket] = (window_start, count)
            return False, 0, reset_at
        self._windows[bucket] = (window_start, count + 1)
        return True, limit - count - 1, reset_at

    def prune(self) -> None:
        now = int(time.time())
        window_start = now - (now % _WINDOW_SECONDS)
        self._windows = {k: v for k, v in self._windows.items() if v[0] == window_start}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, limiter: FixedWindowRateLimiter | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._limiter = limiter or FixedWindowRateLimiter()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.endswith(_EXEMPT_SUFFIXES):
            return await call_next(request)

        settings = get_settings()
        actor_id = request.headers.get(ACTOR_ID_HEADER)
        client_host = request.client.host if request.client else "unknown"
        key = actor_id or f"ip:{client_host}"
        if request.method in _WRITE_METHODS:
            limit_class, limit = "write", settings.rate_limit_write_per_minute
        elif actor_id:
            limit_class, limit = "read", settings.rate_limit_authenticated_per_minute
        else:
            limit_class, limit = "read", settings.rate_limit_anonymous_per_minute

        allowed, remaining, reset_at = self._limiter.check(key, limit_class, limit)
        if not allowed:
            retry_after = max(1, reset_at - int(time.time()))
            body = ErrorResponse(
                error=ErrorBody(
                    code="RATE_LIMITED",
                    message="Too many requests; retry after the current window resets.",
                    details=[],
                    request_id=getattr(request.state, "request_id", None),
                    correlation_id=getattr(request.state, "correlation_id", None),
                )
            )
            return JSONResponse(
                status_code=429,
                content=body.model_dump(),
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        response.headers.setdefault("X-RateLimit-Reset", str(reset_at))
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        metrics.request_started()
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Only a RESOLVED route template may label the registry: raw paths
            # (404 scans) are attacker-controlled and would grow label
            # cardinality without bound.
            route = request.scope.get("route")
            path_template = getattr(route, "path_format", None) or "unmatched"
            metrics.request_finished(
                request.method, path_template, status, time.perf_counter() - started
            )


__all__ = [
    "FixedWindowRateLimiter",
    "MetricsMiddleware",
    "RateLimitMiddleware",
    "SecurityHeadersMiddleware",
]
