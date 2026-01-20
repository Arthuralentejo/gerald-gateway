"""Request ID propagation middleware using context variables."""

import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    return request_id_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Extracts or generates request ID and stores it in context."""

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())
        token = request_id_var.set(request_id)

        try:
            response = await call_next(request)
            response.headers[self.HEADER_NAME] = request_id
            return response
        finally:
            request_id_var.reset(token)
