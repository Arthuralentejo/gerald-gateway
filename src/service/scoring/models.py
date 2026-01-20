"""Data models for the scoring engine."""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from enum import Enum


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


@dataclass
class Transaction:
    """Bank transaction data for risk analysis."""

    date: date
    amount_cents: int
    balance_cents: int
    type: TransactionType
    nsf: bool = False
    description: str = ""

    @property
    def is_credit(self) -> bool:
        return self.type == TransactionType.CREDIT

    @property
    def is_debit(self) -> bool:
        return self.type == TransactionType.DEBIT


@dataclass
class DecisionFactors:
    """Computed risk factors contributing to a decision."""

    avg_daily_balance: float
    income_ratio: float
    nsf_count: int
    risk_score: int


@dataclass
class Decision:
    """Scoring engine decision result."""

    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    plan_id: Optional[str]
    decision_factors: DecisionFactors

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "credit_limit_cents": self.credit_limit_cents,
            "amount_granted_cents": self.amount_granted_cents,
            "plan_id": self.plan_id,
            "decision_factors": {
                "avg_daily_balance": self.decision_factors.avg_daily_balance,
                "income_ratio": self.decision_factors.income_ratio,
                "nsf_count": self.decision_factors.nsf_count,
                "risk_score": self.decision_factors.risk_score,
            },
        }
