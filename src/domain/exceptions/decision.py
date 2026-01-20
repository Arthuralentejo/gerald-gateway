from .base import DomainException


class DecisionNotFoundException(DomainException):
    def __init__(self, decision_id: str):
        super().__init__(
            message=f"Decision not found: {decision_id}",
            code="DECISION_NOT_FOUND",
        )
        self.decision_id = decision_id


class InvalidDecisionRequestException(DomainException):
    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="INVALID_DECISION_REQUEST",
        )
