"""API endpoints for payment plan retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path

from src.application.services import PlanService
from src.core.dependencies import get_plan_service
from src.presentation.schemas import PlanResponseSchema, ErrorResponseSchema

plan_router = APIRouter(prefix="/plan")


@plan_router.get(
    "/{plan_id}",
    response_model=PlanResponseSchema,
    summary="Get Repayment Plan",
    description="""
    Retrieve a repayment plan by its ID.

    Returns the plan details including all installment payments with
    their due dates, amounts, and current status.
    """,
    responses={
        200: {"description": "Plan retrieved successfully"},
        404: {"model": ErrorResponseSchema, "description": "Plan not found"},
    },
)
async def get_plan(
    plan_id: Annotated[
        UUID,
        Path(description="UUID of the plan to retrieve"),
    ],
    plan_service: Annotated[PlanService, Depends(get_plan_service)],
) -> PlanResponseSchema:
    response = await plan_service.get_plan(plan_id)

    return PlanResponseSchema(
        plan_id=response.plan_id,
        user_id=response.user_id,
        total_cents=response.total_cents,
        installments=[
            {
                "installment_id": inst.installment_id,
                "due_date": inst.due_date,
                "amount_cents": inst.amount_cents,
                "status": inst.status,
            }
            for inst in response.installments
        ],
    )
