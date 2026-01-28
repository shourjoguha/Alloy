"""Pydantic schemas for settings and configuration API endpoints."""
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, computed_field, model_validator, field_validator

from app.models.enums import (
    E1RMFormula,
    ExperienceLevel,
    PersonaTone,
    PersonaAggression,
    MovementPattern,
    PrimaryRegion,
    PrimaryMuscle,
    SkillLevel,
    CNSLoad,
    MetricType,
    Sex,
    MuscleRole,
    MovementTier,
    MetabolicDemand,
)


# ============== Biomechanics Profile Validator ==============

class BiomechanicsProfileValidator(BaseModel):
    """Soft enum validation for biomechanics_profile JSONB."""
    
    archetype: str
    movement_vectors: dict[str, Any]
    joint_involvement: dict[str, float]
    loading_pattern: dict[str, str]
    stability_demands: dict[str, float]
    range_of_motion: dict[str, str]
    temporal_factors: dict[str, bool]
    
    @field_validator('archetype')
    @classmethod
    def validate_archetype(cls, v: str) -> str:
        """Validate archetype against allowed values."""
        valid_archetypes = {
            "bilateral_compound", "unilateral_compound", "bilateral_isolation",
            "unilateral_isolation", "dynamic_compound", "static_compound",
            "plyometric", "carry_pattern", "rotational_compound", "conditioning_pattern"
        }
        if v not in valid_archetypes:
            raise ValueError(f"Invalid archetype '{v}'. Must be one of: {valid_archetypes}")
        return v
    
    @field_validator('movement_vectors')
    @classmethod
    def validate_movement_vectors(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate movement vector structure."""
        valid_planes = {"sagittal", "frontal", "transverse"}
        
        if 'primary' not in v:
            raise ValueError("movement_vectors must contain 'primary' key")
        
        if v['primary'] not in valid_planes:
            raise ValueError(f"Invalid primary plane: {v['primary']}")
        
        if 'secondary' in v:
            if not isinstance(v['secondary'], list):
                raise ValueError("movement_vectors.secondary must be a list")
            for plane in v['secondary']:
                if plane not in valid_planes:
                    raise ValueError(f"Invalid secondary plane: {plane}")
        
        return v
    
    @field_validator('joint_involvement')
    @classmethod
    def validate_joint_involvement(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate joint involvement scores (0-10)."""
        valid_joints = {"ankle", "knee", "hip", "lumbar", "shoulder", "elbow", "wrist"}
        
        for joint, score in v.items():
            if joint not in valid_joints:
                raise ValueError(f"Invalid joint: {joint}")
            if not isinstance(score, (int, float)):
                raise ValueError(f"Joint score must be numeric: {joint}")
            if not 0 <= score <= 10:
                raise ValueError(f"Joint score must be 0-10: {joint}={score}")
        
        return v
    
    @field_validator('loading_pattern')
    @classmethod
    def validate_loading_pattern(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate loading pattern structure."""
        valid_types = {"axial", "peripheral", "hybrid"}
        valid_spinal_loads = {"none", "low", "moderate", "high"}
        
        if 'type' not in v or v['type'] not in valid_types:
            raise ValueError(f"Invalid loading_pattern.type: {v.get('type')}")
        
        if 'spinal_load' not in v or v['spinal_load'] not in valid_spinal_loads:
            raise ValueError(f"Invalid loading_pattern.spinal_load: {v.get('spinal_load')}")
        
        return v
    
    @field_validator('stability_demands')
    @classmethod
    def validate_stability_demands(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate stability demand scores (0-10)."""
        for demand, score in v.items():
            if not isinstance(score, (int, float)):
                raise ValueError(f"Stability demand must be numeric: {demand}")
            if not 0 <= score <= 10:
                raise ValueError(f"Stability demand must be 0-10: {demand}={score}")
        return v
    
    @field_validator('range_of_motion')
    @classmethod
    def validate_range_of_motion(cls, v: dict[str, str]) -> dict[str, str]:
        """Validate range of motion values."""
        valid_rom = {"full", "partial", "isometric", "none"}
        
        for rom_type, value in v.items():
            if value not in valid_rom:
                raise ValueError(f"Invalid ROM value: {rom_type}={value}")
        return v


# ============== User Settings Schemas ==============

class UserSettingsUpdate(BaseModel):
    """Schema for updating user settings."""
    active_e1rm_formula: E1RMFormula | None = None
    use_metric: bool | None = None  # True = kg, False = lbs


class UserSettingsResponse(BaseModel):
    """User settings response."""
    id: int
    user_id: int | None = None
    active_e1rm_formula: E1RMFormula | None = None
    use_metric: bool | None = None
    
    class Config:
        from_attributes = True


# ============== User Profile Schemas ==============

class UserProfileUpdate(BaseModel):
    """Schema for updating user profile."""
    name: str | None = None
    experience_level: ExperienceLevel | None = None
    persona_tone: PersonaTone | None = None
    persona_aggression: PersonaAggression | None = None
    # UserProfile fields
    date_of_birth: date | None = None
    sex: Sex | None = None
    height_cm: int | None = None
    # Advanced Preferences
    discipline_preferences: dict[str, Any] | None = None
    discipline_experience: dict[str, Any] | None = None
    scheduling_preferences: dict[str, Any] | None = None
    # Long Term Goals
    long_term_goal_category: str | None = None
    long_term_goal_description: str | None = None


class UserProfileResponse(BaseModel):
    """User profile response."""
    id: int
    name: str | None
    email: str | None
    experience_level: ExperienceLevel
    persona_tone: PersonaTone
    persona_aggression: PersonaAggression
    # UserProfile fields
    date_of_birth: date | None = None
    sex: Sex | None = None
    height_cm: int | None = None
    # Advanced Preferences
    discipline_preferences: dict[str, Any] | None = None
    discipline_experience: dict[str, Any] | None = None
    scheduling_preferences: dict[str, Any] | None = None
    # Long Term Goals
    long_term_goal_category: str | None = None
    long_term_goal_description: str | None = None
    
    class Config:
        from_attributes = True


# ============== Movement Schemas ==============

class MovementResponse(BaseModel):
    """Movement response schema."""
    id: int
    name: str
    pattern: str | None = None
    primary_pattern: MovementPattern | None = None
    secondary_patterns: list[str] | None = None
    primary_muscle: str | None = None
    primary_muscles: list[str] | None = None
    secondary_muscles: list[str] | None = None
    primary_region: PrimaryRegion | str | None = None
    default_equipment: str | None = None
    complexity: str | int | None = None
    cns_load: str | None = None
    cns_demand: int | None = None
    skill_level: SkillLevel | str | None = None
    compound: bool | None = None
    is_compound: bool | None = None
    is_complex_lift: bool | None = None
    is_unilateral: bool | None = None
    metric_type: str | None = None
    disciplines: list[str] | None = None
    equipment: list[str] | None = None
    substitution_group: str | None = None
    description: str | None = None
    user_id: int | None = None
    tier: MovementTier | None = None
    metabolic_demand: MetabolicDemand | None = None
    biomechanics_profile: dict[str, Any] | None = None
    
    @model_validator(mode='before')
    @classmethod
    def populate_lists(cls, data: Any) -> Any:
        """Populate list fields from relationships/scalars."""
        if hasattr(data, "__dict__"):
            # It's an ORM object
            
            # 1. Primary Muscles (Scalar -> List)
            if hasattr(data, "primary_muscle") and data.primary_muscle:
                # Ensure we handle both Enum and raw value
                val = data.primary_muscle.value if hasattr(data.primary_muscle, "value") else data.primary_muscle
                setattr(data, "primary_muscles", [val])
            
            # 2. Secondary Muscles (Relationship -> List)
            if hasattr(data, "muscle_maps") and data.muscle_maps:
                # Filter for SECONDARY or STABILIZER
                secondary = []
                for mm in data.muscle_maps:
                    # Check role
                    role_name = mm.role.name if hasattr(mm.role, "name") else str(mm.role)
                    if role_name in ["SECONDARY", "STABILIZER"]:
                        if mm.muscle:
                            secondary.append(mm.muscle.slug)
                setattr(data, "secondary_muscles", secondary)
            
            # 3. Disciplines (Relationship -> List)
            if hasattr(data, "disciplines") and data.disciplines:
                discs = []
                for d in data.disciplines:
                    val = d.discipline.value if hasattr(d.discipline, "value") else d.discipline
                    discs.append(val)
                setattr(data, "disciplines", discs)
                
            # 4. Equipment (Relationship -> List)
            if hasattr(data, "equipment") and data.equipment:
                eqs = []
                for e in data.equipment:
                    if e.equipment:
                        eqs.append(e.equipment.name)
                setattr(data, "equipment", eqs)
                if eqs:
                    setattr(data, "default_equipment", eqs[0])

            # 5. Pattern (Enum -> String/Enum)
            if hasattr(data, "pattern") and data.pattern:
                 setattr(data, "primary_pattern", data.pattern)

        return data

    @computed_field
    def discipline_tags(self) -> list[str] | None:
        """Backward compatibility for discipline_tags."""
        return self.disciplines

    @computed_field
    def equipment_tags(self) -> list[str] | None:
        """Backward compatibility for equipment_tags."""
        return self.equipment

    @computed_field
    def primary_discipline(self) -> str | None:
        """Backward compatibility for primary_discipline."""
        return self.disciplines[0] if self.disciplines else None

    class Config:
        from_attributes = True


class MovementCreate(BaseModel):
    """Schema for creating a custom movement."""
    name: str
    pattern: MovementPattern
    primary_muscle: PrimaryMuscle | None = None
    primary_region: PrimaryRegion | None = None
    secondary_muscles: list[PrimaryMuscle] | None = None
    default_equipment: str | None = None
    skill_level: SkillLevel | None = SkillLevel.INTERMEDIATE
    cns_load: CNSLoad | None = CNSLoad.MODERATE
    metric_type: MetricType | None = MetricType.REPS
    compound: bool = True
    description: str | None = None
    tier: MovementTier = MovementTier.BRONZE
    metabolic_demand: MetabolicDemand = MetabolicDemand.ANABOLIC
    biomechanics_profile: dict[str, Any] | None = None
    
    @field_validator('biomechanics_profile')
    @classmethod
    def validate_biomechanics_profile(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate biomechanics_profile using BiomechanicsProfileValidator."""
        if v is not None:
            try:
                BiomechanicsProfileValidator(**v)
            except ValueError as e:
                raise ValueError(f"Invalid biomechanics_profile: {e}")
        return v


class MovementUpdate(BaseModel):
    """Schema for updating a custom movement."""
    name: str | None = None
    pattern: MovementPattern | None = None
    primary_muscle: PrimaryMuscle | None = None
    primary_region: PrimaryRegion | None = None
    secondary_muscles: list[PrimaryMuscle] | None = None
    default_equipment: str | None = None
    skill_level: SkillLevel | None = None
    cns_load: CNSLoad | None = None
    metric_type: MetricType | None = None
    compound: bool | None = None
    description: str | None = None
    tier: MovementTier | None = None
    metabolic_demand: MetabolicDemand | None = None
    biomechanics_profile: dict[str, Any] | None = None
    
    @field_validator('biomechanics_profile')
    @classmethod
    def validate_biomechanics_profile(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate biomechanics_profile using BiomechanicsProfileValidator."""
        if v is not None:
            try:
                BiomechanicsProfileValidator(**v)
            except ValueError as e:
                raise ValueError(f"Invalid biomechanics_profile: {e}")
        return v


class MovementListResponse(BaseModel):
    """List of movements with filtering."""
    movements: list[MovementResponse]
    total: int
    limit: int | None = None
    offset: int | None = None
    filters_applied: dict[str, Any] | None = None


class MovementFiltersResponse(BaseModel):
    """Distinct movement filters available in the repository."""
    patterns: list[str]
    regions: list[str]
    equipment: list[str]
    primary_disciplines: list[str]
    secondary_muscles: list[str] | None = None
    types: list[str] | None = None


# ============== Heuristic Config Schemas ==============

class HeuristicConfigCreate(BaseModel):
    """Schema for creating a new heuristic config version."""
    name: str
    key: str | None = None
    category: str | None = None
    json_blob: dict[str, Any] | None = None
    value: dict[str, Any] | None = None
    description: str | None = None


class HeuristicConfigResponse(BaseModel):
    """Heuristic config response."""
    id: int
    name: str | None = None
    key: str | None = None
    category: str | None = None
    version: int | None = None
    json_blob: dict[str, Any] | None = None
    value: dict[str, Any] | None = None
    description: str | None = None
    active: bool | None = None
    created_at: datetime | None = None
    
    class Config:
        from_attributes = True


class HeuristicConfigListResponse(BaseModel):
    """List of heuristic configs."""
    configs: list[HeuristicConfigResponse]
    
    
class ActivateConfigRequest(BaseModel):
    """Request to activate a specific config version."""
    version: int | None = None  # If None, activates the latest version


# ============== Movement Rule Schemas ==============

class MovementRuleResponse(BaseModel):
    """Movement rule response."""
    id: int
    user_id: int | None = None
    movement_id: int
    movement_name: str | None = None
    rule_type: str
    substitute_movement_id: int | None = None
    substitute_movement_name: str | None = None
    cadence: str | None = None
    reason: str | None = None
    notes: str | None = None
    
    class Config:
        from_attributes = True


class MovementRuleCreate(BaseModel):
    """Create movement rule."""
    movement_id: int
    rule_type: str
    substitute_movement_id: int | None = None
    cadence: str | None = Field(default="per_microcycle")
    reason: str | None = None
    notes: str | None = None


class MovementRuleUpdate(BaseModel):
    """Update movement rule."""
    rule_type: str | None = None
    substitute_movement_id: int | None = None
    cadence: str | None = None
    reason: str | None = None
    notes: str | None = None


# ============== Enjoyable Activity Schemas ==============

class EnjoyableActivityResponse(BaseModel):
    """Enjoyable activity response."""
    id: int
    user_id: int | None = None
    activity_type: str | None = None
    custom_name: str | None = None
    recommend_every_days: int | None = None
    enabled: bool | None = None
    notes: str | None = None
    
    class Config:
        from_attributes = True


class EnjoyableActivityCreate(BaseModel):
    """Create enjoyable activity."""
    activity_type: str
    custom_name: str | None = None
    recommend_every_days: int | None = Field(default=28, ge=7, le=90)
    notes: str | None = None


class EnjoyableActivityUpdate(BaseModel):
    """Update enjoyable activity."""
    recommend_every_days: int | None = Field(default=None, ge=7, le=90)
    enabled: bool | None = None
    notes: str | None = None


# ============== Movement Query & Substitution Schemas ==============

class MovementSubstitutionRequest(BaseModel):
    """Request for movement substitution."""
    movement_id: int
    user_spinal_tolerance: str = "moderate"
    user_joint_health: dict[str, int] | None = None


class MovementSubstitutionResponse(BaseModel):
    """Response for movement substitution."""
    movement_id: int | None = None
    movement_name: str | None = None
    reason: str | None = None
    safety_score: float | None = None
    biomechanics_profile: dict[str, Any] | None = None


class MovementSimilarityRequest(BaseModel):
    """Request for similar biomechanics substitution."""
    movement_id: int
    preferred_tier: str | None = None
    exclude_ids: list[int] | None = None


class MovementProgressionResponse(BaseModel):
    """Response for movement progression path."""
    movement_id: int
    movement_name: str
    skill_level: str
    tier: str
    cns_load: str | None = None
    spinal_load: str | None = None
    archetype: str | None = None
    notes: str | None = None


class MovementRegressionRequest(BaseModel):
    """Request for movement regression options."""
    movement_id: int
    injury_context: dict[str, Any] | None = None


class MovementRegressionResponse(BaseModel):
    """Response for movement regression options."""
    movement_id: int
    movement_name: str
    reason: str
    safety_score: float
    spinal_load: str | None = None
    archetype: str | None = None


class BiomechanicsQueryRequest(BaseModel):
    """Request for biomechanics-based movement query."""
    archetype: str | None = None
    joint: str | None = None
    min_joint_score: float = 7.0
    spinal_load_max: str | None = None
    primary_plane: str | None = None
    tier: str | None = None
    metabolic_demand: str | None = None
