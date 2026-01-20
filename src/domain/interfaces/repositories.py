"""Abstract repository interfaces for domain entities."""

from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from src.domain.entities import Decision, Plan, OutboundWebhook


class DecisionRepository(ABC):
    """Repository for persisting and retrieving credit decisions."""
    @abstractmethod
    async def save(self, decision: Decision) -> Decision: ...

    @abstractmethod
    async def get_by_id(self, decision_id: UUID) -> Optional[Decision]: ...

    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Decision]: ...


class PlanRepository(ABC):
    """Repository for persisting and retrieving payment plans."""

    @abstractmethod
    async def save(self, plan: Plan) -> Plan: ...

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> Optional[Plan]: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> List[Plan]: ...


class WebhookRepository(ABC):
    """Repository for persisting and retrieving outbound webhooks."""

    @abstractmethod
    async def save(self, webhook: OutboundWebhook) -> OutboundWebhook: ...

    @abstractmethod
    async def update(self, webhook: OutboundWebhook) -> OutboundWebhook: ...

    @abstractmethod
    async def get_by_id(self, webhook_id: UUID) -> Optional[OutboundWebhook]: ...

    @abstractmethod
    async def get_pending(self, limit: int = 100) -> List[OutboundWebhook]: ...
