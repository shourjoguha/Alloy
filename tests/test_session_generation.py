"""Test session generation with block-based templates."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.session_generator import SessionGeneratorService
from app.models.program import Session, Program, Microcycle
from app.models.enums import Goal, SplitTemplate, SessionType, CircuitType
from app.models.circuit import CircuitTemplate
from app.schemas.program import ProgramCreate, GoalWeight


@pytest.mark.asyncio
async def test_session_generator_normal_template(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test normal template generation with main lifts and accessories."""
    service = SessionGeneratorService()
    
    # Create a test program mirroring actual create program flow
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.ENDURANCE, weight=2),
        ],
        duration_weeks=8,
        program_start_date=None,  # Defaults to today
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=60,  # 60 minute sessions
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )
    
    from app.services.program import program_service
    program = await program_service.create_program(async_db_session, test_user.id, request)
    
    # Get active microcycle and first session
    result = await async_db_session.execute(
        select(Microcycle).where(Microcycle.program_id == program.id)
    )
    microcycles = list(result.scalars().all())
    active_mc = microcycles[0]
    
    result = await async_db_session.execute(
        select(Session).where(Session.microcycle_id == active_mc.id)
    )
    sessions = list(result.scalars().all())
    session = sessions[0]
    
    # Generate session content using new block-based approach
    content = await service.generate_session_exercises(
        async_db_session,
        session,
        program,
        active_mc,
        [],  # used_movements: list of strings (movement names)
        {},  # used_movement_groups: dict
        None,  # used_accessory_movements
        None,  # fatigued_muscles
    )
    
    # Verify content structure
    assert content is not None
    assert "warmup" in content
    assert "main" in content
    assert "cooldown" in content
    assert "estimated_duration_minutes" in content
    
    # Count total exercises
    total_exercises = 0
    for section in ["warmup", "main", "accessory", "cooldown"]:
        if section in content and content[section]:
            total_exercises += len(content[section])
    
    # Verify session has exercises
    assert total_exercises > 0, "Session should have exercises populated"
    
    # Verify duration is within 5% buffer of target (60 min default)
    target_duration = program.max_session_duration or 60
    from app.services.time_estimation import TimeEstimationService
    time_service = TimeEstimationService()
    
    estimated_duration = time_service.estimate_session_time_with_transitions(
        warmup=content.get("warmup", []),
        main=content.get("main", []),
        accessory=content.get("accessory", []),
        circuit=content.get("circuit"),
        finisher=content.get("finisher"),
        cooldown=content.get("cooldown", []),
        intent="strength",
    )
    
    actual_duration = estimated_duration.total_minutes
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05
    
    assert buffer_min <= actual_duration <= buffer_max, \
        f"Duration {actual_duration} should be within 5% of target {target_duration}"


@pytest.mark.asyncio
async def test_session_generator_cardio_template(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test cardio template generation."""
    service = SessionGeneratorService()
    
    # Create a program with cardio goal
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.ENDURANCE, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.MOBILITY, weight=2),
        ],
        duration_weeks=8,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=45,  # 45 minute sessions
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )
    
    from app.services.program import program_service
    program = await program_service.create_program(async_db_session, test_user.id, request)
    
    # Get a session and set it to cardio type
    result = await async_db_session.execute(
        select(Microcycle).where(Microcycle.program_id == program.id)
    )
    microcycles = list(result.scalars().all())
    active_mc = microcycles[0]
    
    result = await async_db_session.execute(
        select(Session).where(Session.microcycle_id == active_mc.id)
    )
    sessions = list(result.scalars().all())
    session = sessions[0]
    session.session_type = SessionType.CARDIO
    
    # Generate content
    content = await service.generate_session_exercises(
        async_db_session,
        session,
        program,
        active_mc,
        [],  # used_movements
        {},  # used_movement_groups
        None,  # used_accessory_movements
        None,  # fatigued_muscles
    )
    
    # Verify cardio template structure
    assert content is not None
    assert "warmup" in content
    assert "main" in content
    assert "cooldown" in content
    
    # Main block should have cardio movements (1-3)
    main_exercises = content.get("main", [])
    assert 1 <= len(main_exercises) <= 3, "Cardio sessions should have 1-3 movements"
    
    # Verify duration
    from app.services.time_estimation import TimeEstimationService
    time_service = TimeEstimationService()
    
    estimated_duration = time_service.estimate_session_time_with_transitions(
        warmup=content.get("warmup", []),
        main=content.get("main", []),
        cooldown=content.get("cooldown", []),
        intent="endurance",
    )
    
    assert estimated_duration.total_minutes > 0


@pytest.mark.asyncio
async def test_session_generator_mobility_template(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test mobility template generation."""
    service = SessionGeneratorService()
    
    # Create a program
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.MOBILITY, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.STRENGTH, weight=2),
        ],
        duration_weeks=8,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=30,  # 30 minute sessions
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )
    
    from app.services.program import program_service
    program = await program_service.create_program(async_db_session, test_user.id, request)
    
    # Get a session and set it to mobility type with mobility intent
    result = await async_db_session.execute(
        select(Microcycle).where(Microcycle.program_id == program.id)
    )
    microcycles = list(result.scalars().all())
    active_mc = microcycles[0]
    
    result = await async_db_session.execute(
        select(Session).where(Session.microcycle_id == active_mc.id)
    )
    sessions = list(result.scalars().all())
    session = sessions[0]
    session.session_type = SessionType.MOBILITY
    session.intent_tags = ["mobility"]
    
    # Generate content
    content = await service.generate_session_exercises(
        async_db_session,
        session,
        program,
        active_mc,
        [],  # used_movements
        {},  # used_movement_groups
        None,  # used_accessory_movements
        None,  # fatigued_muscles
    )
    
    # Verify mobility template structure
    assert content is not None
    
    # Main block should have mobility movements (8-12)
    main_exercises = content.get("main", [])
    assert 8 <= len(main_exercises) <= 12, "Mobility sessions should have 8-12 movements"
