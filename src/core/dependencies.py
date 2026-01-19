"""Dependency injection for FastAPI."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import get_db_session
from src.infrastructure.repositories import (
    PostgresDecisionRepository,
    PostgresPlanRepository,
)
from src.infrastructure.clients import (
    HttpBankAPIClient,
    HttpLedgerWebhookClient,
)
from src.application.services import DecisionService, PlanService


# Repository dependencies
async def get_decision_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresDecisionRepository:
    """Get a DecisionRepository instance."""
    return PostgresDecisionRepository(session)


async def get_plan_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresPlanRepository:
    """Get a PlanRepository instance."""
    return PostgresPlanRepository(session)


# External client dependencies
def get_bank_client() -> HttpBankAPIClient:
    """Get a BankAPIClient instance."""
    return HttpBankAPIClient()


def get_ledger_client() -> HttpLedgerWebhookClient:
    """Get a LedgerWebhookClient instance."""
    return HttpLedgerWebhookClient()


# Service dependencies
async def get_decision_service(
    decision_repo: Annotated[PostgresDecisionRepository, Depends(get_decision_repository)],
    plan_repo: Annotated[PostgresPlanRepository, Depends(get_plan_repository)],
    bank_client: Annotated[HttpBankAPIClient, Depends(get_bank_client)],
    ledger_client: Annotated[HttpLedgerWebhookClient, Depends(get_ledger_client)],
) -> DecisionService:
    """Get a DecisionService instance with all dependencies."""
    return DecisionService(
        decision_repository=decision_repo,
        plan_repository=plan_repo,
        bank_client=bank_client,
        ledger_client=ledger_client,
    )


async def get_plan_service(
    plan_repo: Annotated[PostgresPlanRepository, Depends(get_plan_repository)],
) -> PlanService:
    """Get a PlanService instance."""
    return PlanService(plan_repository=plan_repo)
