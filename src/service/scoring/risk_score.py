"""Functions to convert risk factors into numerical scores."""

from typing import Optional

from .settings import ScoringSettings, scoring_settings


def score_avg_daily_balance(
    adb: float,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """Convert average daily balance to score (0-100)."""
    if adb < 0:
        return max(0, int(20 + adb / 10))
    elif adb < settings.adb_low_threshold:
        return 20 + int((adb / settings.adb_low_threshold) * 20)
    elif adb < settings.adb_moderate_threshold:
        range_size = settings.adb_moderate_threshold - settings.adb_low_threshold
        return 40 + int(((adb - settings.adb_low_threshold) / range_size) * 30)
    elif adb < settings.adb_good_threshold:
        range_size = settings.adb_good_threshold - settings.adb_moderate_threshold
        return 70 + int(((adb - settings.adb_moderate_threshold) / range_size) * 20)
    else:
        return min(100, 90 + int((adb - settings.adb_good_threshold) / 500) * 10)


def score_income_spend_ratio(
    ratio: float,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """Convert income/spend ratio to score (0-100)."""
    if ratio == float('inf'):
        return 100

    if ratio < settings.ratio_critical_threshold:
        return int(ratio / settings.ratio_critical_threshold * 25)
    elif ratio < settings.ratio_breakeven_threshold:
        range_size = settings.ratio_breakeven_threshold - settings.ratio_critical_threshold
        return 25 + int(((ratio - settings.ratio_critical_threshold) / range_size) * 25)
    elif ratio < settings.ratio_sustainable_threshold:
        range_size = settings.ratio_sustainable_threshold - settings.ratio_breakeven_threshold
        return 50 + int(((ratio - settings.ratio_breakeven_threshold) / range_size) * 25)
    elif ratio < settings.ratio_healthy_threshold:
        range_size = settings.ratio_healthy_threshold - settings.ratio_sustainable_threshold
        return 75 + int(((ratio - settings.ratio_sustainable_threshold) / range_size) * 15)
    else:
        return min(100, 90 + int((ratio - settings.ratio_healthy_threshold) / 1.0 * 10))


def score_nsf_count(
    nsf_count: int,
    settings: ScoringSettings = scoring_settings,
) -> int:
    """Convert NSF count to score (0-100, fewer is better)."""
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
    """Calculate weighted composite risk score (0-100)."""
    adb_score = score_avg_daily_balance(avg_daily_balance, settings)
    ratio_score = score_income_spend_ratio(income_spend_ratio, settings)
    nsf_score = score_nsf_count(nsf_count, settings)

    if income_consistency is not None:
        if (income_consistency < settings.gig_worker_consistency_threshold and
                income_spend_ratio > settings.gig_worker_ratio_threshold):
            ratio_score = min(100, ratio_score + settings.gig_worker_boost)

    composite = (
        adb_score * settings.weight_adb +
        ratio_score * settings.weight_ratio +
        nsf_score * settings.weight_nsf
    )

    return int(composite)
