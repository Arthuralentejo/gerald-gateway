"""BNPL payment plan domain entities."""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import List
from uuid import UUID, uuid4


class InstallmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Installment:
    """A single scheduled payment within a plan."""

    due_date: date
    amount_cents: int
    plan_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: InstallmentStatus = InstallmentStatus.SCHEDULED
    paid_at: datetime | None = None

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100

    def to_dict(self) -> dict:
        return {
            "installment_id": str(self.id),
            "due_date": self.due_date.isoformat(),
            "amount_cents": self.amount_cents,
            "status": self.status.value,
        }


@dataclass
class Plan:
    """A BNPL payment plan with multiple installments."""

    user_id: str
    decision_id: UUID
    total_cents: int
    installments: List[Installment] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_dollars(self) -> float:
        return self.total_cents / 100

    @property
    def num_installments(self) -> int:
        return len(self.installments)

    def to_dict(self) -> dict:
        return {
            "plan_id": str(self.id),
            "user_id": self.user_id,
            "total_cents": self.total_cents,
            "installments": [inst.to_dict() for inst in self.installments],
            "created_at": self.created_at.isoformat() + "Z",
        }
