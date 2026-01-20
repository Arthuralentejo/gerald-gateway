"""Configurable settings for the risk scoring engine."""

import json
from functools import lru_cache
from typing import List, Tuple

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringSettings(BaseSettings):
    """Environment-configurable thresholds and weights for scoring."""
    model_config = SettingsConfigDict(
        env_prefix="SCORING_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    min_transactions: int = Field(
        default=10,
        description="Minimum transactions required for standard scoring",
    )
    min_history_days: int = Field(
        default=30,
        description="Minimum days of history required for standard scoring",
    )
    thin_file_limit_cents: int = Field(
        default=10_000,
        description="Credit limit in cents for approved thin-file users ($100)",
    )

    weight_adb: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight for Average Daily Balance in composite score",
    )
    weight_ratio: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Weight for Income/Spend Ratio in composite score",
    )
    weight_nsf: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Weight for NSF Count in composite score",
    )

    gig_worker_consistency_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Income consistency below this triggers gig worker detection",
    )
    gig_worker_ratio_threshold: float = Field(
        default=1.2,
        gt=0.0,
        description="Minimum income/spend ratio to qualify for gig worker boost",
    )
    gig_worker_boost: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Points added to ratio score for qualifying gig workers",
    )

    approval_threshold: int = Field(
        default=30,
        ge=0,
        le=100,
        description="Minimum composite score required for approval (below = declined)",
    )

    adb_negative_floor: float = Field(
        default=-200.0,
        description="ADB at or below this value gets score 0 (dollars)",
    )
    adb_low_threshold: float = Field(
        default=100.0,
        description="ADB below this is considered low cushion (dollars)",
    )
    adb_moderate_threshold: float = Field(
        default=500.0,
        description="ADB below this is considered moderate cushion (dollars)",
    )
    adb_good_threshold: float = Field(
        default=1500.0,
        description="ADB at or above this is considered good cushion (dollars)",
    )

    ratio_critical_threshold: float = Field(
        default=0.8,
        gt=0.0,
        description="Income/spend ratio below this indicates severe overspending",
    )
    ratio_breakeven_threshold: float = Field(
        default=1.0,
        gt=0.0,
        description="Income/spend ratio at this point means income equals spending",
    )
    ratio_sustainable_threshold: float = Field(
        default=1.3,
        gt=0.0,
        description="Income/spend ratio above this indicates sustainable margin",
    )
    ratio_healthy_threshold: float = Field(
        default=2.0,
        gt=0.0,
        description="Income/spend ratio above this indicates strong financial health",
    )

    nsf_forgivable_count: int = Field(
        default=1,
        ge=0,
        description="NSF count at or below this gets partial credit (timing issues)",
    )
    nsf_concerning_count: int = Field(
        default=2,
        ge=0,
        description="NSF count at this level indicates an emerging pattern",
    )
    nsf_high_risk_count: int = Field(
        default=4,
        ge=0,
        description="NSF count above this indicates chronic payment issues",
    )

    credit_limit_tiers_json: str = Field(
        default="[[0,29,0],[30,44,10000],[45,59,20000],[60,74,30000],[75,84,40000],[85,94,50000],[95,100,60000]]",
        description="Credit limit tiers as JSON array: [[min_score, max_score, limit_cents], ...]",
    )

    @field_validator("credit_limit_tiers_json")
    @classmethod
    def validate_tiers_json(cls, v: str) -> str:
        try:
            tiers = json.loads(v)
            if not isinstance(tiers, list):
                raise ValueError("Tiers must be a list")
            for tier in tiers:
                if not isinstance(tier, list) or len(tier) != 3:
                    raise ValueError(
                        "Each tier must be [min_score, max_score, limit_cents]"
                    )
                min_score, max_score, limit_cents = tier
                if not all(isinstance(x, int) for x in tier):
                    raise ValueError("All tier values must be integers")
                if min_score > max_score:
                    raise ValueError(
                        f"min_score ({min_score}) > max_score ({max_score})"
                    )
                if limit_cents < 0:
                    raise ValueError(f"limit_cents cannot be negative: {limit_cents}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        return v

    @property
    def credit_limit_tiers(self) -> List[Tuple[int, int, int]]:
        tiers = json.loads(self.credit_limit_tiers_json)
        return [tuple(tier) for tier in tiers]

    @property
    def max_credit_limit_cents(self) -> int:
        return max(tier[2] for tier in self.credit_limit_tiers)

    @property
    def min_credit_limit_cents(self) -> int:
        non_zero = [tier[2] for tier in self.credit_limit_tiers if tier[2] > 0]
        return min(non_zero) if non_zero else 0


@lru_cache
def get_scoring_settings() -> ScoringSettings:
    return ScoringSettings()


scoring_settings = get_scoring_settings()
