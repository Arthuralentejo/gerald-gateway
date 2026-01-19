"""
Credit Limit Mapping for Gerald BNPL Approval Engine.

This module maps composite risk scores to credit limits, implementing
the graduated tier system that balances risk with revenue opportunity.
"""

from .settings import ScoringSettings, scoring_settings


def score_to_credit_limit_cents(
    risk_score: int,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """
    Map a risk score to a credit limit in cents.

    Args:
        risk_score: Composite risk score (0-100)
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Credit limit in cents (0 = declined)
    """
    if risk_score < 0:
        risk_score = 0
    elif risk_score > 100:
        risk_score = 100

    for min_score, max_score, limit_cents in settings.credit_limit_tiers:
        if min_score <= risk_score <= max_score:
            return limit_cents

    return 0


def get_credit_limit_bucket(limit_cents: int) -> str:
    """
    Get the bucket label for a credit limit (for metrics reporting).

    Args:
        limit_cents: Credit limit in cents

    Returns:
        Bucket label string
    """
    if limit_cents == 0:
        return "0"
    elif limit_cents <= 10000:
        return "100"
    elif limit_cents <= 20000:
        return "100-200"
    elif limit_cents <= 30000:
        return "200-300"
    elif limit_cents <= 40000:
        return "300-400"
    elif limit_cents <= 50000:
        return "400-500"
    else:
        return "500-600"


def is_approved(
    risk_score: int,
    settings: ScoringSettings = scoring_settings,
) -> bool:
    """
    Determine if a risk score results in approval.

    Args:
        risk_score: Composite risk score (0-100)
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        True if approved, False if declined
    """
    return score_to_credit_limit_cents(risk_score, settings) > 0
