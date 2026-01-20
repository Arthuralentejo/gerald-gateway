"""PostgreSQL repository implementation for payment plans."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.entities import Plan, Installment, InstallmentStatus
from src.domain.interfaces import PlanRepository
from src.infrastructure.database.models import PlanModel, InstallmentModel


class PostgresPlanRepository(PlanRepository):
    """PostgreSQL-backed plan repository."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, plan: Plan) -> Plan:
        model = PlanModel(
            id=str(plan.id),
            decision_id=str(plan.decision_id),
            user_id=plan.user_id,
            total_cents=plan.total_cents,
            created_at=plan.created_at,
        )

        for installment in plan.installments:
            inst_model = InstallmentModel(
                id=str(installment.id),
                plan_id=str(plan.id),
                due_date=installment.due_date,
                amount_cents=installment.amount_cents,
                status=installment.status.value,
            )
            model.installments.append(inst_model)

        self._session.add(model)
        await self._session.flush()

        return plan

    async def get_by_id(self, plan_id: UUID) -> Optional[Plan]:
        stmt = (
            select(PlanModel)
            .options(selectinload(PlanModel.installments))
            .where(PlanModel.id == str(plan_id))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def get_by_user_id(self, user_id: str) -> List[Plan]:
        stmt = (
            select(PlanModel)
            .options(selectinload(PlanModel.installments))
            .where(PlanModel.user_id == user_id)
            .order_by(PlanModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def _to_entity(self, model: PlanModel) -> Plan:
        installments = [
            Installment(
                id=UUID(inst.id),
                plan_id=UUID(inst.plan_id),
                due_date=inst.due_date,
                amount_cents=inst.amount_cents,
                status=InstallmentStatus(inst.status),
            )
            for inst in model.installments
        ]

        return Plan(
            id=UUID(model.id),
            user_id=model.user_id,
            total_cents=model.total_cents,
            decision_id=UUID(model.decision_id),
            installments=installments,
            created_at=model.created_at,
        )
