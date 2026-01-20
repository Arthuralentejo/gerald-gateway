"""Thin file detection and handling for users with limited history."""

from typing import List, Optional, Tuple

from .models import Transaction
from .risk_factors import count_nsf_events
from .settings import ScoringSettings, scoring_settings


def is_thin_file(
    transactions: List[Transaction],
    settings: ScoringSettings = scoring_settings,
) -> bool:
    """Check if user has insufficient transaction history."""
    if len(transactions) < settings.min_transactions:
        return True

    unique_days = len(set(t.date for t in transactions))
    if unique_days < settings.min_history_days:
        return True

    return False


def handle_thin_file(
    transactions: List[Transaction],
    settings: ScoringSettings = scoring_settings,
) -> Optional[Tuple[bool, int]]:
    """Handle thin file users, returning (approved, limit) or None for standard scoring."""
    if not is_thin_file(transactions, settings):
        return None

    nsf_count = count_nsf_events(transactions)

    if nsf_count > 0:
        return (False, 0)

    return (True, settings.thin_file_limit_cents)


def get_thin_file_reason(
    transactions: List[Transaction],
    settings: ScoringSettings = scoring_settings,
) -> str:
    """Get human-readable reason for thin file status."""
    if len(transactions) < settings.min_transactions:
        return f"Insufficient transactions ({len(transactions)} < {settings.min_transactions})"

    unique_days = len(set(t.date for t in transactions))
    if unique_days < settings.min_history_days:
        return f"Insufficient history ({unique_days} days < {settings.min_history_days} days)"

    return "Not a thin file"
