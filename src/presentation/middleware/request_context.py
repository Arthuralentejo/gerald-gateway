"""Request context middleware for tracing."""

import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable for request ID
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that sets up request context.

    Generates or extracts a request ID for tracing and adds it to
    the response headers.
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        """Process request and set up context."""
        # Get or generate request ID
        request_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())

        # Set in context variable
        token = request_id_var.set(request_id)

        try:
            # Process request
            response = await call_next(request)

            # Add request ID to response headers
            response.headers[self.HEADER_NAME] = request_id

            return response
        finally:
            # Reset context
            request_id_var.reset(token)
