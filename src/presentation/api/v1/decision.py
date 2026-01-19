"""Decision API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.application.dto import DecisionRequest
from src.application.services import DecisionService
from src.core.dependencies import get_decision_service
from src.core.metrics import record_decision, track_decision_latency
from src.presentation.schemas import (
    DecisionRequestSchema,
    DecisionResponseSchema,
    DecisionHistoryResponseSchema,
    ErrorResponseSchema,
)
from src.presentation.schemas.decision import (
    DecisionFactorsSchema,
    DecisionSummarySchema,
)

decision_router = APIRouter(
    prefix="/decision",
    responses={
        400: {"model": ErrorResponseSchema, "description": "Invalid request"},
        404: {"model": ErrorResponseSchema, "description": "User not found"},
        503: {"model": ErrorResponseSchema, "description": "Bank API unavailable"},
    },
)


@decision_router.post(
    "",
    response_model=DecisionResponseSchema,
    status_code=200,
    summary="Request BNPL Decision",
    description="""Request a BNPL approval decision and credit limit for a user""",
    responses={
        200: {"description": "Decision processed successfully"},
    },
)
async def create_decision(
    request: DecisionRequestSchema,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> DecisionResponseSchema:
    """
    Request a BNPL decision for a user.

    Returns approval status, credit limit, and repayment plan details.
    """
    dto = DecisionRequest(
        user_id=request.user_id,
        amount_cents_requested=request.amount_cents_requested,
    )

    with track_decision_latency():
        response = await decision_service.make_decision(dto)

    # Record business metrics
    record_decision(response.approved, response.credit_limit_cents)

    return DecisionResponseSchema(
        approved=response.approved,
        credit_limit_cents=response.credit_limit_cents,
        amount_granted_cents=response.amount_granted_cents,
        plan_id=response.plan_id,
        decision_factors=DecisionFactorsSchema(
            avg_daily_balance=response.decision_factors.avg_daily_balance,
            income_ratio=response.decision_factors.income_ratio,
            nsf_count=response.decision_factors.nsf_count,
            risk_score=response.decision_factors.risk_score,
        ),
    )


@decision_router.get(
    "/history",
    response_model=DecisionHistoryResponseSchema,
    summary="Get Decision History",
    description="""
    Retrieve the decision history for a user.

    Returns a list of past decisions ordered by date (newest first).
    """,
    responses={
        200: {"description": "History retrieved successfully"},
    },
)
async def get_decision_history(
    user_id: Annotated[
        str,
        Query(
            min_length=1,
            max_length=255,
            description="User ID to get history for",
        ),
    ],
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of decisions to return"),
    ] = 10,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)] = None,
) -> DecisionHistoryResponseSchema:
    """
    Get recent decision history for a user.

    Returns decisions ordered by created_at descending.
    """
    response = await decision_service.get_decision_history(user_id, limit)

    return DecisionHistoryResponseSchema(
        user_id=response.user_id,
        decisions=[
            DecisionSummarySchema(
                decision_id=d.decision_id,
                approved=d.approved,
                credit_limit_cents=d.credit_limit_cents,
                amount_granted_cents=d.amount_granted_cents,
                created_at=d.created_at,
            )
            for d in response.decisions
        ],
    )
