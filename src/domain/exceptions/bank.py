"""Bank API-related domain exceptions."""

from .base import DomainException


class BankAPIException(DomainException):
    """Raised when the bank API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(
            message=message,
            code="BANK_API_ERROR",
        )
        self.status_code = status_code


class BankAPITimeoutException(BankAPIException):
    """Raised when the bank API times out."""

    def __init__(self):
        super().__init__(
            message="Bank API request timed out",
            status_code=None,
        )
        self.code = "BANK_API_TIMEOUT"


class UserNotFoundException(DomainException):
    """Raised when a user is not found in the bank system."""

    def __init__(self, user_id: str):
        super().__init__(
            message=f"User not found: {user_id}",
            code="USER_NOT_FOUND",
        )
        self.user_id = user_id
