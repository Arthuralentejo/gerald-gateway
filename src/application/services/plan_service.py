"""Service for retrieving payment plan information."""

from uuid import UUID

import structlog

from src.domain.exceptions import PlanNotFoundException
from src.domain.interfaces import PlanRepository
from src.application.dto import PlanResponse

logger = structlog.get_logger(__name__)


class PlanService:
    """Retrieves payment plans by ID or user."""

    def __init__(self, plan_repository: PlanRepository):
        self._plan_repo = plan_repository

    async def get_plan(self, plan_id: UUID) -> PlanResponse:
        plan = await self._plan_repo.get_by_id(plan_id)

        if plan is None:
            logger.warning("plan_not_found", plan_id=str(plan_id))
            raise PlanNotFoundException(str(plan_id))

        logger.info(
            "plan_retrieved",
            plan_id=str(plan_id),
            user_id=plan.user_id,
            num_installments=len(plan.installments),
        )

        return PlanResponse.from_entity(plan)

    async def get_plans_by_user(self, user_id: str) -> list[PlanResponse]:
        plans = await self._plan_repo.get_by_user_id(user_id)

        logger.info(
            "user_plans_retrieved",
            user_id=user_id,
            count=len(plans),
        )

        return [PlanResponse.from_entity(plan) for plan in plans]
