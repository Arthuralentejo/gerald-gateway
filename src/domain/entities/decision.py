"""BNPL credit decision domain entity."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DecisionFactors:
    """Risk factors used to calculate the credit decision."""
    avg_daily_balance: float
    income_ratio: float
    nsf_count: int
    risk_score: int

    def to_dict(self) -> dict:
        return {
            "avg_daily_balance": round(self.avg_daily_balance, 2),
            "income_ratio": round(self.income_ratio, 2),
            "nsf_count": self.nsf_count,
            "risk_score": self.risk_score,
        }


@dataclass
class Decision:
    """A BNPL credit decision with approval status and granted amount."""

    user_id: str
    approved: bool
    credit_limit_cents: int
    amount_requested_cents: int
    amount_granted_cents: int
    decision_factors: DecisionFactors
    id: UUID = field(default_factory=uuid4)
    plan_id: Optional[UUID] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def credit_limit_dollars(self) -> float:
        return self.credit_limit_cents / 100

    @property
    def amount_granted_dollars(self) -> float:
        return self.amount_granted_cents / 100

    def to_dict(self) -> dict:
        return {
            "decision_id": str(self.id),
            "user_id": self.user_id,
            "approved": self.approved,
            "credit_limit_cents": self.credit_limit_cents,
            "amount_granted_cents": self.amount_granted_cents,
            "plan_id": str(self.plan_id) if self.plan_id else None,
            "decision_factors": self.decision_factors.to_dict(),
            "created_at": self.created_at.isoformat() + "Z",
        }
