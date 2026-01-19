"""
Scoring Settings for Gerald BNPL Approval Engine.

This module contains all configurable parameters for the risk scoring system.
These can be adjusted for A/B testing, different user segments, or tuning
based on observed default rates.

Usage:
    from src.service.scoring.settings import scoring_settings

    # Use default settings
    limit = scoring_settings.thin_file_limit_cents

    # Or create custom settings for testing
    custom = ScoringSettings(approval_threshold=25)
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class ScoringSettings:
    """
    Configurable parameters for the risk scoring algorithm.

    All monetary values are in cents.
    All scores are 0-100.
    """

    # === Thin File Settings ===
    min_transactions: int = 10
    """Minimum transactions required for standard scoring."""

    min_history_days: int = 30
    """Minimum days of history required for standard scoring."""

    thin_file_limit_cents: int = 10_000  # $100
    """Credit limit for approved thin-file users."""

    # === Factor Weights ===
    weight_adb: float = 0.30
    """Weight for Average Daily Balance in composite score."""

    weight_ratio: float = 0.35
    """Weight for Income/Spend Ratio in composite score."""

    weight_nsf: float = 0.35
    """Weight for NSF Count in composite score."""

    # === Gig Worker Adjustment ===
    gig_worker_consistency_threshold: float = 0.5
    """Income consistency below this triggers gig worker detection."""

    gig_worker_ratio_threshold: float = 1.2
    """Minimum ratio to qualify for gig worker boost."""

    gig_worker_boost: int = 10
    """Points added to ratio score for qualifying gig workers."""

    # === Approval Threshold ===
    approval_threshold: int = 30
    """Minimum score required for approval (scores below = declined)."""

    # === Credit Limit Tiers ===
    # Format: (min_score, max_score, limit_cents)
    credit_limit_tiers: List[Tuple[int, int, int]] = field(default_factory=lambda: [
        (0, 29, 0),          # Declined
        (30, 44, 10_000),    # $100 - starter
        (45, 59, 20_000),    # $200 - low
        (60, 74, 30_000),    # $300 - moderate
        (75, 84, 40_000),    # $400 - good
        (85, 94, 50_000),    # $500 - very good
        (95, 100, 60_000),   # $600 - excellent
    ])
    """Credit limit tiers mapping score ranges to limits in cents."""

    # === ADB Scoring Thresholds (in dollars) ===
    adb_negative_floor: float = -200.0
    """ADB at or below this gets score 0."""

    adb_low_threshold: float = 100.0
    """ADB below this is considered low cushion."""

    adb_moderate_threshold: float = 500.0
    """ADB below this is considered moderate cushion."""

    adb_good_threshold: float = 1500.0
    """ADB below this is considered good cushion."""

    # === Ratio Scoring Thresholds ===
    ratio_critical_threshold: float = 0.8
    """Ratio below this indicates severe overspending."""

    ratio_breakeven_threshold: float = 1.0
    """Ratio at this point means income equals spending."""

    ratio_sustainable_threshold: float = 1.3
    """Ratio above this indicates sustainable margin."""

    ratio_healthy_threshold: float = 2.0
    """Ratio above this indicates strong financial health."""

    # === NSF Scoring ===
    nsf_forgivable_count: int = 1
    """NSF count at or below this gets partial credit (one-time issue)."""

    nsf_concerning_count: int = 2
    """NSF count at this level indicates emerging pattern."""

    nsf_high_risk_count: int = 4
    """NSF count above this indicates chronic issues."""

    @property
    def max_credit_limit_cents(self) -> int:
        """Maximum credit limit available."""
        return max(tier[2] for tier in self.credit_limit_tiers)

    @property
    def min_credit_limit_cents(self) -> int:
        """Minimum non-zero credit limit."""
        non_zero = [tier[2] for tier in self.credit_limit_tiers if tier[2] > 0]
        return min(non_zero) if non_zero else 0


# Default settings instance
scoring_settings = ScoringSettings()
