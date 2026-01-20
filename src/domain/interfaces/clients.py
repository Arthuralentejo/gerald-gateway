"""Abstract client interfaces for external services."""

from abc import ABC, abstractmethod
from typing import List

from src.domain.entities import Transaction, Plan


class BankAPIClient(ABC):
    """Client for fetching transaction data from the bank API."""
    @abstractmethod
    async def get_transactions(self, user_id: str) -> List[Transaction]: ...


class LedgerWebhookClient(ABC):
    """Client for sending webhook notifications to the ledger service."""

    @abstractmethod
    async def send_plan_created(self, plan: Plan) -> bool: ...

    @abstractmethod
    async def send_decision_made(
        self,
        decision_id: str,
        user_id: str,
        approved: bool,
        amount_cents: int,
    ) -> bool: ...
