"""Base domain exception."""


class DomainException(Exception):
    """
    Base exception for all domain-level errors.

    Domain exceptions represent business rule violations or
    domain-specific error conditions.
    """

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)
