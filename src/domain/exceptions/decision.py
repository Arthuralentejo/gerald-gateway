"""Decision-related domain exceptions."""

from .base import DomainException


class DecisionNotFoundException(DomainException):
    """Raised when a decision cannot be found."""

    def __init__(self, decision_id: str):
        super().__init__(
            message=f"Decision not found: {decision_id}",
            code="DECISION_NOT_FOUND",
        )
        self.decision_id = decision_id


class InvalidDecisionRequestException(DomainException):
    """Raised when a decision request is invalid."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            code="INVALID_DECISION_REQUEST",
        )
