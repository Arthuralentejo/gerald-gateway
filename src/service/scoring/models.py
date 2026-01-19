"""
Data models for risk scoring.

These models represent the data structures used throughout the scoring pipeline,
from raw bank transactions to final approval decisions.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional
from enum import Enum


class TransactionType(str, Enum):
    """Transaction type indicator."""
    CREDIT = "credit"  # Money in (income, deposits, refunds)
    DEBIT = "debit"    # Money out (purchases, withdrawals, payments)


@dataclass
class Transaction:
    """
    A single bank transaction from the user's 90-day history.

    Attributes:
        date: Date of the transaction
        amount_cents: Transaction amount in cents (positive for credits, negative for debits)
        balance_cents: Account balance after this transaction
        type: Whether this is a credit (money in) or debit (money out)
        nsf: True if this transaction resulted in Non-Sufficient Funds
        description: Human-readable transaction description
    """
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
    """
    Risk factors calculated from transaction history.

    These are the key signals used to determine approval and credit limit.
    All factors are included in the API response for transparency.

    Attributes:
        avg_daily_balance: Average balance over 90 days, in dollars.
            Higher values indicate more financial cushion.
        income_ratio: Ratio of monthly income to monthly spending.
            Values > 1.0 indicate income exceeds spending.
        nsf_count: Number of NSF/overdraft events in the 90-day window.
            Lower is better; 0 is ideal.
        risk_score: Composite score from 0-100 (higher = lower risk).
            Derived from the weighted combination of the above factors.
    """
    avg_daily_balance: float
    income_ratio: float
    nsf_count: int
    risk_score: int


@dataclass
class Decision:
    """
    The final approval decision for a BNPL request.

    Attributes:
        approved: Whether the user is approved for BNPL
        credit_limit_cents: Maximum amount the user can borrow (0 if declined)
        amount_granted_cents: Actual amount granted (min of requested and limit)
        plan_id: UUID of the repayment plan (None if declined)
        decision_factors: The risk factors that led to this decision
    """
    approved: bool
    credit_limit_cents: int
    amount_granted_cents: int
    plan_id: Optional[str]
    decision_factors: DecisionFactors

    def to_dict(self) -> dict:
        """Convert to API response format."""
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
