"""Pydantic schemas for onboarding API endpoints."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class OnboardingStatusResponse(BaseModel):
    """Onboarding status response."""
    completed: bool
    version: Optional[str] = None
    
    class Config:
        from_attributes = True


class OnboardingAnswers(BaseModel):
    """Complete onboarding answers."""
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    sex: Optional[str] = None
    
    gym_comfort_level: Optional[str] = None
    athletic_background: Optional[dict[str, Any]] = None
    
    equipment_familiarity: Optional[dict[str, int]] = None
    movement_experience: Optional[dict[str, bool]] = None
    
    enjoyable_activities: Optional[list[str]] = None
    
    goal_category: Optional[str] = None
    goal_description: Optional[str] = None
    
    @field_validator('gym_comfort_level')
    @classmethod
    def validate_gym_comfort_level(cls, v: Optional[str]) -> Optional[str]:
        """Validate gym comfort level."""
        if v is not None:
            valid_levels = {'beginner', 'active', 'experienced'}
            if v not in valid_levels:
                raise ValueError(f"Invalid gym_comfort_level: {v}. Must be one of {valid_levels}")
        return v
    
    @field_validator('sex')
    @classmethod
    def validate_sex(cls, v: Optional[str]) -> Optional[str]:
        """Validate sex."""
        if v is not None:
            valid_values = {'male', 'female', 'intersex', 'unspecified'}
            if v not in valid_values:
                raise ValueError(f"Invalid sex: {v}. Must be one of {valid_values}")
        return v
    
    @field_validator('equipment_familiarity')
    @classmethod
    def validate_equipment_familiarity(cls, v: Optional[dict[str, int]]) -> Optional[dict[str, int]]:
        """Validate equipment familiarity scores are 1-5."""
        if v is not None:
            valid_equipment = {'barbell', 'dumbbell', 'kettlebell', 'machines', 'cables'}
            for eq, score in v.items():
                if eq not in valid_equipment:
                    raise ValueError(f"Invalid equipment: {eq}. Must be one of {valid_equipment}")
                if not isinstance(score, int) or not 1 <= score <= 5:
                    raise ValueError(f"Equipment familiarity score must be 1-5: {eq}={score}")
        return v
    
    @field_validator('movement_experience')
    @classmethod
    def validate_movement_experience(cls, v: Optional[dict[str, bool]]) -> Optional[dict[str, bool]]:
        """Validate movement experience values are booleans."""
        if v is not None:
            for movement, has_tried in v.items():
                if not isinstance(has_tried, bool):
                    raise ValueError(f"Movement experience must be boolean: {movement}={has_tried}")
        return v


class OnboardingProgressUpdate(BaseModel):
    """Partial onboarding progress update."""
    question_id: str
    answer_value: Any
    question_set_version: str = Field(default="v1")


class OnboardingResponseData(BaseModel):
    """Individual onboarding response."""
    id: int
    user_id: int
    question_id: str
    answer_value: Optional[Any] = None
    answered_at: datetime
    question_set_version: str
    
    class Config:
        from_attributes = True


class OnboardingSubmitResponse(BaseModel):
    """Response after successful onboarding submission."""
    message: str
    completed_at: datetime
    version: str