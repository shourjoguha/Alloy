"""Test session duration validation across different max_session_duration values.

These tests verify that sessions respect the user's max_session_duration setting
within the 5% tolerance rule.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.session_generator import SessionGeneratorService
from app.services.program import program_service
from app.models.program import Session, Program, Microcycle
from app.models.enums import Goal, SplitTemplate, ProgressionStyle
from app.schemas.program import ProgramCreate, GoalWeight
from app.services.time_estimation import TimeEstimationService


@pytest.mark.asyncio
async def test_30_min_program_generates_valid_duration(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test that 30 min program generates 28-32 min sessions (±5%)."""
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.ENDURANCE, weight=2),
        ],
        duration_weeks=8,
        program_start_date=None,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=30,
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )

    program = await program_service.create_program(async_db_session, test_user.id, request)
    await program_service.generate_active_microcycle_sessions(program.id)

    result = await async_db_session.execute(
        select(Session).where(Session.program_id == program.id)
    )
    sessions = list(result.scalars().all())

    time_service = TimeEstimationService()
    target_duration = 30
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05

    for session in sessions:
        if session.session_type.value == "recovery":
            continue

        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=session.warmup_json or [],
            main=session.main_json or [],
            accessory=session.accessory_json,
            circuit=session.circuit_json,
            finisher=session.finisher_json,
            cooldown=session.cooldown_json or [],
            intent="strength",
        )
        actual_duration = estimated_duration.total_minutes

        assert buffer_min <= actual_duration <= buffer_max, (
            f"Session {session.id} duration {actual_duration:.1f}min "
            f"outside 5% tolerance for {target_duration}min target "
            f"(range: {buffer_min:.1f}-{buffer_max:.1f}min)"
        )


@pytest.mark.asyncio
async def test_45_min_program_generates_valid_duration(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test that 45 min program generates 42-48 min sessions (±5%)."""
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.ENDURANCE, weight=2),
        ],
        duration_weeks=8,
        program_start_date=None,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=45,
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )

    program = await program_service.create_program(async_db_session, test_user.id, request)
    await program_service.generate_active_microcycle_sessions(program.id)

    result = await async_db_session.execute(
        select(Session).where(Session.program_id == program.id)
    )
    sessions = list(result.scalars().all())

    time_service = TimeEstimationService()
    target_duration = 45
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05

    for session in sessions:
        if session.session_type.value == "recovery":
            continue

        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=session.warmup_json or [],
            main=session.main_json or [],
            accessory=session.accessory_json,
            circuit=session.circuit_json,
            finisher=session.finisher_json,
            cooldown=session.cooldown_json or [],
            intent="strength",
        )
        actual_duration = estimated_duration.total_minutes

        assert buffer_min <= actual_duration <= buffer_max, (
            f"Session {session.id} duration {actual_duration:.1f}min "
            f"outside 5% tolerance for {target_duration}min target "
            f"(range: {buffer_min:.1f}-{buffer_max:.1f}min)"
        )


@pytest.mark.asyncio
async def test_90_min_program_generates_valid_duration(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test that 90 min program generates 85-95 min sessions (±5%)."""
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.ENDURANCE, weight=2),
        ],
        duration_weeks=8,
        program_start_date=None,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=90,
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )

    program = await program_service.create_program(async_db_session, test_user.id, request)
    await program_service.generate_active_microcycle_sessions(program.id)

    result = await async_db_session.execute(
        select(Session).where(Session.program_id == program.id)
    )
    sessions = list(result.scalars().all())

    time_service = TimeEstimationService()
    target_duration = 90
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05

    for session in sessions:
        if session.session_type.value == "recovery":
            continue

        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=session.warmup_json or [],
            main=session.main_json or [],
            accessory=session.accessory_json,
            circuit=session.circuit_json,
            finisher=session.finisher_json,
            cooldown=session.cooldown_json or [],
            intent="strength",
        )
        actual_duration = estimated_duration.total_minutes

        assert buffer_min <= actual_duration <= buffer_max, (
            f"Session {session.id} duration {actual_duration:.1f}min "
            f"outside 5% tolerance for {target_duration}min target "
            f"(range: {buffer_min:.1f}-{buffer_max:.1f}min)"
        )


@pytest.mark.asyncio
async def test_120_min_program_generates_valid_duration(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test that 120 min program generates 114-126 min sessions (±5%)."""
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.HYPERTROPHY, weight=3),
            GoalWeight(goal=Goal.ENDURANCE, weight=2),
        ],
        duration_weeks=8,
        program_start_date=None,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=120,
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )

    program = await program_service.create_program(async_db_session, test_user.id, request)
    await program_service.generate_active_microcycle_sessions(program.id)

    result = await async_db_session.execute(
        select(Session).where(Session.program_id == program.id)
    )
    sessions = list(result.scalars().all())

    time_service = TimeEstimationService()
    target_duration = 120
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05

    for session in sessions:
        if session.session_type.value == "recovery":
            continue

        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=session.warmup_json or [],
            main=session.main_json or [],
            accessory=session.accessory_json,
            circuit=session.circuit_json,
            finisher=session.finisher_json,
            cooldown=session.cooldown_json or [],
            intent="strength",
        )
        actual_duration = estimated_duration.total_minutes

        assert buffer_min <= actual_duration <= buffer_max, (
            f"Session {session.id} duration {actual_duration:.1f}min "
            f"outside 5% tolerance for {target_duration}min target "
            f"(range: {buffer_min:.1f}-{buffer_max:.1f}min)"
        )


@pytest.mark.asyncio
async def test_conditioning_session_respects_max_duration(
    async_db_session: AsyncSession,
    test_user,
    test_movements,
):
    """Test that conditioning sessions scale to fit max_session_duration."""
    service = SessionGeneratorService()

    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.ENDURANCE, weight=7),
            GoalWeight(goal=Goal.FAT_LOSS, weight=3),
        ],
        duration_weeks=8,
        program_start_date=None,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=3,
        max_session_duration=60,
        progression_style="double_progression",
        deload_every_n_microcycles=4,
    )

    program = await program_service.create_program(async_db_session, test_user.id, request)

    result = await async_db_session.execute(
        select(Session).where(Session.program_id == program.id)
    )
    sessions = list(result.scalars().all())

    conditioning_session = next(
        (s for s in sessions if s.session_type.value == "conditioning"), None
    )
    assert conditioning_session is not None, "Should have at least one conditioning session"

    time_service = TimeEstimationService()
    estimated_duration = time_service.estimate_session_time_with_transitions(
        warmup=conditioning_session.warmup_json or [],
        main=conditioning_session.main_json or [],
        accessory=conditioning_session.accessory_json,
        circuit=conditioning_session.circuit_json,
        finisher=conditioning_session.finisher_json,
        cooldown=conditioning_session.cooldown_json or [],
        intent="conditioning",
    )
    actual_duration = estimated_duration.total_minutes

    target_duration = 60
    buffer_min = target_duration * 0.95
    buffer_max = target_duration * 1.05

    assert buffer_min <= actual_duration <= buffer_max, (
        f"Conditioning session duration {actual_duration:.1f}min "
        f"outside 5% tolerance for {target_duration}min target "
        f"(range: {buffer_min:.1f}-{buffer_max:.1f}min)"
    )
