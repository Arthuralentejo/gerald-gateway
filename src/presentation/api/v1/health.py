"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from src import __version__

health_router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the health status of the service.",
)
async def health_check() -> HealthResponse:
    """Check if the service is healthy."""

    return HealthResponse(status="healthy", version=__version__)
