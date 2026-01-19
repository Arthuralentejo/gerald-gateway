"""
Unit Tests for Gerald BNPL Risk Scoring Module.

These tests verify:
1. Risk factor calculations (ADB, income ratio, NSF count)
2. Scoring functions and boundaries
3. Credit limit mapping
4. Thin file handling
5. Complete decision flow

Test Categories:
- test_avg_daily_balance_*: ADB calculation tests
- test_income_spend_ratio_*: Ratio calculation tests
- test_nsf_*: NSF counting tests
- test_score_*: Scoring function tests
- test_credit_limit_*: Limit mapping tests
- test_thin_file_*: Thin file handling tests
- test_decision_*: Integration tests
"""

import pytest
from datetime import date, timedelta

from src.service.scoring.models import Transaction, TransactionType
from src.service.scoring.risk_factors import (
    calculate_avg_daily_balance,
    calculate_income_spend_ratio,
    count_nsf_events,
    calculate_income_consistency,
)
from src.service.scoring.risk_score import (
    score_avg_daily_balance,
    score_income_spend_ratio,
    score_nsf_count,
    calculate_risk_score,
)
from src.service.scoring.credit_limit import (
    score_to_credit_limit_cents,
    get_credit_limit_bucket,
    is_approved,
)
from src.service.scoring.thin_file import (
    is_thin_file,
    handle_thin_file,
)
from src.service.scoring.decision import make_decision, explain_decision


# =============================================================================
# Test Fixtures
# =============================================================================

def make_transaction(
    days_ago: int,
    amount_cents: int,
    balance_cents: int,
    txn_type: TransactionType = TransactionType.DEBIT,
    nsf: bool = False,
    description: str = "",
) -> Transaction:
    """Helper to create transactions relative to today."""
    return Transaction(
        date=date.today() - timedelta(days=days_ago),
        amount_cents=amount_cents,
        balance_cents=balance_cents,
        type=txn_type,
        nsf=nsf,
        description=description,
    )


def generate_healthy_transactions(num_days: int = 90) -> list[Transaction]:
    """Generate transactions for a healthy user (user_good archetype)."""
    transactions = []
    balance = 120000  # Start with $1,200

    for day in range(num_days):
        # Bi-weekly paycheck on days 14, 28, 42, etc.
        if day % 14 == 0:
            balance += 200000  # $2,000 income
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=200000,
                balance_cents=balance,
                txn_type=TransactionType.CREDIT,
                description="Direct Deposit",
            ))

        # Daily spending of ~$50
        if day % 2 == 0:
            balance -= 5000
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=-5000,
                balance_cents=balance,
                txn_type=TransactionType.DEBIT,
                description="Purchase",
            ))

    return transactions


def generate_overdraft_transactions(num_days: int = 90) -> list[Transaction]:
    """Generate transactions for an overdraft-prone user with multiple NSFs."""
    transactions = []
    balance = -5000  # Start in overdraft already

    for day in range(num_days):
        # Sparse, small income that doesn't cover spending
        if day % 30 == 15:  # Income mid-month only
            balance += 80000  # $800 income (not enough)
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=80000,
                balance_cents=balance,
                txn_type=TransactionType.CREDIT,
            ))

        # Heavy, frequent spending that causes overdrafts
        if day % 5 == 0:
            balance -= 15000  # $150 spending
            is_nsf = balance < 0
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=-15000,
                balance_cents=balance,
                txn_type=TransactionType.DEBIT,
                nsf=is_nsf,
            ))

    return transactions


def generate_thin_file_transactions() -> list[Transaction]:
    """Generate minimal transactions (thin file)."""
    return [
        make_transaction(30, 50000, 50000, TransactionType.CREDIT),
        make_transaction(25, -2000, 48000, TransactionType.DEBIT),
        make_transaction(20, -3000, 45000, TransactionType.DEBIT),
        make_transaction(15, 50000, 95000, TransactionType.CREDIT),
        make_transaction(10, -5000, 90000, TransactionType.DEBIT),
    ]


def generate_gig_worker_transactions(num_days: int = 90) -> list[Transaction]:
    """Generate irregular income pattern (gig worker)."""
    transactions = []
    balance = 40000  # $400

    for day in range(num_days):
        # Irregular gig payments
        if day in [3, 5, 8, 15, 18, 25, 30, 35, 45, 50, 60, 70, 75, 85]:
            amount = 15000 + (day % 10) * 5000  # Variable amounts
            balance += amount
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=amount,
                balance_cents=balance,
                txn_type=TransactionType.CREDIT,
            ))

        # Regular spending
        if day % 4 == 0:
            balance -= 4000
            transactions.append(make_transaction(
                days_ago=num_days - day,
                amount_cents=-4000,
                balance_cents=balance,
                txn_type=TransactionType.DEBIT,
            ))

    return transactions


# =============================================================================
# Average Daily Balance Tests
# =============================================================================

class TestAvgDailyBalance:
    """Tests for calculate_avg_daily_balance()."""

    def test_single_transaction(self):
        """Single transaction should carry forward for 90 days."""
        transactions = [make_transaction(0, 10000, 100000)]
        adb = calculate_avg_daily_balance(transactions)
        # Balance of $1000 carried for all 90 days
        assert adb == 1000.0

    def test_carry_forward_on_empty_days(self):
        """Balance should carry forward on days with no transactions."""
        transactions = [
            make_transaction(89, 10000, 50000),   # Day 1: $500
            make_transaction(45, -5000, 100000),  # Day 45: $1000
        ]
        adb = calculate_avg_daily_balance(transactions)
        # First 44 days at $500, remaining 46 days at $1000
        expected = (44 * 500 + 46 * 1000) / 90
        assert abs(adb - expected) < 0.01

    def test_negative_balance(self):
        """Negative balances should be included in average."""
        transactions = [
            make_transaction(89, 5000, 5000),    # $50
            make_transaction(45, -10000, -5000), # -$50
        ]
        adb = calculate_avg_daily_balance(transactions)
        # First 44 days at $50, remaining 46 days at -$50
        expected = (44 * 50 + 46 * (-50)) / 90
        assert abs(adb - expected) < 0.01

    def test_empty_transactions_raises(self):
        """Empty transaction list should raise ValueError."""
        with pytest.raises(ValueError):
            calculate_avg_daily_balance([])

    def test_healthy_user_high_adb(self):
        """Healthy user should have high average daily balance."""
        transactions = generate_healthy_transactions()
        adb = calculate_avg_daily_balance(transactions)
        assert adb > 500  # Should have substantial balance


class TestIncomeSpendRatio:
    """Tests for calculate_income_spend_ratio()."""

    def test_income_exceeds_spending(self):
        """When income > spending, ratio should be > 1."""
        transactions = [
            make_transaction(30, 100000, 100000, TransactionType.CREDIT),
            make_transaction(20, -50000, 50000, TransactionType.DEBIT),
        ]
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio == 2.0  # $1000 income / $500 spending

    def test_spending_exceeds_income(self):
        """When spending > income, ratio should be < 1."""
        transactions = [
            make_transaction(30, 50000, 50000, TransactionType.CREDIT),
            make_transaction(20, -100000, -50000, TransactionType.DEBIT),
        ]
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio == 0.5  # $500 income / $1000 spending

    def test_no_debits_returns_infinity(self):
        """All income with no spending should return infinity."""
        transactions = [
            make_transaction(30, 100000, 100000, TransactionType.CREDIT),
        ]
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio == float('inf')

    def test_no_credits_returns_zero(self):
        """All spending with no income should return 0."""
        transactions = [
            make_transaction(30, -100000, -100000, TransactionType.DEBIT),
        ]
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio == 0.0

    def test_empty_transactions(self):
        """Empty list should return neutral ratio of 1.0."""
        ratio = calculate_income_spend_ratio([])
        assert ratio == 1.0

    def test_healthy_user_ratio(self):
        """Healthy user should have ratio > 1."""
        transactions = generate_healthy_transactions()
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio > 1.0


class TestNSFCount:
    """Tests for count_nsf_events()."""

    def test_no_nsf_events(self):
        """Healthy transactions should have 0 NSF count."""
        transactions = generate_healthy_transactions()
        nsf = count_nsf_events(transactions)
        assert nsf == 0

    def test_explicit_nsf_flag(self):
        """Transactions with nsf=True should be counted."""
        transactions = [
            make_transaction(30, 10000, 10000, TransactionType.CREDIT),
            make_transaction(20, -5000, 5000, TransactionType.DEBIT, nsf=True),
            make_transaction(10, -3000, 2000, TransactionType.DEBIT),
        ]
        nsf = count_nsf_events(transactions)
        assert nsf == 1

    def test_implicit_nsf_negative_balance(self):
        """Debits causing negative balance should be counted as NSF."""
        transactions = [
            make_transaction(30, 10000, 10000, TransactionType.CREDIT),
            make_transaction(20, -5000, 5000, TransactionType.DEBIT),
            make_transaction(10, -10000, -5000, TransactionType.DEBIT),  # Goes negative
        ]
        nsf = count_nsf_events(transactions)
        assert nsf == 1

    def test_multiple_nsf_events(self):
        """Multiple NSF events should all be counted."""
        transactions = generate_overdraft_transactions()
        nsf = count_nsf_events(transactions)
        assert nsf >= 3  # Should have multiple overdrafts

    def test_empty_transactions(self):
        """Empty list should return 0."""
        nsf = count_nsf_events([])
        assert nsf == 0


class TestIncomeConsistency:
    """Tests for calculate_income_consistency()."""

    def test_regular_income_high_consistency(self):
        """Regular bi-weekly income should have high consistency."""
        transactions = generate_healthy_transactions()
        consistency = calculate_income_consistency(transactions)
        assert consistency > 0.5

    def test_irregular_income_low_consistency(self):
        """Gig worker income should have lower consistency."""
        transactions = generate_gig_worker_transactions()
        consistency = calculate_income_consistency(transactions)
        # Gig workers have variable income
        assert 0.0 <= consistency <= 1.0

    def test_insufficient_data(self):
        """Too few credits should return neutral 0.5."""
        transactions = [
            make_transaction(30, 10000, 10000, TransactionType.CREDIT),
        ]
        consistency = calculate_income_consistency(transactions)
        assert consistency == 0.5


# =============================================================================
# Scoring Function Tests
# =============================================================================

class TestScoreAvgDailyBalance:
    """Tests for score_avg_daily_balance()."""

    def test_negative_balance_low_score(self):
        """Negative balance should score 0-20."""
        assert score_avg_daily_balance(-200) == 0  # Very negative
        assert score_avg_daily_balance(-50) < 20   # Slightly negative

    def test_low_balance_moderate_score(self):
        """$0-100 should score 20-40."""
        assert 20 <= score_avg_daily_balance(0) <= 40
        assert 20 <= score_avg_daily_balance(50) <= 40
        assert 20 <= score_avg_daily_balance(100) <= 40

    def test_moderate_balance_good_score(self):
        """$100-500 should score 40-70."""
        assert 40 <= score_avg_daily_balance(200) <= 70
        assert 40 <= score_avg_daily_balance(400) <= 70

    def test_high_balance_excellent_score(self):
        """$1500+ should score 90-100."""
        assert score_avg_daily_balance(1500) >= 90
        assert score_avg_daily_balance(3000) >= 90

    def test_score_boundaries(self):
        """Test exact threshold boundaries."""
        # At boundary between tiers
        assert score_avg_daily_balance(100) >= 40
        assert score_avg_daily_balance(500) >= 70
        assert score_avg_daily_balance(1500) >= 90


class TestScoreIncomeSpendRatio:
    """Tests for score_income_spend_ratio()."""

    def test_low_ratio_low_score(self):
        """Ratio < 0.8 should score 0-25."""
        assert score_income_spend_ratio(0.5) < 25
        assert score_income_spend_ratio(0.7) < 25

    def test_borderline_ratio(self):
        """Ratio 0.8-1.0 should score 25-50."""
        assert 25 <= score_income_spend_ratio(0.9) <= 50

    def test_sustainable_ratio(self):
        """Ratio 1.0-1.3 should score 50-75."""
        assert 50 <= score_income_spend_ratio(1.1) <= 75

    def test_healthy_ratio(self):
        """Ratio 1.3-2.0 should score 75-90."""
        assert 75 <= score_income_spend_ratio(1.5) <= 90

    def test_excellent_ratio(self):
        """Ratio > 2.0 should score 90-100."""
        assert score_income_spend_ratio(2.5) >= 90

    def test_infinity_ratio(self):
        """Infinite ratio (no spending) should score 100."""
        assert score_income_spend_ratio(float('inf')) == 100


class TestScoreNSFCount:
    """Tests for score_nsf_count()."""

    def test_zero_nsf_perfect_score(self):
        """0 NSFs should score 100."""
        assert score_nsf_count(0) == 100

    def test_one_nsf_good_score(self):
        """1 NSF should score 75."""
        assert score_nsf_count(1) == 75

    def test_two_nsf_moderate_score(self):
        """2 NSFs should score 50."""
        assert score_nsf_count(2) == 50

    def test_three_to_four_nsf_low_score(self):
        """3-4 NSFs should score 25."""
        assert score_nsf_count(3) == 25
        assert score_nsf_count(4) == 25

    def test_five_plus_nsf_zero_score(self):
        """5+ NSFs should score 0."""
        assert score_nsf_count(5) == 0
        assert score_nsf_count(10) == 0


class TestCalculateRiskScore:
    """Tests for calculate_risk_score()."""

    def test_excellent_user(self):
        """Excellent user (high ADB, high ratio, 0 NSF) should score 85+."""
        score = calculate_risk_score(
            avg_daily_balance=1500.0,
            income_spend_ratio=2.0,
            nsf_count=0,
        )
        assert score >= 85

    def test_poor_user(self):
        """Poor user (negative ADB, low ratio, high NSF) should score < 30."""
        score = calculate_risk_score(
            avg_daily_balance=-100.0,
            income_spend_ratio=0.7,
            nsf_count=5,
        )
        assert score < 30

    def test_borderline_user(self):
        """Borderline user should score around 30-50."""
        score = calculate_risk_score(
            avg_daily_balance=50.0,
            income_spend_ratio=1.0,
            nsf_count=2,
        )
        assert 20 <= score <= 60

    def test_gig_worker_adjustment(self):
        """Gig worker with good ratio should get boosted score."""
        base_score = calculate_risk_score(
            avg_daily_balance=300.0,
            income_spend_ratio=1.5,
            nsf_count=0,
            income_consistency=None,
        )
        boosted_score = calculate_risk_score(
            avg_daily_balance=300.0,
            income_spend_ratio=1.5,
            nsf_count=0,
            income_consistency=0.3,  # Low consistency (gig worker)
        )
        assert boosted_score >= base_score


# =============================================================================
# Credit Limit Tests
# =============================================================================

class TestCreditLimitMapping:
    """Tests for score_to_credit_limit_cents()."""

    def test_decline_threshold(self):
        """Scores 0-29 should result in $0 (decline)."""
        assert score_to_credit_limit_cents(0) == 0
        assert score_to_credit_limit_cents(15) == 0
        assert score_to_credit_limit_cents(29) == 0

    def test_starter_limit(self):
        """Scores 30-44 should get $100 limit."""
        assert score_to_credit_limit_cents(30) == 10000
        assert score_to_credit_limit_cents(35) == 10000
        assert score_to_credit_limit_cents(44) == 10000

    def test_graduated_limits(self):
        """Each tier should get appropriate limit."""
        assert score_to_credit_limit_cents(50) == 20000   # $200
        assert score_to_credit_limit_cents(65) == 30000   # $300
        assert score_to_credit_limit_cents(80) == 40000   # $400
        assert score_to_credit_limit_cents(90) == 50000   # $500

    def test_max_limit(self):
        """Scores 95-100 should get $600 limit."""
        assert score_to_credit_limit_cents(95) == 60000
        assert score_to_credit_limit_cents(100) == 60000

    def test_out_of_range_scores(self):
        """Scores outside 0-100 should be clamped."""
        assert score_to_credit_limit_cents(-10) == 0
        assert score_to_credit_limit_cents(150) == 60000


class TestCreditLimitBucket:
    """Tests for get_credit_limit_bucket()."""

    def test_buckets(self):
        """Each limit should map to correct bucket."""
        assert get_credit_limit_bucket(0) == "0"
        assert get_credit_limit_bucket(10000) == "100"
        assert get_credit_limit_bucket(20000) == "100-200"
        assert get_credit_limit_bucket(30000) == "200-300"
        assert get_credit_limit_bucket(40000) == "300-400"
        assert get_credit_limit_bucket(50000) == "400-500"
        assert get_credit_limit_bucket(60000) == "500-600"


class TestIsApproved:
    """Tests for is_approved()."""

    def test_approved_scores(self):
        """Scores 30+ should be approved."""
        assert is_approved(30) is True
        assert is_approved(50) is True
        assert is_approved(100) is True

    def test_declined_scores(self):
        """Scores < 30 should be declined."""
        assert is_approved(0) is False
        assert is_approved(29) is False


# =============================================================================
# Thin File Tests
# =============================================================================

class TestThinFile:
    """Tests for thin file handling."""

    def test_is_thin_file_few_transactions(self):
        """Users with < 10 transactions are thin file."""
        transactions = generate_thin_file_transactions()
        assert is_thin_file(transactions) is True

    def test_is_thin_file_normal_user(self):
        """Users with sufficient history are not thin file."""
        transactions = generate_healthy_transactions()
        assert is_thin_file(transactions) is False

    def test_thin_file_clean_approved(self):
        """Clean thin file should be approved with starter limit."""
        transactions = generate_thin_file_transactions()
        result = handle_thin_file(transactions)
        assert result is not None
        approved, limit = result
        assert approved is True
        assert limit == 10000  # $100 starter

    def test_thin_file_with_nsf_declined(self):
        """Thin file with NSF should be declined."""
        transactions = [
            make_transaction(30, 50000, 50000, TransactionType.CREDIT),
            make_transaction(20, -60000, -10000, TransactionType.DEBIT, nsf=True),
        ]
        result = handle_thin_file(transactions)
        assert result is not None
        approved, limit = result
        assert approved is False
        assert limit == 0

    def test_standard_user_returns_none(self):
        """Standard users should return None (use standard scoring)."""
        transactions = generate_healthy_transactions()
        result = handle_thin_file(transactions)
        assert result is None


# =============================================================================
# Decision Integration Tests
# =============================================================================

class TestMakeDecision:
    """Integration tests for make_decision()."""

    def test_healthy_user_approved_high_limit(self):
        """Healthy user should be approved with high limit."""
        transactions = generate_healthy_transactions()
        decision = make_decision(transactions, amount_requested_cents=40000)

        assert decision.approved is True
        assert decision.credit_limit_cents >= 30000  # At least $300
        assert decision.amount_granted_cents == 40000
        assert decision.plan_id is not None
        assert decision.decision_factors.risk_score >= 60

    def test_overdraft_user_declined(self):
        """Overdraft-prone user should be declined."""
        transactions = generate_overdraft_transactions()
        decision = make_decision(transactions, amount_requested_cents=30000)

        assert decision.approved is False
        assert decision.credit_limit_cents == 0
        assert decision.amount_granted_cents == 0
        assert decision.plan_id is None
        assert decision.decision_factors.nsf_count >= 3

    def test_thin_file_starter_limit(self):
        """Thin file user should get starter limit."""
        transactions = generate_thin_file_transactions()
        decision = make_decision(transactions, amount_requested_cents=50000)

        assert decision.approved is True
        assert decision.credit_limit_cents == 10000  # $100 starter
        assert decision.amount_granted_cents == 10000  # Capped to limit

    def test_amount_capped_to_limit(self):
        """Requested amount should be capped to credit limit."""
        transactions = generate_healthy_transactions()
        # Request more than max possible limit
        decision = make_decision(transactions, amount_requested_cents=100000)

        assert decision.approved is True
        assert decision.amount_granted_cents <= decision.credit_limit_cents
        assert decision.amount_granted_cents <= 60000  # Max limit

    def test_empty_transactions_declined(self):
        """Empty transaction list should result in decline."""
        decision = make_decision([], amount_requested_cents=10000)

        assert decision.approved is False
        assert decision.credit_limit_cents == 0

    def test_decision_factors_populated(self):
        """Decision factors should be populated correctly."""
        transactions = generate_healthy_transactions()
        decision = make_decision(transactions, amount_requested_cents=30000)

        factors = decision.decision_factors
        assert factors.avg_daily_balance > 0
        assert factors.income_ratio > 0
        assert factors.nsf_count >= 0
        assert 0 <= factors.risk_score <= 100


class TestExplainDecision:
    """Tests for explain_decision()."""

    def test_explain_approved(self):
        """Approved decision should have clear explanation."""
        transactions = generate_healthy_transactions()
        decision = make_decision(transactions, amount_requested_cents=30000)
        explanation = explain_decision(decision)

        assert "APPROVED" in explanation
        assert "Risk Score:" in explanation

    def test_explain_declined(self):
        """Declined decision should have clear explanation."""
        transactions = generate_overdraft_transactions()
        decision = make_decision(transactions, amount_requested_cents=30000)
        explanation = explain_decision(decision)

        assert "DECLINED" in explanation


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Edge case and boundary tests."""

    def test_score_boundary_at_30(self):
        """Test exact boundary at approval threshold."""
        # Just below threshold
        assert score_to_credit_limit_cents(29) == 0
        # At threshold
        assert score_to_credit_limit_cents(30) == 10000

    def test_all_same_day_transactions(self):
        """Handle multiple transactions on same day."""
        transactions = [
            make_transaction(0, 10000, 10000, TransactionType.CREDIT),
            make_transaction(0, -5000, 5000, TransactionType.DEBIT),
            make_transaction(0, -2000, 3000, TransactionType.DEBIT),
        ]
        adb = calculate_avg_daily_balance(transactions)
        # Should use last balance of the day (3000 cents = $30)
        assert adb == 30.0

    def test_very_high_income_ratio(self):
        """Handle extremely high income ratios."""
        transactions = [
            make_transaction(30, 1000000, 1000000, TransactionType.CREDIT),
            make_transaction(20, -1000, 999000, TransactionType.DEBIT),
        ]
        ratio = calculate_income_spend_ratio(transactions)
        assert ratio == 1000.0  # $10,000 / $10
        score = score_income_spend_ratio(ratio)
        assert score == 100

    def test_decision_to_dict(self):
        """Test Decision.to_dict() method."""
        transactions = generate_healthy_transactions()
        decision = make_decision(transactions, amount_requested_cents=30000)
        result = decision.to_dict()

        assert "approved" in result
        assert "credit_limit_cents" in result
        assert "amount_granted_cents" in result
        assert "plan_id" in result
        assert "decision_factors" in result
        assert "avg_daily_balance" in result["decision_factors"]
