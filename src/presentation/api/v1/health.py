"""Health check endpoint for service monitoring."""

from fastapi import APIRouter
from pydantic import BaseModel

from src import __version__

health_router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the health status of the service.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version=__version__)
