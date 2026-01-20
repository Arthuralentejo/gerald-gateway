"""Functions to map risk scores to credit limits."""

from .settings import ScoringSettings, scoring_settings


def score_to_credit_limit_cents(
    risk_score: int,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """Map risk score to credit limit in cents using configured tiers."""
    if risk_score < 0:
        risk_score = 0
    elif risk_score > 100:
        risk_score = 100

    for min_score, max_score, limit_cents in settings.credit_limit_tiers:
        if min_score <= risk_score <= max_score:
            return limit_cents

    return 0


def get_credit_limit_bucket(limit_cents: int) -> str:
    """Get display bucket label for credit limit."""
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
    """Check if risk score qualifies for approval."""
    return score_to_credit_limit_cents(risk_score, settings) > 0
