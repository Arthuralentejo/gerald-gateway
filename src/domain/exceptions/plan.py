from .base import DomainException


class PlanNotFoundException(DomainException):
    def __init__(self, plan_id: str):
        super().__init__(
            message=f"Plan not found: {plan_id}",
            code="PLAN_NOT_FOUND",
        )
        self.plan_id = plan_id
