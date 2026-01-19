"""Decision-related Pydantic schemas."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DecisionRequestSchema(BaseModel):
    """Schema for POST /v1/decision request body."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_good",
                    "amount_cents_requested": 40000,
                }
            ]
        }
    )
    user_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier for the user",
        examples=["user_good"],
    )
    amount_cents_requested: int = Field(
        ...,
        gt=0,
        description="Amount requested in cents",
        examples=[40000],
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Ensure user_id is not just whitespace."""
        if not v.strip():
            raise ValueError("user_id cannot be empty or whitespace")
        return v.strip()


class DecisionFactorsSchema(BaseModel):
    """Schema for decision factors in the response."""

    avg_daily_balance: float = Field(
        ...,
        description="Average daily balance in dollars",
        examples=[1200.50],
    )
    income_ratio: float = Field(
        ...,
        description="Ratio of income to spending",
        examples=[2.3],
    )
    nsf_count: int = Field(
        ...,
        ge=0,
        description="Number of NSF/overdraft events",
        examples=[0],
    )
    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Composite risk score (0-100, higher is better)",
        examples=[85],
    )


class DecisionResponseSchema(BaseModel):
    """Schema for POST /v1/decision response body."""

    approved: bool = Field(
        ...,
        description="Whether the user is approved for BNPL",
    )
    credit_limit_cents: int = Field(
        ...,
        ge=0,
        description="Maximum credit limit in cents",
        examples=[60000],
    )
    amount_granted_cents: int = Field(
        ...,
        ge=0,
        description="Actual amount granted in cents",
        examples=[40000],
    )
    plan_id: Optional[str] = Field(
        None,
        description="UUID of the repayment plan (null if declined)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    decision_factors: DecisionFactorsSchema = Field(
        ...,
        description="Risk factors that contributed to the decision",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "approved": True,
                    "credit_limit_cents": 60000,
                    "amount_granted_cents": 40000,
                    "plan_id": "550e8400-e29b-41d4-a716-446655440000",
                    "decision_factors": {
                        "avg_daily_balance": 1200.50,
                        "income_ratio": 2.3,
                        "nsf_count": 0,
                        "risk_score": 85,
                    },
                }
            ]
        }
    )


class DecisionSummarySchema(BaseModel):
    """Schema for a decision summary in history."""

    decision_id: str = Field(
        ...,
        description="UUID of the decision",
    )
    approved: bool = Field(
        ...,
        description="Whether the decision was approved",
    )
    credit_limit_cents: int = Field(
        ...,
        ge=0,
        description="Credit limit granted",
    )
    amount_granted_cents: int = Field(
        ...,
        ge=0,
        description="Amount granted",
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 timestamp of the decision",
    )


class DecisionHistoryResponseSchema(BaseModel):
    """Schema for GET /v1/decision/history response."""

    user_id: str = Field(
        ...,
        description="The user's identifier",
    )
    decisions: list[DecisionSummarySchema] = Field(
        ...,
        description="List of past decisions, newest first",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "user_good",
                    "decisions": [
                        {
                            "decision_id": "550e8400-e29b-41d4-a716-446655440000",
                            "approved": True,
                            "credit_limit_cents": 60000,
                            "amount_granted_cents": 40000,
                            "created_at": "2025-09-17T12:00:00Z",
                        }
                    ],
                }
            ]
        }
    )
