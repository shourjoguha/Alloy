"""API routes for workout logging."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.config.settings import get_settings
from app.models import (
    WorkoutLog,
    TopSetLog,
    SorenessLog,
    RecoverySignal,
    MuscleRecoveryState,
    PatternExposure,
    Session,
    SessionExercise,
    Movement,
    MovementPattern,
    RecoverySource,
    CircuitTemplate,
)
from app.models.enums import ExerciseRole
from app.schemas.logging import (
    WorkoutLogCreate,
    WorkoutLogResponse,
    TopSetResponse,
    SorenessLogCreate,
    SorenessLogResponse,
    RecoverySignalCreate,
    RecoverySignalResponse,
    MuscleRecoveryStateResponse,
    PatternExposureResponse,
    WorkoutLogListResponse,
    CustomWorkoutCreate,
    CustomExerciseCreate,
)
from app.services.metrics import calculate_e1rm, E1RM_FORMULAS
from app.api.routes.dependencies import get_current_user_id

router = APIRouter()
settings = get_settings()



@router.post("/workouts/custom", response_model=WorkoutLogResponse)
async def create_custom_workout_log(
    log: CustomWorkoutCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Log a custom workout (create ad-hoc session and log it).
    """
    # 1. Create ad-hoc Session
    session = Session(
        user_id=user_id,
        program_id=None,
        microcycle_id=None,
        name=log.workout_name if log.workout_name else f"Custom Workout - {log.log_date}",
        order=0,
        day_number=0,
        total_stimulus=0.0,
        total_fatigue=0.0,
        cns_fatigue=0.0,
        muscle_volume_json={},
    )
    db.add(session)
    await db.flush()

    # 2. Stats Accumulators
    stats = {
        "total_stimulus": 0.0,
        "total_fatigue": 0.0,
        "cns_fatigue": 0.0,
        "muscle_volume": {}  # muscle -> sets
    }
    
    cns_weights = {
        "very_low": 0.5, "low": 1.0, "moderate": 2.0, "high": 3.0, "very_high": 4.0
    }

    async def update_stats(movement_id: int, sets: int):
        movement = await db.get(Movement, movement_id)
        if not movement:
            return
        
        # Stimulus/Fatigue
        stats["total_stimulus"] += sets * (movement.stimulus_factor or 1.0)
        stats["total_fatigue"] += sets * (movement.fatigue_factor or 1.0)
        
        # CNS
        cns_load = movement.cns_load.lower() if isinstance(movement.cns_load, str) else str(movement.cns_load).lower()
        stats["cns_fatigue"] += sets * cns_weights.get(cns_load, 2.0)
        
        # Volume
        pm = str(movement.primary_muscle) if hasattr(movement.primary_muscle, 'value') else str(movement.primary_muscle)
        stats["muscle_volume"][pm] = stats["muscle_volume"].get(pm, 0) + sets
        
        for sm in (movement.secondary_muscles or []):
            sm_str = str(sm) if hasattr(sm, 'value') else str(sm)
            stats["muscle_volume"][sm_str] = stats["muscle_volume"].get(sm_str, 0) + (sets * 0.5)

    # 3. Process Sections
    async def process_exercises(exercises: list[CustomExerciseCreate], role: ExerciseRole, order_start: int) -> int:
        current_order = order_start
        for ex in exercises:
            sets = ex.sets or 1
            await update_stats(ex.movement_id, sets)
            
            session_exercise = SessionExercise(
                session_id=session.id,
                movement_id=ex.movement_id,
                exercise_role=role,
                order=current_order,
                target_sets=sets,
                target_rep_range_min=ex.reps,
                target_rep_range_max=ex.reps,
                notes=ex.notes or (f"Weight: {ex.weight}" if ex.weight else None),
                target_duration_seconds=ex.duration_seconds,
                stimulus=0.0, # Per-exercise stimulus could be calc here too, but schema implies session total?
                fatigue=0.0,
                user_id=user_id,
            )
            db.add(session_exercise)
            current_order += 1
        return current_order

    order_counter = 1
    if log.warmup:
        order_counter = await process_exercises(log.warmup, ExerciseRole.WARM_UP, order_counter)
    if log.main:
        order_counter = await process_exercises(log.main, ExerciseRole.MAIN_LIFT, order_counter)
    if log.accessory:
        order_counter = await process_exercises(log.accessory, ExerciseRole.ACCESSORY, order_counter)
    
    # Process Circuits
    async def process_circuit(circuit_id: int, role: ExerciseRole, order_start: int) -> int:
        circuit = await db.get(CircuitTemplate, circuit_id)
        if not circuit or not circuit.exercises_json:
            return order_start
        current_order = order_start
        rounds = circuit.default_rounds or 3
        
        for ex_data in circuit.exercises_json:
            movement_id = ex_data.get("movement_id")
            if not movement_id:
                continue
                
            await update_stats(movement_id, rounds)
            
            session_exercise = SessionExercise(
                session_id=session.id,
                movement_id=movement_id,
                exercise_role=role,
                order=current_order,
                target_sets=rounds,
                user_id=user_id,
                notes=f"Part of Circuit: {circuit.name}"
            )
            db.add(session_exercise)
            current_order += 1
        return current_order

    if log.finisher:
        order_counter = await process_exercises(log.finisher, ExerciseRole.FINISHER, order_counter)
    if log.finisher_circuit_id:
        order_counter = await process_circuit(log.finisher_circuit_id, ExerciseRole.FINISHER, order_counter)
    if log.cooldown:
        order_counter = await process_exercises(log.cooldown, ExerciseRole.COOL_DOWN, order_counter)

    # 4. Update Session Stats
    session.total_stimulus = stats["total_stimulus"]
    session.total_fatigue = stats["total_fatigue"]
    session.cns_fatigue = stats["cns_fatigue"]
    session.muscle_volume_json = stats["muscle_volume"]
    db.add(session)

    # 5. Create WorkoutLog
    workout_log = WorkoutLog(
        user_id=user_id,
        session_id=session.id,
        notes=log.notes,
        date=log.log_date,
        completed=True,
        perceived_difficulty=log.perceived_difficulty,
        enjoyment_rating=log.enjoyment_rating,
        actual_duration_minutes=log.duration_minutes,
    )
    db.add(workout_log)
    await db.commit()
    await db.refresh(workout_log)
    return workout_log


@router.post("/workouts", response_model=WorkoutLogResponse)

async def create_workout_log(
    log: WorkoutLogCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Log a completed workout with top sets and exercises.
    
    Calculates e1RM for each top set and records pattern exposure.
    """
    session: Session | None = None
    if log.session_id is not None:
        session = await db.get(Session, log.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Create workout log
    workout_log = WorkoutLog(
        user_id=user_id,
        session_id=log.session_id,
        notes=log.notes,
        date=log.log_date or date.today(),
        completed=log.completed,
        perceived_difficulty=log.perceived_difficulty,
        enjoyment_rating=log.enjoyment_rating,
        feedback_tags=log.feedback_tags or [],
        actual_duration_minutes=log.actual_duration_minutes,
    )
    db.add(workout_log)
    await db.flush()
    
    # Process top sets
    top_sets_response = []
    for top_set in log.top_sets or []:
        # Get movement for e1RM calculation
        movement = await db.get(Movement, top_set.movement_id)
        if not movement:
            raise HTTPException(status_code=404, detail=f"Movement not found: {top_set.movement_id}")
        
        try:
            pattern_enum = MovementPattern(movement.pattern)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Movement has invalid pattern: {movement.pattern}")
        
        # Calculate e1RM using preferred formula
        formula_enum = E1RM_FORMULAS.get(settings.default_e1rm_formula, E1RM_FORMULAS["epley"])
        e1rm = calculate_e1rm(
            weight=top_set.weight,
            reps=top_set.reps,
            formula=formula_enum,
        )
        
        top_set_log = TopSetLog(
            workout_log_id=workout_log.id,
            movement_id=top_set.movement_id,
            weight=top_set.weight,
            reps=top_set.reps,
            rpe=top_set.rpe,
            rir=top_set.rir,
            avg_rest_seconds=top_set.avg_rest_seconds,
            e1rm_value=e1rm,
            e1rm_formula=formula_enum,
            pattern=pattern_enum,
        )
        db.add(top_set_log)
        await db.flush()

        if session is not None:
            exposure = PatternExposure(
                user_id=user_id,
                microcycle_id=session.microcycle_id,
                date=workout_log.date,
                pattern=pattern_enum,
                e1rm_value=e1rm,
                source_top_set_log_id=top_set_log.id,
            )
            db.add(exposure)

        top_sets_response.append(TopSetResponse(
            id=top_set_log.id,
            movement_id=top_set.movement_id,
            movement_name=movement.name,
            weight=top_set.weight,
            reps=top_set.reps,
            rpe=top_set.rpe,
            rir=top_set.rir,
            avg_rest_seconds=top_set.avg_rest_seconds,
            e1rm=e1rm,
            e1rm_value=e1rm,
            e1rm_formula=formula_enum,
            pattern=pattern_enum,
            created_at=top_set_log.created_at,
        ))
    
    await db.commit()
    
    return WorkoutLogResponse(
        id=workout_log.id,
        user_id=workout_log.user_id,
        session_id=workout_log.session_id,
        log_date=workout_log.date,
        notes=workout_log.notes,
        perceived_difficulty=workout_log.perceived_difficulty,
        enjoyment_rating=workout_log.enjoyment_rating,
        feedback_tags=workout_log.feedback_tags,
        actual_duration_minutes=workout_log.actual_duration_minutes,
        top_sets=top_sets_response,
        created_at=workout_log.created_at,
    )


@router.get("/workouts", response_model=WorkoutLogListResponse)
async def list_workout_logs(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    program_id: Optional[int] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List workout logs with optional filtering."""
    query = select(WorkoutLog).where(WorkoutLog.user_id == user_id)
    
    if start_date:
        query = query.where(WorkoutLog.date >= start_date)
    if end_date:
        query = query.where(WorkoutLog.date <= end_date)
    
    query = query.order_by(WorkoutLog.date.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    # Get total count
    count_query = select(func.count(WorkoutLog.id)).where(WorkoutLog.user_id == user_id)
    if start_date:
        count_query = count_query.where(WorkoutLog.date >= start_date)
    if end_date:
        count_query = count_query.where(WorkoutLog.date <= end_date)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Build responses
    log_responses = []
    for log in logs:
        # Get top sets for this log
        top_sets_result = await db.execute(
            select(TopSetLog).where(TopSetLog.workout_log_id == log.id)
        )
        top_sets = list(top_sets_result.scalars().all())
        
        top_set_responses = []
        for ts in top_sets:
            movement = await db.get(Movement, ts.movement_id)
            top_set_responses.append(TopSetResponse(
                id=ts.id,
                movement_id=ts.movement_id,
                movement_name=movement.name if movement else "Unknown",
                weight=ts.weight,
                reps=ts.reps,
                rpe=ts.rpe,
                rir=ts.rir,
                avg_rest_seconds=ts.avg_rest_seconds,
                e1rm=ts.e1rm_value,
                e1rm_value=ts.e1rm_value,
                e1rm_formula=ts.e1rm_formula,
                pattern=ts.pattern,
                created_at=ts.created_at,
            ))
        
        log_responses.append(WorkoutLogResponse(
            id=log.id,
            session_id=log.session_id,
            log_date=log.date,
            notes=log.notes,
            perceived_difficulty=log.perceived_difficulty,
            enjoyment_rating=log.enjoyment_rating,
            feedback_tags=log.feedback_tags,
            actual_duration_minutes=log.actual_duration_minutes,
            top_sets=top_set_responses,
            created_at=log.created_at,
        ))
    
    return WorkoutLogListResponse(
        logs=log_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/workouts/{log_id}", response_model=WorkoutLogResponse)
async def get_workout_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get a specific workout log by ID."""
    log = await db.get(WorkoutLog, log_id)
    
    if not log or log.user_id != user_id:
        raise HTTPException(status_code=404, detail="Workout log not found")
    
    # Get top sets
    top_sets_result = await db.execute(
        select(TopSetLog).where(TopSetLog.workout_log_id == log.id)
    )
    top_sets = list(top_sets_result.scalars().all())
    
    top_set_responses = []
    for ts in top_sets:
        movement = await db.get(Movement, ts.movement_id)
        top_set_responses.append(TopSetResponse(
            id=ts.id,
            movement_id=ts.movement_id,
            movement_name=movement.name if movement else "Unknown",
            weight=ts.weight,
            reps=ts.reps,
            rpe=ts.rpe,
            rir=ts.rir,
            avg_rest_seconds=ts.avg_rest_seconds,
            e1rm=ts.e1rm_value,
            e1rm_value=ts.e1rm_value,
            e1rm_formula=ts.e1rm_formula,
            pattern=ts.pattern,
            created_at=ts.created_at,
        ))
    
    return WorkoutLogResponse(
        id=log.id,
        user_id=log.user_id,
        session_id=log.session_id,
        log_date=log.date,
        notes=log.notes,
        perceived_difficulty=log.perceived_difficulty,
        enjoyment_rating=log.enjoyment_rating,
        feedback_tags=log.feedback_tags,
        actual_duration_minutes=log.actual_duration_minutes,
        top_sets=top_set_responses,
        created_at=log.created_at,
    )


# Soreness logging
@router.post("/soreness", response_model=SorenessLogResponse)
async def create_soreness_log(
    log: SorenessLogCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Log muscle soreness for a body part and update recovery state."""
    from datetime import datetime
    
    log_date = log.log_date or date.today()
    
    # Create soreness log
    soreness = SorenessLog(
        user_id=user_id,
        date=log_date,
        body_part=log.body_part,
        soreness_1_5=log.soreness_1_5,
        notes=log.notes,
    )
    db.add(soreness)
    await db.flush()
    
    # Update muscle recovery state
    # Get existing state or create new
    existing_state = await db.execute(
        select(MuscleRecoveryState).where(
            MuscleRecoveryState.user_id == user_id,
            MuscleRecoveryState.muscle == log.body_part
        )
    )
    existing = existing_state.scalar_one_or_none()
    
    now = datetime.utcnow()
    
    if existing:
        # Update existing state with new soreness level
        existing.recovery_level = log.soreness_1_5
        existing.last_updated_at = now
        db.add(existing)
    else:
        # Create new state
        recovery_state = MuscleRecoveryState(
            user_id=user_id,
            muscle=log.body_part,
            recovery_level=log.soreness_1_5,
            last_updated_at=now,
        )
        db.add(recovery_state)
    
    await db.commit()
    await db.refresh(soreness)
    
    return SorenessLogResponse(
        id=soreness.id,
        log_date=soreness.date,
        body_part=soreness.body_part,
        soreness_1_5=soreness.soreness_1_5,
        notes=soreness.notes,
    )


@router.get("/soreness", response_model=List[SorenessLogResponse])
async def list_soreness_logs(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    body_part: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List soreness logs with optional filtering."""
    query = select(SorenessLog).where(SorenessLog.user_id == user_id)
    
    if start_date:
        query = query.where(SorenessLog.date >= start_date)
    if end_date:
        query = query.where(SorenessLog.date <= end_date)
    if body_part:
        query = query.where(SorenessLog.body_part == body_part)
    
    query = query.order_by(SorenessLog.date.desc()).limit(limit)
    
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    return [
        SorenessLogResponse(
            id=log.id,
            log_date=log.date,
            body_part=log.body_part,
            soreness_1_5=log.soreness_1_5,
            notes=log.notes,
        )
        for log in logs
]


# Muscle recovery state endpoints
@router.get("/muscle-recovery", response_model=List[MuscleRecoveryStateResponse])
async def get_muscle_recovery_states(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get current muscle recovery states with decay applied.
    Returns recovery levels adjusted for time since last update (1 point per 10 hours decay).
    """
    from datetime import datetime
    
    query = select(MuscleRecoveryState).where(
        MuscleRecoveryState.user_id == user_id
    )
    
    result = await db.execute(query)
    states = list(result.scalars().all())
    
    # Apply decay function: 1 point per 10 hours
    now = datetime.utcnow()
    decayed_states = []
    
    for state in states:
        hours_since_update = (now - state.last_updated_at).total_seconds() / 3600
        decay_points = int(hours_since_update / 10)
        
        # Apply decay (minimum 0)
        decayed_level = max(0, state.recovery_level - decay_points)
        
        decayed_states.append(MuscleRecoveryStateResponse(
            id=state.id,
            user_id=state.user_id,
            muscle=state.muscle,
            recovery_level=decayed_level,
            last_updated_at=state.last_updated_at,
            created_at=state.created_at,
        ))
    
    return decayed_states


@router.get("/muscle-recovery/{muscle}", response_model=MuscleRecoveryStateResponse)
async def get_muscle_recovery_state(
    muscle: str,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get current recovery state for a specific muscle with decay applied.
    Returns recovery level adjusted for time since last update (1 point per 10 hours decay).
    """
    from datetime import datetime
    
    query = select(MuscleRecoveryState).where(
        MuscleRecoveryState.user_id == user_id,
        MuscleRecoveryState.muscle == muscle
    )
    
    result = await db.execute(query)
    state = result.scalar_one_or_none()
    
    if not state:
        raise HTTPException(status_code=404, detail="Muscle recovery state not found")
    
    # Apply decay function using config setting
    now = datetime.utcnow()
    decay_hours = settings.soreness_decay_hours
    hours_since_update = (now - state.last_updated_at).total_seconds() / 3600
    decay_points = int(hours_since_update / decay_hours)
    
    # Apply decay (minimum 0)
    decayed_level = max(0, state.recovery_level - decay_points)
    
    return MuscleRecoveryStateResponse(
        id=state.id,
        user_id=state.user_id,
        muscle=state.muscle,
        recovery_level=decayed_level,
        last_updated_at=state.last_updated_at,
        created_at=state.created_at,
    )


# Recovery signals
@router.post("/recovery", response_model=RecoverySignalResponse)
async def create_recovery_signal(
    signal: RecoverySignalCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Log recovery signal from wearable or manual input."""
    recovery = RecoverySignal(
        user_id=user_id,
        date=signal.log_date or date.today(),
        session_id=signal.session_id,
        source=signal.source,
        sleep_score=signal.sleep_score,
        sleep_hours=signal.sleep_hours,
        readiness=signal.readiness,
        hrv=signal.hrv,
        resting_hr=signal.resting_hr,
        raw_payload_json=signal.raw_payload,
        notes=signal.notes,
    )
    db.add(recovery)
    await db.commit()
    
    return RecoverySignalResponse(
        id=recovery.id,
        user_id=recovery.user_id,
        log_date=recovery.date,
        session_id=recovery.session_id,
        source=recovery.source,
        sleep_score=recovery.sleep_score,
        sleep_hours=recovery.sleep_hours,
        readiness=recovery.readiness,
        hrv=recovery.hrv,
        resting_hr=recovery.resting_hr,
        raw_payload=recovery.raw_payload_json,
        notes=recovery.notes,
        created_at=recovery.created_at,
    )


@router.get("/recovery", response_model=List[RecoverySignalResponse])
async def list_recovery_signals(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    source: Optional[RecoverySource] = None,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """List recovery signals with optional filtering."""
    query = select(RecoverySignal).where(RecoverySignal.user_id == user_id)
    
    if start_date:
        query = query.where(RecoverySignal.date >= start_date)
    if end_date:
        query = query.where(RecoverySignal.date <= end_date)
    if source:
        query = query.where(RecoverySignal.source == source)
    
    query = query.order_by(RecoverySignal.date.desc()).limit(limit)
    
    result = await db.execute(query)
    signals = list(result.scalars().all())
    
    return [
        RecoverySignalResponse(
            id=sig.id,
            user_id=sig.user_id,
            log_date=sig.date,
            session_id=sig.session_id,
            source=sig.source,
            sleep_score=sig.sleep_score,
            sleep_hours=sig.sleep_hours,
            readiness=sig.readiness,
            hrv=sig.hrv,
            resting_hr=sig.resting_hr,
            raw_payload=sig.raw_payload_json,
            notes=sig.notes,
            created_at=sig.created_at,
        )
        for sig in signals
    ]


@router.get("/recovery/latest", response_model=RecoverySignalResponse)
async def get_latest_recovery(
    target_date: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get the latest recovery signal, optionally for a specific date."""
    query = select(RecoverySignal).where(RecoverySignal.user_id == user_id)
    
    if target_date:
        query = query.where(RecoverySignal.date == target_date)
    
    query = query.order_by(RecoverySignal.created_at.desc()).limit(1)
    
    result = await db.execute(query)
    signal = result.scalar_one_or_none()
    
    if not signal:
        raise HTTPException(status_code=404, detail="No recovery signal found")
    
    return RecoverySignalResponse(
        id=signal.id,
        user_id=signal.user_id,
        log_date=signal.date,
        session_id=signal.session_id,
        source=signal.source,
        sleep_score=signal.sleep_score,
        sleep_hours=signal.sleep_hours,
        readiness=signal.readiness,
        hrv=signal.hrv,
        resting_hr=signal.resting_hr,
        raw_payload=signal.raw_payload_json,
        notes=signal.notes,
        created_at=signal.created_at,
    )


# Dashboard stats
@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    Get aggregated stats for the dashboard.
    
    Returns workout count, streak, heaviest lift, total volume, etc.
    """
    from datetime import timedelta
    from sqlalchemy import desc
    
    today = date.today()
    month_start = today.replace(day=1)
    
    # Total workouts
    total_workouts_result = await db.execute(
        select(func.count(WorkoutLog.id)).where(WorkoutLog.user_id == user_id)
    )
    total_workouts = total_workouts_result.scalar() or 0
    
    # Workouts this month
    month_workouts_result = await db.execute(
        select(func.count(WorkoutLog.id)).where(
            and_(
                WorkoutLog.user_id == user_id,
                WorkoutLog.date >= month_start
            )
        )
    )
    workouts_this_month = month_workouts_result.scalar() or 0
    
    # Calculate week streak (consecutive weeks with at least one workout)
    # Get all workout dates
    dates_result = await db.execute(
        select(WorkoutLog.date)
        .where(WorkoutLog.user_id == user_id)
        .order_by(desc(WorkoutLog.date))
    )
    workout_dates = [row[0] for row in dates_result.fetchall()]
    
    week_streak = 0
    if workout_dates:
        # Get current week's Monday
        current_week_monday = today - timedelta(days=today.weekday())
        checking_week = current_week_monday
        
        while True:
            week_end = checking_week + timedelta(days=6)
            has_workout = any(
                checking_week <= d <= week_end for d in workout_dates
            )
            if has_workout:
                week_streak += 1
                checking_week -= timedelta(days=7)
            else:
                break
    
    # Heaviest lift (by e1RM)
    heaviest_result = await db.execute(
        select(TopSetLog, Movement)
        .join(WorkoutLog)
        .join(Movement, TopSetLog.movement_id == Movement.id)
        .where(WorkoutLog.user_id == user_id)
        .order_by(desc(TopSetLog.e1rm_value))
        .limit(1)
    )
    heaviest_row = heaviest_result.first()
    heaviest_lift = None
    if heaviest_row:
        top_set, movement = heaviest_row
        heaviest_lift = {
            "weight": top_set.weight,
            "movement": movement.name,
            "e1rm": top_set.e1rm_value,
        }
    
    # Longest workout (by duration)
    longest_result = await db.execute(
        select(WorkoutLog)
        .where(
            and_(
                WorkoutLog.user_id == user_id,
                WorkoutLog.actual_duration_minutes.isnot(None),
            )
        )
        .order_by(
            desc(WorkoutLog.actual_duration_minutes)
        )
        .limit(1)
    )
    longest_workout = longest_result.scalar_one_or_none()
    longest_duration = None
    if longest_workout and longest_workout.actual_duration_minutes:
        longest_duration = {
            "minutes": longest_workout.actual_duration_minutes,
            "date": longest_workout.date.isoformat() if longest_workout.date else None,
        }
    
    # Total volume this month (sum of weight * reps for all top sets)
    volume_result = await db.execute(
        select(func.sum(TopSetLog.weight * TopSetLog.reps))
        .join(WorkoutLog)
        .where(
            and_(
                WorkoutLog.user_id == user_id,
                WorkoutLog.date >= month_start
            )
        )
    )
    total_volume = volume_result.scalar() or 0
    
    # Note: adherence_percentage field doesn't exist in WorkoutLog model yet
    # TODO: Add adherence tracking when workout logging is implemented
    
    return {
        "total_workouts": total_workouts,
        "workouts_this_month": workouts_this_month,
        "week_streak": week_streak,
        "heaviest_lift": heaviest_lift,
        "longest_workout": longest_duration,
        "total_volume_this_month": round(total_volume, 1),
        "average_adherence": None,  # Not tracked yet
    }


# Pattern exposure
@router.get("/pattern-exposure", response_model=List[PatternExposureResponse])
async def list_pattern_exposure(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    pattern: Optional[MovementPattern] = None,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get pattern exposure history for tracking volume by movement pattern."""
    query = select(PatternExposure).where(PatternExposure.user_id == user_id)
    
    if start_date:
        query = query.where(PatternExposure.date >= start_date)
    if end_date:
        query = query.where(PatternExposure.date <= end_date)
    if pattern:
        query = query.where(PatternExposure.pattern == pattern)
    
    query = query.order_by(PatternExposure.date.desc())
    
    result = await db.execute(query)
    exposures = list(result.scalars().all())
    
    return [
        PatternExposureResponse(
            id=exp.id,
            user_id=exp.user_id,
            microcycle_id=exp.microcycle_id,
            log_date=exp.date,
            pattern=exp.pattern,
            e1rm_value=exp.e1rm_value,
            source_top_set_log_id=exp.source_top_set_log_id,
            created_at=exp.created_at,
        )
        for exp in exposures
    ]
