"""Pydantic schemas for program-related API endpoints."""
from datetime import date as DateType, datetime as DatetimeType
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    Goal,
    SplitTemplate,
    ProgressionStyle,
    PersonaTone,
    PersonaAggression,
    MicrocycleStatus,
    SessionType,
    MetricType,
    CircuitType,
)


# ============== Program Schemas ==============

class GoalWeight(BaseModel):
    """Single goal with its weight."""
    goal: Goal
    weight: int = Field(ge=0, le=10)


class DisciplineWeight(BaseModel):
    """Single discipline/training style with its weight."""
    discipline: str  # e.g., "bodybuilding", "powerlifting", "crossfit"
    weight: int = Field(ge=0, le=10)


class HybridDayDefinition(BaseModel):
    """Day definition for hybrid splits."""
    day: int = Field(ge=1, le=14)
    session_type: SessionType
    focus: list[str] | None = None  # Movement patterns to focus on
    notes: str | None = None


class HybridBlockComposition(BaseModel):
    """Block composition for hybrid splits."""
    blocks: list[str]  # e.g., ["ppl_block", "ppl_block", "cardio_block", "rest_block"]


class HybridDefinition(BaseModel):
    """Hybrid split definition - either day-by-day or block composition."""
    mode: str = Field(pattern="^(day_by_day|block_composition)$")
    days: list[HybridDayDefinition] | None = None
    composition: HybridBlockComposition | None = None
    
    @model_validator(mode="after")
    def validate_mode_data(self):
        if self.mode == "day_by_day" and not self.days:
            raise ValueError("days required for day_by_day mode")
        if self.mode == "block_composition" and not self.composition:
            raise ValueError("composition required for block_composition mode")
        return self


class MovementRuleCreate(BaseModel):
    """Movement rule for program creation."""
    movement_id: int
    rule_type: str = Field(pattern="^(hard_no|hard_yes|preferred)$")
    cadence: str = Field(default="per_microcycle", pattern="^(per_microcycle|weekly|biweekly)$")
    notes: str | None = None


class EnjoyableActivityCreate(BaseModel):
    """Enjoyable activity for program creation."""
    activity_type: str
    custom_name: str | None = None
    recommend_every_days: int = Field(default=28, ge=7, le=90)


class ProgramCreate(BaseModel):
    """Schema for creating a new program."""
    name: str | None = None
    # Goals (1-3 required, weights must sum to 10)
    goals: list[GoalWeight] = Field(min_length=1, max_length=3)
    
    # Duration
    duration_weeks: int = Field(ge=8, le=12)
    program_start_date: DateType | None = None  # Defaults to today (renamed to avoid shadowing)
    
    # Structure
    split_template: SplitTemplate | None = None  # Optional - system determines if not provided
    days_per_week: int = Field(ge=2, le=7)  # User's training frequency preference
    max_session_duration: int = Field(default=60, ge=15, le=180)  # Max minutes per session
    progression_style: ProgressionStyle | None = None
    hybrid_definition: HybridDefinition | None = None
    
    # Deload
    deload_every_n_microcycles: int = Field(default=4, ge=2, le=8)
    
    # Persona (optional - uses user defaults if not provided)
    persona_tone: PersonaTone | None = None
    persona_aggression: PersonaAggression | None = None
    
    # Disciplines/Training styles (optional - ten dollar method, weights sum to 10)
    disciplines: list[DisciplineWeight] | None = None
    
    # Movement rules (optional)
    movement_rules: list[MovementRuleCreate] | None = None
    
    # Enjoyable activities (optional)
    enjoyable_activities: list[EnjoyableActivityCreate] | None = None
    
    @field_validator("goals")
    @classmethod
    def validate_goals_sum(cls, v):
        total = sum(g.weight for g in v)
        if total != 10:
            raise ValueError(f"Goal weights must sum to 10, got {total}")
        # Check for unique goals
        goal_names = [g.goal for g in v]
        if len(goal_names) != len(set(goal_names)):
            raise ValueError("Goals must be unique")
        return v

    @field_validator("duration_weeks")
    @classmethod
    def validate_duration_weeks_even(cls, v: int):
        if v % 2 != 0:
            raise ValueError("duration_weeks must be an even number")
        return v
    
    @model_validator(mode="after")
    def validate_hybrid(self):
        if self.split_template == SplitTemplate.HYBRID and not self.hybrid_definition:
            raise ValueError("hybrid_definition required for HYBRID split template")
        return self


class ProgramUpdate(BaseModel):
    """Schema for updating a program."""
    name: str | None = None
    is_active: bool | None = None


class ProgramResponse(BaseModel):
    """Program response schema."""
    id: int
    user_id: int
    name: str | None = None
    program_start_date: DateType | None = None  # Renamed to avoid shadowing
    duration_weeks: int
    goal_1: Goal
    goal_2: Goal
    goal_3: Goal
    goal_weight_1: int
    goal_weight_2: int
    goal_weight_3: int
    split_template: SplitTemplate
    progression_style: ProgressionStyle
    hybrid_definition: dict | None = None
    deload_every_n_microcycles: int
    persona_tone: PersonaTone | None = None
    persona_aggression: PersonaAggression | None = None
    is_active: bool = True
    created_at: DatetimeType | None = None
    program_disciplines: list[DisciplineWeight] = []

    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def convert_program_disciplines(cls, data: Any) -> Any:
        """Convert ProgramDiscipline ORM instances to DisciplineWeight and map start_date to program_start_date."""
        try:
            if isinstance(data, dict):
                if 'start_date' in data and 'program_start_date' not in data:
                    data['program_start_date'] = data.pop('start_date')
                return data
                
            if not hasattr(data, 'program_disciplines'):
                return data
            
            converted_disciplines = []
            for pd in data.program_disciplines:
                if hasattr(pd, 'discipline') and hasattr(pd, 'weight'):
                    converted_disciplines.append({
                        'discipline': pd.discipline,
                        'weight': pd.weight
                    })
            
            data_dict = {}
            for field in cls.model_fields:
                if hasattr(data, field):
                    data_dict[field] = getattr(data, field)
            
            data_dict['program_disciplines'] = converted_disciplines
            return data_dict
        except Exception as e:
            import logging
            logging.exception("Error in convert_program_disciplines validator: %s", e)
            raise


# ============== Microcycle Schemas ==============

class MicrocycleResponse(BaseModel):
    """Microcycle response schema."""
    id: int
    program_id: int
    micro_start_date: DateType | None = None  # Renamed to avoid shadowing
    length_days: int
    sequence_number: int
    status: MicrocycleStatus
    is_deload: bool = False
    
    class Config:
        from_attributes = True


class MicrocycleWithSessionsResponse(MicrocycleResponse):
    """Microcycle with its sessions."""
    sessions: list["SessionResponse"] = []


# ============== Session Schemas ==============

class CircuitExerciseBlock(BaseModel):
    """Exercise within a circuit with full circuit-specific metrics."""
    movement: str
    movement_id: int | None = None
    exercise_sequence: int | None = None  # Position within the circuit
    
    # Metric type and value (mutually exclusive based on metric_type)
    metric_type: MetricType | None = None  # reps, time, distance, calories, time_under_tension
    reps: int | None = None
    distance_meters: float | None = None
    duration_seconds: int | None = None
    calories: int | None = None
    
    # Rest and notes
    rest_seconds: int | None = None
    notes: str | None = None
    
    # Prescribed weights for male/female
    rx_weight_male: float | None = None
    rx_weight_female: float | None = None


class CircuitBlock(BaseModel):
    """Circuit block schema with complete circuit metadata."""
    id: int | None = None  # Circuit template ID
    name: str | None = None
    circuit_type: CircuitType | None = None
    
    # Circuit-level metrics
    time_cap_seconds: int | None = None
    number_of_rounds: int | None = None
    work_rest_seconds: int | None = None  # For EMOM, work:rest ratio
    
    # All exercises in sequence
    exercises: list[CircuitExerciseBlock] = []
    
    # Optional circuit metadata
    notes: str | None = None
    difficulty_tier: int | str | None = None  # Can be int (1-5) or string (bronze/silver/gold)
    tags: list[str] = []


class ExerciseBlock(BaseModel):
    """Exercise within a session block."""
    movement: str
    movement_id: int | None = None
    sets: int | None = None  # Optional for cooldown/stretches that only have duration
    rep_range_min: int | None = None
    rep_range_max: int | None = None
    target_rpe: float | None = None
    target_rir: int | None = None
    duration_seconds: int | None = None
    rest_seconds: int | None = None
    superset_with: str | None = None
    notes: str | None = None


class FinisherBlock(BaseModel):
    """Finisher block schema (circuit-based finisher)."""
    type: str  # EMOM, AMRAP, circuit, etc.
    circuit_type: str | None = None
    duration_minutes: int | None = None
    rounds: str | int | None = None
    duration_seconds: int | None = None
    rest_seconds: int | None = None
    exercises: list[ExerciseBlock] | None = None
    notes: str | None = None
    
    # Full circuit data (when finisher is a circuit template)
    circuit: CircuitBlock | None = None


class SessionResponse(BaseModel):
    """Session response schema."""
    id: int
    microcycle_id: int
    session_date: DateType | None = Field(None, validation_alias="date")
    day_number: int
    session_type: SessionType
    intent_tags: list[str] = []
    
    # Circuit blocks (populated from circuit relationships)
    finisher_circuit: CircuitBlock | None = None
    
    # Sections (populated from exercises relationship)
    warmup: list[ExerciseBlock] | None = None
    main: list[ExerciseBlock] | None = None
    accessory: list[ExerciseBlock] | None = None
    cooldown: list[ExerciseBlock] | None = None
    
    # Time estimation
    estimated_duration_minutes: int | None = None
    warmup_duration_minutes: int | None = None
    main_duration_minutes: int | None = None
    accessory_duration_minutes: int | None = None
    finisher_duration_minutes: int | None = None
    cooldown_duration_minutes: int | None = None
    
    coach_notes: str | None
    
    class Config:
        from_attributes = True

    @model_validator(mode='before')
    @classmethod
    def populate_sections_from_exercises(cls, data: Any) -> Any:
        """Populate section fields from the exercises relationship."""
        # specific imports to avoid circular dependencies
        from app.models.enums import ExerciseRole
        
        # If data is not an object with 'exercises' attribute, return as is
        if not hasattr(data, 'exercises'):
            return data
            
        # Initialize sections
        warmup = []
        main = []
        accessory = []
        cooldown = []
        finisher_circuit = None
        
        # Helper to convert SessionExercise to ExerciseBlock
        def to_block(ex) -> dict:
            return {
                "movement": ex.movement.name if ex.movement else "Unknown Movement",
                "movement_id": ex.movement_id,
                "sets": ex.target_sets,
                "rep_range_min": ex.target_rep_range_min,
                "rep_range_max": ex.target_rep_range_max,
                "target_rpe": ex.target_rpe,
                "target_rir": ex.target_rir,
                "duration_seconds": ex.target_duration_seconds,
                "rest_seconds": ex.default_rest_seconds,
                "superset_with": None, # Logic for superset naming could be added here
                "notes": ex.notes
            }
        
        # Helper to convert circuit template to CircuitBlock with full exercise details
        def circuit_to_block(circuit_template) -> dict:
            """Convert a CircuitTemplate ORM object to CircuitBlock with complete exercise data."""
            if not circuit_template:
                return None
            
            # Get macro metrics if available for complete circuit data
            macro = getattr(circuit_template, 'macro_metrics', None)
            
            # Prefer melted_exercises relationship (normalized data) over exercises_json
            exercises = []
            
            # Check if melted_exercises relationship is loaded
            melted_exercises = getattr(circuit_template, 'melted_exercises', None)
            if melted_exercises is not None:
                # Use normalized CircuitMelted data
                for melted in melted_exercises:
                    exercises.append({
                        "movement": melted.movement_name or "Unknown Movement",
                        "movement_id": melted.movement_id or 0,
                        "sequence": melted.exercise_sequence,  # Frontend expects 'sequence' not 'exercise_sequence'
                        "metric_type": melted.metric_type.value if hasattr(melted.metric_type, 'value') else melted.metric_type,
                        "reps": melted.reps,
                        "distance_meters": melted.distance_meters,
                        "duration_seconds": melted.duration_seconds,
                        "calories": melted.calories,
                        "rest_seconds": melted.rest_seconds,
                        "notes": melted.notes,
                        "rx_weight_male": melted.rx_weight_male,
                        "rx_weight_female": melted.rx_weight_female,
                    })
            else:
                # Fallback to exercises_json (legacy format)
                for idx, ex_data in enumerate(circuit_template.exercises_json or []):
                    if isinstance(ex_data, dict):
                        exercises.append({
                            "movement": ex_data.get("movement_name") or ex_data.get("original", "Unknown Movement"),
                            "movement_id": ex_data.get("movement_id") or 0,
                            "sequence": idx + 1,  # Frontend expects 'sequence'
                            "metric_type": ex_data.get("metric_type"),
                            "reps": ex_data.get("reps"),
                            "distance_meters": ex_data.get("distance_meters"),
                            "duration_seconds": ex_data.get("duration_seconds"),
                            "calories": ex_data.get("calories"),
                            "rest_seconds": ex_data.get("rest_seconds"),
                            "notes": ex_data.get("notes"),
                            "rx_weight_male": ex_data.get("rx_weight_male"),
                            "rx_weight_female": ex_data.get("rx_weight_female"),
                        })
            
            # Return complete circuit data matching frontend CircuitBlock interface
            return {
                "circuit_id": circuit_template.id,
                "name": circuit_template.name,
                "circuit_type": circuit_template.circuit_type.value if hasattr(circuit_template.circuit_type, 'value') else circuit_template.circuit_type,
                "difficulty_tier": getattr(macro, 'difficulty_tier', 1) if macro else circuit_template.difficulty_tier,
                # Provide safe defaults when values are None to prevent NaN in frontend
                "estimated_duration_seconds": getattr(macro, 'estimated_duration_seconds', circuit_template.default_duration_seconds) if macro else (circuit_template.default_duration_seconds or 1500),  # Default to 25 min
                "default_rounds": getattr(macro, 'default_rounds', circuit_template.default_rounds) if macro else (circuit_template.default_rounds or 1),  # Default to 1 round
                "primary_region": getattr(macro, 'primary_region', "full_body").value if macro and hasattr(getattr(macro, 'primary_region', None), 'value') else "full_body",
                "primary_muscles": getattr(macro, 'primary_muscles', []) if macro else [],
                "fatigue_factor": getattr(macro, 'fatigue_factor', 1.0) if macro else 1.0,
                "stimulus_factor": getattr(macro, 'stimulus_factor', 1.0) if macro else 1.0,
                "exercises": exercises,
            }

        # Sort exercises by order
        sorted_exercises = sorted(data.exercises, key=lambda x: x.order_in_session)
        
        for ex in sorted_exercises:
            # Skip if no section defined (shouldn't happen)
            if not ex.exercise_role:
                continue
                
            block = to_block(ex)
            
            # Robust comparison for Enum or string
            section_val = ex.exercise_role
            if hasattr(section_val, 'value'):
                section_val = section_val.value
            
            if section_val == ExerciseRole.WARMUP.value:
                warmup.append(block)
            elif section_val == ExerciseRole.MAIN.value:
                main.append(block)
            elif section_val == ExerciseRole.ACCESSORY.value:
                accessory.append(block)
            elif section_val == ExerciseRole.COOLDOWN.value:
                cooldown.append(block)
            elif section_val == ExerciseRole.FINISHER.value:
                # For finisher, we might have multiple exercises in a circuit
                # This logic assumes simple mapping for now.
                pass

        # Extract finisher_circuit data with complete circuit information
        # When finisher_circuit exists, it provides complete circuit data with proper metric values
        if hasattr(data, 'finisher_circuit') and data.finisher_circuit:
            finisher_circuit = circuit_to_block(data.finisher_circuit)

        # Better approach: Return a dict with all fields populated
        result = {
            "id": data.id,
            "microcycle_id": data.microcycle_id,
            "date": data.date,
            "day_number": data.day_number,
            "session_type": data.session_type,
            "intent_tags": data.intent_tags,
            "finisher_circuit": finisher_circuit,
            "warmup": warmup,
            "main": main,
            "accessory": accessory,
            "cooldown": cooldown,
            "estimated_duration_minutes": data.estimated_duration_minutes,
            "warmup_duration_minutes": data.warmup_duration_minutes,
            "main_duration_minutes": data.main_duration_minutes,
            "accessory_duration_minutes": data.accessory_duration_minutes,
            "finisher_duration_minutes": data.finisher_duration_minutes,
            "cooldown_duration_minutes": data.cooldown_duration_minutes,
            "coach_notes": data.coach_notes,
            "has_circuits": bool(data.finisher_circuit_id),
        }
        return result


class ProgramWithMicrocycleResponse(BaseModel):
    """Program with active microcycle and sessions."""
    program: ProgramResponse
    active_microcycle: MicrocycleResponse | None
    upcoming_sessions: list[SessionResponse]
    microcycles: list[MicrocycleWithSessionsResponse] = []
    
    class Config:
        from_attributes = True
