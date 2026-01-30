"""API routes for unified movement preferences management.

This provides a single source of truth for user-level movement preferences.
Most recent input always wins - no duplicate errors, just updates.
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models import Movement, UserMovementRule
from app.models.enums import MovementRuleType, RuleCadence, RuleOperator
from app.api.routes.dependencies import get_current_user_id


router = APIRouter()
logger = logging.getLogger(__name__)


class MovementPreferenceBase(BaseModel):
    movement_id: int
    rule_type: str = Field(
        description="Rule type: hard_no, hard_yes, preferred, include, exclude, bias",
        pattern="^(hard_no|hard_yes|preferred|include|exclude|bias)$"
    )
    cadence: str = Field(
        default="per_microcycle",
        description="Cadence: per_microcycle, weekly, biweekly",
        pattern="^(per_microcycle|weekly|biweekly)$"
    )
    notes: Optional[str] = None


class MovementPreferenceCreate(MovementPreferenceBase):
    pass


class MovementPreferenceBatchCreate(BaseModel):
    preferences: List[MovementPreferenceCreate] = Field(
        min_length=1,
        max_length=100,
        description="List of preferences to create"
    )


class MovementPreferenceUpdate(BaseModel):
    rule_type: Optional[str] = Field(
        default=None,
        pattern="^(hard_no|hard_yes|preferred|include|exclude|bias)$"
    )
    cadence: Optional[str] = Field(
        default=None,
        pattern="^(per_microcycle|weekly|biweekly)$"
    )
    notes: Optional[str] = None


class MovementPreferenceReplace(MovementPreferenceBase):
    pass


class MovementPreferenceResponse(BaseModel):
    id: int
    user_id: int
    movement_id: int
    movement_name: str
    movement_pattern: str
    primary_muscle: str
    primary_region: str
    rule_type: str
    cadence: str
    notes: Optional[str] = None
    created_at: str
    updated_at: str
    is_favorite: bool

    class Config:
        from_attributes = True


class MovementPreferenceListResponse(BaseModel):
    items: List[MovementPreferenceResponse]
    total: int


class MovementPreferenceBatchResponse(BaseModel):
    created: List[MovementPreferenceResponse]
    skipped: List[dict] = Field(default_factory=list)
    errors: List[dict] = Field(default_factory=list)
    summary: dict


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: Optional[dict] = None


def _format_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else ""


def _get_enum_value(value: str, enum_class) -> str:
    try:
        return enum_class[value.upper()].value
    except KeyError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value '{value}'. Must be one of: {[e.value for e in enum_class]}"
        )


@router.get("", response_model=MovementPreferenceListResponse)
async def list_movement_preferences(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    include_favorites_only: bool = Query(False, description="Only return HARD_YES rules"),
):
    """List all movement preferences for current user.
    
    User-level preferences only (program_id is always NULL).
    """
    logger.info("list_movement_preferences: user_id=%s, rule_type=%s, favorites_only=%s", 
                user_id, rule_type, include_favorites_only)
    
    query = select(UserMovementRule).options(selectinload(UserMovementRule.movement))
    
    if include_favorites_only:
        query = query.where(
            and_(
                UserMovementRule.user_id == user_id,
                UserMovementRule.rule_type == MovementRuleType.HARD_YES
            )
        )
    elif rule_type:
        try:
            rule_type_enum = MovementRuleType[rule_type.upper()]
            query = query.where(UserMovementRule.user_id == user_id)
            query = query.where(UserMovementRule.rule_type == rule_type_enum)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid rule_type: {rule_type}")
    else:
        query = query.where(UserMovementRule.user_id == user_id)
    
    query = query.order_by(UserMovementRule.updated_at.desc())
    
    result = await db.execute(query)
    rules = list(result.scalars().unique().all())
    
    responses = []
    for rule in rules:
        movement = rule.movement
        if movement:
            pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
            primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
            primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
        else:
            pattern_value = ""
            primary_muscle_value = ""
            primary_region_value = ""
        
        responses.append(MovementPreferenceResponse(
            id=rule.id,
            user_id=rule.user_id,
            movement_id=rule.movement_id,
            movement_name=movement.name if movement else "Unknown",
            movement_pattern=pattern_value,
            primary_muscle=primary_muscle_value,
            primary_region=primary_region_value,
            rule_type=rule.rule_type.value if rule.rule_type else None,
            cadence=rule.cadence.value if rule.cadence else None,
            notes=rule.notes,
            created_at=_format_datetime(rule.created_at),
            updated_at=_format_datetime(rule.updated_at),
            is_favorite=rule.is_favorite,
        ))
    
    return MovementPreferenceListResponse(items=responses, total=len(responses))


@router.post("", response_model=MovementPreferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_movement_preference(
    preference: MovementPreferenceCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create or update a movement preference (most recent wins).
    
    If a preference already exists for this movement+rule_type combination,
    it is updated (not rejected) - most recent input wins.
    """
    logger.info("create_movement_preference: user_id=%s, data=%s", user_id, preference.model_dump())
    
    movement = await db.get(Movement, preference.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    rule_type_enum = _get_enum_value(preference.rule_type, MovementRuleType)
    cadence_enum = _get_enum_value(preference.cadence, RuleCadence) if preference.cadence else RuleCadence.PER_MICROCYCLE
    
    existing_result = await db.execute(
        select(UserMovementRule).where(
            and_(
                UserMovementRule.user_id == user_id,
                UserMovementRule.movement_id == preference.movement_id,
                UserMovementRule.rule_type == rule_type_enum
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        logger.info("Updating existing rule: user_id=%s, rule_id=%s", user_id, existing.id)
        existing.rule_type = rule_type_enum
        existing.cadence = cadence_enum
        existing.notes = preference.notes
        existing.updated_at = datetime.utcnow()
    else:
        logger.info("Creating new rule: user_id=%s", user_id)
        movement_rule = UserMovementRule(
            user_id=user_id,
            movement_id=preference.movement_id,
            rule_type=rule_type_enum,
            rule_operator=RuleOperator.EQ,
            cadence=cadence_enum,
            notes=preference.notes,
        )
        db.add(movement_rule)
        existing = movement_rule
    
    await db.commit()
    await db.refresh(existing)
    
    movement = existing.movement
    pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
    primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
    primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
    
    return MovementPreferenceResponse(
        id=existing.id,
        user_id=existing.user_id,
        movement_id=existing.movement_id,
        movement_name=movement.name,
        movement_pattern=pattern_value,
        primary_muscle=primary_muscle_value,
        primary_region=primary_region_value,
        rule_type=existing.rule_type.value,
        cadence=existing.cadence.value,
        notes=existing.notes,
        created_at=_format_datetime(existing.created_at),
        updated_at=_format_datetime(existing.updated_at),
        is_favorite=existing.is_favorite,
    )


@router.post("/batch", response_model=MovementPreferenceBatchResponse, status_code=status.HTTP_201_CREATED)
async def batch_create_movement_preferences(
    batch: MovementPreferenceBatchCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create or update multiple movement preferences (most recent wins).
    
    Used by program wizard to save user preferences.
    """
    logger.info("batch_create_movement_preferences: user_id=%s, count=%s", user_id, len(batch.preferences))
    
    created = []
    skipped = []
    
    for pref_data in batch.preferences:
        movement = await db.get(Movement, pref_data.movement_id)
        if not movement:
            skipped.append({
                "movement_id": pref_data.movement_id,
                "reason": "Movement not found"
            })
            continue
        
        rule_type_enum = _get_enum_value(pref_data.rule_type, MovementRuleType)
        cadence_enum = _get_enum_value(pref_data.cadence, RuleCadence) if pref_data.cadence else RuleCadence.PER_MICROCYCLE
        
        existing_result = await db.execute(
            select(UserMovementRule).where(
                and_(
                    UserMovementRule.user_id == user_id,
                    UserMovementRule.movement_id == pref_data.movement_id,
                    UserMovementRule.rule_type == rule_type_enum
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            existing.rule_type = rule_type_enum
            existing.cadence = cadence_enum
            existing.notes = pref_data.notes
            existing.updated_at = datetime.utcnow()
            rule = existing
        else:
            rule = UserMovementRule(
                user_id=user_id,
                movement_id=pref_data.movement_id,
                rule_type=rule_type_enum,
                rule_operator=RuleOperator.EQ,
                cadence=cadence_enum,
                notes=pref_data.notes,
            )
            db.add(rule)
        
        created.append(rule)
    
    await db.commit()
    
    for rule in created:
        await db.refresh(rule)
    
    responses = []
    for rule in created:
        movement = rule.movement
        pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
        primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
        primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
        
        responses.append(MovementPreferenceResponse(
            id=rule.id,
            user_id=rule.user_id,
            movement_id=rule.movement_id,
            movement_name=movement.name,
            movement_pattern=pattern_value,
            primary_muscle=primary_muscle_value,
            primary_region=primary_region_value,
            rule_type=rule.rule_type.value,
            cadence=rule.cadence.value,
            notes=rule.notes,
            created_at=_format_datetime(rule.created_at),
            updated_at=_format_datetime(rule.updated_at),
            is_favorite=rule.is_favorite,
        ))
    
    return MovementPreferenceBatchResponse(
        created=responses,
        skipped=skipped,
        errors=[],
        summary={
            "total": len(batch.preferences),
            "created": len(created),
            "skipped": len(skipped),
            "failed": len(skipped),
        }
    )


@router.get("/{preference_id}", response_model=MovementPreferenceResponse)
async def get_movement_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific movement preference by ID."""
    result = await db.execute(
        select(UserMovementRule).options(selectinload(UserMovementRule.movement)).where(
            UserMovementRule.id == preference_id
        )
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Movement preference not found")
    
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this preference")
    
    movement = rule.movement
    pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
    primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
    primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
    
    return MovementPreferenceResponse(
        id=rule.id,
        user_id=rule.user_id,
        movement_id=rule.movement_id,
        movement_name=movement.name,
        movement_pattern=pattern_value,
        primary_muscle=primary_muscle_value,
        primary_region=primary_region_value,
        rule_type=rule.rule_type.value,
        cadence=rule.cadence.value,
        notes=rule.notes,
        created_at=_format_datetime(rule.created_at),
        updated_at=_format_datetime(rule.updated_at),
        is_favorite=rule.is_favorite,
    )


@router.patch("/{preference_id}", response_model=MovementPreferenceResponse)
async def update_movement_preference(
    preference_id: int,
    update: MovementPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Partially update a movement preference."""
    logger.info("update_movement_preference: user_id=%s, preference_id=%s, data=%s", 
                user_id, preference_id, update.model_dump(exclude_none=True))
    
    result = await db.execute(
        select(UserMovementRule).where(UserMovementRule.id == preference_id)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Movement preference not found")
    
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this preference")
    
    if update.rule_type is not None:
        rule.rule_type = _get_enum_value(update.rule_type, MovementRuleType)
    if update.cadence is not None:
        rule.cadence = _get_enum_value(update.cadence, RuleCadence)
    if update.notes is not None:
        rule.notes = update.notes
    
    rule.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rule)
    
    movement = rule.movement
    pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
    primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
    primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
    
    return MovementPreferenceResponse(
        id=rule.id,
        user_id=rule.user_id,
        movement_id=rule.movement_id,
        movement_name=movement.name,
        movement_pattern=pattern_value,
        primary_muscle=primary_muscle_value,
        primary_region=primary_region_value,
        rule_type=rule.rule_type.value,
        cadence=rule.cadence.value,
        notes=rule.notes,
        created_at=_format_datetime(rule.created_at),
        updated_at=_format_datetime(rule.updated_at),
        is_favorite=rule.is_favorite,
    )


@router.put("/{preference_id}", response_model=MovementPreferenceResponse)
async def replace_movement_preference(
    preference_id: int,
    replacement: MovementPreferenceReplace,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Fully replace a movement preference."""
    logger.info("replace_movement_preference: user_id=%s, preference_id=%s, data=%s", 
                user_id, preference_id, replacement.model_dump())
    
    result = await db.execute(
        select(UserMovementRule).where(UserMovementRule.id == preference_id)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Movement preference not found")
    
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update this preference")
    
    movement = await db.get(Movement, replacement.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    rule.movement_id = replacement.movement_id
    rule.rule_type = _get_enum_value(replacement.rule_type, MovementRuleType)
    rule.cadence = _get_enum_value(replacement.cadence, RuleCadence)
    rule.notes = replacement.notes
    rule.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(rule)
    
    pattern_value = movement.pattern.value if hasattr(movement.pattern, 'value') else str(movement.pattern)
    primary_muscle_value = movement.primary_muscle.value if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
    primary_region_value = movement.primary_region.value if hasattr(movement.primary_region, 'value') else str(movement.primary_region)
    
    return MovementPreferenceResponse(
        id=rule.id,
        user_id=rule.user_id,
        movement_id=rule.movement_id,
        movement_name=movement.name,
        movement_pattern=pattern_value,
        primary_muscle=primary_muscle_value,
        primary_region=primary_region_value,
        rule_type=rule.rule_type.value,
        cadence=rule.cadence.value,
        notes=rule.notes,
        created_at=_format_datetime(rule.created_at),
        updated_at=_format_datetime(rule.updated_at),
        is_favorite=rule.is_favorite,
    )


@router.delete("/{preference_id}", status_code=status.HTTP_200_OK)
async def delete_movement_preference(
    preference_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Delete a movement preference."""
    logger.info("delete_movement_preference: user_id=%s, preference_id=%s", user_id, preference_id)
    
    result = await db.execute(
        select(UserMovementRule).where(UserMovementRule.id == preference_id)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Movement preference not found")
    
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this preference")
    
    await db.delete(rule)
    await db.commit()
    
    return {
        "id": preference_id,
        "message": "Movement preference deleted successfully"
    }
