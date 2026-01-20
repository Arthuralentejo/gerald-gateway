"""Functions to calculate individual risk factors from transactions."""

from collections import defaultdict
from datetime import date, timedelta
from typing import List

from .models import Transaction, TransactionType


def calculate_avg_daily_balance(transactions: List[Transaction]) -> float:
    """Calculate 90-day average daily balance in dollars."""
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
    """Calculate ratio of monthly income to spending."""
    if not transactions:
        return 1.0

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

    monthly_income = total_credits / 3
    monthly_spending = total_debits / 3

    return monthly_income / monthly_spending


def count_nsf_events(transactions: List[Transaction]) -> int:
    """Count NSF (insufficient funds) events from transactions."""
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
    """Calculate income consistency score (0-1) based on weekly variance."""
    credits = [t for t in transactions if t.type == TransactionType.CREDIT]

    if len(credits) < 3:
        return 0.5

    weekly_income: dict[int, int] = defaultdict(int)
    for txn in credits:
        year_week = txn.date.isocalendar()[:2]
        weekly_income[year_week] += txn.amount_cents

    if len(weekly_income) < 4:
        return 0.5

    values = list(weekly_income.values())
    mean = sum(values) / len(values)

    if mean <= 0:
        return 0.5

    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = variance ** 0.5
    cv = std_dev / mean
    consistency = max(0.0, 1.0 - cv)
    return min(1.0, consistency)
