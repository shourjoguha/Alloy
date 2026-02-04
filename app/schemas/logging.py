"""Pydantic schemas for logging API endpoints."""
from datetime import date as DateType, datetime as DatetimeType

from pydantic import BaseModel, Field

from app.models.enums import E1RMFormula, MovementPattern, RecoverySource


# ============== Top Set Schemas ==============

class TopSetCreate(BaseModel):
    """Top set log creation schema."""
    movement_id: int
    weight: float = Field(gt=0)
    reps: int = Field(ge=1)
    rpe: float | None = Field(default=None, ge=1, le=10)
    rir: int | None = Field(default=None, ge=0, le=10)
    avg_rest_seconds: int | None = Field(default=None, ge=0)


class TopSetResponse(BaseModel):
    """Top set response schema."""
    id: int
    movement_id: int
    movement_name: str | None = None
    weight: float
    reps: int
    rpe: float | None = None
    rir: int | None = None
    avg_rest_seconds: int | None = None
    e1rm: float | None = None  # Alias for e1rm_value
    e1rm_value: float | None = None
    e1rm_formula: E1RMFormula | None = None
    pattern: MovementPattern | None = None
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True


# ============== Workout Log Schemas (DB-backed) ==============

class WorkoutLogCreate(BaseModel):
    """Workout log creation schema."""
    session_id: int | None = None
    log_date: DateType | None = None
    completed: bool = True
    top_sets: list[TopSetCreate] | None = None
    notes: str | None = None
    perceived_difficulty: int | None = Field(default=None, ge=1, le=10)
    enjoyment_rating: int | None = Field(default=None, ge=1, le=5)
    feedback_tags: list[str] | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=0)


class WorkoutLogResponse(BaseModel):
    """Workout log response schema."""
    id: int
    user_id: int | None = None
    session_id: int | None = None
    log_date: DateType | None = None  # Renamed to avoid shadowing
    completed: bool = True
    notes: str | None = None
    perceived_difficulty: int | None = None
    enjoyment_rating: int | None = None
    feedback_tags: list[str] | None = None
    actual_duration_minutes: int | None = None
    top_sets: list[TopSetResponse] = []
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True


class WorkoutLogListResponse(BaseModel):
    """List of workout logs response."""
    logs: list[WorkoutLogResponse]
    total: int
    limit: int
    offset: int


class WorkoutLogSummary(BaseModel):
    """Summary of logged workout with computed metrics."""
    workout_log: WorkoutLogResponse
    pattern_exposures_created: int
    psi_updates: dict[str, float | None]  # Pattern -> new PSI value


# ============== Soreness Log Schemas ==============

class SorenessLogCreate(BaseModel):
    """Soreness log creation schema."""
    log_date: DateType | None = None
    body_part: str
    soreness_1_5: int = Field(ge=0, le=5)
    notes: str | None = None


# ============== Activity Logging Schemas ==============

class ActivityInstanceCreate(BaseModel):
    """Activity instance creation schema."""
    activity_definition_id: int
    duration_minutes: int = Field(ge=1)
    distance_km: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=500)
    perceived_difficulty: int = Field(ge=1, le=10)
    enjoyment_rating: int = Field(ge=1, le=5)
    performed_start: DatetimeType | None = None


# ============== Custom Workout Schemas ==============

class CustomExerciseCreate(BaseModel):
    """Exercise in a custom workout."""
    movement_id: int
    sets: int | None = None
    reps: int | None = None
    weight: float | None = None
    distance_meters: float | None = None
    duration_seconds: int | None = None
    notes: str | None = None

class CustomWorkoutCreate(BaseModel):
    """Custom workout creation schema."""
    log_date: DateType
    workout_name: str | None = Field(default=None, max_length=50)
    duration_minutes: int | None = None
    notes: str | None = None
    perceived_difficulty: int | None = Field(default=None, ge=1, le=10)
    enjoyment_rating: int | None = Field(default=None, ge=1, le=5)
    
    # Sections
    warmup: list[CustomExerciseCreate] | None = None
    main: list[CustomExerciseCreate] | None = None
    accessory: list[CustomExerciseCreate] | None = None
    finisher: list[CustomExerciseCreate] | None = None
    cooldown: list[CustomExerciseCreate] | None = None
    
    # Circuits
    finisher_circuit_id: int | None = None


class SorenessLogResponse(BaseModel):
    """Soreness log response schema."""
    id: int
    user_id: int | None = None
    log_date: DateType | None = None
    body_part: str
    soreness_1_5: int
    inferred_cause_session_id: int | None = None
    inferred_cause_description: str | None = None
    notes: str | None = None
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True


# ============== Recovery Signal Schemas ==============

class RecoverySignalCreate(BaseModel):
    """Recovery signal creation schema."""
    log_date: DateType | None = None
    session_id: int | None = None
    source: RecoverySource = RecoverySource.MANUAL
    hrv: float | None = None
    resting_hr: int | None = Field(default=None, ge=20, le=200)
    sleep_score: float | None = Field(default=None, ge=0, le=100)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    readiness: float | None = Field(default=None, ge=0, le=100)
    raw_payload: dict | None = None
    notes: str | None = None


class RecoverySignalResponse(BaseModel):
    """Recovery signal response schema."""
    id: int
    user_id: int | None = None
    log_date: DateType | None = None
    session_id: int | None = None
    source: RecoverySource
    hrv: float | None = None
    resting_hr: int | None = None
    sleep_score: float | None = None
    sleep_hours: float | None = None
    readiness: float | None = None
    raw_payload: dict | None = None
    notes: str | None = None
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True


class MuscleRecoveryStateResponse(BaseModel):
    """Muscle recovery state response schema."""
    id: int
    user_id: int | None = None
    muscle: str
    recovery_level: int
    last_updated_at: DatetimeType | None = None
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True


# ============== Progress/Metrics Schemas ==============

class PatternPSIResponse(BaseModel):
    """PSI for a single pattern."""
    pattern: MovementPattern
    psi_value: float | None
    exposure_count: int
    trend: str | None  # "increasing", "decreasing", "stable", "insufficient_data"


class ProgressSummaryResponse(BaseModel):
    """Overall progress summary."""
    user_id: int
    as_of_date: DateType
    pattern_psi: list[PatternPSIResponse]
    recent_workouts_count: int
    total_volume_last_week: float | None
    deload_recommended: bool
    declining_patterns: list[MovementPattern]


class PatternExposureResponse(BaseModel):
    """Pattern exposure response."""
    id: int
    user_id: int | None = None
    microcycle_id: int | None = None
    log_date: DateType | None = None
    pattern: MovementPattern
    e1rm_value: float
    source_top_set_log_id: int | None = None
    created_at: DatetimeType | None = None
    
    class Config:
        from_attributes = True
