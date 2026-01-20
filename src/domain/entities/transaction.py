"""Bank transaction domain entity."""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


@dataclass(frozen=True)
class Transaction:
    """A bank transaction with amount, balance, and NSF status."""

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

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100

    @property
    def balance_dollars(self) -> float:
        return self.balance_cents / 100
