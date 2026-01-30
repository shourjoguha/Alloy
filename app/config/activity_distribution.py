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
        "rounds": "Max Rounds",
        "duration_minutes": 8,
        "notes": "Metabolic finisher",
        "exercises": [
            {"movement": "Kettlebell Swing", "reps": 15},
            {"movement": "Burpee", "reps": 10},
            {"movement": "Mountain Climber", "duration_seconds": 40},
        ],
    },
    "endurance": {
        "type": "interval",
        "circuit_type": "EMOM",
        "rounds": "10 Rounds",
        "duration_minutes": 10,
        "notes": "Endurance intervals",
        "exercises": [
            {"movement": "Row", "duration_seconds": 60},
            {"movement": "Easy Cardio", "duration_seconds": 30},
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
