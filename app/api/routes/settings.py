"""API routes for user settings and configuration."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.config.settings import get_settings
from app.config import heuristics
from app.models import (
    User,
    UserProfile,
    UserSettings,
    UserMovementRule,
    UserEnjoyableActivity,
    Movement,
    MovementDiscipline,
    MovementEquipment,
    MovementMuscleMap,
    Muscle,
    Equipment,
    HeuristicConfig,
    MovementPattern,
)
from app.schemas.settings import (
    UserSettingsResponse,
    UserSettingsUpdate,
    UserProfileResponse,
    UserProfileUpdate,
    MovementRuleCreate,
    MovementRuleResponse,
    EnjoyableActivityCreate,
    EnjoyableActivityResponse,
    HeuristicConfigResponse,
    MovementResponse,
    MovementListResponse,
    MovementCreate,
    MovementFiltersResponse,
    MovementSubstitutionRequest,
    MovementSubstitutionResponse,
    MovementSimilarityRequest,
    MovementProgressionResponse,
    MovementRegressionRequest,
    MovementRegressionResponse,
    BiomechanicsQueryRequest,
)
from app.models.enums import MuscleRole
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
settings = get_settings()


# User settings
@router.get("/user", response_model=UserSettingsResponse)
async def get_user_settings(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get current user settings."""
    user_settings = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = user_settings.scalar_one_or_none()
    
    if not user_settings:
        # Create default settings
        user_settings = UserSettings(user_id=user_id)
        db.add(user_settings)
        await db.commit()
        await db.refresh(user_settings)
    
    return UserSettingsResponse(
        id=user_settings.id,
        user_id=user_settings.user_id,
        active_e1rm_formula=user_settings.active_e1rm_formula,
        use_metric=user_settings.use_metric,
    )


# User Profile
@router.get("/user/profile", response_model=UserProfileResponse)
async def get_user_profile(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get current user profile."""
    # Fetch User and UserProfile
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # UserProfile is a relationship, so it might be lazy loaded or we join it
    # But since we use async, we should probably eager load it or query it separately if lazy loading issues arise.
    # However, standard async access to relationships works if session is open.
    # Let's check if we need to explicitly query it.
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    
    return UserProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        experience_level=user.experience_level,
        persona_tone=user.persona_tone,
        persona_aggression=user.persona_aggression,
        date_of_birth=profile.date_of_birth if profile else None,
        sex=profile.sex if profile else None,
        height_cm=profile.height_cm if profile else None,
        discipline_preferences=profile.discipline_preferences if profile else None,
        discipline_experience=profile.discipline_experience if profile else None,
        scheduling_preferences=profile.scheduling_preferences if profile else None,
        long_term_goal_category=profile.long_term_goal_category if profile else None,
        long_term_goal_description=profile.long_term_goal_description if profile else None,
    )


@router.patch("/user/profile", response_model=UserProfileResponse)
async def update_user_profile(
    update: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Update user profile."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
    
    # Update User fields
    update_data = update.model_dump(exclude_unset=True)
    user_fields = {"name", "experience_level", "persona_tone", "persona_aggression"}
    profile_fields = {
        "date_of_birth", "sex", "height_cm", 
        "discipline_preferences", "discipline_experience", "scheduling_preferences",
        "long_term_goal_category", "long_term_goal_description"
    }
    
    for field, value in update_data.items():
        if field in user_fields:
            setattr(user, field, value)
        elif field in profile_fields:
            setattr(profile, field, value)
            
    await db.commit()
    await db.refresh(user)
    await db.refresh(profile)
    
    return UserProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        experience_level=user.experience_level,
        persona_tone=user.persona_tone,
        persona_aggression=user.persona_aggression,
        date_of_birth=profile.date_of_birth,
        sex=profile.sex,
        height_cm=profile.height_cm,
        discipline_preferences=profile.discipline_preferences,
        discipline_experience=profile.discipline_experience,
        scheduling_preferences=profile.scheduling_preferences,
        long_term_goal_category=profile.long_term_goal_category,
        long_term_goal_description=profile.long_term_goal_description,
    )


@router.patch("/user", response_model=UserSettingsResponse)
async def update_user_settings(
    update: UserSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Update user settings."""
    user_settings = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = user_settings.scalar_one_or_none()
    
    if not user_settings:
        user_settings = UserSettings(user_id=user_id)
        db.add(user_settings)
    
    # Update fields that are provided
    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user_settings, field, value)
    
    await db.commit()
    await db.refresh(user_settings)
    
    return UserSettingsResponse(
        id=user_settings.id,
        user_id=user_settings.user_id,
        active_e1rm_formula=user_settings.active_e1rm_formula,
        use_metric=user_settings.use_metric,
    )


# Movement rules
@router.get("/movement-rules", response_model=List[MovementRuleResponse])
async def list_movement_rules(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List all user movement rules (exclusions, substitutions, etc.)."""
    result = await db.execute(
        select(UserMovementRule).where(UserMovementRule.user_id == user_id)
    )
    rules = list(result.scalars().all())
    
    responses = []
    for rule in rules:
        movement = await db.get(Movement, rule.movement_id)
        
        responses.append(MovementRuleResponse(
            id=rule.id,
            movement_id=rule.movement_id,
            movement_name=movement.name if movement else "Unknown",
            rule_type=rule.rule_type.value if rule.rule_type else None,
            cadence=rule.cadence.value if rule.cadence else None,
            notes=rule.notes,
        ))
    
    return responses


@router.post("/movement-rules", response_model=MovementRuleResponse)
async def create_movement_rule(
    rule: MovementRuleCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create a new movement rule (exclude, substitute, prefer)."""
    from app.models.enums import MovementRuleType, RuleCadence
    
    # Verify movement exists
    movement = await db.get(Movement, rule.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    # Parse rule_type enum
    try:
        rule_type_enum = MovementRuleType[rule.rule_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid rule_type: {rule.rule_type}")
    
    # Parse cadence enum if provided
    cadence_enum = RuleCadence.PER_MICROCYCLE
    if rule.cadence:
        try:
            cadence_enum = RuleCadence[rule.cadence.upper()]
        except KeyError:
            pass  # Use default
    
    movement_rule = UserMovementRule(
        user_id=user_id,
        movement_id=rule.movement_id,
        rule_type=rule_type_enum,
        cadence=cadence_enum,
        notes=rule.notes,
    )
    db.add(movement_rule)
    await db.commit()
    
    return MovementRuleResponse(
        id=movement_rule.id,
        movement_id=movement_rule.movement_id,
        movement_name=movement.name,
        rule_type=movement_rule.rule_type.value,
        cadence=movement_rule.cadence.value if movement_rule.cadence else None,
        notes=movement_rule.notes,
    )


@router.delete("/movement-rules/{rule_id}")
async def delete_movement_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Delete a movement rule."""
    rule = await db.get(UserMovementRule, rule_id)
    
    if not rule or rule.user_id != user_id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"detail": "Rule deleted"}


# Enjoyable activities
@router.get("/enjoyable-activities", response_model=List[EnjoyableActivityResponse])
async def list_enjoyable_activities(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List user's enjoyable activities for active recovery suggestions."""
    result = await db.execute(
        select(UserEnjoyableActivity).where(UserEnjoyableActivity.user_id == user_id)
    )
    activities = list(result.scalars().all())
    
    return [
        EnjoyableActivityResponse(
            id=act.id,
            user_id=act.user_id,
            activity_type=act.activity_type.value if act.activity_type else None,
            custom_name=act.custom_name,
            recommend_every_days=act.recommend_every_days,
            enabled=act.enabled,
            notes=act.notes,
        )
        for act in activities
    ]


@router.post("/enjoyable-activities", response_model=EnjoyableActivityResponse)
async def create_enjoyable_activity(
    activity: EnjoyableActivityCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Add an enjoyable activity."""
    from app.models.enums import EnjoyableActivity as EnjoyableActivityEnum

    try:
        activity_type = EnjoyableActivityEnum(activity.activity_type)
    except ValueError:
        try:
            activity_type = EnjoyableActivityEnum[activity.activity_type.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid activity_type: {activity.activity_type}")

    new_activity = UserEnjoyableActivity(
        user_id=user_id,
        activity_type=activity_type,
        custom_name=activity.custom_name,
        recommend_every_days=activity.recommend_every_days,
        enabled=True,
        notes=activity.notes,
    )
    db.add(new_activity)
    await db.commit()
    
    return EnjoyableActivityResponse(
        id=new_activity.id,
        user_id=new_activity.user_id,
        activity_type=new_activity.activity_type.value if new_activity.activity_type else None,
        custom_name=new_activity.custom_name,
        recommend_every_days=new_activity.recommend_every_days,
        enabled=new_activity.enabled,
        notes=new_activity.notes,
    )


@router.delete("/enjoyable-activities/{activity_id}")
async def delete_enjoyable_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Delete an enjoyable activity."""
    activity = await db.get(UserEnjoyableActivity, activity_id)
    
    if not activity or activity.user_id != user_id:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    await db.delete(activity)
    await db.commit()
    
    return {"detail": "Activity deleted"}


# Heuristic configs (read-only for MVP - now from in-memory code config)
@router.get("/heuristics", response_model=List[HeuristicConfigResponse])
async def list_heuristic_configs(
    category: Optional[str] = None,
):
    """List all heuristic configurations from in-memory code config."""
    configs = [
        {
            "name": "goal_dose_heuristics",
            "category": "training",
            "json_blob": heuristics.GOAL_DOSE_HEURISTICS,
            "description": "Training parameters by goal (strength, hypertrophy, endurance, etc.)"
        },
        {
            "name": "interference_rules",
            "category": "training",
            "json_blob": heuristics.INTERFERENCE_RULES,
            "description": "Activity & training interference rules"
        },
        {
            "name": "time_estimation",
            "category": "session",
            "json_blob": heuristics.TIME_ESTIMATION,
            "description": "Session time estimation defaults"
        },
        {
            "name": "cns_load_budget",
            "category": "recovery",
            "json_blob": heuristics.CNS_LOAD_BUDGET,
            "description": "CNS load budgeting parameters"
        },
        {
            "name": "deload_policy",
            "category": "recovery",
            "json_blob": heuristics.DELOAD_POLICY,
            "description": "Deload timing and intensity rules"
        },
        {
            "name": "psi_calculation",
            "category": "performance",
            "json_blob": heuristics.PSI_CALCULATION,
            "description": "PSI calculation parameters"
        },
        {
            "name": "split_templates",
            "category": "programming",
            "json_blob": heuristics.SPLIT_TEMPLATES,
            "description": "Predefined split structures (upper_lower, ppl, full_body, hybrid)"
        },
        {
            "name": "progression_rules",
            "category": "training",
            "json_blob": heuristics.PROGRESSION_RULES,
            "description": "Progression style rules"
        },
        {
            "name": "persona_definitions",
            "category": "ai",
            "json_blob": heuristics.PERSONA_DEFINITIONS,
            "description": "Coach persona tones & aggression levels"
        },
        {
            "name": "doms_attribution",
            "category": "recovery",
            "json_blob": heuristics.DOMS_ATTRIBUTION,
            "description": "DOMS attribution rules"
        }
    ]
    
    if category:
        configs = [c for c in configs if c["category"] == category]
    
    return [
        HeuristicConfigResponse(
            id=idx + 1,
            key=config["name"],
            category=config["category"],
            value=config["json_blob"],
            description=config["description"],
        )
        for idx, config in enumerate(configs)
    ]


@router.get("/heuristics/{key}", response_model=HeuristicConfigResponse)
async def get_heuristic_config(
    key: str,
):
    """Get a specific heuristic configuration by key from in-memory code config."""
    config_map = {
        "goal_dose_heuristics": {
            "category": "training",
            "value": heuristics.GOAL_DOSE_HEURISTICS,
            "description": "Training parameters by goal (strength, hypertrophy, endurance, etc.)"
        },
        "interference_rules": {
            "category": "training",
            "value": heuristics.INTERFERENCE_RULES,
            "description": "Activity & training interference rules"
        },
        "time_estimation": {
            "category": "session",
            "value": heuristics.TIME_ESTIMATION,
            "description": "Session time estimation defaults"
        },
        "cns_load_budget": {
            "category": "recovery",
            "value": heuristics.CNS_LOAD_BUDGET,
            "description": "CNS load budgeting parameters"
        },
        "deload_policy": {
            "category": "recovery",
            "value": heuristics.DELOAD_POLICY,
            "description": "Deload timing and intensity rules"
        },
        "psi_calculation": {
            "category": "performance",
            "value": heuristics.PSI_CALCULATION,
            "description": "PSI calculation parameters"
        },
        "split_templates": {
            "category": "programming",
            "value": heuristics.SPLIT_TEMPLATES,
            "description": "Predefined split structures (upper_lower, ppl, full_body, hybrid)"
        },
        "progression_rules": {
            "category": "training",
            "value": heuristics.PROGRESSION_RULES,
            "description": "Progression style rules"
        },
        "persona_definitions": {
            "category": "ai",
            "value": heuristics.PERSONA_DEFINITIONS,
            "description": "Coach persona tones & aggression levels"
        },
        "doms_attribution": {
            "category": "recovery",
            "value": heuristics.DOMS_ATTRIBUTION,
            "description": "DOMS attribution rules"
        }
    }
    
    if key not in config_map:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config = config_map[key]
    
    return HeuristicConfigResponse(
        id=1,
        key=key,
        category=config["category"],
        value=config["value"],
        description=config["description"],
    )


# Movements repository
@router.get("/movements", response_model=MovementListResponse)
async def list_movements(
    pattern: Optional[MovementPattern] = None,
    equipment: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=1000, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List available movements from the repository."""
    query = select(Movement).options(
        selectinload(Movement.disciplines),
        selectinload(Movement.equipment).selectinload(MovementEquipment.equipment),
        selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
    )
    
    # Filter by user (system movements + user's movements)
    query = query.where((Movement.user_id.is_(None)) | (Movement.user_id == user_id))
    
    if pattern:
        query = query.where(Movement.pattern == pattern)
    if search:
        query = query.where(Movement.name.ilike(f"%{search}%"))
    if equipment:
        query = query.join(Movement.equipment).join(MovementEquipment.equipment).where(Equipment.name == equipment)
    
    # Get total
    from sqlalchemy import func
    count_query = select(func.count(Movement.id)).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id)
    )
    if pattern:
        count_query = count_query.where(Movement.pattern == pattern)
    if search:
        count_query = count_query.where(Movement.name.ilike(f"%{search}%"))
    if equipment:
        count_query = count_query.join(Movement.equipment).join(MovementEquipment.equipment).where(Equipment.name == equipment)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    query = query.order_by(Movement.name).limit(limit).offset(offset)
    
    result = await db.execute(query)
    movements = list(result.scalars().all())
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle.value if m.primary_muscle else None,
                primary_muscles=[m.primary_muscle.value] if m.primary_muscle else [],
                secondary_muscles=[
                    mm.muscle.slug for mm in m.muscle_maps 
                    if mm.role in [MuscleRole.SECONDARY, MuscleRole.STABILIZER] and mm.muscle
                ] if m.muscle_maps else [],
                primary_region=m.primary_region,
                compound=m.compound,
                is_compound=m.compound,
                skill_level=m.skill_level,
                cns_load=m.cns_load.value,
                metric_type=m.metric_type.value,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/movements/filters", response_model=MovementFiltersResponse)
async def get_movement_filters(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Return distinct movement filters available to the current user.

    This endpoint is designed for frontend filter UIs so they always
    reflect whatever values exist in the movements table, while still
    respecting access control (system movements + this user's movements).
    """
    # Reuse the same visibility rules as list_movements
    query = select(Movement).where((Movement.user_id.is_(None)) | (Movement.user_id == user_id))
    result = await db.execute(query)
    movements = list(result.scalars().all())

    patterns = sorted({m.pattern.value for m in movements if m.pattern})
    regions = sorted({m.primary_region for m in movements if m.primary_region})
    
    # Get distinct disciplines for visible movements
    disc_query = select(MovementDiscipline.discipline).join(Movement).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id)
    ).distinct()
    disc_result = await db.execute(disc_query)
    disciplines = sorted([d.value for d in disc_result.scalars().all() if d])

    # Get distinct equipment for visible movements
    eq_query = select(Equipment.name).join(MovementEquipment).join(Movement).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id)
    ).distinct()
    eq_result = await db.execute(eq_query)
    equipment = sorted([e for e in eq_result.scalars().all() if e])

    # Get distinct secondary muscles for visible movements
    mus_query = select(Muscle.slug).join(MovementMuscleMap).join(Movement).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id),
        MovementMuscleMap.role.in_([MuscleRole.SECONDARY, MuscleRole.STABILIZER])
    ).distinct()
    mus_result = await db.execute(mus_query)
    secondary_muscles = sorted([m for m in mus_result.scalars().all() if m])

    types = ["compound", "accessory"]

    return MovementFiltersResponse(
        patterns=patterns,
        regions=regions,
        equipment=equipment,
        primary_disciplines=disciplines,
        secondary_muscles=secondary_muscles,
        types=types,
    )


@router.post("/movements", response_model=MovementResponse)
async def create_movement(
    movement: MovementCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Create a custom movement."""
    # Check if movement with same name exists
    existing = await db.execute(select(Movement).where(Movement.name.ilike(movement.name)))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Movement with this name already exists")
    
    new_movement = Movement(
        name=movement.name,
        pattern=movement.pattern,
        primary_muscle=movement.primary_muscle or "other",
        primary_region=movement.primary_region or "full_body",
        compound=movement.compound,
        description=movement.description,
        user_id=user_id,
        # Defaults
        cns_load=movement.cns_load or "moderate",
        skill_level=movement.skill_level or "intermediate",
        metric_type=movement.metric_type or "reps",
    )
    
    db.add(new_movement)
    await db.flush()

    # Handle Secondary Muscles
    if movement.secondary_muscles:
        for muscle_enum in movement.secondary_muscles:
            # Find muscle by slug (assuming enum value == slug)
            muscle_slug = muscle_enum.value if hasattr(muscle_enum, 'value') else muscle_enum
            muscle_res = await db.execute(select(Muscle).where(Muscle.slug == muscle_slug))
            muscle = muscle_res.scalar_one_or_none()
            if muscle:
                mm = MovementMuscleMap(
                    movement_id=new_movement.id, 
                    muscle_id=muscle.id, 
                    role=MuscleRole.SECONDARY
                )
                db.add(mm)
    
    # Handle Equipment
    if movement.default_equipment:
        # Find or create equipment
        eq_name = movement.default_equipment
        eq_result = await db.execute(select(Equipment).where(Equipment.name == eq_name))
        eq = eq_result.scalar_one_or_none()
        if not eq:
            eq = Equipment(name=eq_name)
            db.add(eq)
            await db.flush()
        
        # Link
        me = MovementEquipment(movement_id=new_movement.id, equipment_id=eq.id)
        db.add(me)
    
    await db.commit()
    await db.refresh(new_movement)
    
    # Refresh relations
    query = select(Movement).where(Movement.id == new_movement.id).options(
        selectinload(Movement.disciplines),
        selectinload(Movement.equipment).selectinload(MovementEquipment.equipment),
        selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
    )
    result = await db.execute(query)
    new_movement = result.scalar_one()
    
    return MovementResponse(
        id=new_movement.id,
        name=new_movement.name,
        pattern=new_movement.pattern.value,
        primary_pattern=new_movement.pattern,
        primary_muscle=new_movement.primary_muscle.value,
        primary_muscles=[new_movement.primary_muscle.value],
        secondary_muscles=[
            mm.muscle.slug for mm in new_movement.muscle_maps 
            if mm.role in [MuscleRole.SECONDARY, MuscleRole.STABILIZER] and mm.muscle
        ] if new_movement.muscle_maps else [],
        primary_region=new_movement.primary_region,
        default_equipment=new_movement.equipment[0].equipment.name if new_movement.equipment else None,
        complexity=new_movement.skill_level,
        skill_level=new_movement.skill_level,
        is_compound=new_movement.compound,
        cns_load=new_movement.cns_load.value,
        metric_type=new_movement.metric_type.value,
        is_complex_lift=new_movement.is_complex_lift,
        is_unilateral=new_movement.is_unilateral,
        substitution_group=new_movement.substitution_group,
        description=new_movement.description,
        user_id=new_movement.user_id,
        disciplines=[d.discipline.value for d in new_movement.disciplines] if new_movement.disciplines else [],
        equipment=[e.equipment.name for e in new_movement.equipment if e.equipment] if new_movement.equipment else [],
    )


@router.get("/movements/{movement_id}", response_model=MovementResponse)
async def get_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get details for a specific movement."""
    query = select(Movement).where(Movement.id == movement_id).options(
        selectinload(Movement.disciplines),
        selectinload(Movement.equipment).selectinload(MovementEquipment.equipment),
        selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
    )
    result = await db.execute(query)
    movement = result.scalar_one_or_none()
    
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    return MovementResponse(
        id=movement.id,
        name=movement.name,
        pattern=movement.pattern.value if movement.pattern else None,
        primary_pattern=movement.pattern,
        primary_muscle=movement.primary_muscle.value if movement.primary_muscle else None,
        primary_muscles=[movement.primary_muscle.value] if movement.primary_muscle else [],
        secondary_muscles=[
            mm.muscle.slug for mm in movement.muscle_maps 
            if mm.role in [MuscleRole.SECONDARY, MuscleRole.STABILIZER] and mm.muscle
        ] if movement.muscle_maps else [],
        primary_region=movement.primary_region,
        default_equipment=movement.equipment[0].equipment.name if movement.equipment else None,
        complexity=movement.skill_level,
        skill_level=movement.skill_level,
        is_compound=movement.compound,
        cns_load=movement.cns_load.value if movement.cns_load else None,
        metric_type=movement.metric_type.value if movement.metric_type else None,
        is_complex_lift=movement.is_complex_lift,
        is_unilateral=movement.is_unilateral,
        substitution_group=movement.substitution_group,
        description=movement.description,
        user_id=movement.user_id,
        disciplines=[d.discipline.value for d in movement.disciplines] if movement.disciplines else [],
        equipment=[e.equipment.name for e in movement.equipment if e.equipment] if movement.equipment else [],
    )


# ============== Movement Substitution & Query Endpoints ==============

@router.post("/movements/substitution", response_model=MovementSubstitutionResponse)
async def find_safest_substitution(
    request: MovementSubstitutionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find the safest movement substitution based on biomechanics profile."""
    from app.services.movement import MovementSubstitutionService
    
    movement = await db.get(Movement, request.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    substitution_service = MovementSubstitutionService()
    safest = await substitution_service.find_safest_substitution(
        db, movement, request.user_spinal_tolerance, request.user_joint_health
    )
    
    if not safest:
        return MovementSubstitutionResponse()
    
    return MovementSubstitutionResponse(
        movement_id=safest.id,
        movement_name=safest.name,
        reason="Safest biomechanical alternative",
        safety_score=80.0,
        biomechanics_profile=safest.biomechanics_profile
    )


@router.post("/movements/similar", response_model=MovementResponse)
async def find_similar_movement(
    request: MovementSimilarityRequest,
    db: AsyncSession = Depends(get_db),
):
    """Find movement with similar biomechanics profile."""
    from app.services.movement import MovementSubstitutionService
    from app.models.enums import MovementTier
    
    movement = await db.get(Movement, request.movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    preferred_tier = None
    if request.preferred_tier:
        try:
            preferred_tier = MovementTier(request.preferred_tier.lower())
        except ValueError:
            pass
    
    substitution_service = MovementSubstitutionService()
    similar = await substitution_service.find_similar_biomechanics_substitution(
        db, movement, preferred_tier, request.exclude_ids
    )
    
    if not similar:
        raise HTTPException(status_code=404, detail="No similar movements found")
    
    return MovementResponse(
        id=similar.id,
        name=similar.name,
        pattern=similar.pattern.value if similar.pattern else None,
        primary_pattern=similar.pattern,
        primary_muscle=similar.primary_muscle.value if similar.primary_muscle else None,
        primary_muscles=[similar.primary_muscle.value] if similar.primary_muscle else [],
        secondary_muscles=[
            mm.muscle.slug for mm in similar.muscle_maps 
            if mm.role in [MuscleRole.SECONDARY, MuscleRole.STABILIZER] and mm.muscle
        ] if similar.muscle_maps else [],
        primary_region=similar.primary_region,
        default_equipment=similar.equipment[0].equipment.name if similar.equipment else None,
        complexity=similar.skill_level,
        skill_level=similar.skill_level,
        is_compound=similar.compound,
        cns_load=similar.cns_load.value if similar.cns_load else None,
        metric_type=similar.metric_type.value if similar.metric_type else None,
        is_complex_lift=similar.is_complex_lift,
        is_unilateral=similar.is_unilateral,
        substitution_group=similar.substitution_group,
        description=similar.description,
        user_id=similar.user_id,
        disciplines=[d.discipline.value for d in similar.disciplines] if similar.disciplines else [],
        equipment=[e.equipment.name for e in similar.equipment if e.equipment] if similar.equipment else [],
    )


@router.get("/movements/{movement_id}/progression", response_model=List[MovementProgressionResponse])
async def get_progression_path(
    movement_id: int,
    user_skill_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get progression path for a movement."""
    from app.services.movement import MovementSubstitutionService
    
    movement = await db.get(Movement, movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    substitution_service = MovementSubstitutionService()
    progression = await substitution_service.find_progression_path(
        db, movement_id, user_skill_level
    )
    
    return [
        MovementProgressionResponse(**step)
        for step in progression
    ]


@router.post("/movements/{movement_id}/regression", response_model=List[MovementRegressionResponse])
async def get_regression_options(
    movement_id: int,
    request: MovementRegressionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Get regression options for a movement based on injury context."""
    from app.services.movement import MovementSubstitutionService
    
    movement = await db.get(Movement, movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    substitution_service = MovementSubstitutionService()
    regressions = await substitution_service.find_regression_options(
        db, movement_id, request.injury_context
    )
    
    return [
        MovementRegressionResponse(**reg)
        for reg in regressions
    ]


@router.post("/movements/query", response_model=MovementListResponse)
async def query_movements_by_biomechanics(
    request: BiomechanicsQueryRequest,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Query movements by biomechanics attributes."""
    from app.services.movement import MovementQueryService
    from app.models.enums import MovementTier, MetabolicDemand
    
    query = select(Movement).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id)
    )
    
    if request.tier:
        try:
            tier = MovementTier(request.tier.lower())
            query = query.where(Movement.tier == tier)
        except ValueError:
            pass
    
    if request.metabolic_demand:
        try:
            demand = MetabolicDemand(request.metabolic_demand.lower())
            query = query.where(Movement.metabolic_demand == demand)
        except ValueError:
            pass
    
    if request.archetype:
        query = query.where(
            Movement.biomechanics_profile['archetype'].astext == request.archetype
        )
    
    if request.spinal_load_max:
        valid_loads = ["none", "low", "moderate", "high"]
        if request.spinal_load_max in valid_loads:
            max_idx = valid_loads.index(request.spinal_load_max)
            allowed_loads = valid_loads[:max_idx + 1]
            query = query.where(
                Movement.biomechanics_profile['loading_pattern']['spinal_load'].astext.in_(allowed_loads)
            )
    
    if request.joint and request.min_joint_score:
        query = query.where(
            Movement.biomechanics_profile['joint_involvement'][request.joint].astext.cast(Float) >= request.min_joint_score
        )
    
    if request.primary_plane:
        query = query.where(
            Movement.biomechanics_profile['movement_vectors']['primary'].astext == request.primary_plane
        )
    
    from sqlalchemy import func
    count_query = select(func.count(Movement.id)).where(
        (Movement.user_id.is_(None)) | (Movement.user_id == user_id)
    )
    
    if request.tier:
        try:
            tier = MovementTier(request.tier.lower())
            count_query = count_query.where(Movement.tier == tier)
        except ValueError:
            pass
    
    count_result = await db.execute(count_query)
    total = count_result.scalar()
    
    query = query.order_by(Movement.name).offset(offset).limit(limit)
    
    result = await db.execute(
        query.options(
            selectinload(Movement.disciplines),
            selectinload(Movement.equipment).selectinload(MovementEquipment.equipment),
            selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
        )
    )
    movements = result.scalars().all()
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle.value if m.primary_muscle else None,
                primary_muscles=[m.primary_muscle.value] if m.primary_muscle else [],
                secondary_muscles=[
                    mm.muscle.slug for mm in m.muscle_maps 
                    if mm.role in [MuscleRole.SECONDARY, MuscleRole.STABILIZER] and mm.muscle
                ] if m.muscle_maps else [],
                primary_region=m.primary_region,
                default_equipment=m.equipment[0].equipment.name if m.equipment else None,
                complexity=m.skill_level,
                skill_level=m.skill_level,
                is_compound=m.compound,
                cns_load=m.cns_load.value if m.cns_load else None,
                metric_type=m.metric_type.value if m.metric_type else None,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=total,
        limit=limit,
        offset=offset,
        filters_applied={
            "tier": request.tier,
            "metabolic_demand": request.metabolic_demand,
            "archetype": request.archetype,
            "joint": request.joint,
            "spinal_load_max": request.spinal_load_max,
            "primary_plane": request.primary_plane
        }
    )


@router.get("/movements/disciplines/{discipline}", response_model=MovementListResponse)
async def get_movements_by_discipline(
    discipline: str,
    match_all: bool = False,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements filtered by discipline type."""
    from app.models.enums import DisciplineType
    from app.services.movement import MovementQueryService
    
    try:
        discipline_enum = DisciplineType(discipline)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid discipline: {discipline}")
    
    movements = await MovementQueryService.get_movements_by_disciplines(
        db, [discipline_enum], match_all=match_all
    )
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"discipline": discipline, "match_all": match_all}
    )


@router.get("/movements/equipment", response_model=MovementListResponse)
async def get_movements_by_equipment(
    equipment: str = Query(..., description="Equipment name (e.g., barbell, dumbbell)"),
    match_all: bool = Query(False, description="Require all equipment if True, any if False"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements filtered by equipment."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_movements_by_equipment(
        db, [equipment], match_all=match_all
    )
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"equipment": equipment, "match_all": match_all}
    )


@router.get("/movements/tags", response_model=MovementListResponse)
async def get_movements_by_tags(
    tags: str = Query(..., description="Comma-separated tag names"),
    match_all: bool = Query(False, description="Require all tags if True, any if False"),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements filtered by tags."""
    from app.services.movement import MovementQueryService
    
    tag_list = [tag.strip() for tag in tags.split(",")]
    
    movements = await MovementQueryService.get_movements_by_tags(
        db, tag_list, match_all=match_all
    )
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"tags": tag_list, "match_all": match_all}
    )


@router.get("/movements/bodyweight", response_model=MovementListResponse)
async def get_bodyweight_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements that don't require any equipment."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_movements_without_equipment(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"equipment": "none"}
    )


@router.get("/movements/powerlifting", response_model=MovementListResponse)
async def get_powerlifting_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get all powerlifting movements."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_powerlifting_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"discipline": "powerlifting"}
    )


@router.get("/movements/olympic", response_model=MovementListResponse)
async def get_olympic_weightlifting_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get all Olympic weightlifting movements."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_olympic_weightlifting_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"discipline": "olympic_weightlifting"}
    )


@router.get("/movements/{movement_id}/disciplines")
async def get_movement_disciplines(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get all disciplines for a specific movement."""
    from app.services.movement import MovementQueryService
    
    movement = await db.get(Movement, movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    disciplines = await MovementQueryService.get_movement_disciplines(db, movement_id)
    
    return {
        "movement_id": movement_id,
        "movement_name": movement.name,
        "disciplines": disciplines
    }


@router.get("/movements/{movement_id}/equipment")
async def get_movement_equipment(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get all equipment for a specific movement."""
    from app.services.movement import MovementQueryService
    
    movement = await db.get(Movement, movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    equipment = await MovementQueryService.get_movement_equipment(db, movement_id)
    
    return {
        "movement_id": movement_id,
        "movement_name": movement.name,
        "equipment": equipment
    }


@router.get("/movements/{movement_id}/tags")
async def get_movement_tags(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get all tags for a specific movement."""
    from app.services.movement import MovementQueryService
    
    movement = await db.get(Movement, movement_id)
    if not movement:
        raise HTTPException(status_code=404, detail="Movement not found")
    
    tags = await MovementQueryService.get_movement_tags(db, movement_id)
    
    return {
        "movement_id": movement_id,
        "movement_name": movement.name,
        "tags": tags
    }


@router.get("/movements/stats/disciplines")
async def get_discipline_stats(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movement count statistics grouped by discipline."""
    from app.services.movement import MovementQueryService
    
    counts = await MovementQueryService.count_movements_by_discipline(db)
    
    return {
        "discipline_counts": counts,
        "total": sum(counts.values())
    }


@router.get("/movements/stats/equipment")
async def get_equipment_stats(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movement count statistics grouped by equipment."""
    from app.services.movement import MovementQueryService
    
    counts = await MovementQueryService.count_movements_by_equipment(db)
    
    return {
        "equipment_counts": counts,
        "total": sum(counts.values())
    }


@router.get("/movements/embeddings", response_model=MovementListResponse)
async def get_movements_with_embeddings(
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements that have embedding vectors (for semantic search)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_movements_with_embeddings(db, limit=limit)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=limit,
        offset=None,
        filters_applied={"has_embeddings": True}
    )


@router.post("/movements/similarity", response_model=List[dict])
async def get_similar_movements(
    movement_id: int = Query(..., description="Reference movement ID"),
    limit: int = Query(default=10, le=50),
    min_similarity: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements semantically similar to a reference movement using embeddings."""
    from app.services.movement import MovementQueryService
    
    reference_movement = await db.get(Movement, movement_id)
    if not reference_movement:
        raise HTTPException(status_code=404, detail="Reference movement not found")
    
    if not reference_movement.embedding_vector:
        raise HTTPException(status_code=400, detail="Reference movement has no embedding vector")
    
    similar_movements = await MovementQueryService.get_semantic_similar_movements(
        db, movement_id, limit=limit, min_similarity=min_similarity
    )
    
    return [
        {
            "movement": {
                "id": m.id,
                "name": m.name,
                "pattern": m.pattern,
                "primary_muscle": m.primary_muscle,
                "primary_region": m.primary_region,
                "tier": m.tier,
                "metabolic_demand": m.metabolic_demand,
            },
            "similarity": similarity
        }
        for m, similarity in similar_movements
    ]


@router.get("/movements/tier/premium", response_model=MovementListResponse)
async def get_premium_tier_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get diamond and gold tier movements (highest quality)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_premium_tier_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"tier": ["diamond", "gold"]}
    )


@router.get("/movements/metabolic-demand/{demand}", response_model=MovementListResponse)
async def get_movements_by_metabolic_demand(
    demand: str,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements by metabolic demand category."""
    from app.models.enums import MetabolicDemand
    from app.services.movement import MovementQueryService
    
    try:
        demand_enum = MetabolicDemand(demand)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid metabolic demand: {demand}")
    
    movements = await MovementQueryService.get_metabolic_demand_movements(db, demand_enum)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"metabolic_demand": demand}
    )


@router.get("/movements/anabolic", response_model=MovementListResponse)
async def get_anabolic_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get anabolic movements (optimal for hypertrophy)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_anabolic_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"metabolic_demand": "anabolic"}
    )


@router.get("/movements/archetype/{archetype}", response_model=MovementListResponse)
async def get_movements_by_archetype(
    archetype: str,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements by biomechanics archetype."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_movements_by_archetype(db, archetype)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"archetype": archetype}
    )


@router.get("/movements/low-spinal-load", response_model=MovementListResponse)
async def get_low_spinal_load_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements with none or low spinal load."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_low_spinal_load_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"spinal_load": ["none", "low"]}
    )


@router.get("/movements/joint/{joint}", response_model=MovementListResponse)
async def get_joint_dominant_movements(
    joint: str = Path(..., description="Joint name (e.g., knee, hip, shoulder)"),
    min_score: float = Query(default=7.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements with high involvement for a specific joint."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_joint_dominant_movements(db, joint, min_score)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"joint": joint, "min_score": min_score}
    )


@router.get("/movements/knee-dominant", response_model=MovementListResponse)
async def get_knee_dominant_movements(
    min_score: float = Query(default=7.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get knee-dominant movements (high knee involvement)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_knee_dominant_movements(db, min_score)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"joint": "knee", "min_score": min_score}
    )


@router.get("/movements/hip-dominant", response_model=MovementListResponse)
async def get_hip_dominant_movements(
    min_score: float = Query(default=7.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get hip-dominant movements (high hip involvement)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_hip_dominant_movements(db, min_score)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"joint": "hip", "min_score": min_score}
    )


@router.get("/movements/shoulder-dominant", response_model=MovementListResponse)
async def get_shoulder_dominant_movements(
    min_score: float = Query(default=7.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get shoulder-dominant movements (high shoulder involvement)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_shoulder_dominant_movements(db, min_score)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"joint": "shoulder", "min_score": min_score}
    )


@router.get("/movements/knee-dominant-low-spinal", response_model=MovementListResponse)
async def get_knee_dominant_low_spinal_movements(
    min_knee: float = Query(default=7.0, ge=0.0, le=10.0),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get knee-dominant movements with low spinal load (ideal for back health)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_knee_dominant_low_spinal_movements(db, min_knee)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"joint": "knee", "min_score": min_knee, "spinal_load": ["none", "low"]}
    )


@router.get("/movements/unilateral-compound", response_model=MovementListResponse)
async def get_unilateral_compound_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get unilateral compound movements (good for imbalances)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_unilateral_compound_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"archetype": "unilateral_compound"}
    )


@router.get("/movements/plane/{plane}", response_model=MovementListResponse)
async def get_movements_by_plane(
    plane: str,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements by primary movement plane."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_by_primary_plane(db, plane)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"plane": plane}
    )


@router.get("/movements/multi-plane", response_model=MovementListResponse)
async def get_multi_plane_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements that work across multiple planes of motion."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_multi_plane_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"multi_plane": True}
    )


@router.get("/movements/equipment/barbell", response_model=MovementListResponse)
async def get_barbell_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get barbell movements."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_barbell_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"equipment": "barbell"}
    )


@router.get("/movements/equipment/dumbbell", response_model=MovementListResponse)
async def get_dumbbell_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get dumbbell movements."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_dumbbell_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"equipment": "dumbbell"}
    )


@router.get("/movements/equipment/kettlebell", response_model=MovementListResponse)
async def get_kettlebell_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get kettlebell movements."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_kettlebell_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"equipment": "kettlebell"}
    )


@router.get("/movements/gymnastics", response_model=MovementListResponse)
async def get_gymnastics_movements(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get gymnastics movements (bodyweight skills)."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_gymnastics_movements(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"discipline": "gymnastics"}
    )


@router.get("/movements/compound", response_model=MovementListResponse)
async def get_compound_lifts(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements tagged as compound lifts."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_compound_lifts(db)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"tags": ["compound"]}
    )


@router.get("/movements/multi-discipline", response_model=MovementListResponse)
async def get_multi_discipline_movements(
    min_disciplines: int = Query(default=2, ge=2, le=10),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get movements that belong to multiple disciplines."""
    from app.services.movement import MovementQueryService
    
    movements = await MovementQueryService.get_multi_discipline_movements(db, min_disciplines)
    
    return MovementListResponse(
        movements=[
            MovementResponse(
                id=m.id,
                name=m.name,
                pattern=m.pattern.value if m.pattern else None,
                primary_muscle=m.primary_muscle,
                primary_region=m.primary_region,
                tier=m.tier,
                metabolic_demand=m.metabolic_demand,
                cns_load=m.cns_load,
                skill_level=m.skill_level,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
                is_unilateral=m.is_unilateral,
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                injury_risk_factor=m.injury_risk_factor,
                min_recovery_hours=m.min_recovery_hours,
                spinal_compression=m.spinal_compression,
                metric_type=m.metric_type,
                substitution_group=m.substitution_group,
                description=m.description,
                user_id=m.user_id,
                disciplines=[d.discipline.value for d in m.disciplines] if m.disciplines else [],
                equipment=[e.equipment.name for e in m.equipment if e.equipment] if m.equipment else [],
            )
            for m in movements
        ],
        total=len(movements),
        limit=None,
        offset=None,
        filters_applied={"min_disciplines": min_disciplines}
    )
