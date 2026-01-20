"""
Risk Scoring Module for Gerald BNPL Approval Engine
"""

from .models import Transaction, DecisionFactors, Decision
from .settings import ScoringSettings, scoring_settings
from .risk_factors import (
    calculate_avg_daily_balance,
    calculate_income_spend_ratio,
    count_nsf_events,
    calculate_income_consistency,
)
from .risk_score import (
    score_avg_daily_balance,
    score_income_spend_ratio,
    score_nsf_count,
    calculate_risk_score,
)
from .credit_limit import score_to_credit_limit_cents
from .thin_file import handle_thin_file, is_thin_file
from .decision import make_decision

__all__ = [
    "ScoringSettings",
    "scoring_settings",
    "Transaction",
    "DecisionFactors",
    "Decision",
    "calculate_avg_daily_balance",
    "calculate_income_spend_ratio",
    "count_nsf_events",
    "calculate_income_consistency",
    "score_avg_daily_balance",
    "score_income_spend_ratio",
    "score_nsf_count",
    "calculate_risk_score",
    "score_to_credit_limit_cents",
    "handle_thin_file",
    "is_thin_file",
    "make_decision",
]
