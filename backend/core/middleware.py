"""
backend/core/middleware.py
---------------------------
Custom ASGI middleware for the DermaAI backend.

RequestIDMiddleware
-------------------
- Generates a unique X-Request-ID UUID for every incoming request.
- Attaches the ID to the request state (request.state.request_id).
- Echoes the ID in the response header so clients can correlate logs.

TimingLoggingMiddleware
-----------------------
- Logs every request: method, path, status code, duration (ms).
- Uses Python's standard logging — plays nicely with logging_config.py.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assign a unique X-Request-ID to every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class TimingLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, and elapsed time for every request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s -> %d  %.1fms  [%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        # Add timing header for client-side observability
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
