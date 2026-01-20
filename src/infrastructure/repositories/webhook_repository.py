"""PostgreSQL implementation of WebhookRepository."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities import OutboundWebhook, WebhookStatus, WebhookEventType
from src.domain.interfaces import WebhookRepository
from src.infrastructure.database.models import OutboundWebhookModel


class PostgresWebhookRepository(WebhookRepository):
    """
    PostgreSQL implementation of the Webhook repository.

    Uses SQLAlchemy async session for database operations.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, webhook: OutboundWebhook) -> OutboundWebhook:
        """Persist a webhook record to the database."""
        model = OutboundWebhookModel(
            id=str(webhook.id),
            event_type=webhook.event_type.value,
            payload=webhook.payload,
            target_url=webhook.target_url,
            status=webhook.status.value,
            attempts=webhook.attempts,
            last_attempt_at=webhook.last_attempt_at,
            created_at=webhook.created_at,
        )

        self._session.add(model)
        await self._session.flush()

        return webhook

    async def update(self, webhook: OutboundWebhook) -> OutboundWebhook:
        """Update an existing webhook record."""
        stmt = select(OutboundWebhookModel).where(
            OutboundWebhookModel.id == str(webhook.id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise ValueError(f"Webhook {webhook.id} not found")

        model.status = webhook.status.value
        model.attempts = webhook.attempts
        model.last_attempt_at = webhook.last_attempt_at

        await self._session.flush()

        return webhook

    async def get_by_id(self, webhook_id: UUID) -> Optional[OutboundWebhook]:
        """Retrieve a webhook by ID."""
        stmt = select(OutboundWebhookModel).where(
            OutboundWebhookModel.id == str(webhook_id)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_entity(model)

    async def get_pending(self, limit: int = 100) -> List[OutboundWebhook]:
        """Retrieve pending webhooks for retry processing."""
        stmt = (
            select(OutboundWebhookModel)
            .where(
                or_(
                    OutboundWebhookModel.status == WebhookStatus.PENDING.value,
                    OutboundWebhookModel.status == WebhookStatus.RETRYING.value,
                )
            )
            .order_by(OutboundWebhookModel.created_at.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        return [self._to_entity(model) for model in models]

    def _to_entity(self, model: OutboundWebhookModel) -> OutboundWebhook:
        """Convert database model to domain entity."""
        return OutboundWebhook(
            id=UUID(model.id),
            event_type=WebhookEventType(model.event_type),
            payload=model.payload,
            target_url=model.target_url,
            status=WebhookStatus(model.status),
            attempts=model.attempts,
            last_attempt_at=model.last_attempt_at,
            created_at=model.created_at,
        )
