from dataclasses import dataclass, field
from typing import Dict, List
from enum import Enum


class RoundingStrategy(str, Enum):
    CEIL = "ceil"
    FLOOR = "floor"
    ROUND = "round"


class CardioPreferenceMode(str, Enum):
    FINISHER = "finisher"
    DEDICATED_DAY = "dedicated_day"
    BOTH_FINISHERS_AND_CARDIO_DAYS = "both_finishers_and_cardio_days"
    MIXED = "mixed"
    NONE = "none"


@dataclass
class SessionTypePreferences:
    cardio_preference: CardioPreferenceMode = CardioPreferenceMode.FINISHER
    max_finishers_per_week: int = 3
    max_cardio_days_per_week: int = 2

    def __post_init__(self):
        if self.max_finishers_per_week < 0:
            raise ValueError(
                f"max_finishers_per_week must be >= 0, got {self.max_finishers_per_week}"
            )
        if self.max_cardio_days_per_week < 0:
            raise ValueError(
                f"max_cardio_days_per_week must be >= 0, got {self.max_cardio_days_per_week}"
            )


@dataclass
class SessionTypeTargets:
    target_accessory_count: int
    target_finisher_count: int
    target_cardio_day_count: int
    total_sessions: int

    raw_accessory_ratio: float = field(default=0.0)
    raw_finisher_ratio: float = field(default=0.0)
    raw_cardio_day_ratio: float = field(default=0.0)

    allocation_accuracy: float = field(default=1.0)
    rounding_errors: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.total_sessions > 0:
            self.raw_accessory_ratio = self.target_accessory_count / self.total_sessions
            self.raw_finisher_ratio = self.target_finisher_count / self.total_sessions
            self.raw_cardio_day_ratio = (
                self.target_cardio_day_count / self.total_sessions
            )

            expected_total = (
                self.target_accessory_count
                + self.target_finisher_count
                + self.target_cardio_day_count
            )
            self.allocation_accuracy = (
                1.0 - abs(expected_total - self.total_sessions) / self.total_sessions
            )

            self.rounding_errors = {
                "finisher": round(self.raw_finisher_ratio * self.total_sessions)
                - self.target_finisher_count,
                "cardio_day": round(self.raw_cardio_day_ratio * self.total_sessions)
                - self.target_cardio_day_count,
            }


@dataclass
class MicrocycleAllocation:
    microcycle_id: int
    targets: SessionTypeTargets
    preferences: SessionTypePreferences
    assigned_session_types: Dict[int, str] = field(default_factory=dict)
    finisher_session_indices: List[int] = field(default_factory=list)
    cardio_day_indices: List[int] = field(default_factory=list)
    accessory_session_indices: List[int] = field(default_factory=list)


@dataclass
class GoalBucketWeights:
    strength: float = 0.0
    hypertrophy: float = 0.0
    endurance: float = 0.0
    fat_loss: float = 0.0
    mobility: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.strength
            + self.hypertrophy
            + self.endurance
            + self.fat_loss
            + self.mobility
        )

    @property
    def conditioning_weight(self) -> float:
        return self.endurance + self.fat_loss

    @property
    def hypertrophy_weight(self) -> float:
        return self.strength + self.hypertrophy
