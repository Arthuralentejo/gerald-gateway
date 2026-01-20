"""
Integration tests for data persistence.

These tests verify:
1. GET /v1/plan/{plan_id} - Retrieve repayment plan with correct schedule
2. Decision and plan data are properly persisted
3. Installment calculations are correct
"""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from uuid import UUID


# =============================================================================
# GET /v1/plan/{plan_id} Tests
# =============================================================================

class TestPlanRetrieval:
    """Tests for GET /v1/plan/{plan_id} endpoint."""

    @pytest.mark.asyncio
    async def test_plan_retrieval_returns_correct_schedule(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """
        GET /v1/plan/{plan_id} should return the correct repayment schedule.

        The plan should have:
        - 4 installments
        - Bi-weekly due dates (14 days apart)
        - Amounts that sum to total granted
        """
        # First, create a decision to get a plan
        decision_response = await client.post("/v1/decision", json=user_good_request)
        assert decision_response.status_code == 200

        decision_data = decision_response.json()

        # Skip if not approved (no plan created)
        if not decision_data["approved"]:
            pytest.skip("User was not approved, no plan to test")

        plan_id = decision_data["plan_id"]
        amount_granted = decision_data["amount_granted_cents"]

        # Fetch the plan
        plan_response = await client.get(f"/v1/plan/{plan_id}")

        assert plan_response.status_code == 200

        plan_data = plan_response.json()

        # Verify plan structure
        assert plan_data["plan_id"] == plan_id
        assert plan_data["user_id"] == user_good_request["user_id"]
        assert plan_data["total_cents"] == amount_granted

        # Verify 4 installments
        installments = plan_data["installments"]
        assert len(installments) == 4

        # Verify installments sum to total
        installment_total = sum(inst["amount_cents"] for inst in installments)
        assert installment_total == amount_granted

        # Verify each installment has required fields
        for inst in installments:
            assert "installment_id" in inst
            assert "due_date" in inst
            assert "amount_cents" in inst
            assert "status" in inst
            assert inst["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_plan_installments_are_bi_weekly(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Installments should be spaced 14 days (bi-weekly) apart."""
        # Create a decision
        decision_response = await client.post("/v1/decision", json=user_good_request)
        decision_data = decision_response.json()

        if not decision_data["approved"]:
            pytest.skip("User was not approved")

        # Fetch the plan
        plan_response = await client.get(f"/v1/plan/{decision_data['plan_id']}")
        plan_data = plan_response.json()

        installments = plan_data["installments"]
        due_dates = [date.fromisoformat(inst["due_date"]) for inst in installments]

        # Check that each subsequent due date is 14 days after the previous
        for i in range(1, len(due_dates)):
            days_apart = (due_dates[i] - due_dates[i - 1]).days
            assert days_apart == 14, f"Expected 14 days between installments, got {days_apart}"

    @pytest.mark.asyncio
    async def test_plan_first_installment_is_14_days_from_today(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """First installment should be due 14 days from creation date."""
        # Create a decision
        decision_response = await client.post("/v1/decision", json=user_good_request)
        decision_data = decision_response.json()

        if not decision_data["approved"]:
            pytest.skip("User was not approved")

        # Fetch the plan
        plan_response = await client.get(f"/v1/plan/{decision_data['plan_id']}")
        plan_data = plan_response.json()

        first_due_date = date.fromisoformat(plan_data["installments"][0]["due_date"])
        expected_date = date.today() + timedelta(days=14)

        assert first_due_date == expected_date

    @pytest.mark.asyncio
    async def test_plan_installments_handle_uneven_division(
        self,
        client: AsyncClient,
    ):
        """
        When amount doesn't divide evenly by 4, remainder should go to first installment.

        Example: $100.03 (10003 cents) / 4 = 2500.75
        - Installment 1: 2503 cents (base + remainder)
        - Installments 2-4: 2500 cents each
        - Total: 10003 cents
        """
        # Request an amount that doesn't divide evenly by 4
        response = await client.post("/v1/decision", json={
            "user_id": "user_good",
            "amount_cents_requested": 10003,  # $100.03
        })

        data = response.json()

        if not data["approved"] or data["amount_granted_cents"] != 10003:
            pytest.skip("Amount was capped or user declined")

        plan_response = await client.get(f"/v1/plan/{data['plan_id']}")
        plan_data = plan_response.json()

        installments = plan_data["installments"]
        amounts = [inst["amount_cents"] for inst in installments]

        # Total should be exact
        assert sum(amounts) == 10003

        # First installment should have the remainder
        base_amount = 10003 // 4  # 2500
        remainder = 10003 % 4  # 3

        assert amounts[0] == base_amount + remainder  # 2503

    @pytest.mark.asyncio
    async def test_plan_not_found_returns_404(
        self,
        client: AsyncClient,
    ):
        """Requesting a non-existent plan should return 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/v1/plan/{fake_uuid}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_plan_invalid_uuid_returns_422(
        self,
        client: AsyncClient,
    ):
        """Requesting with invalid UUID format should return 422."""
        response = await client.get("/v1/plan/not-a-valid-uuid")

        assert response.status_code == 422


# =============================================================================
# Decision Persistence Tests
# =============================================================================

class TestDecisionPersistence:
    """Tests for decision data persistence."""

    @pytest.mark.asyncio
    async def test_decision_persisted_to_database(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Decisions should be persisted and retrievable via history."""
        # Create a decision
        decision_response = await client.post("/v1/decision", json=user_good_request)
        assert decision_response.status_code == 200
        decision_data = decision_response.json()

        # Retrieve via history
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_good_request['user_id']}"
        )
        assert history_response.status_code == 200

        history_data = history_response.json()
        assert len(history_data["decisions"]) >= 1

        # Find our decision in history
        found = False
        for hist_decision in history_data["decisions"]:
            if hist_decision["approved"] == decision_data["approved"] and \
               hist_decision["credit_limit_cents"] == decision_data["credit_limit_cents"]:
                found = True
                break

        assert found, "Decision not found in history"

    @pytest.mark.asyncio
    async def test_declined_decisions_are_persisted(
        self,
        client: AsyncClient,
        user_overdraft_request: dict,
    ):
        """Declined decisions should also be persisted."""
        # Create a declined decision
        decision_response = await client.post("/v1/decision", json=user_overdraft_request)
        assert decision_response.status_code == 200

        decision_data = decision_response.json()
        assert decision_data["approved"] is False

        # Should still appear in history
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_overdraft_request['user_id']}"
        )
        assert history_response.status_code == 200

        history_data = history_response.json()
        assert len(history_data["decisions"]) >= 1

        # Find the declined decision
        found_declined = any(
            d["approved"] is False for d in history_data["decisions"]
        )
        assert found_declined, "Declined decision not found in history"

    @pytest.mark.asyncio
    async def test_decision_history_ordered_by_date_descending(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Decision history should be ordered by created_at descending (newest first)."""
        # Create multiple decisions
        for _ in range(3):
            await client.post("/v1/decision", json=user_good_request)

        # Get history
        history_response = await client.get(
            f"/v1/decision/history?user_id={user_good_request['user_id']}"
        )

        history_data = history_response.json()
        decisions = history_data["decisions"]

        # Verify ordering (newest first)
        for i in range(1, len(decisions)):
            assert decisions[i - 1]["created_at"] >= decisions[i]["created_at"], \
                "History should be ordered by created_at descending"


# =============================================================================
# Plan-Decision Relationship Tests
# =============================================================================

class TestPlanDecisionRelationship:
    """Tests for the relationship between decisions and plans."""

    @pytest.mark.asyncio
    async def test_approved_decision_has_plan_id(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Approved decisions should have a plan_id."""
        response = await client.post("/v1/decision", json=user_good_request)
        data = response.json()

        if data["approved"]:
            assert data["plan_id"] is not None
            # Verify UUID format
            try:
                UUID(data["plan_id"])
            except ValueError:
                pytest.fail(f"plan_id is not a valid UUID: {data['plan_id']}")

    @pytest.mark.asyncio
    async def test_declined_decision_has_no_plan_id(
        self,
        client: AsyncClient,
        user_overdraft_request: dict,
    ):
        """Declined decisions should have plan_id = null."""
        response = await client.post("/v1/decision", json=user_overdraft_request)
        data = response.json()

        assert data["approved"] is False
        assert data["plan_id"] is None

    @pytest.mark.asyncio
    async def test_plan_user_id_matches_decision(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Plan's user_id should match the requesting user."""
        decision_response = await client.post("/v1/decision", json=user_good_request)
        decision_data = decision_response.json()

        if not decision_data["approved"]:
            pytest.skip("User was not approved")

        plan_response = await client.get(f"/v1/plan/{decision_data['plan_id']}")
        plan_data = plan_response.json()

        assert plan_data["user_id"] == user_good_request["user_id"]

    @pytest.mark.asyncio
    async def test_plan_total_equals_amount_granted(
        self,
        client: AsyncClient,
        user_good_request: dict,
    ):
        """Plan's total_cents should equal the amount_granted_cents from decision."""
        decision_response = await client.post("/v1/decision", json=user_good_request)
        decision_data = decision_response.json()

        if not decision_data["approved"]:
            pytest.skip("User was not approved")

        plan_response = await client.get(f"/v1/plan/{decision_data['plan_id']}")
        plan_data = plan_response.json()

        assert plan_data["total_cents"] == decision_data["amount_granted_cents"]
