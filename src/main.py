"""
Gerald Gateway - Main Application Entry Point

A BNPL Approval & Credit-Limit Service that evaluates users
for Buy Now Pay Later eligibility based on their banking history.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from src import __version__
from src.core.config import settings
from src.core.logging import setup_logging
from src.core.metrics import get_metrics, get_metrics_content_type
from src.infrastructure.database import db_manager
from src.presentation.api import api_router
from src.presentation.middleware import (
    LoggingMiddleware,
    RequestContextMiddleware,
    error_handler_middleware,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Initialize database connection pool
    - Set up logging
    - Clean up on shutdown
    """
    setup_logging()
    db_manager.init()

    logger = structlog.get_logger(__name__)
    logger.info("application_started", version=__version__)

    yield

    await db_manager.close()
    logger.info("application_stopped")


app = FastAPI(
    title="Gerald Gateway",
    description="BNPL Approval & Credit-Limit Service",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestContextMiddleware)

error_handler_middleware(app)

app.include_router(api_router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""

    return RedirectResponse(url="/docs")
