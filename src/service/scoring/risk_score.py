"""
Risk Score Calculation for Gerald BNPL Approval Engine.

This module normalizes raw risk factors into 0-100 scores and combines
them into a composite risk score that drives approval decisions.
"""

from typing import Optional

from .settings import ScoringSettings, scoring_settings


def score_avg_daily_balance(
    adb: float,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """
    Convert average daily balance (in dollars) to a 0-100 score.

    Args:
        adb: Average daily balance in dollars
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Score from 0-100
    """
    if adb < 0:
        # Negative balance: scale from 0 to 20 based on how negative
        return max(0, int(20 + adb / 10))
    elif adb < settings.adb_low_threshold:
        # $0-100: scale from 20 to 40
        return 20 + int((adb / settings.adb_low_threshold) * 20)
    elif adb < settings.adb_moderate_threshold:
        # $100-500: scale from 40 to 70
        range_size = settings.adb_moderate_threshold - settings.adb_low_threshold
        return 40 + int(((adb - settings.adb_low_threshold) / range_size) * 30)
    elif adb < settings.adb_good_threshold:
        # $500-1500: scale from 70 to 90
        range_size = settings.adb_good_threshold - settings.adb_moderate_threshold
        return 70 + int(((adb - settings.adb_moderate_threshold) / range_size) * 20)
    else:
        # $1500+: scale from 90 to 100, capped
        return min(100, 90 + int((adb - settings.adb_good_threshold) / 500) * 10)


def score_income_spend_ratio(
    ratio: float,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """
    Convert income/spend ratio to a 0-100 score.

    Args:
        ratio: Income/spend ratio (0 to infinity)
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Score from 0-100
    """
    if ratio == float('inf'):
        return 100

    if ratio < settings.ratio_critical_threshold:
        # Heavy overspending: 0-25
        return int(ratio / settings.ratio_critical_threshold * 25)
    elif ratio < settings.ratio_breakeven_threshold:
        # Borderline: 25-50
        range_size = settings.ratio_breakeven_threshold - settings.ratio_critical_threshold
        return 25 + int(((ratio - settings.ratio_critical_threshold) / range_size) * 25)
    elif ratio < settings.ratio_sustainable_threshold:
        # Sustainable: 50-75
        range_size = settings.ratio_sustainable_threshold - settings.ratio_breakeven_threshold
        return 50 + int(((ratio - settings.ratio_breakeven_threshold) / range_size) * 25)
    elif ratio < settings.ratio_healthy_threshold:
        # Healthy: 75-90
        range_size = settings.ratio_healthy_threshold - settings.ratio_sustainable_threshold
        return 75 + int(((ratio - settings.ratio_sustainable_threshold) / range_size) * 15)
    else:
        # Very healthy: 90-100
        return min(100, 90 + int((ratio - settings.ratio_healthy_threshold) / 1.0 * 10))


def score_nsf_count(
    nsf_count: int,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """
    Convert NSF count to a 0-100 score (inverse - fewer is better).

    Args:
        nsf_count: Number of NSF events (0 or higher)
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Score from 0-100
    """
    if nsf_count == 0:
        return 100
    elif nsf_count <= settings.nsf_forgivable_count:
        return 75
    elif nsf_count <= settings.nsf_concerning_count:
        return 50
    elif nsf_count <= settings.nsf_high_risk_count:
        return 25
    else:
        return 0


def calculate_risk_score(
    avg_daily_balance: float,
    income_spend_ratio: float,
    nsf_count: int,
    income_consistency: Optional[float] = None,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """
    Calculate the composite risk score from individual factors.

    Args:
        avg_daily_balance: Average daily balance in dollars
        income_spend_ratio: Income/spend ratio
        nsf_count: Number of NSF events
        income_consistency: Optional consistency score (0-1) for gig worker detection
        settings: Scoring settings (uses defaults if not provided)

    Returns:
        Composite risk score from 0-100 (higher = lower risk)
    """
    adb_score = score_avg_daily_balance(avg_daily_balance, settings)
    ratio_score = score_income_spend_ratio(income_spend_ratio, settings)
    nsf_score = score_nsf_count(nsf_count, settings)

    # Gig worker adjustment
    if income_consistency is not None:
        if (income_consistency < settings.gig_worker_consistency_threshold and
                income_spend_ratio > settings.gig_worker_ratio_threshold):
            ratio_score = min(100, ratio_score + settings.gig_worker_boost)

    # Weighted average
    composite = (
        adb_score * settings.weight_adb +
        ratio_score * settings.weight_ratio +
        nsf_score * settings.weight_nsf
    )

    return int(composite)
