"""PostgreSQL implementation of DecisionRepository."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.entities import Decision, DecisionFactors
from src.domain.interfaces import DecisionRepository
from src.infrastructure.database.models import DecisionModel


class PostgresDecisionRepository(DecisionRepository):
    """
    PostgreSQL implementation of the Decision repository.

    Uses SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, decision: Decision) -> Decision:
        """Persist a decision to the database."""
        model = DecisionModel(
            id=str(decision.id),
            user_id=decision.user_id,
            requested_cents=decision.amount_requested_cents,
            approved=decision.approved,
            credit_limit_cents=decision.credit_limit_cents,
            amount_granted_cents=decision.amount_granted_cents,
            score_numeric=float(decision.decision_factors.risk_score),
            score_band=self._get_score_band(decision.decision_factors.risk_score),
            created_at=decision.created_at,
        )

        self._session.add(model)
        await self._session.flush()

        return decision

    async def get_by_id(self, decision_id: UUID) -> Optional[Decision]:
        """Retrieve a decision by ID."""
        stmt = (
            select(DecisionModel)
            .options(selectinload(DecisionModel.plan))
            .where(DecisionModel.id == str(decision_id))
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Decision]:
        """Retrieve decisions for a user, ordered by created_at descending."""
        stmt = (
            select(DecisionModel)
            .options(selectinload(DecisionModel.plan))
            .where(DecisionModel.user_id == user_id)
            .order_by(DecisionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def _get_score_band(self, risk_score: int) -> str:
        """Map risk score to a band label."""
        if risk_score >= 95:
            return "excellent"
        elif risk_score >= 85:
            return "very_good"
        elif risk_score >= 75:
            return "good"
        elif risk_score >= 60:
            return "moderate"
        elif risk_score >= 45:
            return "low"
        elif risk_score >= 30:
            return "starter"
        else:
            return "declined"

    def _to_entity(self, model: DecisionModel) -> Decision:
        """Convert database model to domain entity."""
        risk_score = int(model.score_numeric) if model.score_numeric else 0

        return Decision(
            id=UUID(model.id),
            user_id=model.user_id,
            approved=model.approved,
            credit_limit_cents=model.credit_limit_cents,
            amount_requested_cents=model.requested_cents,
            amount_granted_cents=model.amount_granted_cents,
            decision_factors=DecisionFactors(
                avg_daily_balance=0.0,
                income_ratio=0.0,
                nsf_count=0,
                risk_score=risk_score,
            ),
            plan_id=UUID(model.plan.id) if model.plan else None,
            created_at=model.created_at,
        )
