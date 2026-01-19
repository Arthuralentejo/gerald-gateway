"""HTTP implementation of BankAPIClient."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List

import httpx
import structlog

from src.core.config import settings
from src.core.metrics import (
    track_bank_fetch_latency,
    record_bank_fetch_success,
    record_bank_fetch_failure,
)
from src.domain.entities import Transaction, TransactionType
from src.domain.exceptions import (
    BankAPIException,
    BankAPITimeoutException,
    UserNotFoundException,
)
from src.domain.interfaces import BankAPIClient

logger = structlog.get_logger(__name__)


class HttpBankAPIClient(BankAPIClient):
    """
    HTTP client for the Bank API.

    Fetches transaction history with retry logic and proper error handling.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 3,
    ):
        self._base_url = base_url or settings.bank_api_url
        self._timeout = timeout or settings.bank_api_timeout
        self._max_retries = max_retries

    async def get_transactions(self, user_id: str) -> List[Transaction]:
        """
        Fetch 90-day transaction history for a user.

        Implements retry logic with exponential backoff.
        """
        url = f"{self._base_url}/bank/transactions"
        params = {"user_id": user_id}

        last_exception = None

        for attempt in range(self._max_retries):
            try:
                with track_bank_fetch_latency():
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.get(url, params=params)

                        if response.status_code == 404:
                            record_bank_fetch_failure("not_found")
                            raise UserNotFoundException(user_id)

                        if response.status_code >= 400:
                            record_bank_fetch_failure("error")
                            raise BankAPIException(
                                message=f"Bank API error: {response.text}",
                                status_code=response.status_code,
                            )

                        data = response.json()
                        record_bank_fetch_success()
                        return self._parse_transactions(data)

            except httpx.TimeoutException:
                record_bank_fetch_failure("timeout")
                last_exception = BankAPITimeoutException()
                logger.warning(
                    "bank_api_timeout",
                    user_id=user_id,
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                )
            except (UserNotFoundException, BankAPIException):
                raise
            except Exception as e:
                record_bank_fetch_failure("error")
                last_exception = BankAPIException(
                    message=f"Unexpected error: {str(e)}",
                )
                logger.error(
                    "bank_api_error",
                    user_id=user_id,
                    attempt=attempt + 1,
                    error=str(e),
                )

            # Exponential backoff
            if attempt < self._max_retries - 1:
                await asyncio.sleep(2**attempt * 0.1)

        raise last_exception or BankAPIException("Failed to fetch transactions")

    def _parse_transactions(self, data: Dict[str, Any]) -> List[Transaction]:
        """Parse raw API response into Transaction entities."""
        transactions = []

        for item in data.get("transactions", []):
            date_str = item.get("date", "")
            if "T" in date_str:
                txn_date = datetime.fromisoformat(
                    date_str.replace("Z", "+00:00")
                ).date()
            else:
                txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Determine transaction type
            amount = item.get("amount_cents", item.get("amount", 0))
            if isinstance(amount, float):
                amount = int(amount * 100)

            txn_type_str = item.get("type", "").lower()
            if txn_type_str == "credit":
                txn_type = TransactionType.CREDIT
            elif txn_type_str == "debit":
                txn_type = TransactionType.DEBIT
            else:
                # Infer from amount sign
                txn_type = (
                    TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT
                )

            balance = item.get("balance_cents", item.get("balance", 0))
            if isinstance(balance, float):
                balance = int(balance * 100)

            transaction = Transaction(
                date=txn_date,
                amount_cents=amount,
                balance_cents=balance,
                type=txn_type,
                nsf=item.get("nsf", False),
                description=item.get("description", ""),
            )
            transactions.append(transaction)

        return transactions
