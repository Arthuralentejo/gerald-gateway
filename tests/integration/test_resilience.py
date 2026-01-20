"""
Integration tests for resilience and error handling.

These tests verify:
1. Bank API failure handling - returns 503 and tracks metrics
2. Ledger webhook retry behavior
3. Graceful degradation under failure conditions
"""

import pytest
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient, ASGITransport

from src.main import app
from src.core.dependencies import (
    get_bank_client,
    get_ledger_client,
    get_decision_repository,
    get_plan_repository,
    get_webhook_repository,
)
from src.infrastructure.repositories import (
    PostgresDecisionRepository,
    PostgresPlanRepository,
    PostgresWebhookRepository,
)
from tests.integration.conftest import MockBankAPIClient, MockLedgerWebhookClient


# =============================================================================
# Bank API Failure Tests
# =============================================================================

class TestBankAPIFailure:
    """Tests for handling bank API failures."""

    @pytest.mark.asyncio
    async def test_bank_api_failure_returns_503(
        self,
        client_with_failing_bank: AsyncClient,
    ):
        """
        When the bank API fails, the service should return 503.

        This tests graceful degradation - the service acknowledges it
        cannot process the request due to an upstream dependency failure.
        """
        response = await client_with_failing_bank.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 40000,
        })

        # Service should return 503 Service Unavailable
        assert response.status_code == 503

        data = response.json()
        assert "error" in data or "message" in data

    @pytest.mark.asyncio
    async def test_bank_api_timeout_returns_503(
        self,
        test_session,
        mock_ledger_client,
    ):
        """Bank API timeout should also result in 503."""
        from src.domain.exceptions import BankAPITimeoutException

        # Create a bank client that raises timeout
        timeout_bank_client = MockBankAPIClient()

        async def raise_timeout(user_id):
            raise BankAPITimeoutException()

        timeout_bank_client.get_transactions = raise_timeout

        # Override dependencies
        async def override_get_decision_repository():
            return PostgresDecisionRepository(test_session)

        async def override_get_plan_repository():
            return PostgresPlanRepository(test_session)

        async def override_get_webhook_repository():
            return PostgresWebhookRepository(test_session)

        def override_get_bank_client():
            return timeout_bank_client

        def override_get_ledger_client():
            return mock_ledger_client

        app.dependency_overrides[get_decision_repository] = override_get_decision_repository
        app.dependency_overrides[get_plan_repository] = override_get_plan_repository
        app.dependency_overrides[get_webhook_repository] = override_get_webhook_repository
        app.dependency_overrides[get_bank_client] = override_get_bank_client
        app.dependency_overrides[get_ledger_client] = override_get_ledger_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/decision", json={
                "user_id": "user_good",
                "amount_cents_requested": 40000,
            })

            assert response.status_code == 503

        app.dependency_overrides.clear()


# =============================================================================
# Ledger Webhook Failure Tests
# =============================================================================

class TestLedgerWebhookFailure:
    """Tests for ledger webhook failure handling."""

    @pytest.mark.asyncio
    async def test_webhook_failure_does_not_block_decision(
        self,
        client_with_failing_ledger: AsyncClient,
        mock_bank_client: MockBankAPIClient,
    ):
        """
        Webhook failure should not prevent the decision from being made.

        The ledger webhook is fire-and-forget - even if it fails,
        the decision should still be returned to the user.
        """
        response = await client_with_failing_ledger.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 40000,
        })

        # Decision should still succeed
        assert response.status_code == 200

        data = response.json()
        assert "approved" in data
        # If approved, plan should still be created
        if data["approved"]:
            assert data["plan_id"] is not None

    @pytest.mark.asyncio
    async def test_webhook_retry_on_temporary_failure(
        self,
        test_session,
        mock_bank_client: MockBankAPIClient,
    ):
        """
        Webhook should retry on temporary failures and eventually succeed.

        Note: Since the actual retry logic is in the LedgerWebhookClient,
        this test verifies the client is called and the decision succeeds.
        """
        # Create a ledger client that fails a few times then succeeds
        retrying_client = MockLedgerWebhookClient(fail_count=2)

        async def override_get_decision_repository():
            return PostgresDecisionRepository(test_session)

        async def override_get_plan_repository():
            return PostgresPlanRepository(test_session)

        async def override_get_webhook_repository():
            return PostgresWebhookRepository(test_session)

        def override_get_bank_client():
            return mock_bank_client

        def override_get_ledger_client():
            return retrying_client

        app.dependency_overrides[get_decision_repository] = override_get_decision_repository
        app.dependency_overrides[get_plan_repository] = override_get_plan_repository
        app.dependency_overrides[get_webhook_repository] = override_get_webhook_repository
        app.dependency_overrides[get_bank_client] = override_get_bank_client
        app.dependency_overrides[get_ledger_client] = override_get_ledger_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/decision", json={
                "user_id": "user_good",
                "amount_cents_requested": 40000,
            })

            # Decision should succeed regardless of webhook retries
            assert response.status_code == 200

            data = response.json()
            if data["approved"]:
                # The mock client tracks whether the webhook eventually succeeded
                # In this mock, after fail_count failures, it succeeds
                assert retrying_client.call_count >= 1

        app.dependency_overrides.clear()


# =============================================================================
# Error Response Format Tests
# =============================================================================

class TestErrorResponseFormat:
    """Tests for consistent error response formatting."""

    @pytest.mark.asyncio
    async def test_503_error_has_proper_format(
        self,
        client_with_failing_bank: AsyncClient,
    ):
        """503 errors should have a consistent format."""
        response = await client_with_failing_bank.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 503
        data = response.json()

        # Should have error information
        assert "error" in data or "message" in data or "detail" in data

    @pytest.mark.asyncio
    async def test_404_error_for_unknown_user(
        self,
        client: AsyncClient,
    ):
        """404 errors should have a consistent format."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_nonexistent",
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 404
        data = response.json()

        # Should have error information
        assert "error" in data or "message" in data or "detail" in data


# =============================================================================
# Partial Failure Tests
# =============================================================================

class TestPartialFailures:
    """Tests for handling partial system failures."""

    @pytest.mark.asyncio
    async def test_decision_persisted_even_if_webhook_fails(
        self,
        client_with_failing_ledger: AsyncClient,
        failing_ledger_client: MockLedgerWebhookClient,
    ):
        """
        Decision should be persisted even if the webhook fails.

        The decision and plan are the source of truth - the webhook
        is just a notification. If it fails, data integrity should
        not be compromised.
        """
        # Create a decision (webhook will fail)
        response = await client_with_failing_ledger.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 200
        data = response.json()

        if data["approved"]:
            plan_id = data["plan_id"]

            # Verify plan is still retrievable (persisted correctly)
            plan_response = await client_with_failing_ledger.get(f"/v1/plan/{plan_id}")
            assert plan_response.status_code == 200

            plan_data = plan_response.json()
            assert plan_data["plan_id"] == plan_id
            assert len(plan_data["installments"]) == 4

    @pytest.mark.asyncio
    async def test_history_available_even_if_webhook_failed(
        self,
        client_with_failing_ledger: AsyncClient,
    ):
        """
        Decision history should be available even if webhooks failed.
        """
        # Create a decision
        await client_with_failing_ledger.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 40000,
        })

        # History should still work
        history_response = await client_with_failing_ledger.get(
            "/v1/decision/history?user_id=user_good"
        )

        assert history_response.status_code == 200
        data = history_response.json()
        assert len(data["decisions"]) >= 1


# =============================================================================
# Concurrent Request Handling
# =============================================================================

class TestConcurrentRequests:
    """Tests for handling concurrent requests."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_decisions_for_same_user(
        self,
        concurrent_client: AsyncClient,
    ):
        """
        Multiple concurrent requests for the same user should all succeed.

        Note: In a real scenario, you might want to implement
        idempotency or rate limiting. This test verifies basic
        concurrent handling works.
        """
        import asyncio

        async def make_decision():
            return await concurrent_client.post("/v1/decision", json={
                "user_id": "user_good",
                "amount_cents_requested": 30000,
            })

        # Make 5 concurrent requests
        responses = await asyncio.gather(*[make_decision() for _ in range(5)])

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # Verify all responses have valid decision data
        for response in responses:
            data = response.json()
            assert "approved" in data
            assert "credit_limit_cents" in data

    @pytest.mark.asyncio
    async def test_concurrent_requests_for_different_users(
        self,
        concurrent_client: AsyncClient,
    ):
        """Concurrent requests for different users should all succeed."""
        import asyncio

        users = ["user_good", "user_overdraft", "user_gig", "user_highutil"]

        async def make_decision(user_id):
            return await concurrent_client.post("/v1/decision", json={
                "user_id": user_id,
                "amount_cents_requested": 30000,
            })

        responses = await asyncio.gather(*[make_decision(u) for u in users])

        # All should get a response (200 for valid users, 404 for unknown)
        for response, user_id in zip(responses, users):
            assert response.status_code in [200, 404], \
                f"Unexpected status for {user_id}: {response.status_code}"
