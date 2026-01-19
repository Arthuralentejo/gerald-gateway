"""Transaction entity representing a bank transaction."""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class TransactionType(str, Enum):
    """Type of bank transaction."""

    CREDIT = "credit"  # Money in (income, deposits, refunds)
    DEBIT = "debit"  # Money out (purchases, withdrawals, payments)


@dataclass(frozen=True)
class Transaction:
    """
    Immutable representation of a bank transaction.

    Attributes:
        date: Date of the transaction
        amount_cents: Transaction amount in cents
        balance_cents: Account balance after this transaction
        type: Whether this is a credit or debit
        nsf: True if this transaction resulted in NSF
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
        """Check if this is a credit transaction."""
        return self.type == TransactionType.CREDIT

    @property
    def is_debit(self) -> bool:
        """Check if this is a debit transaction."""
        return self.type == TransactionType.DEBIT

    @property
    def amount_dollars(self) -> float:
        """Get amount in dollars."""
        return self.amount_cents / 100

    @property
    def balance_dollars(self) -> float:
        """Get balance in dollars."""
        return self.balance_cents / 100
