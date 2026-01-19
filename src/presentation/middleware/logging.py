"""Logging middleware for request/response logging."""

import time
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .request_context import get_request_id

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all requests and responses.

    Captures timing, status codes, and request metadata in
    structured JSON format.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request and response details."""
        start_time = time.perf_counter()

        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else None

        # Bind request context to logger
        log = logger.bind(
            request_id=get_request_id(),
            method=method,
            path=path,
        )

        log.info("request_started", query=query)

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            log.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as e:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            log.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
            )
            raise
