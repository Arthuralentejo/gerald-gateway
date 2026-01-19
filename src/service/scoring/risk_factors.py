"""
Risk Factor Calculations for Gerald BNPL Approval Engine.

This module calculates the raw risk factors from bank transaction history:
- Average Daily Balance (ADB)
- Income vs. Spend Ratio
- NSF/Overdraft Count
- Income Consistency (for gig worker detection)

Each factor is documented with:
- The calculation algorithm
- Business rationale for why this factor matters
- Edge cases and how they're handled
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import List

from .models import Transaction, TransactionType


def calculate_avg_daily_balance(transactions: List[Transaction]) -> float:
    """
    Calculate the average daily balance over the 90-day transaction window.

    Algorithm:
        1. Build a map of date -> end-of-day balance from transactions
        2. For each day in the 90-day range:
           - If transactions exist: use the end-of-day balance
           - If no transactions: carry forward the previous day's balance
        3. Sum all daily balances and divide by the number of days

    Business Rationale:
        ADB measures the user's financial cushion. Users with consistent
        positive balances are less likely to default because they have
        reserves to handle unexpected expenses. A negative ADB indicates
        chronic overdraft, which is a strong default predictor.

    Args:
        transactions: List of bank transactions (must be non-empty)

    Returns:
        Average daily balance in dollars (can be negative)

    Raises:
        ValueError: If transactions list is empty
    """
    if not transactions:
        raise ValueError("Cannot calculate ADB with no transactions")

    daily_balances: dict[date, int] = {}
    for txn in sorted(transactions, key=lambda t: t.date):
        daily_balances[txn.date] = txn.balance_cents

    start_date = min(daily_balances.keys())
    end_date = start_date + timedelta(days=89)

    total_cents = 0
    last_balance = 0
    current_date = start_date

    while current_date <= end_date:
        if current_date in daily_balances:
            last_balance = daily_balances[current_date]
        total_cents += last_balance
        current_date += timedelta(days=1)

    num_days = (end_date - start_date).days + 1
    return total_cents / (num_days * 100)


def calculate_income_spend_ratio(transactions: List[Transaction]) -> float:
    """
    Calculate the ratio of monthly income to monthly spending.

    Algorithm:
        1. Sum all credit transactions (income)
        2. Sum all debit transactions (spending, absolute value)
        3. Calculate monthly averages (divide by 3 for 90-day window)
        4. Return monthly_income / monthly_spending

    Business Rationale:
        - Ratio > 1.0: Income exceeds spending (sustainable, low risk)
        - Ratio = 1.0: Break-even (risky, no margin for error)
        - Ratio < 1.0: Spending exceeds income (high default risk)

        This is one of the most predictive factors because it indicates
        whether the user can sustainably afford new debt.

    Edge Cases:
        - No debits: Return infinity if credits exist, 1.0 if no transactions
        - No credits: Return 0.0 (user has no visible income)

    Args:
        transactions: List of bank transactions

    Returns:
        Income/spend ratio (0.0 to infinity)
    """
    if not transactions:
        return 1.0  # Neutral for no data

    total_credits = sum(
        t.amount_cents for t in transactions
        if t.type == TransactionType.CREDIT
    )
    total_debits = abs(sum(
        t.amount_cents for t in transactions
        if t.type == TransactionType.DEBIT
    ))

    if total_debits == 0:
        return float('inf') if total_credits > 0 else 1.0

    # Calculate monthly averages (90 days = 3 months)
    monthly_income = total_credits / 3
    monthly_spending = total_debits / 3

    return monthly_income / monthly_spending


def count_nsf_events(transactions: List[Transaction]) -> int:
    """
    Count the number of NSF (Non-Sufficient Funds) or overdraft events.

    Algorithm:
        1. Count transactions with explicit `nsf: true` flag
        2. Count debits that caused balance to go negative (implicit NSF)
        3. Avoid double-counting if both conditions are true for same transaction

    Business Rationale:
        NSF events are the strongest predictor of default. Each NSF indicates
        the user couldn't cover a payment - exactly what we're trying to avoid
        with BNPL. Users with chronic NSFs are very likely to default on
        Gerald's installment payments.

    Why we count implicit NSFs:
        Some banks don't always set the NSF flag but the balance going
        negative after a debit is effectively the same situation.

    Args:
        transactions: List of bank transactions

    Returns:
        Total count of NSF events (0 or higher)
    """
    if not transactions:
        return 0

    nsf_count = 0
    prev_balance = 0

    for txn in sorted(transactions, key=lambda t: t.date):
        if txn.nsf:
            nsf_count += 1
        elif txn.type == TransactionType.DEBIT and txn.balance_cents < 0 and prev_balance >= 0:
            nsf_count += 1

        prev_balance = txn.balance_cents

    return nsf_count


def calculate_income_consistency(transactions: List[Transaction]) -> float:
    """
    Calculate how consistent/regular the user's income is.

    This metric helps distinguish between:
    - W-2 employees with regular paychecks (high consistency)
    - Gig workers with variable income (low consistency)

    Algorithm:
        1. Filter to credit (income) transactions only
        2. Group income by week
        3. Calculate coefficient of variation (std_dev / mean)
        4. Convert to 0-1 scale where 1.0 = perfectly consistent

    Business Rationale:
        Gig workers may have variable income but still be creditworthy if
        their overall income/spend ratio is healthy. This metric allows us
        to apply a fairness adjustment for users with irregular but sufficient
        income, rather than penalizing them for income variability.

    Args:
        transactions: List of bank transactions

    Returns:
        Income consistency score from 0.0 (highly irregular) to 1.0 (perfectly regular)
    """
    credits = [t for t in transactions if t.type == TransactionType.CREDIT]

    if len(credits) < 3:
        return 0.5  # Neutral for insufficient data

    # Group income by week
    weekly_income: dict[int, int] = defaultdict(int)
    for txn in credits:
        # Use ISO week number as key
        year_week = txn.date.isocalendar()[:2]  # (year, week)
        weekly_income[year_week] += txn.amount_cents

    if len(weekly_income) < 4:
        return 0.5  # Need at least 4 weeks of data

    values = list(weekly_income.values())
    mean = sum(values) / len(values)

    if mean <= 0:
        return 0.5  # Can't calculate CV without positive mean

    # Calculate standard deviation
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5

    # Coefficient of variation (lower = more consistent)
    cv = std_dev / mean

    # Convert to 0-1 scale
    # CV of 0 = perfectly consistent = 1.0 score
    # CV of 1+ = highly variable = 0.0 score
    consistency = max(0.0, 1.0 - cv)
    return min(1.0, consistency)
