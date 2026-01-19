"""Plan service - handles plan retrieval use cases."""

from uuid import UUID

import structlog

from src.domain.exceptions import PlanNotFoundException
from src.domain.interfaces import PlanRepository
from src.application.dto import PlanResponse

logger = structlog.get_logger(__name__)


class PlanService:
    """
    Application service for repayment plan use cases.

    Handles plan retrieval and status operations.
    """

    def __init__(self, plan_repository: PlanRepository):
        self._plan_repo = plan_repository

    async def get_plan(self, plan_id: UUID) -> PlanResponse:
        """
        Retrieve a repayment plan by ID.

        Args:
            plan_id: The plan's unique identifier

        Returns:
            PlanResponse with plan details and installments

        Raises:
            PlanNotFoundException: If plan not found
        """
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
        """
        Retrieve all plans for a user.

        Args:
            user_id: The user's identifier

        Returns:
            List of PlanResponse objects
        """
        plans = await self._plan_repo.get_by_user_id(user_id)

        logger.info(
            "user_plans_retrieved",
            user_id=user_id,
            count=len(plans),
        )

        return [PlanResponse.from_entity(plan) for plan in plans]
