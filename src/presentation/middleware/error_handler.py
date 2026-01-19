"""Error handling middleware and exception handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import structlog

from src.domain.exceptions import (
    DomainException,
    DecisionNotFoundException,
    PlanNotFoundException,
    InvalidDecisionRequestException,
    BankAPIException,
    BankAPITimeoutException,
    UserNotFoundException,
)
from .request_context import get_request_id

logger = structlog.get_logger(__name__)


def error_handler_middleware(app: FastAPI) -> None:
    """
    Register exception handlers with the FastAPI app.

    Maps domain exceptions to appropriate HTTP responses.
    """

    @app.exception_handler(DecisionNotFoundException)
    async def decision_not_found_handler(
        request: Request,
        exc: DecisionNotFoundException,
    ) -> JSONResponse:
        """Handle decision not found errors."""
        return JSONResponse(
            status_code=404,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(PlanNotFoundException)
    async def plan_not_found_handler(
        request: Request,
        exc: PlanNotFoundException,
    ) -> JSONResponse:
        """Handle plan not found errors."""
        return JSONResponse(
            status_code=404,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(UserNotFoundException)
    async def user_not_found_handler(
        request: Request,
        exc: UserNotFoundException,
    ) -> JSONResponse:
        """Handle user not found errors."""
        return JSONResponse(
            status_code=404,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(InvalidDecisionRequestException)
    async def invalid_request_handler(
        request: Request,
        exc: InvalidDecisionRequestException,
    ) -> JSONResponse:
        """Handle invalid request errors."""
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(BankAPITimeoutException)
    async def bank_timeout_handler(
        request: Request,
        exc: BankAPITimeoutException,
    ) -> JSONResponse:
        """Handle bank API timeout errors."""
        logger.error(
            "bank_api_timeout",
            request_id=get_request_id(),
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": exc.code,
                "message": "Service temporarily unavailable. Please try again.",
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(BankAPIException)
    async def bank_error_handler(
        request: Request,
        exc: BankAPIException,
    ) -> JSONResponse:
        """Handle bank API errors."""
        logger.error(
            "bank_api_error",
            request_id=get_request_id(),
            message=exc.message,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=503,
            content={
                "error": exc.code,
                "message": "Unable to process request. Please try again later.",
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request: Request,
        exc: DomainException,
    ) -> JSONResponse:
        """Handle generic domain exceptions."""
        logger.warning(
            "domain_exception",
            request_id=get_request_id(),
            code=exc.code,
            message=exc.message,
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
                "request_id": get_request_id(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected exceptions."""
        logger.exception(
            "unhandled_exception",
            request_id=get_request_id(),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "request_id": get_request_id(),
            },
        )
