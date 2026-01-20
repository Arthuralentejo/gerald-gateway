"""FastAPI dependency injection providers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import get_db_session
from src.infrastructure.repositories import (
    PostgresDecisionRepository,
    PostgresPlanRepository,
    PostgresWebhookRepository,
)
from src.infrastructure.clients import (
    HttpBankAPIClient,
    HttpLedgerWebhookClient,
)
from src.application.services import DecisionService, PlanService


async def get_decision_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresDecisionRepository:
    return PostgresDecisionRepository(session)


async def get_plan_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresPlanRepository:
    return PostgresPlanRepository(session)


async def get_webhook_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresWebhookRepository:
    return PostgresWebhookRepository(session)


def get_bank_client() -> HttpBankAPIClient:
    return HttpBankAPIClient()


def get_ledger_client() -> HttpLedgerWebhookClient:
    return HttpLedgerWebhookClient()


async def get_decision_service(
    decision_repo: Annotated[PostgresDecisionRepository, Depends(get_decision_repository)],
    plan_repo: Annotated[PostgresPlanRepository, Depends(get_plan_repository)],
    webhook_repo: Annotated[PostgresWebhookRepository, Depends(get_webhook_repository)],
    bank_client: Annotated[HttpBankAPIClient, Depends(get_bank_client)],
    ledger_client: Annotated[HttpLedgerWebhookClient, Depends(get_ledger_client)],
) -> DecisionService:
    return DecisionService(
        decision_repository=decision_repo,
        plan_repository=plan_repo,
        webhook_repository=webhook_repo,
        bank_client=bank_client,
        ledger_client=ledger_client,
    )


async def get_plan_service(
    plan_repo: Annotated[PostgresPlanRepository, Depends(get_plan_repository)],
) -> PlanService:
    return PlanService(plan_repository=plan_repo)
