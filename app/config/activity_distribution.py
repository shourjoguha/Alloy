"""
Centralized program-distribution and goal-bias configuration.

This module intentionally includes plain-text bias rationale so the system’s
implicit choices are inspectable (e.g., why fat loss tends to add cardio blocks
or metabolic finishers).
"""

from __future__ import annotations


mobility_max_pct: float = 0.30
cardio_max_pct: float = 0.75

preference_deviation_pct: float = 0.15

default_microcycle_length_days: int = 14

min_conditioning_minutes: int = 30
min_conditioning_unique_movements: int = 5

default_lifting_warmup_minutes: int = 10
default_lifting_cooldown_minutes: int = 5

default_finisher_minutes: int = 8
max_finisher_minutes: int = 15

goal_finisher_thresholds = {
    "fat_loss_min_weight": 3,
    "endurance_min_weight": 3,
}

goal_finisher_presets = {
    "fat_loss": {
        "type": "circuit",
        "circuit_type": "AMRAP",
        "name": "AMRAP Finisher",
        "duration_minutes": 8,
        "exercises": [
            {"movement": "Burpees", "reps": 10, "rest_seconds": 30},
            {"movement": "Jumping Squats", "reps": 15, "rest_seconds": 30},
            {"movement": "Mountain Climbers", "reps": 20, "rest_seconds": 30},
        ],
    },
    "endurance": {
        "type": "circuit",
        "circuit_type": "EMOM",
        "name": "EMOM Finisher",
        "duration_minutes": 8,
        "exercises": [
            {"movement": "Burpees", "reps": 10, "rest_seconds": 0},
            {"movement": "Push-Up", "reps": 15, "rest_seconds": 0},
            {"movement": "Air Squat", "reps": 20, "rest_seconds": 0},
        ],
    },
}

goal_bucket_weights = {
    "strength": {"lifting": 1.0},
    "hypertrophy": {"lifting": 1.0},
    "fat_loss": {"cardio": 0.2, "finisher": 0.5, "lifting": 0.3},
    "endurance": {"cardio": 0.5, "finisher": 0.5},
    "mobility": {"mobility": 1.0},
}

endurance_heavy_dedicated_cardio_day_default: bool = True
endurance_heavy_dedicated_cardio_day_min_weight: int = 6
endurance_heavy_dedicated_cardio_day_min_cycle_length_days: int = 7

# OR-Tools Constraint Solver Configuration
or_tools_max_fatigue: float = 8.0
or_tools_solver_timeout_seconds: int = 60
or_tools_min_sets_per_movement: int = 2
or_tools_max_sets_per_movement: int = 5
or_tools_volume_target_reduction_pct: float = 0.2

BIAS_RATIONALE = {
    "fat_loss": "Bias toward higher weekly energy expenditure via cardio blocks and/or metabolic finishers while keeping lifting exposure for lean mass retention.",
    "endurance": "Bias toward time-under-aerobic-load via cardio blocks or interval-style finishers; lifting stays but is not the sole driver.",
    "strength": "Bias toward main lifts and accessory volume; cardio is minimized unless required for safety or user preference.",
    "hypertrophy": "Bias toward main lifts plus accessories for volume; finishers are deprioritized unless fat loss/endurance is also high.",
    "mobility": "Bias toward mobility sessions and extended warmup/cooldown; mobility time is capped to prevent dominating the week.",
    "conditioning": "Conditioning-only sessions are reserved for explicit allowance or safe scenarios; they require 5+ conditioning movements and 30+ minutes.",
}

HARD_CODED_BIAS_LOCATIONS = [
    "app/services/program.py:create_program split-template selection (days_per_week-based)",
    "app/services/program.py:_get_default_split_template (discipline_preference-driven cardio/mobility days)",
    "app/config/activity_distribution.py:goal_bucket_weights and goal_finisher_thresholds",
]


DEFAULT_USER_PREFERENCES = {
    "cardio_preference": "finisher",
    "max_finishers_per_week": 3,
    "max_cardio_days_per_week": 2,
}

GOAL_SESSION_TYPE_WEIGHTS = {
    "strength": {
        "accessory": 0.8,
        "finisher": 0.1,
        "cardio_day": 0.1,
    },
    "hypertrophy": {
        "accessory": 0.8,
        "finisher": 0.1,
        "cardio_day": 0.1,
    },
    "endurance": {
        "accessory": 0.2,
        "finisher": 0.5,
        "cardio_day": 0.3,
    },
    "fat_loss": {
        "accessory": 0.3,
        "finisher": 0.5,
        "cardio_day": 0.2,
    },
    "mobility": {
        "accessory": 0.5,
        "finisher": 0.2,
        "cardio_day": 0.3,
    },
}

ROUNDING_STRATEGIES = {
    "finisher": "ceil",
    "cardio_day": "floor",
    "accessory": "round",
}

SESSION_TYPE_CALCULATOR_CONFIG = {
    "min_lifting_days": 1,
    "max_cardio_pct": 0.5,
    "min_allocation_accuracy": 0.85,
    "rounding_drift_threshold": 0.15,
}

SESSION_TYPE_DISTRIBUTOR_CONFIG = {
    "min_finisher_gap_days": 2,
    "max_cardio_gap_days": 3,
    "balance_upper_lower_ratio_min": 0.5,
    "balance_upper_lower_ratio_max": 2.0,
    "strict_validation": True,
}
