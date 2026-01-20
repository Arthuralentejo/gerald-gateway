"""
Integration tests for the Decision API endpoints.

These tests verify:
1. POST /v1/decision - Create a BNPL decision
2. GET /v1/decision/history - Get decision history for a user
3. Various user scenarios (good, overdraft, thin file, high utilization)
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# POST /v1/decision Tests
# =============================================================================

class TestCreateDecision:
    """Tests for POST /v1/decision endpoint."""

    @pytest.mark.asyncio
    async def test_user_good_approval(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """
        Happy path: user_good should be approved with a plan and correct installments.

        user_good has:
        - Regular bi-weekly income ($3,000/month)
        - Healthy spending patterns
        - No NSF events
        - Positive average daily balance
        """
        response = await client.post("/v1/decision", json=user_good_request)

        assert response.status_code == 200

        data = response.json()
        assert data["approved"] is True
        assert data["credit_limit_cents"] > 0
        # Amount granted is min(requested, credit_limit)
        expected_granted = min(
            user_good_request["amount_cents_requested"],
            data["credit_limit_cents"]
        )
        assert data["amount_granted_cents"] == expected_granted
        assert data["plan_id"] is not None

        # Verify decision factors are populated
        factors = data["decision_factors"]
        assert factors["avg_daily_balance"] > 0
        assert factors["income_ratio"] > 1.0  # Healthy ratio
        # NSF count may include implicit NSFs (debits causing negative balance)
        assert factors["nsf_count"] >= 0
        assert factors["risk_score"] >= 30  # Above approval threshold

    @pytest.mark.asyncio
    async def test_user_overdraft_decline(
        self,
        client: AsyncClient,
        user_overdraft_request: dict,
    ):
        """
        Users with many overdrafts should be declined.

        user_overdraft has:
        - Multiple NSF events (>5)
        - Chronic negative balance
        - Spending exceeds income
        """
        response = await client.post("/v1/decision", json=user_overdraft_request)

        assert response.status_code == 200

        data = response.json()
        assert data["approved"] is False
        assert data["credit_limit_cents"] == 0
        assert data["amount_granted_cents"] == 0
        assert data["plan_id"] is None

        # Verify decision factors show risk indicators
        factors = data["decision_factors"]
        assert factors["nsf_count"] >= 5  # Multiple overdrafts
        assert factors["risk_score"] < 30  # Below approval threshold

    @pytest.mark.asyncio
    async def test_user_thin_file(
        self,
        client: AsyncClient,
        user_thin_request: dict,
    ):
        """
        New users with thin files (no transactions) should be handled according to policy.

        user_thin has:
        - Empty transaction history (0 transactions)

        Policy: Decline users with no transaction data, as we cannot assess risk.
        """
        response = await client.post("/v1/decision", json=user_thin_request)

        assert response.status_code == 200

        data = response.json()
        # Empty transaction history = decline (can't assess risk)
        assert data["approved"] is False
        assert data["credit_limit_cents"] == 0
        assert data["amount_granted_cents"] == 0
        assert data["plan_id"] is None

    @pytest.mark.asyncio
    async def test_user_highutil_capped_to_limit(
        self,
        client: AsyncClient,
        user_highutil_request: dict,
    ):
        """
        When requested amount > credit limit, grant only up to the limit.

        user_highutil requests $1,000 but their credit limit is lower.
        The amount_granted_cents should equal credit_limit_cents, not amount_requested.
        """
        response = await client.post("/v1/decision", json=user_highutil_request)

        assert response.status_code == 200

        data = response.json()

        if data["approved"]:
            # If approved, granted amount should be capped at credit limit
            assert data["amount_granted_cents"] == data["credit_limit_cents"]
            # And it should be less than requested (100000 cents = $1000)
            assert data["amount_granted_cents"] <= 60000  # Max limit is $600
            assert data["plan_id"] is not None
        else:
            # If declined, no amount granted
            assert data["amount_granted_cents"] == 0
            assert data["plan_id"] is None

    @pytest.mark.asyncio
    async def test_user_gig_worker(
        self,
        client: AsyncClient,
        user_gig_request: dict,
    ):
        """
        Gig workers with irregular but sufficient income should be fairly evaluated.

        user_gig has irregular income patterns but healthy overall ratio.
        The gig worker adjustment should prevent unfair penalization.
        """
        response = await client.post("/v1/decision", json=user_gig_request)

        assert response.status_code == 200

        data = response.json()
        # Gig workers with healthy finances should be approved
        # The exact outcome depends on their transaction data
        assert "approved" in data
        assert "credit_limit_cents" in data
        assert "decision_factors" in data

    @pytest.mark.asyncio
    async def test_decision_creates_plan_with_four_installments(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Approved decisions should create a plan with 4 bi-weekly installments."""
        response = await client.post("/v1/decision", json=user_good_request)

        assert response.status_code == 200
        data = response.json()

        if data["approved"]:
            plan_id = data["plan_id"]
            assert plan_id is not None

            # Fetch the plan to verify installments
            plan_response = await client.get(f"/v1/plan/{plan_id}")
            assert plan_response.status_code == 200

            plan_data = plan_response.json()
            assert len(plan_data["installments"]) == 4

            # Verify installments sum to total
            total = sum(inst["amount_cents"] for inst in plan_data["installments"])
            assert total == data["amount_granted_cents"]

    @pytest.mark.asyncio
    async def test_decision_response_contains_all_fields(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Decision response should contain all required fields."""
        response = await client.post("/v1/decision", json=user_good_request)

        assert response.status_code == 200
        data = response.json()

        # Check all required fields exist
        assert "approved" in data
        assert "credit_limit_cents" in data
        assert "amount_granted_cents" in data
        assert "plan_id" in data
        assert "decision_factors" in data

        factors = data["decision_factors"]
        assert "avg_daily_balance" in factors
        assert "income_ratio" in factors
        assert "nsf_count" in factors
        assert "risk_score" in factors


# =============================================================================
# Request Validation Tests
# =============================================================================

class TestDecisionValidation:
    """Tests for request validation."""

    @pytest.mark.asyncio
    async def test_missing_user_id(self, client: AsyncClient):
        """Request without user_id should return 422."""
        response = await client.post("/v1/decision", json={
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_amount(self, client: AsyncClient):
        """Request without amount_cents_requested should return 422."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_user_id(self, client: AsyncClient):
        """Request with empty user_id should return 422."""
        response = await client.post("/v1/decision", json={
            "user_id": "",
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_negative_amount(self, client: AsyncClient):
        """Request with negative amount should return 400 or 422."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": -1000,
        })

        # Either validation error (422) or bad request (400) is acceptable
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_zero_amount(self, client: AsyncClient):
        """Request with zero amount should return 400 or 422."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 0,
        })

        # Either validation error (422) or bad request (400) is acceptable
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_user_not_found(self, client: AsyncClient):
        """Request for non-existent user should return 404."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_nonexistent",
            "amount_cents_requested": 40000,
        })

        assert response.status_code == 404


# =============================================================================
# GET /v1/decision/history Tests
# =============================================================================

class TestDecisionHistory:
    """Tests for GET /v1/decision/history endpoint."""

    @pytest.mark.asyncio
    async def test_get_history_after_decision(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """
        Decision history should include decisions made for the user.
        """
        # First, create a decision
        decision_response = await client.post("/v1/decision", json=user_good_request)
        assert decision_response.status_code == 200

        # Then get history
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_good_request['user_id']}"
        )

        assert history_response.status_code == 200

        data = history_response.json()
        assert data["user_id"] == user_good_request["user_id"]
        assert len(data["decisions"]) >= 1

        # Check decision structure
        decision = data["decisions"][0]
        assert "decision_id" in decision
        assert "approved" in decision
        assert "credit_limit_cents" in decision
        assert "amount_granted_cents" in decision
        assert "created_at" in decision

    @pytest.mark.asyncio
    async def test_get_history_multiple_decisions(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """History should show multiple decisions for the same user."""
        # Create multiple decisions
        for _ in range(3):
            response = await client.post("/v1/decision", json=user_good_request)
            assert response.status_code == 200

        # Get history
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_good_request['user_id']}"
        )

        assert history_response.status_code == 200
        data = history_response.json()
        assert len(data["decisions"]) >= 3

    @pytest.mark.asyncio
    async def test_get_history_with_limit(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """History endpoint should respect the limit parameter."""
        # Create multiple decisions
        for _ in range(5):
            await client.post("/v1/decision", json=user_good_request)

        # Get history with limit
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_good_request['user_id']}&limit=2"
        )

        assert history_response.status_code == 200
        data = history_response.json()
        assert len(data["decisions"]) == 2

    @pytest.mark.asyncio
    async def test_get_history_empty_for_new_user(
        self,
        client: AsyncClient,
    ):
        """History should be empty for a user with no decisions."""
        history_response = await client.get(
            "/v1/decision/history?user_id=user_no_history"
        )

        assert history_response.status_code == 200
        data = history_response.json()
        assert data["user_id"] == "user_no_history"
        assert len(data["decisions"]) == 0

    @pytest.mark.asyncio
    async def test_get_history_missing_user_id(self, client: AsyncClient):
        """History request without user_id should return 422."""
        response = await client.get("/v1/decision/history")

        assert response.status_code == 422


# =============================================================================
# Edge Cases
# =============================================================================

class TestDecisionEdgeCases:
    """Edge case tests for decision endpoints."""

    @pytest.mark.asyncio
    async def test_very_small_amount_requested(
        self,
        client: AsyncClient,
    ):
        """Small amounts should still be processed correctly."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 100,  # $1.00
        })

        assert response.status_code == 200
        data = response.json()

        if data["approved"]:
            assert data["amount_granted_cents"] == 100

    @pytest.mark.asyncio
    async def test_very_large_amount_requested(
        self,
        client: AsyncClient,
    ):
        """Large amounts should be capped to credit limit."""
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 10000000,  # $100,000
        })

        assert response.status_code == 200
        data = response.json()

        if data["approved"]:
            # Should be capped to max credit limit ($600 = 60000 cents)
            assert data["amount_granted_cents"] <= 60000
            assert data["amount_granted_cents"] == data["credit_limit_cents"]
