"""HTTP implementation of LedgerWebhookClient."""

import asyncio
from typing import Any, Dict

import httpx
import structlog

from src.core.config import settings
from src.core.metrics import (
    track_webhook_latency,
    record_webhook_retry,
    record_webhook_success,
    record_webhook_failure,
)
from src.domain.entities import Plan
from src.domain.interfaces import LedgerWebhookClient

logger = structlog.get_logger(__name__)


class HttpLedgerWebhookClient(LedgerWebhookClient):
    """
    HTTP client for the Ledger Webhook.

    Sends async notifications with retry logic and exponential backoff.
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        max_retries: int = 5,
    ):
        self._base_url = base_url or settings.ledger_webhook_url
        self._timeout = timeout or settings.ledger_webhook_timeout
        self._max_retries = max_retries

    async def send_plan_created(self, plan: Plan) -> bool:
        """
        Send a plan created webhook to the ledger.

        Implements retry with exponential backoff.
        """
        payload = {
            "event": "plan_created",
            "plan_id": str(plan.id),
            "user_id": plan.user_id,
            "total_cents": plan.total_cents,
            "num_installments": len(plan.installments),
            "installments": [
                {
                    "installment_id": str(inst.id),
                    "due_date": inst.due_date.isoformat(),
                    "amount_cents": inst.amount_cents,
                }
                for inst in plan.installments
            ],
            "created_at": plan.created_at.isoformat() + "Z",
        }

        return await self._send_webhook(payload, "plan_created")

    async def send_decision_made(
        self,
        decision_id: str,
        user_id: str,
        approved: bool,
        amount_cents: int,
    ) -> bool:
        """Send a decision made webhook to the ledger."""
        payload = {
            "event": "decision_made",
            "decision_id": decision_id,
            "user_id": user_id,
            "approved": approved,
            "amount_cents": amount_cents,
        }

        return await self._send_webhook(payload, "decision_made")

    async def _send_webhook(
        self,
        payload: Dict[str, Any],
        event_type: str,
    ) -> bool:
        """
        Send a webhook with retry logic.

        Uses exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
        """
        url = self._base_url

        for attempt in range(self._max_retries):
            try:
                with track_webhook_latency():
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(
                            url,
                            json=payload,
                            headers={"Content-Type": "application/json"},
                        )

                        if response.status_code < 400:
                            logger.info(
                                "webhook_sent",
                                event_type=event_type,
                                status_code=response.status_code,
                            )
                            record_webhook_success()
                            return True

                        logger.warning(
                            "webhook_failed",
                            event_type=event_type,
                            status_code=response.status_code,
                            attempt=attempt + 1,
                            response=response.text[:200],
                        )

            except httpx.TimeoutException:
                logger.warning(
                    "webhook_timeout",
                    event_type=event_type,
                    attempt=attempt + 1,
                )
            except Exception as e:
                logger.error(
                    "webhook_error",
                    event_type=event_type,
                    attempt=attempt + 1,
                    error=str(e),
                )

            # Record retry and exponential backoff
            if attempt < self._max_retries - 1:
                record_webhook_retry()
                delay = 2 ** attempt * 0.1
                await asyncio.sleep(delay)

        logger.error(
            "webhook_exhausted_retries",
            event_type=event_type,
            max_retries=self._max_retries,
        )
        record_webhook_failure()
        return False
