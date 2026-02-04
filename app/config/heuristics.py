"""Heuristic configurations for training logic.

This module contains all heuristic configurations that were previously stored in the database.
Moving to code provides better type safety, performance, and version control.

All configurations are read-only constants imported at module load time.
"""

from typing import TypedDict, Dict, Any, List


class GoalDoseConfig(TypedDict):
    """Configuration for a single training goal."""
    intensity_range: List[float]
    rep_range: List[int]
    sets_per_muscle_group_weekly: List[int]
    rest_seconds: List[int]
    preferred_patterns: List[str]
    preferred_disciplines: List[str]
    tempo: str
    frequency_per_pattern_weekly: int
    cns_budget_daily: str


class ActivityInterferenceConfig(TypedDict):
    """Configuration for activity interference rules."""
    conflicts_with_before: List[str]
    conflicts_with_after: List[str]
    buffer_hours_before: int
    buffer_hours_after: int
    affected_muscles: List[str]
    cns_impact: str


class TrainingInterferenceConfig(TypedDict):
    """Configuration for training interference rules."""
    min_recovery_hours: int
    max_consecutive_days: int


class SetExecutionTimeConfig(TypedDict):
    """Configuration for set execution time by rep range."""
    by_rep_range: Dict[str, int]
    by_metric_type: Dict[str, str]


class RestConfig(TypedDict):
    """Configuration for rest times."""
    warmup: int
    main: Dict[str, int]
    accessory: int
    skill: int
    finisher: int
    cooldown: int


class TimeEstimationConfig(TypedDict):
    """Time estimation configuration."""
    warmup: Dict[str, int]
    cooldown: Dict[str, int]
    transition_between_exercises_seconds: int
    set_execution_time: SetExecutionTimeConfig
    rest_seconds_by_role: RestConfig
    superset_rest_reduction_percent: int
    circuit_rest_between_rounds_seconds: int


class CnsDailyBudgetConfig(TypedDict):
    """CNS daily budget by persona aggression level."""
    level_1: int
    level_2: int
    level_3: int
    level_4: int
    level_5: int


class CnsMultiplierConfig(TypedDict):
    """CNS load multipliers."""
    main_lift: float
    accessory: float
    warmup: float
    finisher: float
    deload_week: float


class RecoveryModifierConfig(TypedDict):
    """Recovery modifier factors."""
    sleep_poor: float
    sleep_good: float
    sleep_excellent: float
    soreness_high: float
    soreness_moderate: float
    soreness_low: float
    hrv_below_baseline: float
    hrv_at_baseline: float
    hrv_above_baseline: float


class CnsLoadBudgetConfig(TypedDict):
    """CNS load budget configuration."""
    daily_budget_by_persona_aggression: CnsDailyBudgetConfig
    movement_cns_costs: Dict[str, int]
    multipliers: CnsMultiplierConfig
    recovery_modifiers: RecoveryModifierConfig
    pattern_daily_limits: Dict[str, int]


class DeloadPerformanceOverrideConfig(TypedDict):
    """Deload performance override configuration."""
    psi_drop_threshold_percent: int
    consecutive_sessions_threshold: int
    trigger_early_deload: bool


class DeloadSkipConditionsConfig(TypedDict):
    """Deload skip conditions configuration."""
    psi_trend_positive: bool
    user_feels_good: bool
    max_skip_count: int


class DeloadSessionStructureConfig(TypedDict):
    """Deload session structure configuration."""
    remove_finishers: bool
    reduce_main_sets: bool
    keep_mobility_work: bool
    reduce_accessory_exercises: bool
    max_rpe: int


class DeloadPolicyConfig(TypedDict):
    """Deload policy configuration."""
    default_deload_every_microcycles: int
    deload_intensity_reduction: float
    deload_volume_reduction: float
    performance_override: DeloadPerformanceOverrideConfig
    skip_deload_conditions: DeloadSkipConditionsConfig
    deload_session_structure: DeloadSessionStructureConfig


class E1RMFormulaConfig(TypedDict):
    """E1RM formula configuration."""
    formula: str
    description: str


class E1RMFormulasConfig(TypedDict):
    """E1RM formulas configuration."""
    epley: E1RMFormulaConfig
    brzycki: E1RMFormulaConfig
    lombardi: E1RMFormulaConfig
    oconner: E1RMFormulaConfig


class TrendDetectionConfig(TypedDict):
    """Trend detection configuration."""
    window_microcycles: int
    significant_change_percent: int


class PsiCalculationConfig(TypedDict):
    """PSI calculation configuration."""
    lookback_microcycles: int
    weighting: str
    minimum_exposures_for_valid_psi: int
    e1rm_formula_default: str
    e1rm_formulas: E1RMFormulasConfig
    trend_detection: TrendDetectionConfig


class DayStructureConfig(TypedDict):
    """Day structure configuration."""
    day: int
    type: str
    focus: List[str]


class SplitTemplateConfig(TypedDict):
    """Split template configuration."""
    days_per_cycle: int
    structure: List[DayStructureConfig]
    training_days: int
    rest_days: int


class CompositionBlockConfig(TypedDict):
    """Composition block configuration."""
    days: int
    sessions: List[str]


class HybridCompositionConfig(TypedDict):
    """Hybrid split composition configuration."""
    days_per_cycle: str
    structure: str
    composition_blocks: Dict[str, CompositionBlockConfig]


class SplitTemplatesConfig(TypedDict):
    """Split templates configuration."""
    upper_lower: SplitTemplateConfig
    ppl: SplitTemplateConfig
    full_body: SplitTemplateConfig
    hybrid: HybridCompositionConfig


class SingleProgressionConfig(TypedDict):
    """Single progression configuration."""
    description: str
    trigger: str
    weight_increase_percent: float
    weight_increase_min_kg: float
    reset_reps_on_increase: bool


class Phase1Config(TypedDict):
    """Phase 1 configuration."""
    increase: str
    until: str


class Phase2Config(TypedDict):
    """Phase 2 configuration."""
    increase: str
    amount_percent: int
    reset_reps_to: str


class DoubleProgressionConfig(TypedDict):
    """Double progression configuration."""
    description: str
    phase_1: Phase1Config
    phase_2: Phase2Config


class PausePositionsConfig(TypedDict):
    """Pause positions configuration."""
    squat: str
    bench: str
    deadlift: str
    row: str


class PausedVariationsConfig(TypedDict):
    """Paused variations configuration."""
    description: str
    pause_positions: PausePositionsConfig
    pause_duration_seconds: List[int]
    progression_order: List[str]


class BuildPhaseConfig(TypedDict):
    """Build phase configuration."""
    start_reps: str
    target_reps: str
    weeks_to_build: int


class DropPhaseConfig(TypedDict):
    """Drop phase configuration."""
    drop_reps_to: str
    weight_increase_percent: int


class BuildToDropConfig(TypedDict):
    """Build to drop configuration."""
    description: str
    build_phase: BuildPhaseConfig
    drop_phase: DropPhaseConfig


class ProgressionRulesConfig(TypedDict):
    """Progression rules configuration."""
    single_progression: SingleProgressionConfig
    double_progression: DoubleProgressionConfig
    paused_variations: PausedVariationsConfig
    build_to_drop: BuildToDropConfig


class ToneConfig(TypedDict):
    """Coach persona tone configuration."""
    language_style: str
    encouragement_level: str
    explanation_depth: str
    example_phrases: List[str]


class AggressionLevelConfig(TypedDict):
    """Aggression level configuration."""
    name: str
    intensity_modifier: float
    volume_modifier: float
    deload_frequency_modifier: float
    risk_tolerance: str


class PersonaDefinitionsConfig(TypedDict):
    """Persona definitions configuration."""
    tones: Dict[str, ToneConfig]
    aggression_levels: Dict[str, AggressionLevelConfig]


class OnsetHoursConfig(TypedDict):
    """DOMS onset hours configuration."""
    min: int
    typical: int
    max: int


class PeakHoursConfig(TypedDict):
    """DOMS peak hours configuration."""
    min: int
    typical: int
    max: int


class AttributionConfidenceConfig(TypedDict):
    """Attribution confidence configuration."""
    single_session_in_window: str
    multiple_sessions_same_pattern: str
    no_recent_training: str


class DomsAttributionConfig(TypedDict):
    """DOMS attribution configuration."""
    onset_hours: OnsetHoursConfig
    peak_hours: PeakHoursConfig
    muscle_to_pattern_mapping: Dict[str, List[str]]
    attribution_confidence: AttributionConfidenceConfig


GOAL_DOSE_HEURISTICS: Dict[str, GoalDoseConfig] = {
    "strength": {
        "intensity_range": [0.80, 0.95],
        "rep_range": [1, 6],
        "sets_per_muscle_group_weekly": [10, 15],
        "rest_seconds": [180, 300],
        "preferred_patterns": ["squat", "hinge", "horizontal_push", "vertical_push", "horizontal_pull", "vertical_pull"],
        "preferred_disciplines": ["powerlifting", "strength"],
        "tempo": "controlled",
        "frequency_per_pattern_weekly": 2,
        "cns_budget_daily": "high"
    },
    "hypertrophy": {
        "intensity_range": [0.60, 0.80],
        "rep_range": [6, 15],
        "sets_per_muscle_group_weekly": [15, 25],
        "rest_seconds": [60, 120],
        "preferred_patterns": ["all"],
        "preferred_disciplines": ["hypertrophy", "strength"],
        "tempo": "controlled_with_squeeze",
        "frequency_per_pattern_weekly": 2,
        "cns_budget_daily": "moderate"
    },
    "endurance": {
        "intensity_range": [0.40, 0.65],
        "rep_range": [15, 30],
        "sets_per_muscle_group_weekly": [12, 20],
        "rest_seconds": [30, 60],
        "preferred_patterns": ["all"],
        "preferred_disciplines": ["endurance", "calisthenics", "athleticism"],
        "tempo": "moderate",
        "frequency_per_pattern_weekly": 3,
        "cns_budget_daily": "low"
    },
    "fat_loss": {
        "intensity_range": [0.50, 0.75],
        "rep_range": [10, 20],
        "sets_per_muscle_group_weekly": [12, 18],
        "rest_seconds": [30, 60],
        "preferred_patterns": ["all"],
        "preferred_disciplines": ["athleticism", "endurance"],
        "tempo": "fast_controlled",
        "frequency_per_pattern_weekly": 3,
        "cns_budget_daily": "moderate",
        "prefer_supersets": True,
        "prefer_circuits": True
    },
    "mobility": {
        "intensity_range": [0.0, 0.50],
        "rep_range": [8, 15],
        "sets_per_muscle_group_weekly": [6, 12],
        "rest_seconds": [30, 60],
        "preferred_patterns": ["mobility", "isometric", "core"],
        "preferred_disciplines": ["mobility", "yoga", "rehabilitation"],
        "tempo": "slow_controlled",
        "frequency_per_pattern_weekly": 4,
        "cns_budget_daily": "very_low",
        "hold_duration_seconds": [30, 90]
    },
    "explosiveness": {
        "intensity_range": [0.50, 0.80],
        "rep_range": [1, 6],
        "sets_per_muscle_group_weekly": [8, 15],
        "rest_seconds": [120, 240],
        "preferred_patterns": ["plyometric", "olympic", "hinge", "squat"],
        "preferred_disciplines": ["olympic", "athleticism", "explosiveness"],
        "tempo": "explosive",
        "frequency_per_pattern_weekly": 2,
        "cns_budget_daily": "high",
        "require_full_recovery": True
    },
    "speed": {
        "intensity_range": [0.30, 0.60],
        "rep_range": [3, 8],
        "sets_per_muscle_group_weekly": [8, 12],
        "rest_seconds": [180, 300],
        "preferred_patterns": ["plyometric", "carry", "lunge"],
        "preferred_disciplines": ["athleticism", "speed"],
        "tempo": "maximum_velocity",
        "frequency_per_pattern_weekly": 2,
        "cns_budget_daily": "high",
        "require_full_recovery": True
    }
}

INTERFERENCE_RULES: Dict[str, Any] = {
    "activity_interference": {
        "bouldering": {
            "conflicts_with_before": ["horizontal_pull", "vertical_pull"],
            "conflicts_with_after": ["horizontal_pull", "vertical_pull"],
            "buffer_hours_before": 24,
            "buffer_hours_after": 48,
            "affected_muscles": ["lats", "biceps", "forearms", "upper_back"],
            "cns_impact": "high"
        },
        "tennis": {
            "conflicts_with_before": ["horizontal_push", "vertical_push"],
            "conflicts_with_after": ["squat", "lunge", "horizontal_push"],
            "buffer_hours_before": 12,
            "buffer_hours_after": 24,
            "affected_muscles": ["front_delts", "triceps", "quadriceps", "calves"],
            "cns_impact": "moderate"
        },
        "cycling": {
            "conflicts_with_before": [],
            "conflicts_with_after": ["squat", "hinge", "lunge"],
            "buffer_hours_before": 0,
            "buffer_hours_after": 12,
            "affected_muscles": ["quadriceps", "hamstrings", "glutes"],
            "cns_impact": "low"
        },
        "swimming": {
            "conflicts_with_before": [],
            "conflicts_with_after": ["horizontal_pull", "vertical_pull"],
            "buffer_hours_before": 0,
            "buffer_hours_after": 12,
            "affected_muscles": ["lats", "front_delts", "core"],
            "cns_impact": "low"
        },
        "hiking": {
            "conflicts_with_before": [],
            "conflicts_with_after": ["squat", "lunge", "hinge"],
            "buffer_hours_before": 0,
            "buffer_hours_after": 24,
            "affected_muscles": ["quadriceps", "hamstrings", "glutes", "calves"],
            "cns_impact": "moderate"
        },
        "basketball": {
            "conflicts_with_before": ["plyometric"],
            "conflicts_with_after": ["squat", "lunge", "plyometric"],
            "buffer_hours_before": 24,
            "buffer_hours_after": 48,
            "affected_muscles": ["quadriceps", "calves", "hamstrings"],
            "cns_impact": "high"
        },
        "football": {
            "conflicts_with_before": ["plyometric"],
            "conflicts_with_after": ["squat", "lunge", "plyometric"],
            "buffer_hours_before": 24,
            "buffer_hours_after": 48,
            "affected_muscles": ["quadriceps", "hamstrings", "glutes", "calves"],
            "cns_impact": "high"
        },
        "yoga": {
            "conflicts_with_before": [],
            "conflicts_with_after": [],
            "buffer_hours_before": 0,
            "buffer_hours_after": 0,
            "affected_muscles": [],
            "cns_impact": "very_low"
        },
        "martial_arts": {
            "conflicts_with_before": ["horizontal_push", "vertical_push", "core"],
            "conflicts_with_after": ["full_body"],
            "buffer_hours_before": 24,
            "buffer_hours_after": 48,
            "affected_muscles": ["core", "front_delts", "quadriceps"],
            "cns_impact": "high"
        },
        "dance": {
            "conflicts_with_before": [],
            "conflicts_with_after": ["squat", "lunge"],
            "buffer_hours_before": 0,
            "buffer_hours_after": 12,
            "affected_muscles": ["quadriceps", "calves", "core"],
            "cns_impact": "low"
        }
    },
    "training_interference": {
        "very_high_cns_session": {
            "min_recovery_hours": 72,
            "max_consecutive_days": 1
        },
        "high_cns_session": {
            "min_recovery_hours": 48,
            "max_consecutive_days": 2
        },
        "moderate_cns_session": {
            "min_recovery_hours": 24,
            "max_consecutive_days": 3
        },
        "low_cns_session": {
            "min_recovery_hours": 12,
            "max_consecutive_days": 5
        }
    }
}

TIME_ESTIMATION: TimeEstimationConfig = {
    "warmup": {
        "base_minutes": 5,
        "per_exercise_minutes": 1
    },
    "cooldown": {
        "base_minutes": 5,
        "per_stretch_minutes": 1
    },
    "transition_between_exercises_seconds": 45,
    "set_execution_time": {
        "by_rep_range": {
            "1-3": 15,
            "4-6": 25,
            "7-10": 35,
            "11-15": 45,
            "16-20": 55,
            "21+": 70
        },
        "by_metric_type": {
            "reps": "use_rep_range",
            "time": "use_target_duration",
            "time_under_tension": "use_target_duration",
            "distance": 60
        }
    },
    "rest_seconds_by_role": {
        "warmup": 30,
        "main": {
            "strength": 180,
            "hypertrophy": 90,
            "endurance": 45
        },
        "accessory": 60,
        "skill": 90,
        "finisher": 30,
        "cooldown": 15
    },
    "superset_rest_reduction_percent": 50,
    "circuit_rest_between_rounds_seconds": 60
}

CNS_LOAD_BUDGET: CnsLoadBudgetConfig = {
    "daily_budget_by_persona_aggression": {
        "level_1": 50,
        "level_2": 65,
        "level_3": 80,
        "level_4": 95,
        "level_5": 110
    },
    "movement_cns_costs": {
        "very_high": 25,
        "high": 18,
        "moderate": 12,
        "low": 6,
        "very_low": 2
    },
    "multipliers": {
        "main_lift": 1.5,
        "accessory": 1.0,
        "warmup": 0.3,
        "finisher": 0.8,
        "deload_week": 0.5
    },
    "recovery_modifiers": {
        "sleep_poor": 0.8,
        "sleep_good": 1.0,
        "sleep_excellent": 1.1,
        "soreness_high": 0.7,
        "soreness_moderate": 0.85,
        "soreness_low": 1.0,
        "hrv_below_baseline": 0.8,
        "hrv_at_baseline": 1.0,
        "hrv_above_baseline": 1.1
    },
    "pattern_daily_limits": {
        "olympic": 1,
        "plyometric": 2,
        "very_high_cns": 2
    }
}

DELOAD_POLICY: DeloadPolicyConfig = {
    "default_deload_every_microcycles": 4,
    "deload_intensity_reduction": 0.6,
    "deload_volume_reduction": 0.5,
    "performance_override": {
        "psi_drop_threshold_percent": 10,
        "consecutive_sessions_threshold": 2,
        "trigger_early_deload": True
    },
    "skip_deload_conditions": {
        "psi_trend_positive": True,
        "user_feels_good": True,
        "max_skip_count": 1
    },
    "deload_session_structure": {
        "remove_finishers": True,
        "reduce_main_sets": True,
        "keep_mobility_work": True,
        "reduce_accessory_exercises": True,
        "max_rpe": 6
    }
}

PSI_CALCULATION: PsiCalculationConfig = {
    "lookback_microcycles": 2,
    "weighting": "equal",
    "minimum_exposures_for_valid_psi": 2,
    "e1rm_formula_default": "epley",
    "e1rm_formulas": {
        "epley": {
            "formula": "weight * (1 + reps / 30)",
            "description": "Epley formula: weight × (1 + reps/30)"
        },
        "brzycki": {
            "formula": "weight * (36 / (37 - reps))",
            "description": "Brzycki formula: weight × 36 / (37 - reps)"
        },
        "lombardi": {
            "formula": "weight * (reps ** 0.10)",
            "description": "Lombardi formula: weight × reps^0.10"
        },
        "oconner": {
            "formula": "weight * (1 + reps / 40)",
            "description": "O'Conner formula: weight × (1 + reps/40)"
        }
    },
    "trend_detection": {
        "window_microcycles": 4,
        "significant_change_percent": 5
    }
}

SPLIT_TEMPLATES: SplitTemplatesConfig = {
    "upper_lower": {
        "days_per_cycle": 7,
        "structure": [
            {"day": 1, "type": "upper", "focus": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull"]},
            {"day": 2, "type": "lower", "focus": ["squat", "hinge", "lunge"]},
            {"day": 3, "type": "rest", "focus": []},
            {"day": 4, "type": "upper", "focus": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull"]},
            {"day": 5, "type": "lower", "focus": ["squat", "hinge", "lunge"]},
            {"day": 6, "type": "rest", "focus": []},
            {"day": 7, "type": "rest", "focus": []}
        ],
        "training_days": 4,
        "rest_days": 3
    },
    "ppl": {
        "days_per_cycle": 7,
        "structure": [
            {"day": 1, "type": "push", "focus": ["horizontal_push", "vertical_push", "triceps"]},
            {"day": 2, "type": "pull", "focus": ["horizontal_pull", "vertical_pull", "biceps"]},
            {"day": 3, "type": "legs", "focus": ["squat", "hinge", "lunge"]},
            {"day": 4, "type": "rest", "focus": []},
            {"day": 5, "type": "push", "focus": ["horizontal_push", "vertical_push", "triceps"]},
            {"day": 6, "type": "pull", "focus": ["horizontal_pull", "vertical_pull", "biceps"]},
            {"day": 7, "type": "legs", "focus": ["squat", "hinge", "lunge"]}
        ],
        "training_days": 6,
        "rest_days": 1
    },
    "full_body": {
        "days_per_cycle": 7,
        "structure": [
            {"day": 1, "type": "full_body", "focus": ["squat", "horizontal_push", "horizontal_pull"]},
            {"day": 2, "type": "rest", "focus": []},
            {"day": 3, "type": "full_body", "focus": ["hinge", "vertical_push", "vertical_pull"]},
            {"day": 4, "type": "rest", "focus": []},
            {"day": 5, "type": "full_body", "focus": ["lunge", "horizontal_push", "horizontal_pull"]},
            {"day": 6, "type": "rest", "focus": []},
            {"day": 7, "type": "rest", "focus": []}
        ],
        "training_days": 3,
        "rest_days": 4
    },
    "hybrid": {
        "days_per_cycle": "user_defined",
        "structure": "user_defined",
        "composition_blocks": {
            "ppl_block": {
                "days": 3,
                "sessions": ["push", "pull", "legs"]
            },
            "upper_lower_block": {
                "days": 2,
                "sessions": ["upper", "lower"]
            },
            "cardio_block": {
                "days": 1,
                "sessions": ["cardio"]
            },
            "mobility_block": {
                "days": 1,
                "sessions": ["mobility"]
            },
            "rest_block": {
                "days": 1,
                "sessions": ["rest"]
            }
        }
    }
}

PROGRESSION_RULES: ProgressionRulesConfig = {
    "single_progression": {
        "description": "Increase weight when hitting top of rep range for all sets",
        "trigger": "all_sets_at_rep_max",
        "weight_increase_percent": 2.5,
        "weight_increase_min_kg": 1.25,
        "reset_reps_on_increase": False
    },
    "double_progression": {
        "description": "Increase reps first, then weight when hitting rep ceiling",
        "phase_1": {
            "increase": "reps",
            "until": "all_sets_at_rep_max"
        },
        "phase_2": {
            "increase": "weight",
            "amount_percent": 5,
            "reset_reps_to": "rep_range_min"
        }
    },
    "paused_variations": {
        "description": "Add pauses to increase difficulty without adding weight",
        "pause_positions": {
            "squat": "bottom",
            "bench": "chest",
            "deadlift": "floor",
            "row": "contracted"
        },
        "pause_duration_seconds": [1, 2, 3],
        "progression_order": ["add_pause", "increase_pause", "remove_pause_add_weight"]
    },
    "build_to_drop": {
        "description": "Build up to rep range ceiling, then drop reps and increase load",
        "build_phase": {
            "start_reps": "rep_range_min",
            "target_reps": "rep_range_max",
            "weeks_to_build": 3
        },
        "drop_phase": {
            "drop_reps_to": "rep_range_min",
            "weight_increase_percent": 5
        }
    }
}

PERSONA_DEFINITIONS: PersonaDefinitionsConfig = {
    "tones": {
        "drill_sergeant": {
            "language_style": "direct, commanding, no-nonsense",
            "encouragement_level": "minimal",
            "explanation_depth": "brief",
            "example_phrases": ["Get it done.", "No excuses.", "Push through."]
        },
        "supportive": {
            "language_style": "warm, encouraging, patient",
            "encouragement_level": "high",
            "explanation_depth": "moderate",
            "example_phrases": ["You've got this!", "Great progress!", "Let's work together."]
        },
        "analytical": {
            "language_style": "data-driven, precise, methodical",
            "encouragement_level": "moderate",
            "explanation_depth": "high",
            "example_phrases": ["The data suggests...", "Based on your trends...", "Optimal approach is..."]
        },
        "motivational": {
            "language_style": "inspiring, energetic, positive",
            "encouragement_level": "very_high",
            "explanation_depth": "moderate",
            "example_phrases": ["Let's crush it!", "You're stronger than yesterday!", "Champions are made here!"]
        },
        "minimalist": {
            "language_style": "concise, efficient, to-the-point",
            "encouragement_level": "minimal",
            "explanation_depth": "minimal",
            "example_phrases": ["Do this.", "Next.", "Done."]
        }
    },
    "aggression_levels": {
        "1": {
            "name": "Conservative",
            "intensity_modifier": 0.85,
            "volume_modifier": 0.85,
            "deload_frequency_modifier": 0.75,
            "risk_tolerance": "low"
        },
        "2": {
            "name": "Moderate Conservative",
            "intensity_modifier": 0.92,
            "volume_modifier": 0.92,
            "deload_frequency_modifier": 0.9,
            "risk_tolerance": "low_moderate"
        },
        "3": {
            "name": "Balanced",
            "intensity_modifier": 1.0,
            "volume_modifier": 1.0,
            "deload_frequency_modifier": 1.0,
            "risk_tolerance": "moderate"
        },
        "4": {
            "name": "Moderate Aggressive",
            "intensity_modifier": 1.08,
            "volume_modifier": 1.08,
            "deload_frequency_modifier": 1.15,
            "risk_tolerance": "moderate_high"
        },
        "5": {
            "name": "Aggressive",
            "intensity_modifier": 1.15,
            "volume_modifier": 1.15,
            "deload_frequency_modifier": 1.25,
            "risk_tolerance": "high"
        }
    }
}

DOMS_ATTRIBUTION: DomsAttributionConfig = {
    "onset_hours": {
        "min": 12,
        "typical": 24,
        "max": 72
    },
    "peak_hours": {
        "min": 24,
        "typical": 48,
        "max": 72
    },
    "muscle_to_pattern_mapping": {
        "quadriceps": ["squat", "lunge", "plyometric"],
        "hamstrings": ["hinge", "lunge"],
        "glutes": ["hinge", "squat", "lunge"],
        "calves": ["plyometric", "carry"],
        "chest": ["horizontal_push"],
        "lats": ["vertical_pull", "horizontal_pull"],
        "upper_back": ["horizontal_pull", "vertical_pull"],
        "front_delts": ["vertical_push", "horizontal_push"],
        "rear_delts": ["horizontal_pull"],
        "side_delts": ["isolation"],
        "biceps": ["vertical_pull", "horizontal_pull"],
        "triceps": ["horizontal_push", "vertical_push"],
        "forearms": ["carry", "horizontal_pull"],
        "core": ["core", "rotation", "carry"],
        "obliques": ["rotation", "carry"],
        "lower_back": ["hinge", "squat"]
    },
    "attribution_confidence": {
        "single_session_in_window": "high",
        "multiple_sessions_same_pattern": "medium",
        "no_recent_training": "low"
    }
}

SECTION_PATTERN_FILTERS: Dict[str, Any] = {
    "warmup": {
        "include": ["mobility", "plyometric", "cardio"],
        "exclude": [],
        "max_duration_minutes": 10,
    },
    "main": {
        "exclude": ["mobility", "stretch", "cardio", "conditioning", "isolation"],
        "min_compound": 2,
    },
    "accessory": {
        "include": ["isolation"],
        "exclude": [],
    },
    "cooldown": {
        "include": ["stretch", "mobility"],
        "max_duration_minutes": 10,
    },
}
