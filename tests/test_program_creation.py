"""Test program creation with user preferences."""
import pytest
import pytest_asyncio
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User, UserSettings, UserProfile, Movement, Session, SessionExercise
from app.models.enums import Goal, SplitTemplate, ProgressionStyle, SkillLevel, PrimaryRegion, PrimaryMuscle, MovementPattern, CNSLoad
from app.schemas.program import ProgramCreate, GoalWeight, DisciplineWeight
from app.services.program import program_service


@pytest_asyncio.fixture
async def test_user_with_profile(async_db_session: AsyncSession) -> User:
    """Create a test user with profile and settings."""
    user = User(
        name="Test User",
        email="test@example.com",
    )
    async_db_session.add(user)
    await async_db_session.flush()
    
    # Create user profile
    profile = UserProfile(
        user_id=user.id,
    )
    async_db_session.add(profile)
    
    # Create user settings
    settings = UserSettings(
        user_id=user.id,
    )
    async_db_session.add(settings)
    
    await async_db_session.commit()
    return user


@pytest_asyncio.fixture
async def test_crossfit_movements(async_db_session: AsyncSession) -> list[Movement]:
    """Create test movements for CrossFit and powerlifting."""
    movements = [
        Movement(
            name="Back Squat",
            pattern=MovementPattern.SQUAT.value,
            primary_muscle=PrimaryMuscle.QUADRICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_LOWER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Deadlift",
            pattern=MovementPattern.HINGE.value,
            primary_muscle=PrimaryMuscle.HAMSTRINGS.value,
            primary_region=PrimaryRegion.POSTERIOR_LOWER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.HIGH.value,
            compound=True,
        ),
        Movement(
            name="Bench Press",
            pattern=MovementPattern.HORIZONTAL_PUSH.value,
            primary_muscle=PrimaryMuscle.CHEST.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Pull-up",
            pattern=MovementPattern.VERTICAL_PULL.value,
            primary_muscle=PrimaryMuscle.LATS.value,
            primary_region=PrimaryRegion.POSTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Overhead Press",
            pattern=MovementPattern.VERTICAL_PUSH.value,
            primary_muscle=PrimaryMuscle.FRONT_DELTS.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Box Jump",
            pattern=MovementPattern.PLYOMETRIC.value,
            primary_muscle=PrimaryMuscle.QUADRICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_LOWER.value,
            skill_level=SkillLevel.INTERMEDIATE.value,
            cns_load=CNSLoad.HIGH.value,
            compound=True,
        ),
        Movement(
            name="Kettlebell Swing",
            pattern=MovementPattern.HINGE.value,
            primary_muscle=PrimaryMuscle.HAMSTRINGS.value,
            primary_region=PrimaryRegion.POSTERIOR_LOWER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.MODERATE.value,
            compound=True,
        ),
        Movement(
            name="Dumbbell Lunge",
            pattern=MovementPattern.LUNGE.value,
            primary_muscle=PrimaryMuscle.QUADRICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_LOWER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=True,
        ),
        Movement(
            name="Dumbbell Row",
            pattern=MovementPattern.HORIZONTAL_PULL.value,
            primary_muscle=PrimaryMuscle.LATS.value,
            primary_region=PrimaryRegion.POSTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=True,
        ),
        Movement(
            name="Push-up",
            pattern=MovementPattern.HORIZONTAL_PUSH.value,
            primary_muscle=PrimaryMuscle.CHEST.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=True,
        ),
        Movement(
            name="Light Cardio",
            pattern=MovementPattern.CARDIO.value,
            primary_muscle=PrimaryMuscle.QUADRICEPS.value,
            primary_region=PrimaryRegion.ANTERIOR_LOWER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=False,
        ),
        Movement(
            name="Arm Circles",
            pattern=MovementPattern.MOBILITY.value,
            primary_muscle=PrimaryMuscle.FRONT_DELTS.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=False,
        ),
        Movement(
            name="Chest Stretch",
            pattern=MovementPattern.STRETCH.value,
            primary_muscle=PrimaryMuscle.CHEST.value,
            primary_region=PrimaryRegion.ANTERIOR_UPPER.value,
            skill_level=SkillLevel.BEGINNER.value,
            cns_load=CNSLoad.LOW.value,
            compound=False,
        ),
    ]
    async_db_session.add_all(movements)
    await async_db_session.commit()
    return movements


@pytest.mark.asyncio
async def test_program_creation(
    async_db_session: AsyncSession,
    test_user_with_profile: User,
    test_crossfit_movements: list[Movement],
):
    """Test creating a program with 4 days and CrossFit."""
    print("\n=== Testing Program Creation ===")
    
    # Create program request with all preferences
    request = ProgramCreate(
        goals=[
            GoalWeight(goal=Goal.STRENGTH, weight=5),
            GoalWeight(goal=Goal.EXPLOSIVENESS, weight=3),
            GoalWeight(goal=Goal.SPEED, weight=2),
        ],
        duration_weeks=12,
        split_template=SplitTemplate.FULL_BODY,
        days_per_week=4,
        progression_style=ProgressionStyle.DOUBLE_PROGRESSION,
        disciplines=[
            DisciplineWeight(discipline="crossfit", weight=5),
            DisciplineWeight(discipline="powerlifting", weight=5),
        ],
    )
    
    print(f"Creating program with:")
    print(f"  - Goals: {[f'{g.goal.value}({g.weight})' for g in request.goals]}")
    print(f"  - Days per week: {request.days_per_week}")
    print(f"  - Disciplines: {[(d.discipline, d.weight) for d in request.disciplines]}")
    print(f"  - Split: {request.split_template.value}")
    
    # Create program
    user_id = test_user_with_profile.id
    program = await program_service.create_program(async_db_session, user_id, request)
    
    print(f"\n✓ Program created successfully!")
    print(f"  - Program ID: {program.id}")
    print(f"  - Days per week (stored): {program.days_per_week}")
    
    # Note: Session content generation happens via background task in production
    # For testing, we verify the program structure is correct
    
    # Check microcycles and sessions
    await async_db_session.refresh(program, ["microcycles", "program_disciplines"])
    if program.program_disciplines:
        print(f"  - Disciplines (stored): {[(pd.discipline_type, pd.weight) for pd in program.program_disciplines]}")
    
    if program.microcycles:
        active_mc = next((mc for mc in program.microcycles if mc.status.value == "active"), None)
        if active_mc:
            await async_db_session.refresh(active_mc, ["sessions"])
            print(f"  - Active microcycle: {active_mc.id} with {len(active_mc.sessions)} sessions")
            
            training_sessions = [s for s in active_mc.sessions if s.session_type.value != "recovery"]
            print(f"  - Training sessions: {len(training_sessions)}")
            
            # Verify session structure (sessions are empty shells - content generated via background task)
            print(f"\n=== Session Structure (Content Generated via Background Task) ===")
            for session in training_sessions[:3]:  # Check first 3 sessions
                print(f"  Session Day {session.day_number} ({session.session_type.value}):")
                print(f"    ID: {session.id}")
                print(f"    Has circuits: {session.has_circuits}")
                print(f"    Estimated duration: {session.estimated_duration_minutes} min")
            
            # Summary
            print(f"\n=== Summary ===")
            print(f"Total microcycles: {len(program.microcycles)}")
            print(f"Total sessions in active microcycle: {len(active_mc.sessions)}")
            print(f"Training sessions: {len(training_sessions)}")
            print(f"Recovery sessions: {len(active_mc.sessions) - len(training_sessions)}")
            
            # Assertions - verify program structure is correct
            assert len(program.microcycles) >= 1, "Program should have at least one microcycle"
            assert active_mc is not None, "Program should have an active microcycle"
            assert len(training_sessions) >= 4, f"Program should have at least 4 training sessions (requested {request.days_per_week} days/week)"
            
            print(f"\n✓ All program structure checks passed!")
        else:
            print("\n✗ No active microcycle found!")
            pytest.fail("No active microcycle found after program creation")
    else:
        print("\n✗ No microcycles found!")
        pytest.fail("No microcycles found after program creation")
