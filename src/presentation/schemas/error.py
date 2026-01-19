"""Error response schemas."""

from pydantic import BaseModel, Field


class ErrorResponseSchema(BaseModel):
    """Schema for error responses."""

    error: str = Field(
        ...,
        description="Error code",
        examples=["DECISION_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Decision not found: 550e8400-e29b-41d4-a716-446655440000"],
    )
    request_id: str | None = Field(
        None,
        description="Request ID for tracing",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "DECISION_NOT_FOUND",
                    "message": "Decision not found: 550e8400-e29b-41d4-a716-446655440000",
                    "request_id": "abc123",
                }
            ]
        }
    }
