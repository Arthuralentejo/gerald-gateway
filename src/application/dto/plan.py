"""Plan-related DTOs."""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class InstallmentDTO:
    """DTO for an installment in the plan response."""

    installment_id: str
    due_date: str
    amount_cents: int
    status: str


@dataclass(frozen=True)
class PlanResponse:
    """Output DTO for a repayment plan."""

    plan_id: str
    user_id: str
    total_cents: int
    installments: List[InstallmentDTO]

    @classmethod
    def from_entity(cls, plan) -> "PlanResponse":
        """Create from a Plan entity."""
        installments = [
            InstallmentDTO(
                installment_id=str(inst.id),
                due_date=inst.due_date.isoformat(),
                amount_cents=inst.amount_cents,
                status=inst.status.value,
            )
            for inst in plan.installments
        ]

        return cls(
            plan_id=str(plan.id),
            user_id=plan.user_id,
            total_cents=plan.total_cents,
            installments=installments,
        )
