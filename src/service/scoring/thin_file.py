"""
Thin File Handling for Gerald BNPL Approval Engine.

"Thin file" refers to users with limited transaction history, making
it difficult to accurately assess their risk using standard scoring.
"""

from typing import List, Optional, Tuple

from .models import Transaction
from .risk_factors import count_nsf_events
from .settings import ScoringSettings, scoring_settings


def is_thin_file(
    transactions: List[Transaction],
    settings: ScoringSettings = scoring_settings,
) -> bool:
    """
    Determine if a user has a "thin file" (insufficient transaction history).

    A file is considered "thin" if either:
    - Fewer than min_transactions total transactions
    - Fewer than min_history_days unique days with transactions

    Args:
        transactions: List of bank transactions
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        True if the user has a thin file
    """
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
    """
    Handle thin-file users with a special approval policy.

    Policy:
        1. If not a thin file: return None (use standard scoring)
        2. If thin file with ANY NSF: decline
        3. If thin file with no NSFs: approve with starter limit

    Args:
        transactions: List of bank transactions
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Tuple of (approved, credit_limit_cents) if thin file,
        None if should use standard scoring
    """
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
    """
    Get a human-readable explanation for thin file classification.

    Args:
        transactions: List of bank transactions
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Explanation string
    """
    if len(transactions) < settings.min_transactions:
        return f"Insufficient transactions ({len(transactions)} < {settings.min_transactions})"

    unique_days = len(set(t.date for t in transactions))
    if unique_days < settings.min_history_days:
        return f"Insufficient history ({unique_days} days < {settings.min_history_days} days)"

    return "Not a thin file"
