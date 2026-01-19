"""Plan-related Pydantic schemas."""

from pydantic import BaseModel, Field


class InstallmentSchema(BaseModel):
    """Schema for an installment in the plan response."""

    installment_id: str = Field(
        ...,
        description="UUID of the installment",
    )
    due_date: str = Field(
        ...,
        description="Due date in ISO 8601 format (YYYY-MM-DD)",
        examples=["2025-10-01"],
    )
    amount_cents: int = Field(
        ...,
        gt=0,
        description="Installment amount in cents",
        examples=[10000],
    )
    status: str = Field(
        ...,
        description="Current status of the installment",
        examples=["scheduled"],
    )


class PlanResponseSchema(BaseModel):
    """Schema for GET /v1/plan/{plan_id} response."""

    plan_id: str = Field(
        ...,
        description="UUID of the plan",
    )
    user_id: str = Field(
        ...,
        description="User who owns this plan",
    )
    total_cents: int = Field(
        ...,
        gt=0,
        description="Total amount to be repaid",
        examples=[40000],
    )
    installments: list[InstallmentSchema] = Field(
        ...,
        description="List of installment payments",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "plan_id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "user_good",
                    "total_cents": 40000,
                    "installments": [
                        {
                            "installment_id": "...",
                            "due_date": "2025-10-01",
                            "amount_cents": 10000,
                            "status": "scheduled",
                        },
                        {
                            "installment_id": "...",
                            "due_date": "2025-10-15",
                            "amount_cents": 10000,
                            "status": "scheduled",
                        },
                        {
                            "installment_id": "...",
                            "due_date": "2025-10-29",
                            "amount_cents": 10000,
                            "status": "scheduled",
                        },
                        {
                            "installment_id": "...",
                            "due_date": "2025-11-12",
                            "amount_cents": 10000,
                            "status": "scheduled",
                        },
                    ],
                }
            ]
        }
    }
