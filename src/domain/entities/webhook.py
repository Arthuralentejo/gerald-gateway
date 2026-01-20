"""OutboundWebhook entity for tracking webhook deliveries."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class WebhookStatus(str, Enum):
    """Status of an outbound webhook."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookEventType(str, Enum):
    """Types of webhook events."""

    PLAN_CREATED = "plan_created"
    DECISION_MADE = "decision_made"


@dataclass
class OutboundWebhook:
    """
    Represents an outbound webhook to be delivered to external systems.

    Webhooks are persisted before sending to ensure delivery tracking
    and enable retry logic for failed deliveries.
    """

    event_type: WebhookEventType
    payload: dict[str, Any]
    target_url: str
    id: UUID = field(default_factory=uuid4)
    status: WebhookStatus = WebhookStatus.PENDING
    attempts: int = 0
    last_attempt_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def mark_sent(self) -> None:
        """Mark the webhook as successfully sent."""
        self.status = WebhookStatus.SENT
        self.attempts += 1
        self.last_attempt_at = datetime.utcnow()

    def mark_failed(self) -> None:
        """Mark the webhook as failed after all retries exhausted."""
        self.status = WebhookStatus.FAILED
        self.attempts += 1
        self.last_attempt_at = datetime.utcnow()

    def mark_retrying(self) -> None:
        """Mark the webhook as retrying."""
        self.status = WebhookStatus.RETRYING
        self.attempts += 1
        self.last_attempt_at = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": str(self.id),
            "event_type": self.event_type.value,
            "payload": self.payload,
            "target_url": self.target_url,
            "status": self.status.value,
            "attempts": self.attempts,
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
            "created_at": self.created_at.isoformat() + "Z",
        }
