"""External client interfaces."""

from abc import ABC, abstractmethod
from typing import List

from src.domain.entities import Transaction, Plan


class BankAPIClient(ABC):
    """
    Abstract client for the Bank API.

    Fetches transaction history for risk assessment.
    """

    @abstractmethod
    async def get_transactions(self, user_id: str) -> List[Transaction]:
        """
        Fetch 90-day transaction history for a user.

        Args:
            user_id: The user's identifier

        Returns:
            List of transactions from the last 90 days

        Raises:
            UserNotFoundException: If the user doesn't exist
            BankAPIException: If the API returns an error
            BankAPITimeoutException: If the request times out
        """
        ...


class LedgerWebhookClient(ABC):
    """
    Abstract client for the Ledger Webhook.

    Sends async notifications when plans are created.
    """

    @abstractmethod
    async def send_plan_created(self, plan: Plan) -> bool:
        """
        Send a plan created webhook to the ledger.

        Args:
            plan: The plan that was created

        Returns:
            True if the webhook was delivered successfully

        Note:
            Implementations should handle retries with backoff.
        """
        ...

    @abstractmethod
    async def send_decision_made(
        self,
        decision_id: str,
        user_id: str,
        approved: bool,
        amount_cents: int,
    ) -> bool:
        """
        Send a decision made webhook to the ledger.

        Args:
            decision_id: The decision's unique identifier
            user_id: The user's identifier
            approved: Whether the decision was approved
            amount_cents: The amount granted (0 if declined)

        Returns:
            True if the webhook was delivered successfully
        """
        ...
