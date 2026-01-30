"""API routes for favorites management."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models import Movement, UserMovementRule
from app.models.enums import MovementRuleType, RuleCadence
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


class FavoriteCreate(BaseModel):
    movement_id: int | None = None
    program_id: int | None = None


class FavoriteResponse(BaseModel):
    id: int
    movement_id: int | None
    program_id: int | None
    created_at: str

    class Config:
        from_attributes = True


class MovementFavoriteResponse(BaseModel):
    id: int
    movement_id: int
    movement_name: str
    pattern: str
    primary_muscle: str
    primary_region: str
    created_at: str

    class Config:
        from_attributes = True


class ProgramFavoriteResponse(BaseModel):
    id: int
    program_id: int
    program_name: str | None
    split_template: str
    duration_weeks: int
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=dict[str, list[MovementFavoriteResponse | ProgramFavoriteResponse]])
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List all favorites for the current user, grouped by type.
    
    Favorites are stored as user_movement_rules with rule_type=HARD_YES.
    """
    logger.info("list_favorites called: user_id=%s", user_id)
    
    # Get movement favorites from user_movement_rules (HARD_YES entries)
    movement_favorites_result = await db.execute(
        select(UserMovementRule)
        .options(selectinload(UserMovementRule.movement))
        .where(
            and_(
                UserMovementRule.user_id == user_id,
                UserMovementRule.rule_type == MovementRuleType.HARD_YES
            )
        )
        .order_by(UserMovementRule.created_at.desc())
    )
    movement_favorites = list(movement_favorites_result.scalars().unique().all())
    
    # Build response for movements
    movement_responses = []
    for rule in movement_favorites:
        if rule.movement:
            pattern_value = rule.movement.pattern.value if hasattr(rule.movement.pattern, 'value') else str(rule.movement.pattern)
            primary_muscle_value = rule.movement.primary_muscle.value if hasattr(rule.movement.primary_muscle, 'value') else str(rule.movement.primary_muscle)
            primary_region_value = rule.movement.primary_region.value if hasattr(rule.movement.primary_region, 'value') else str(rule.movement.primary_region)
            
            movement_responses.append(MovementFavoriteResponse(
                id=rule.id,
                movement_id=rule.movement_id,
                movement_name=rule.movement.name,
                pattern=pattern_value,
                primary_muscle=primary_muscle_value,
                primary_region=primary_region_value,
                created_at=rule.created_at.isoformat() if rule.created_at else ""
            ))
    
    logger.info("list_favorites: found %d movement favorites for user_id=%s", 
                len(movement_responses), user_id)
    
    return {
        "movements": movement_responses,
        "programs": []  # Program favorites not supported with user_movement_rules
    }


@router.post("", response_model=FavoriteResponse, status_code=status.HTTP_201_CREATED)
async def create_favorite(
    favorite_data: FavoriteCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create a new favorite as a user_movement_rule with HARD_YES type.
    
    Only movement_id is supported (program_id not supported with user_movement_rules).
    """
    logger.info("create_favorite called: user_id=%s, data=%s", user_id, favorite_data.model_dump())
    
    if favorite_data.movement_id is None:
        raise HTTPException(
            status_code=400,
            detail="movement_id must be provided (program_id not supported)"
        )
    
    if favorite_data.program_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Program favorites not supported with user_movement_rules"
        )
    
    # Verify movement exists
    movement_result = await db.execute(
        select(Movement).where(Movement.id == favorite_data.movement_id)
    )
    movement = movement_result.scalar_one_or_none()
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    # Check if rule already exists - most recent wins (update, not reject)
    existing_result = await db.execute(
        select(UserMovementRule).where(
            and_(
                UserMovementRule.user_id == user_id,
                UserMovementRule.movement_id == favorite_data.movement_id,
                UserMovementRule.rule_type == MovementRuleType.HARD_YES
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        logger.info("Updating existing favorite: user_id=%s, rule_id=%s", user_id, existing.id)
        existing.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing)
        logger.info("create_favorite: updated movement_rule id=%s for user_id=%s", existing.id, user_id)
    else:
        # Create user_movement_rule with HARD_YES type
        movement_rule = UserMovementRule(
            user_id=user_id,
            movement_id=favorite_data.movement_id,
            rule_type=MovementRuleType.HARD_YES,
            rule_operator=RuleOperator.EQ,
            cadence=RuleCadence.PER_MICROCYCLE
        )
        db.add(movement_rule)
        await db.commit()
        await db.refresh(movement_rule)
        logger.info("create_favorite: created movement_rule id=%s for user_id=%s", movement_rule.id, user_id)
        existing = movement_rule
    
    return FavoriteResponse(
        id=existing.id,
        movement_id=existing.movement_id,
        program_id=None,
        created_at=existing.created_at.isoformat() if existing.created_at else ""
    )


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite(
    favorite_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Delete a favorite (user_movement_rule)."""
    logger.info("delete_favorite called: favorite_id=%s, user_id=%s", favorite_id, user_id)
    
    rule_result = await db.execute(
        select(UserMovementRule).where(UserMovementRule.id == favorite_id)
    )
    rule = rule_result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Favorite not found")
    
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this favorite")
    
    await db.delete(rule)
    await db.commit()
    
    logger.info("delete_favorite: deleted movement_rule id=%s for user_id=%s", favorite_id, user_id)
