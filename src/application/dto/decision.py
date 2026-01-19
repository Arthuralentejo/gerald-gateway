"""Decision-related DTOs."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class DecisionRequest:
    """Input DTO for requesting a BNPL decision."""

    user_id: str
    amount_cents_requested: int

    def validate(self) -> List[str]:
        """
        Validate the request and return any errors.

        Returns:
            List of validation error messages
        """
        errors = []

        if not self.user_id or not self.user_id.strip():
            errors.append("user_id is required")

        if self.amount_cents_requested <= 0:
            errors.append("amount_cents_requested must be positive")

        return errors


@dataclass(frozen=True)
class DecisionFactorsDTO:
    """DTO for decision factors in response.""" 

    avg_daily_balance: float
    income_ratio: float
    nsf_count: int
    risk_score: int


@dataclass(frozen=True)
class DecisionResponse:
    """Output DTO for a BNPL decision."""

    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    plan_id: Optional[str]
    decision_factors: DecisionFactorsDTO

    @classmethod
    def from_entity(cls, decision) -> "DecisionResponse":
        """Create from a Decision entity."""
        return cls(
            approved=decision.approved,
            credit_limit_cents=decision.credit_limit_cents,
            amount_granted_cents=decision.amount_granted_cents,
            plan_id=str(decision.plan_id) if decision.plan_id else None,
            decision_factors=DecisionFactorsDTO(
                avg_daily_balance=round(decision.decision_factors.avg_daily_balance, 2),
                income_ratio=round(decision.decision_factors.income_ratio, 2),
                nsf_count=decision.decision_factors.nsf_count,
                risk_score=decision.decision_factors.risk_score,
            ),
        )


@dataclass(frozen=True)
class DecisionSummary:
    """Summary of a decision for history listing."""

    decision_id: str
    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    created_at: str


@dataclass(frozen=True)
class DecisionHistoryResponse:
    """Output DTO for decision history."""

    user_id: str
    decisions: List[DecisionSummary]

    @classmethod
    def from_entities(cls, user_id: str, decisions: list) -> "DecisionHistoryResponse":
        """Create from a list of Decision entities."""
        summaries = [
            DecisionSummary(
                decision_id=str(d.id),
                approved=d.approved,
                credit_limit_cents=d.credit_limit_cents,
                amount_granted_cents=d.amount_granted_cents,
                created_at=d.created_at.isoformat() + "Z",
            )
            for d in decisions
        ]
        return cls(user_id=user_id, decisions=summaries)
