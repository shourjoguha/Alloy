"""Pydantic schemas for daily planning and adaptation API endpoints."""
from datetime import date as DateType
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import PersonaTone, PersonaAggression, SessionType
from app.schemas.program import (
    ExerciseBlock, 
    FinisherBlock, 
    SessionResponse,
    CircuitBlock,
)


# ============== Daily Plan Schemas ==============

class DailyPlanRequest(BaseModel):
    """Request for getting daily plan."""
    program_id: int


class DailyPlanResponse(BaseModel):
    """Response with daily session plan."""
    plan_date: DateType | None = None  # Renamed to avoid shadowing
    session: SessionResponse | None = None
    is_rest_day: bool = False
    recommended_activities: list[str] | None = None
    coach_message: str | None = None


# ============== Adaptation Schemas ==============

class SorenessInput(BaseModel):
    """Soreness input for adaptation."""
    body_part: str
    level: int = Field(ge=1, le=5)  # 1=none, 5=severe


class RecoveryInput(BaseModel):
    """Recovery signals for adaptation."""
    sleep_quality: Literal["poor", "fair", "good", "excellent"] | None = None
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    energy_level: int | None = Field(default=None, ge=1, le=10)
    stress_level: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class AdaptationRequest(BaseModel):
    """Request to adapt a daily session."""
    program_id: int
    
    # Focus and preference
    focus_for_today: str | None = None  # e.g., "recovery", "strength", "endurance"
    preference: Literal["lift", "calisthenics", "cardio", "sport", "any"] | None = None
    
    # Constraints
    excluded_movements: list[str] | None = None  # Movement names to exclude
    excluded_patterns: list[str] | None = None  # Patterns to exclude (e.g., "squat")
    time_available_minutes: int | None = Field(default=None, ge=15, le=180)
    
    # Recovery context
    soreness: list[SorenessInput] | None = None
    recovery: RecoveryInput | None = None
    activity_yesterday: str | None = None  # e.g., "hiking", "tennis"
    
    # Mode selection
    adherence_vs_optimality: Literal["adherence", "optimality", "balanced"] = "balanced"
    
    # Persona override (for this session only)
    persona_tone_override: PersonaTone | None = None
    persona_aggression_override: PersonaAggression | None = None
    
    # Conversation context
    thread_id: int | None = None  # For continuing a conversation
    user_message: str | None = None  # Free-form input for conversation


class AdaptedSessionPlan(BaseModel):
    """Adapted session plan from LLM."""
    # Circuit blocks (when LLM returns circuits)
    circuit: CircuitBlock | None = None
    finisher_circuit: CircuitBlock | None = None
    
    # Sections (traditional session structure)
    warmup: list[ExerciseBlock] | None = None
    main: list[ExerciseBlock] | None = None
    accessory: list[ExerciseBlock] | None = None
    finisher: FinisherBlock | None = None
    cooldown: list[ExerciseBlock] | None = None
    estimated_duration_minutes: int
    reasoning: str
    trade_offs: str | None = None


class AdaptationResponse(BaseModel):
    """Response from adaptation endpoint."""
    plan_date: DateType | None = None
    original_session_type: SessionType | None = None
    adapted_plan: AdaptedSessionPlan | None = None
    changes_made: list[str] = []
    reasoning: str = ""
    trade_offs: str | None = None
    alternative_suggestion: str | None = None
    follow_up_question: str | None = None
    thread_id: int | None = None  # For continuing the conversation


# ============== Conversation Schemas ==============

class ConversationTurnResponse(BaseModel):
    """Single turn in a conversation."""
    turn_number: int
    role: str
    content: str
    structured_response: dict | None = None


class ConversationThreadResponse(BaseModel):
    """Conversation thread response."""
    id: int
    context_type: str
    context_date: DateType | None = None
    is_active: bool
    final_plan_accepted: bool
    turns: list[ConversationTurnResponse]
    accepted_plan: AdaptedSessionPlan | None = None


class AcceptPlanRequest(BaseModel):
    """Request to accept a plan from adaptation conversation."""
    thread_id: int


class AcceptPlanResponse(BaseModel):
    """Response after accepting a plan."""
    success: bool
    session_id: int | None = None
    message: str
