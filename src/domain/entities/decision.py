"""Decision entity representing a BNPL approval decision."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class DecisionFactors:
    """
    Risk factors that contributed to the decision.

    These are exposed in the API response for transparency.
    """

    avg_daily_balance: float
    income_ratio: float
    nsf_count: int
    risk_score: int

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "avg_daily_balance": round(self.avg_daily_balance, 2),
            "income_ratio": round(self.income_ratio, 2),
            "nsf_count": self.nsf_count,
            "risk_score": self.risk_score,
        }


@dataclass
class Decision:
    """
    Represents a BNPL approval decision.

    This is the core domain entity that encapsulates the result
    of evaluating a user's creditworthiness.
    """

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
        """Get credit limit in dollars."""
        return self.credit_limit_cents / 100

    @property
    def amount_granted_dollars(self) -> float:
        """Get granted amount in dollars."""
        return self.amount_granted_cents / 100

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
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
