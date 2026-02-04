"""
Pytest configuration and shared fixtures for service tests.

Provides:
- In-memory SQLite database for testing
- Async session management
- Sample data fixtures (users, goals, movements, etc.)
"""

import pytest
import pytest_asyncio
from datetime import date, datetime, timedelta
from sqlalchemy import create_engine, TypeDecorator, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TEXT

from app.db.database import Base
from app.models.user import User, UserMovementRule, UserEnjoyableActivity, UserSettings
from app.models.program import Program, Microcycle, Session
from app.models.movement import Movement
from app.models.logging import WorkoutLog, TopSetLog, SorenessLog, RecoverySignal, PatternExposure
from app.models.circuit import CircuitTemplate
from app.models.circuit_extended import CircuitMacro, CircuitMelted
from app.models.enums import (
    ExperienceLevel, PersonaTone, PersonaAggression, Goal, SplitTemplate as SplitTemplateEnum,
    ProgressionStyle, SessionType, MovementRuleType, RuleCadence, EnjoyableActivity,
    MovementPattern, PrimaryMuscle, E1RMFormula, RecoverySource, MicrocycleStatus, PrimaryRegion, SkillLevel, CNSLoad
)


# SQLite doesn't support JSONB, so we use a custom type that stores as JSON for SQLite
class SQLiteJSONB(TypeDecorator):
    """Platform-independent JSONB type.
    
    Uses JSONB for PostgreSQL, falls back to JSON for other databases.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def async_db_session():
    """
    Create an in-memory SQLite database session for testing.
    Tables are created before each test and dropped after.
    """
    # Use in-memory SQLite with async support
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        echo=False,
    )
    
    # Replace JSONB with JSON for SQLite (since SQLite doesn't support JSONB)
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, PGJSONB):
                column.type = SQLiteJSONB()
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(async_db_session: AsyncSession) -> User:
    """Create a test user with default settings."""
    user = User(
        name="Test User",
        email="test@example.com",
        experience_level=ExperienceLevel.INTERMEDIATE,
        persona_tone=PersonaTone.SUPPORTIVE,
        persona_aggression=PersonaAggression.BALANCED,
    )
    async_db_session.add(user)
    await async_db_session.flush()
    
    # Create default settings
    settings = UserSettings(
        user_id=user.id,
        active_e1rm_formula=E1RMFormula.EPLEY,
        use_metric=True,
    )
    async_db_session.add(settings)
    await async_db_session.commit()
    
    return user


@pytest_asyncio.fixture
async def test_goals(async_db_session: AsyncSession) -> dict:
    """Return a dict of test goals (not stored, just references)."""
    return {
        "strength": Goal.STRENGTH,
        "hypertrophy": Goal.HYPERTROPHY,
        "endurance": Goal.ENDURANCE,
        "fat_loss": Goal.FAT_LOSS,
    }


@pytest_asyncio.fixture
async def test_movements(async_db_session: AsyncSession) -> list:
    """Create test movements."""
    movements = [
        Movement(
            name="Barbell Squat",
            pattern=MovementPattern.SQUAT.value,
            primary_muscle=PrimaryMuscle.QUADRICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_LOWER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Barbell Bench Press",
            pattern=MovementPattern.HORIZONTAL_PUSH.value,
            primary_muscle=PrimaryMuscle.CHEST.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Barbell Deadlift",
            pattern=MovementPattern.HINGE.value,
            primary_muscle=PrimaryMuscle.HAMSTRINGS.value,
            primary_region=PrimaryRegion.POSTERIOR_LOWER.value,
            skill_level=SkillLevel.ADVANCED.value,
            cns_load=CNSLoad.HIGH.value,
            compound=True,
        ),
        Movement(
            name="Barbell Rows",
            pattern=MovementPattern.HORIZONTAL_PULL.value,
            primary_muscle=PrimaryMuscle.LATS.value,
            primary_region=PrimaryRegion.POSTERIOR_UPPER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Dumbbell Curl",
            pattern=MovementPattern.ISOLATION.value,
            primary_muscle=PrimaryMuscle.BICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=False,
        ),
    ]
    async_db_session.add_all(movements)
    await async_db_session.commit()
    return movements


@pytest_asyncio.fixture
async def test_program(
    async_db_session: AsyncSession,
    test_user: User,
) -> Program:
    """Create a test program."""
    program = Program(
        user_id=test_user.id,
        split_template=SplitTemplateEnum.UPPER_LOWER,
        start_date=date.today(),
        duration_weeks=8,
        goal_1=Goal.STRENGTH,
        goal_2=Goal.HYPERTROPHY,
        goal_3=Goal.ENDURANCE,
        goal_weight_1=5,
        goal_weight_2=3,
        goal_weight_3=2,
        days_per_week=4,
        progression_style=ProgressionStyle.DOUBLE_PROGRESSION,
        deload_every_n_microcycles=4,
        persona_tone=PersonaTone.SUPPORTIVE,
        persona_aggression=PersonaAggression.BALANCED,
        is_active=True,
    )
    async_db_session.add(program)
    await async_db_session.commit()
    return program


@pytest_asyncio.fixture
async def test_microcycle(
    async_db_session: AsyncSession,
    test_program: Program,
) -> Microcycle:
    """Create a test microcycle."""
    microcycle = Microcycle(
        program_id=test_program.id,
        sequence_number=1,
        start_date=date.today(),
        length_days=7,
        status=MicrocycleStatus.PLANNED,
        is_deload=False,
    )
    async_db_session.add(microcycle)
    await async_db_session.commit()
    return microcycle


@pytest_asyncio.fixture
async def test_session(
    async_db_session: AsyncSession,
    test_microcycle: Microcycle,
    test_user: User,
) -> Session:
    """Create a test session."""
    session = Session(
        microcycle_id=test_microcycle.id,
        date=date.today(),
        day_number=1,
        session_type=SessionType.UPPER,
        intent_tags=[],
        warmup_json=[{"name": "Arm Circles", "sets": 2, "reps": 15}],
        main_json=[{"name": "Bench Press", "sets": 3, "reps": 8}],
        cooldown_json=[{"name": "Chest Stretch", "duration_seconds": 60}],
    )
    async_db_session.add(session)
    await async_db_session.commit()
    return session


@pytest_asyncio.fixture
async def test_workout_log(
    async_db_session: AsyncSession,
    test_user: User,
    test_session: Session,
) -> WorkoutLog:
    """Create a test workout log."""
    log = WorkoutLog(
        user_id=test_user.id,
        session_id=test_session.id,
        date=date.today(),
        completed=True,
        perceived_difficulty=6,
        actual_duration_minutes=45,
    )
    async_db_session.add(log)
    await async_db_session.commit()
    return log


@pytest_asyncio.fixture
async def test_recovery_signal(
    async_db_session: AsyncSession,
    test_user: User,
) -> RecoverySignal:
    """Create a test recovery signal."""
    signal = RecoverySignal(
        user_id=test_user.id,
        date=date.today(),
        source=RecoverySource.MANUAL,
        sleep_score=85.0,
        sleep_hours=8.0,
        readiness=75.0,
        hrv=50.0,
    )
    async_db_session.add(signal)
    await async_db_session.commit()
    return signal


@pytest_asyncio.fixture
async def test_soreness_log(
    async_db_session: AsyncSession,
    test_user: User,
) -> SorenessLog:
    """Create a test soreness log."""
    log = SorenessLog(
        user_id=test_user.id,
        date=date.today(),
        body_part="quadriceps",
        soreness_1_5=3,
        notes="DOMS from squats",
    )
    async_db_session.add(log)
    await async_db_session.commit()
    return log
