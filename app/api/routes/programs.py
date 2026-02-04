"""API routes for program management."""
from datetime import datetime, date
import logging

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.config import activity_distribution as activity_distribution_config
from app.config.settings import get_settings
from app.models import (
    Program,
    Microcycle,
    Session,
    User,
    UserProfile,
    UserMovementRule,
    UserEnjoyableActivity,
    MicrocycleStatus,
    EnjoyableActivity,
    SessionExercise,
    CircuitTemplate,
)
from app.schemas.program import (
    ProgramCreate,
    ProgramResponse,
    MicrocycleResponse,
    MicrocycleWithSessionsResponse,
    SessionResponse,
    ProgramWithMicrocycleResponse,
    ProgramUpdate,
)
from app.services.program import program_service
from app.services.interference import interference_service
from app.services.time_estimation import time_estimation_service
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


def _normalize_enjoyable_activity(activity_type: str, custom_name: str | None) -> tuple[EnjoyableActivity, str | None]:
    if not activity_type:
        return EnjoyableActivity.OTHER, custom_name
    if activity_type == "custom":
        return EnjoyableActivity.OTHER, custom_name or "custom"
    try:
        return EnjoyableActivity(activity_type), custom_name
    except ValueError:
        return EnjoyableActivity.OTHER, custom_name or activity_type


@router.post("", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    program_data: ProgramCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Create a new training program.
    
    Requires:
    - 1-3 goals with weights summing to 10
    - Duration of 8-12 weeks
    - Split template selection
    - Progression style selection
    
    Optional:
    - Name (for historic tracking)
    - Persona overrides
    - Movement rules
    - Enjoyable activities
    """
    logger.info("Starting program creation for user_id=%s, data=%s", user_id, program_data.model_dump())
    
    try:
        logger.info("Fetching user with id=%s", user_id)
        user = await db.get(User, user_id)
        logger.info("User fetched: %s", user)
        if not user:
            logger.error("User not found for user_id=%s", user_id)
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.exception("Error fetching user: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching user: {str(e)}")
    
    # Validate goals before creation (only if multiple goals provided)
    if len(program_data.goals) >= 2:
        # Pad goals to 3 for validation if needed
        goals_for_validation = [g.goal for g in program_data.goals]
        while len(goals_for_validation) < 3:
            goals_for_validation.append(goals_for_validation[0])  # Duplicate first goal
        
        is_valid, warnings = await interference_service.validate_goals(
            db,
            goals_for_validation[0],
            goals_for_validation[1],
            goals_for_validation[2],
        )
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Goal validation failed: {', '.join(warnings)}"
            )
    
    logger.info("Calling ProgramService.create_program")
    # Use ProgramService to create program with microcycles and sessions
    program = await program_service.create_program(db, user_id, program_data)
    logger.info("Program created successfully with id=%s", program.id)
    
    # Refresh program to load program_disciplines relationship
    logger.info("Refreshing program with id=%s", program.id)
    await db.refresh(program)
    logger.info("Program refreshed successfully")
    
    # Explicitly load program_disciplines relationship
    logger.info("Loading program_disciplines for program_id=%s", program.id)
    result = await db.execute(
        select(Program)
        .options(selectinload(Program.program_disciplines))
        .where(Program.id == program.id)
    )
    program = result.scalar_one()
    logger.info("Program disciplines loaded successfully")
    
    # Create or update movement rules if provided (post-program creation)
    if program_data.movement_rules:
        for rule in program_data.movement_rules:
            # Check if rule already exists
            existing_rule = await db.execute(
                select(UserMovementRule).where(
                    and_(
                        UserMovementRule.user_id == user_id,
                        UserMovementRule.movement_id == rule.movement_id,
                        UserMovementRule.rule_type == rule.rule_type
                    )
                )
            )
            existing = existing_rule.scalar_one_or_none()
            
            if existing:
                # Update existing rule
                existing.cadence = rule.cadence
                existing.notes = rule.notes
                existing.updated_at = datetime.utcnow()
            else:
                # Create new rule
                user_rule = UserMovementRule(
                    user_id=user_id,
                    movement_id=rule.movement_id,
                    rule_type=rule.rule_type,
                    cadence=rule.cadence,
                    notes=rule.notes,
                )
                db.add(user_rule)
    
    # Create or update enjoyable activities if provided
    if program_data.enjoyable_activities:
        for activity in program_data.enjoyable_activities:
            activity_enum, normalized_custom_name = _normalize_enjoyable_activity(
                activity.activity_type,
                activity.custom_name,
            )
            # Check if activity already exists
            existing_activity = await db.execute(
                select(UserEnjoyableActivity).where(
                    and_(
                        UserEnjoyableActivity.user_id == user_id,
                        UserEnjoyableActivity.activity_type == activity_enum,
                        UserEnjoyableActivity.custom_name == normalized_custom_name
                    )
                )
            )
            existing = existing_activity.scalar_one_or_none()
            
            if existing:
                # Update existing activity
                existing.recommend_every_days = activity.recommend_every_days
                existing.enabled = True
            else:
                # Create new activity
                user_activity = UserEnjoyableActivity(
                    user_id=user_id,
                    activity_type=activity_enum,
                    custom_name=normalized_custom_name,
                    recommend_every_days=activity.recommend_every_days,
                    enabled=True,
                )
                db.add(user_activity)
    
    # Commit all changes (program, microcycles, sessions, movement rules, enjoyable activities)
    # This ensures all sessions are visible to the background task
    try:
        logger.info(f"[API] About to commit ALL changes for program_id={program.id}")
        logger.info("[API] This commit will make all sessions visible to background tasks")
        await db.commit()
        logger.info(f"Successfully committed all changes for program_id={program.id}")
    except Exception:
        await db.rollback()
        logger.exception(f"Failed to commit program creation for program_id={program.id}")
        raise HTTPException(status_code=500, detail="Internal server error")

    # CRITICAL: Add background task AFTER all transactions are committed
    # This ensures all sessions are available when the background task queries the database
    # If the background task is added before commit, it may query for sessions before they are
    # committed, leading to only seeing the first and last sessions that were flushed
    logger.info("[API] CRITICAL: Adding background task AFTER commit")
    logger.info("[API] All sessions should now be visible in the database")
    background_tasks.add_task(
        program_service.generate_active_microcycle_sessions,
        program.id,
    )
    logger.info(f"Background task added to generate sessions for program_id={program.id}")

    try:
        return program
    except Exception as e:
        logger.exception("Error serializing program response: %s", e)
        raise HTTPException(status_code=500, detail=f"Error serializing program: {str(e)}")


@router.get("/{program_id}", response_model=ProgramWithMicrocycleResponse)
async def get_program(
    program_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get program with active microcycle, upcoming sessions, and per-week sessions."""
    print(f"DEBUG: get_program called with program_id={program_id}, user_id={user_id}")
    try:
        result = await db.execute(
            select(Program)
            .options(selectinload(Program.program_disciplines))
            .where(Program.id == program_id)
        )
        program = result.scalar_one_or_none()
        
        if not program:
            raise HTTPException(status_code=404, detail="Program not found")
        
        if program.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this program")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching program %s: %s", program_id, e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
    
    # Get active microcycle
    try:
        active_microcycle_result = await db.execute(
            select(Microcycle)
            .where(
                and_(
                    Microcycle.program_id == program_id,
                    Microcycle.status == MicrocycleStatus.ACTIVE
                )
            )
            .options(
                selectinload(Microcycle.sessions)
                .options(
                    selectinload(Session.exercises).selectinload(SessionExercise.movement),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.melted_exercises),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.macro_metrics)
                )
            )
        )
        active_microcycle = active_microcycle_result.scalar_one_or_none()
    except Exception as e:
        logger.exception("Error fetching active microcycle for program %s: %s", program_id, e)
        raise HTTPException(status_code=500, detail="Internal server error") from e

    # Get all microcycles with their sessions
    try:
        microcycles_result = await db.execute(
            select(Microcycle)
            .where(Microcycle.program_id == program_id)
            .options(
                selectinload(Microcycle.sessions)
                .options(
                    selectinload(Session.exercises).selectinload(SessionExercise.movement),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.melted_exercises),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.macro_metrics)
                )
            )
            .order_by(Microcycle.sequence_number)
        )
        microcycles = list(microcycles_result.scalars().unique().all())
    except Exception as e:
        logger.exception("Error fetching microcycles for program %s: %s", program_id, e)
        raise HTTPException(status_code=500, detail="Internal server error") from e

    # Get upcoming sessions (rest of active microcycle)
    upcoming_sessions = []
    print(f"DEBUG: active_microcycle = {active_microcycle}")
    if active_microcycle:
        today = date.today()
        from datetime import timedelta
        microcycle_end = active_microcycle.start_date + timedelta(days=active_microcycle.length_days)
        print(f"DEBUG: Fetching sessions from {today} to {microcycle_end}")
        try:
            sessions_result = await db.execute(
                select(Session)
                .where(
                    and_(
                        Session.microcycle_id == active_microcycle.id,
                        Session.date >= today,
                        Session.date < microcycle_end,
                    )
                )
                .options(
                    selectinload(Session.exercises).selectinload(SessionExercise.movement),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.melted_exercises),
                    selectinload(Session.finisher_circuit)
                        .selectinload(CircuitTemplate.macro_metrics)
                )
                .order_by(Session.date)
            )
            upcoming_sessions = list(sessions_result.scalars().all())
            print(f"DEBUG: Found {len(upcoming_sessions)} upcoming sessions")
        except Exception as e:
            logger.exception("Error fetching upcoming sessions for microcycle %s: %s", active_microcycle.id, e)
            raise HTTPException(status_code=500, detail="Internal server error") from e
    
    # Convert upcoming sessions to response format with duration estimates
    # Use simple estimation to avoid N+1 query problem
    session_responses = []
    for session in upcoming_sessions:
        if not session.estimated_duration_minutes:
            try:
                breakdown = time_estimation_service.calculate_session_duration(session)
                session.estimated_duration_minutes = breakdown.total_minutes
                session.warmup_duration_minutes = breakdown.warmup_minutes
                session.main_duration_minutes = breakdown.main_minutes
                session.accessory_duration_minutes = breakdown.accessory_minutes
                session.finisher_duration_minutes = breakdown.finisher_minutes
                session.cooldown_duration_minutes = breakdown.cooldown_minutes
            except Exception as e:
                logger.warning("Error calculating duration for session %s: %s", session.id, e)
                # Simple estimation: 4 mins per exercise + 10 mins warmup
                exercise_count = len(session.exercises) if session.exercises else 0
                session.estimated_duration_minutes = 10 + (exercise_count * 4)
        
        try:
            print(f"DEBUG: Validating session {session.id}")
            session_responses.append(SessionResponse.model_validate(session))
        except Exception as e:
            print(f"ERROR validating session {session.id}: {e}")
            import traceback
            traceback.print_exc()
            logger.exception("Error validating session %s to response model: %s", session.id, e)
            raise HTTPException(status_code=500, detail="Internal server error") from e

    # Build per-microcycle session views
    microcycle_responses: list[MicrocycleWithSessionsResponse] = []
    print(f"DEBUG: Processing {len(microcycles)} microcycles")
    for microcycle in microcycles:
        microcycle_sessions: list[SessionResponse] = []
        # Ensure sessions are ordered by day_number
        ordered_sessions = sorted(
            microcycle.sessions or [],
            key=lambda s: (s.day_number, s.date or date.min),
        )
        print(f"DEBUG: Microcycle {microcycle.id} has {len(ordered_sessions)} sessions")
        for session in ordered_sessions:
            if not session.estimated_duration_minutes:
                try:
                    # Attempt calculation if not set
                    breakdown = time_estimation_service.calculate_session_duration(session)
                    session.estimated_duration_minutes = breakdown.total_minutes
                except Exception as e:
                    logger.warning("Error calculating duration for microcycle session %s: %s", session.id, e)
                    # Simple estimation: 4 mins per exercise + 10 mins warmup
                    exercise_count = len(session.exercises) if session.exercises else 0
                    session.estimated_duration_minutes = 10 + (exercise_count * 4)

            try:
                print(f"DEBUG: Validating microcycle session {session.id}")
                microcycle_sessions.append(SessionResponse.model_validate(session))
            except Exception as e:
                print(f"ERROR validating microcycle session {session.id}: {e}")
                import traceback
                traceback.print_exc()
                logger.exception("Error validating microcycle session %s to response model: %s", session.id, e)
                raise HTTPException(status_code=500, detail="Internal server error") from e

        microcycle_responses.append(
            MicrocycleWithSessionsResponse(
                id=microcycle.id,
                program_id=microcycle.program_id,
                micro_start_date=microcycle.start_date,
                length_days=microcycle.length_days,
                sequence_number=microcycle.sequence_number,
                status=microcycle.status,
                is_deload=microcycle.is_deload,
                sessions=microcycle_sessions,
            )
        )

    print("DEBUG: Constructing ProgramWithMicrocycleResponse")
    print(f"DEBUG: program={program}, active_microcycle={active_microcycle}")
    print(f"DEBUG: upcoming_sessions count={len(session_responses)}, microcycles count={len(microcycle_responses)}")
    
    try:
        response = ProgramWithMicrocycleResponse(
            program=program,
            active_microcycle=active_microcycle,
            upcoming_sessions=session_responses,
            microcycles=microcycle_responses,
        )
        print("DEBUG: ProgramWithMicrocycleResponse constructed successfully")
        return response
    except Exception as e:
        print(f"ERROR: Failed to construct ProgramWithMicrocycleResponse: {e}")
        import traceback
        traceback.print_exc()
        logger.exception("Error constructing ProgramWithMicrocycleResponse: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("", response_model=list[ProgramResponse])
async def list_programs(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List all programs for the current user."""
    logger.info("list_programs called: user_id=%s, active_only=%s", user_id, active_only)
    
    query = select(Program).options(selectinload(Program.program_disciplines)).where(Program.user_id == user_id)
    
    if active_only:
        query = query.where(Program.is_active.is_(True))
    
    query = query.order_by(Program.is_active.desc(), Program.created_at.desc())
    
    result = await db.execute(query)
    programs = list(result.scalars().unique().all())
    
    logger.info("list_programs: found %d programs for user_id=%s", len(programs), user_id)
    for prog in programs:
        logger.info("  Program id=%s, name=%s, is_active=%s, created_at=%s", prog.id, prog.name, prog.is_active, prog.created_at)
    
    return programs


@router.post("/{program_id}/microcycles/generate-next", response_model=MicrocycleResponse)
async def generate_next_microcycle(
    program_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Generate the next microcycle for a program.
    
    This will:
    1. Mark the current active microcycle as complete
    2. Create a new microcycle with sessions
    3. Generate session content for the new microcycle using LLM
    """
    program = await db.get(Program, program_id)
    
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    if program.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get current active microcycle
    active_result = await db.execute(
        select(Microcycle)
        .where(
            and_(
                Microcycle.program_id == program_id,
                Microcycle.status == MicrocycleStatus.ACTIVE
            )
        )
    )
    current_microcycle = active_result.scalar_one_or_none()
    
    # Determine sequence number and start date
    if current_microcycle:
        current_microcycle.status = MicrocycleStatus.COMPLETE
        next_seq = current_microcycle.sequence_number + 1
        next_start = current_microcycle.start_date
        # Add current microcycle length
        from datetime import timedelta
        next_start = next_start + timedelta(days=current_microcycle.length_days)
    else:
        next_seq = 1
        next_start = program.start_date
    
    # Determine if this is a deload week
    is_deload = (next_seq % program.deload_every_n_microcycles == 0)

    user_profile = await db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    scheduling_prefs = user_profile.scheduling_preferences if user_profile else {}
    pref_length = (scheduling_prefs or {}).get("microcycle_length_days")
    if isinstance(pref_length, int) and 7 <= pref_length <= 14:
        length_days = pref_length
    else:
        length_days = activity_distribution_config.default_microcycle_length_days
    
    # Build split configuration for the new microcycle
    # Construct goals from program's goal fields
    from app.schemas.program import GoalWeight
    goals = [
        GoalWeight(goal=program.goal_1, weight=program.goal_weight_1),
        GoalWeight(goal=program.goal_2, weight=program.goal_weight_2),
        GoalWeight(goal=program.goal_3, weight=program.goal_weight_3),
    ]
    
    split_config = program_service._build_freeform_split_config(
        cycle_length_days=length_days,
        days_per_week=program.days_per_week,
    )
    split_config = program_service._apply_goal_based_cycle_distribution(
        split_config=split_config,
        goals=goals,
        days_per_week=program.days_per_week,
        cycle_length_days=length_days,
        max_session_duration=program.max_session_duration,
        user_experience_level=None,  # Will fetch if needed
        scheduling_prefs=scheduling_prefs,
    )
    split_config = program_service._assign_freeform_day_types_and_focus(
        split_config=split_config,
        days_per_week=program.days_per_week,
    )
    
    # Create new microcycle with sessions using the internal method
    new_microcycle = await program_service._create_microcycle(
        db,
        user_id=program.user_id,
        program_id=program_id,
        mc_index=next_seq - 1,  # 0-indexed
        start_date=next_start,
        split_config=split_config,
        is_deload=is_deload,
    )
    
    # Commit microcycle and sessions to database
    await db.commit()
    await db.refresh(new_microcycle)
    
    # Generate session content in background using LLM
    # This ensures all sessions are committed before background task starts
    background_tasks.add_task(program_service.generate_active_microcycle_sessions, program_id)
    
    return new_microcycle


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    program_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Delete a program."""
    program = await db.get(Program, program_id)
    
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    if program.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    await db.delete(program)
    await db.commit()


@router.patch("/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: int,
    program_update: ProgramUpdate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Update program details (name, status)."""
    program = await db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    if program.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = program_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(program, field, value)
    
    await db.commit()
    await db.refresh(program)
    return program


@router.post("/{program_id}/activate", response_model=ProgramResponse)
async def activate_program(
    program_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Activate a program (deactivates any other active programs)."""
    program = await db.get(Program, program_id)
    
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")
    
    if program.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Deactivate other programs
    other_active = await db.execute(
        select(Program).where(
            and_(
                Program.user_id == user_id,
                Program.is_active.is_(True),
                Program.id != program_id
            )
        )
    )
    for prog in other_active.scalars():
        prog.is_active = False
    
    program.is_active = True
    await db.commit()
    await db.refresh(program, ['program_disciplines'])
    
    return program
