from pydantic import BaseModel, Field
from typing import Any, Optional
from app.models.enums import CircuitType, PrimaryRegion, MovementTier

class CircuitTemplateBase(BaseModel):
    name: str
    description: str | None = None
    circuit_type: CircuitType
    exercises_json: list[dict[str, Any]] = []
    default_rounds: int | None = None
    default_duration_seconds: int | None = None
    tags: list[str] = []
    difficulty_tier: int = 1

class CircuitTemplateCreate(CircuitTemplateBase):
    pass

class CircuitTemplateResponse(CircuitTemplateBase):
    id: int

    class Config:
        from_attributes = True


class CircuitTemplateUpdate(BaseModel):
    exercises_json: list[dict[str, Any]]


class CircuitTemplateAdminDetail(CircuitTemplateResponse):
    raw_workout: str | None = None


class CircuitMacroData(BaseModel):
    """Schema for circuit macro data from circuits_macro table."""
    total_exercises: int
    unique_movements: int
    total_reps: Optional[int] = None
    total_distance_meters: Optional[float] = None
    total_work_seconds: Optional[int] = None
    estimated_duration_seconds: Optional[int] = None
    difficulty_tier: MovementTier
    min_recovery_hours: int
    max_rx_weight_male: Optional[float] = None
    max_rx_weight_female: Optional[float] = None
    primary_muscles: list[str]
    muscle_engagement_score: float
    primary_region: PrimaryRegion
    region_diversity_score: float
    required_equipment: list[int]
    equipment_complexity: int
    movement_pattern_counts: dict[str, int]
    pattern_diversity_score: float
    metabolic_profile: Optional[dict[str, float]] = None
    estimated_calories_per_hour: Optional[float] = None
    space_requirement_meters: Optional[float] = None
    station_count: int
    default_rounds: Optional[int] = None
    circuit_type_intensity: Optional[str] = None
    data_completeness_score: float


class CircuitTemplateWithMacro(CircuitTemplateResponse):
    """Schema for circuit template with macro data included."""
    macro: Optional[CircuitMacroData] = None


class CircuitAssignmentCreate(BaseModel):
    """Schema for assigning a circuit to a session."""
    circuit_id: int
    circuit_role: str = Field(pattern="^(MAIN_CIRCUIT|FINISHER_CIRCUIT)$")
    rounds: int | None = Field(None, ge=1, le=10)
    replace_existing: bool = False


class CircuitAssignmentUpdate(BaseModel):
    """Schema for updating circuit assignment."""
    action: str = Field(pattern="^(UPDATE_ROUNDS|REMOVE)$")
    rounds: int | None = Field(None, ge=1, le=10)


class CircuitAssignmentResponse(BaseModel):
    """Schema for circuit assignment response."""
    session_id: int
    circuit_id: int
    circuit_role: str
    exercises_added: int
    exercises: list[dict[str, Any]]
    total_duration_minutes: int
    circuit_metadata: dict[str, Any]


class CircuitRecommendationRequest(BaseModel):
    """Schema for circuit recommendation request."""
    session_id: int
    circuit_type: CircuitType | None = None
    difficulty_tier: int | None = Field(None, ge=1, le=4)
    primary_region: PrimaryRegion | None = None
    exclude_used: bool = True
    max_duration_minutes: int | None = Field(None, ge=5, le=120)
    limit: int = Field(default=10, ge=1, le=50)


class CircuitRecommendationResponse(BaseModel):
    """Schema for circuit recommendation response."""
    session: dict[str, Any]
    recommendations: list[dict[str, Any]]
    total_available: int
    filters_applied: dict[str, Any]


class CircuitPreviewResponse(BaseModel):
    """Schema for circuit assignment preview."""
    preview: dict[str, Any]
    warnings: list[str] = []
