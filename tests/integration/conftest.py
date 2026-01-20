"""
Fixtures for integration tests.

Provides:
- Test client for FastAPI app
- Mock bank client with test user data
- Mock ledger client
- In-memory database for testing
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from src.main import app
from src.core.dependencies import (
    get_bank_client,
    get_ledger_client,
    get_decision_repository,
    get_plan_repository,
)
from src.domain.entities import Transaction, TransactionType
from src.domain.exceptions import UserNotFoundException, BankAPIException
from src.domain.interfaces import BankAPIClient, LedgerWebhookClient
from src.infrastructure.database import Base, db_manager
from src.infrastructure.repositories import (
    PostgresDecisionRepository,
    PostgresPlanRepository,
)


# =============================================================================
# Test Data Loading
# =============================================================================

ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "mock" / "bank_server" / "bank_stub"


def load_user_transactions(user_id: str) -> List[Transaction]:
    """Load transaction data from the mock data files."""
    file_path = ASSETS_DIR / f"transactions_{user_id}.json"

    if not file_path.exists():
        raise UserNotFoundException(user_id)

    with open(file_path) as f:
        data = json.load(f)

    transactions = []
    for item in data.get("transactions", []):
        date_str = item.get("date", "")
        if "T" in date_str:
            txn_date = datetime.fromisoformat(
                date_str.replace("Z", "+00:00")
            ).date()
        else:
            txn_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        amount = item.get("amount_cents", 0)
        txn_type_str = item.get("type", "").lower()

        if txn_type_str == "credit":
            txn_type = TransactionType.CREDIT
        elif txn_type_str == "debit":
            txn_type = TransactionType.DEBIT
        else:
            txn_type = TransactionType.CREDIT if amount > 0 else TransactionType.DEBIT

        transaction = Transaction(
            date=txn_date,
            amount_cents=amount,
            balance_cents=item.get("balance_cents", 0),
            type=txn_type,
            nsf=item.get("nsf", False),
            description=item.get("description", ""),
        )
        transactions.append(transaction)

    return transactions


# =============================================================================
# Mock Clients
# =============================================================================

class MockBankAPIClient(BankAPIClient):
    """Mock bank client that returns data from test files."""

    def __init__(self, fail_mode: bool = False, fail_for_users: set = None):
        self.fail_mode = fail_mode
        self.fail_for_users = fail_for_users or set()
        self.call_count = 0

    async def get_transactions(self, user_id: str) -> List[Transaction]:
        """Return mock transactions or raise exceptions based on mode."""
        self.call_count += 1

        if self.fail_mode or user_id in self.fail_for_users:
            raise BankAPIException(
                message="Bank API unavailable",
                status_code=500,
            )

        return load_user_transactions(user_id)


class MockLedgerWebhookClient(LedgerWebhookClient):
    """Mock ledger client that tracks webhook calls."""

    def __init__(self, fail_mode: bool = False, fail_count: int = 0):
        self.fail_mode = fail_mode
        self.fail_count = fail_count  # Number of failures before success
        self.call_count = 0
        self.webhooks_sent = []
        self.current_failures = 0

    async def send_plan_created(self, plan) -> bool:
        """Track webhook calls and optionally fail."""
        self.call_count += 1

        if self.fail_mode:
            return False

        if self.current_failures < self.fail_count:
            self.current_failures += 1
            return False

        self.webhooks_sent.append({
            "event": "plan_created",
            "plan_id": str(plan.id),
            "user_id": plan.user_id,
            "total_cents": plan.total_cents,
        })
        return True

    async def send_decision_made(
        self,
        decision_id: str,
        user_id: str,
        approved: bool,
        amount_cents: int,
    ) -> bool:
        """Track decision webhooks."""
        self.call_count += 1

        if self.fail_mode:
            return False

        self.webhooks_sent.append({
            "event": "decision_made",
            "decision_id": decision_id,
            "user_id": user_id,
            "approved": approved,
            "amount_cents": amount_cents,
        })
        return True


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite async engine for testing."""
    # Use SQLite with aiosqlite for async support
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with async_session() as session:
        yield session


# =============================================================================
# Mock Client Fixtures
# =============================================================================

@pytest.fixture
def mock_bank_client() -> MockBankAPIClient:
    """Create a mock bank client."""
    return MockBankAPIClient()


@pytest.fixture
def mock_ledger_client() -> MockLedgerWebhookClient:
    """Create a mock ledger client."""
    return MockLedgerWebhookClient()


@pytest.fixture
def failing_bank_client() -> MockBankAPIClient:
    """Create a bank client that always fails."""
    return MockBankAPIClient(fail_mode=True)


@pytest.fixture
def failing_ledger_client() -> MockLedgerWebhookClient:
    """Create a ledger client that always fails."""
    return MockLedgerWebhookClient(fail_mode=True)


@pytest.fixture
def retrying_ledger_client() -> MockLedgerWebhookClient:
    """Create a ledger client that fails a few times then succeeds."""
    return MockLedgerWebhookClient(fail_count=3)


# =============================================================================
# App Client Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def client(
    test_session: AsyncSession,
    mock_bank_client: MockBankAPIClient,
    mock_ledger_client: MockLedgerWebhookClient,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client with mocked dependencies.

    This client:
    - Uses an in-memory SQLite database
    - Mocks the bank API client with test data files
    - Mocks the ledger webhook client
    """
    # Override dependencies
    async def override_get_decision_repository():
        return PostgresDecisionRepository(test_session)

    async def override_get_plan_repository():
        return PostgresPlanRepository(test_session)

    def override_get_bank_client():
        return mock_bank_client

    def override_get_ledger_client():
        return mock_ledger_client

    app.dependency_overrides[get_decision_repository] = override_get_decision_repository
    app.dependency_overrides[get_plan_repository] = override_get_plan_repository
    app.dependency_overrides[get_bank_client] = override_get_bank_client
    app.dependency_overrides[get_ledger_client] = override_get_ledger_client

    # Create test client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clear overrides
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_failing_bank(
    test_session: AsyncSession,
    failing_bank_client: MockBankAPIClient,
    mock_ledger_client: MockLedgerWebhookClient,
) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client where the bank API always fails."""
    async def override_get_decision_repository():
        return PostgresDecisionRepository(test_session)

    async def override_get_plan_repository():
        return PostgresPlanRepository(test_session)

    def override_get_bank_client():
        return failing_bank_client

    def override_get_ledger_client():
        return mock_ledger_client

    app.dependency_overrides[get_decision_repository] = override_get_decision_repository
    app.dependency_overrides[get_plan_repository] = override_get_plan_repository
    app.dependency_overrides[get_bank_client] = override_get_bank_client
    app.dependency_overrides[get_ledger_client] = override_get_ledger_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_with_failing_ledger(
    test_session: AsyncSession,
    mock_bank_client: MockBankAPIClient,
    failing_ledger_client: MockLedgerWebhookClient,
) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client where the ledger webhook always fails."""
    async def override_get_decision_repository():
        return PostgresDecisionRepository(test_session)

    async def override_get_plan_repository():
        return PostgresPlanRepository(test_session)

    def override_get_bank_client():
        return mock_bank_client

    def override_get_ledger_client():
        return failing_ledger_client

    app.dependency_overrides[get_decision_repository] = override_get_decision_repository
    app.dependency_overrides[get_plan_repository] = override_get_plan_repository
    app.dependency_overrides[get_bank_client] = override_get_bank_client
    app.dependency_overrides[get_ledger_client] = override_get_ledger_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def user_good_request() -> dict:
    """Request body for user_good."""
    return {
        "user_id": "user_good",
        "amount_cents_requested": 40000,
    }


@pytest.fixture
def user_overdraft_request() -> dict:
    """Request body for user_overdraft."""
    return {
        "user_id": "user_overdraft",
        "amount_cents_requested": 30000,
    }


@pytest.fixture
def user_thin_request() -> dict:
    """Request body for user_thin (empty transaction history)."""
    return {
        "user_id": "user_thin",
        "amount_cents_requested": 20000,
    }


@pytest.fixture
def user_highutil_request() -> dict:
    """Request body for user_highutil (high utilization)."""
    return {
        "user_id": "user_highutil",
        "amount_cents_requested": 100000,  # Request more than likely limit
    }


@pytest.fixture
def user_gig_request() -> dict:
    """Request body for user_gig (gig worker)."""
    return {
        "user_id": "user_gig",
        "amount_cents_requested": 25000,
    }


# =============================================================================
# Concurrent-Safe Client Fixture
# =============================================================================

@pytest_asyncio.fixture
async def concurrent_client(
    test_engine,
    mock_bank_client: MockBankAPIClient,
    mock_ledger_client: MockLedgerWebhookClient,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create a test client safe for concurrent requests.

    Unlike the regular `client` fixture, this creates a new session
    for each repository access, avoiding SQLAlchemy session conflicts
    during parallel request handling.
    """
    # Create a session factory that produces new sessions
    async_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Override dependencies with factory-based repositories
    async def override_get_decision_repository():
        session = async_session_factory()
        return PostgresDecisionRepository(session)

    async def override_get_plan_repository():
        session = async_session_factory()
        return PostgresPlanRepository(session)

    def override_get_bank_client():
        return mock_bank_client

    def override_get_ledger_client():
        return mock_ledger_client

    app.dependency_overrides[get_decision_repository] = override_get_decision_repository
    app.dependency_overrides[get_plan_repository] = override_get_plan_repository
    app.dependency_overrides[get_bank_client] = override_get_bank_client
    app.dependency_overrides[get_ledger_client] = override_get_ledger_client

    # Create test client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Clear overrides
    app.dependency_overrides.clear()
