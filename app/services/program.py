"""
ProgramService - Generates workout programs with microcycle structure and goal distribution.

Responsible for:
- Creating 8-12 week programs from split template + goal mix
- Distributing goals across microcycles with weighting
- Generating microcycles with appropriate intensity profiles
- Creating session templates with optional sections (warmup, finisher, conditioning)
- Applying movement rule constraints and interference logic
"""

from datetime import timedelta, date
from typing import Optional, Dict, Any
import logging
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Program,
    Microcycle,
    Session,
    User,
    Movement,
    UserProfile,
    UserMovementRule,
    ProgramDiscipline,
    MovementDiscipline,
)
from app.schemas.program import ProgramCreate
from app.models.enums import (
    Goal,
    SplitTemplate,
    SessionType,
    MicrocycleStatus,
    PersonaTone,
    PersonaAggression,
    ProgressionStyle,
    MovementRuleType,
    ExerciseRole,
    MovementPattern,
    DisciplineType,
)
from app.services.interference import interference_service
from app.services.session_generator import session_generator
from app.services.time_estimation import get_default_session_duration
from app.config import activity_distribution as activity_distribution_config
from app.services.allocation_integration import AllocationIntegrationService


logger = logging.getLogger(__name__)


class ProgramService:
    """
    Generates and manages workout programs.

    A Program spans 8-12 weeks and contains Microcycles (1-2 weeks each).
    Each Microcycle contains Sessions (workout days).

    Goals are distributed across microcycles with weighting to balance
    focus across the user's objectives.
    """

    async def create_program(
        self,
        db: AsyncSession,
        user_id: int,
        request: ProgramCreate,
    ) -> Program:
        """
        Create a new 8-12 week program.

        Args:
            db: Database session
            user_id: User ID
            request: Program creation request (goals, duration_weeks, split_template, progression_style)

        Returns:
            Created Program with microcycles and sessions

        Raises:
            ValueError: If split template not found, goals empty, week_count invalid, interference conflict detected
        """
        logger.info("ProgramService.create_program called for user_id=%s", user_id)
        logger.info("Request data: %s", request.model_dump())

        # Validate week count
        if not (8 <= request.duration_weeks <= 12):
            logger.error(
                "Invalid duration_weeks=%s (must be 8-12)", request.duration_weeks
            )
            raise ValueError("Program must be 8-12 weeks")
        if request.duration_weeks % 2 != 0:
            logger.error(
                "Invalid duration_weeks=%s (must be even)", request.duration_weeks
            )
            raise ValueError("Program must be an even number of weeks")

        # Extract goals from request (1-3 goals allowed)
        goals = request.goals  # List of GoalWeight objects
        logger.info("Processing %d goals from request", len(goals))
        if not (1 <= len(goals) <= 3):
            logger.error("Invalid number of goals=%s (must be 1-3)", len(goals))
            raise ValueError("1-3 goals required")

        # Pad goals list to 3 items if needed (with dummy goal of 0 weight)
        while len(goals) < 3:
            # Find a goal not in use
            used_goals = {g.goal for g in goals}
            unused_goal = next(g for g in Goal if g not in used_goals)
            goals.append(type(goals[0])(goal=unused_goal, weight=0))
        logger.info(
            "Goals processed successfully: %s", [(g.goal, g.weight) for g in goals]
        )

        # Check for goal interference (only for goals with weight > 0)
        active_goals = [g.goal for g in goals if g.weight > 0]
        if len(active_goals) >= 2:
            logger.info(
                "Validating %d active goals for interference", len(active_goals)
            )
            # Pad active_goals to 3 for validation if needed
            validation_goals = active_goals[:]
            while len(validation_goals) < 3:
                validation_goals.append(
                    active_goals[0]
                )  # Duplicate first goal for validation

            is_valid, warnings = await interference_service.validate_goals(
                db, validation_goals[0], validation_goals[1], validation_goals[2]
            )
            if not is_valid:
                logger.error("Goal validation failed: %s", warnings)
                raise ValueError(f"Goal validation failed: {warnings}")

        # Fetch user profile for advanced preferences
        logger.info("Fetching user profile for user_id=%s", user_id)
        user_profile = await db.get(UserProfile, user_id)
        discipline_prefs = user_profile.discipline_preferences if user_profile else None
        scheduling_prefs = (
            dict(user_profile.scheduling_preferences)
            if user_profile and user_profile.scheduling_preferences
            else {}
        )
        scheduling_prefs["avoid_cardio_days"] = await self._infer_avoid_cardio_days(
            db, user_id
        )
        logger.info("User profile fetched successfully")

        split_template = request.split_template
        if not split_template:
            preference = scheduling_prefs.get("split_template_preference")
            if (
                isinstance(preference, str)
                and preference.strip()
                and preference.strip().lower() != "none"
            ):
                try:
                    split_template = SplitTemplate[preference.strip().upper()]
                except KeyError:
                    split_template = None
        if not split_template:
            split_template = SplitTemplate.HYBRID
        logger.info("Using split_template=%s", split_template)

        preferred_cycle_length_days = self._resolve_preferred_microcycle_length_days(
            scheduling_prefs
        )
        logger.info("Preferred microcycle length=%s days", preferred_cycle_length_days)

        # Get user for defaults
        user = await db.get(User, user_id)
        logger.info(
            "User fetched for user_id=%s, experience_level=%s",
            user_id,
            user.experience_level if user else "unknown",
        )

        # Determine progression style if not provided
        progression_style = request.progression_style
        if not progression_style:
            # Default based on experience level
            if user and user.experience_level == "beginner":
                progression_style = ProgressionStyle.SINGLE_PROGRESSION
            elif user and user.experience_level in ["advanced", "expert"]:
                progression_style = ProgressionStyle.WAVE_LOADING
            else:
                # Intermediate defaults to Double Progression
                progression_style = ProgressionStyle.DOUBLE_PROGRESSION
        logger.info("Using progression_style=%s", progression_style)

        # Determine persona settings (from request or user defaults)
        persona_tone = request.persona_tone or (
            user.persona_tone if user else PersonaTone.SUPPORTIVE
        )
        persona_aggression = request.persona_aggression or (
            user.persona_aggression if user else PersonaAggression.BALANCED
        )
        logger.info(
            "Persona settings: tone=%s, aggression=%s", persona_tone, persona_aggression
        )

        # If user changed persona settings during program creation, update their profile
        if user:
            if request.persona_tone:
                user.persona_tone = request.persona_tone
            if request.persona_aggression:
                user.persona_aggression = request.persona_aggression

        # Create program
        start_date = request.program_start_date or date.today()

        program = Program(
            user_id=user_id,
            name=request.name,
            split_template=split_template,
            days_per_week=request.days_per_week,
            max_session_duration=request.max_session_duration,
            start_date=start_date,
            duration_weeks=request.duration_weeks,
            goal_1=goals[0].goal,
            goal_2=goals[1].goal,
            goal_3=goals[2].goal,
            goal_weight_1=goals[0].weight,
            goal_weight_2=goals[1].weight,
            goal_weight_3=goals[2].weight,
            progression_style=progression_style,
            deload_every_n_microcycles=request.deload_every_n_microcycles or 4,
            persona_tone=persona_tone,
            persona_aggression=persona_aggression,
            is_active=True,
        )

        # Deactivate other active programs for this user
        logger.info("Deactivating other active programs for user_id=%s", user_id)
        other_active = await db.execute(
            select(Program).where(
                and_(Program.user_id == user_id, Program.is_active.is_(True))
            )
        )
        for prog in other_active.scalars():
            prog.is_active = False

        db.add(program)
        await db.flush()  # Get program.id
        logger.info(
            "Program created with id=%s, flushing to get program.id", program.id
        )

        # Create program disciplines from request or defaults
        logger.info("Creating program disciplines for program_id=%s", program.id)
        if request.disciplines:
            logger.info("Using %d disciplines from request", len(request.disciplines))
            for discipline_data in request.disciplines:
                program_discipline = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type=discipline_data.discipline,
                    weight=discipline_data.weight,
                )
                db.add(program_discipline)
        elif discipline_prefs:
            logger.info("Using %d discipline preferences", len(discipline_prefs))
            for discipline_type, weight in discipline_prefs.items():
                program_discipline = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type=discipline_type,
                    weight=weight,
                )
                db.add(program_discipline)
        else:
            # Fallback based on experience level
            logger.info(
                "Using fallback disciplines based on experience level=%s",
                user.experience_level if user else "unknown",
            )
            default_discipline = "bodybuilding"
            default_weight = 10
            if user and user.experience_level == "beginner":
                program_discipline = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type=default_discipline,
                    weight=default_weight,
                )
                db.add(program_discipline)
            elif user and user.experience_level == "intermediate":
                program_discipline1 = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type="bodybuilding",
                    weight=6,
                )
                program_discipline2 = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type="powerlifting",
                    weight=4,
                )
                db.add(program_discipline1)
                db.add(program_discipline2)
            else:
                program_discipline1 = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type="bodybuilding",
                    weight=5,
                )
                program_discipline2 = ProgramDiscipline(
                    program_id=program.id,
                    discipline_type="powerlifting",
                    weight=5,
                )
                db.add(program_discipline1)
                db.add(program_discipline2)

        total_days = request.duration_weeks * 7
        microcycle_lengths = self._partition_microcycle_lengths(
            total_days, preferred_cycle_length_days
        )
        logger.info("Microcycle lengths: %s", microcycle_lengths)

        # Generate microcycles with sessions
        current_date = start_date
        deload_frequency = request.deload_every_n_microcycles or 4

        for mc_idx, cycle_length_days in enumerate(microcycle_lengths):
            logger.info(
                "Creating microcycle %d with length=%s days", mc_idx, cycle_length_days
            )
            is_deload = (mc_idx + 1) % deload_frequency == 0
            logger.info("Microcycle %d is_deload=%s", mc_idx, is_deload)

            split_config = self._build_freeform_split_config(
                cycle_length_days=cycle_length_days,
                days_per_week=request.days_per_week,
            )
            logger.info("Built freeform split config for microcycle %d", mc_idx)

            split_config = self._apply_goal_based_cycle_distribution(
                split_config=split_config,
                goals=request.goals,
                days_per_week=request.days_per_week,
                cycle_length_days=cycle_length_days,
                max_session_duration=request.max_session_duration,
                user_experience_level=user.experience_level if user else None,
                scheduling_prefs=scheduling_prefs,
            )
            logger.info(
                "Applied goal-based cycle distribution for microcycle %d", mc_idx
            )

            split_config = self._assign_freeform_day_types_and_focus(
                split_config=split_config,
                days_per_week=request.days_per_week,
            )
            logger.info(
                "Assigned freeform day types and focus for microcycle %d", mc_idx
            )

            # Log the structure that will be used to create sessions
            structure = split_config.get("structure", [])
            logger.info(
                f"[create_program] Microcycle {mc_idx} split_config structure length: {len(structure)}"
            )
            for idx, day_def in enumerate(structure):
                logger.info(
                    f"[create_program] Microcycle {mc_idx} day {idx}: {day_def}"
                )

            microcycle = await self._create_microcycle(
                db,
                user_id=program.user_id,
                program_id=program.id,
                mc_index=mc_idx,
                start_date=current_date,
                split_config=split_config,
                is_deload=is_deload,
            )
            logger.info("Microcycle %d created with id=%s", mc_idx, microcycle.id)

            current_date += timedelta(days=cycle_length_days)

        logger.info("Committing program creation transaction")
        logger.info(
            "[COMMIT] About to commit - this will make ALL sessions visible to background tasks"
        )
        await db.commit()
        logger.info("Program creation committed successfully")
        logger.info(
            "[COMMIT] Transaction committed - all sessions should now be visible in database"
        )
        await db.refresh(program)
        logger.info(
            "Program refreshed successfully, returning program id=%s", program.id
        )
        logger.info(
            "Program data for serialization: id=%s, start_date=%s, persona_aggression=%s, persona_tone=%s",
            program.id,
            program.start_date,
            program.persona_aggression,
            program.persona_tone,
        )
        return program

    async def _infer_avoid_cardio_days(self, db: AsyncSession, user_id: int) -> bool:
        try:
            result = await db.execute(
                select(UserMovementRule.id)
                .join(Movement, Movement.id == UserMovementRule.movement_id)
                .outerjoin(MovementDiscipline, MovementDiscipline.movement_id == Movement.id)
                .where(
                    and_(
                        UserMovementRule.user_id == user_id,
                        UserMovementRule.rule_type == MovementRuleType.HARD_NO,
                        or_(
                            Movement.pattern.in_([MovementPattern.CARDIO, MovementPattern.CONDITIONING]),
                            MovementDiscipline.discipline == DisciplineType.RUNNING,
                        ),
                    )
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(
                "[_infer_avoid_cardio_days] ERROR - Database query failed",
                extra={
                    "input_state": {
                        "user_id": user_id,
                    },
                    "failure_context": {
                        "what_failed": "Cardio days inference database query",
                        "why_failed": f"{type(e).__name__}: {str(e)}",
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                },
                exc_info=True,
            )
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(
                    "[_infer_avoid_cardio_days] ERROR - Rollback failed",
                    extra={
                        "failure_context": {
                            "what_failed": "Database rollback",
                            "why_failed": f"{type(rollback_error).__name__}: {str(rollback_error)}",
                            "exception_type": type(rollback_error).__name__,
                            "exception_message": str(rollback_error),
                        },
                    },
                    exc_info=True,
                )
            return False

    async def generate_active_microcycle_sessions(
        self,
        program_id: int,
    ) -> None:
        from app.db.database import async_session_maker

        logger.info(
            f"[generate_active_microcycle_sessions] START - program_id={program_id}"
        )
        logger.info(
            "[generate_active_microcycle_sessions] BACKGROUND TASK STARTED - creating new DB session"
        )

        microcycle_id = None

        async with async_session_maker() as db:
            program = await db.get(Program, program_id)
            if not program:
                logger.error(
                    f"[generate_active_microcycle_sessions] Program not found: {program_id}"
                )
                return

            result = await db.execute(
                select(Microcycle).where(
                    Microcycle.program_id == program_id,
                    Microcycle.status == MicrocycleStatus.ACTIVE,
                )
            )
            microcycle = result.scalar_one_or_none()
            if not microcycle:
                logger.error(
                    f"[generate_active_microcycle_sessions] Active microcycle not found for program {program_id}"
                )
                return

            microcycle_id = microcycle.id

        if microcycle_id is None:
            logger.error(
                f"[generate_active_microcycle_sessions] Failed to extract microcycle_id for program {program_id}"
            )
            return

        try:
            logger.info(
                f"[generate_active_microcycle_sessions] Found active microcycle {microcycle_id}, starting generation..."
            )
            await self._generate_session_content_async(program_id, microcycle_id)
            logger.info(
                f"[generate_active_microcycle_sessions] COMPLETED for program {program_id}"
            )
        except Exception as e:
            logger.exception(
                f"[generate_active_microcycle_sessions] FAILED for program {program_id}: {e}"
            )
            raise

    async def _generate_session_content_async(
        self,
        program_id: int,
        microcycle_id: int,
    ) -> None:
        """
        Generate exercise content for all non-rest sessions in a microcycle.

        This method creates its own database sessions to avoid holding locks
        during long-running LLM calls.

        Args:
            program_id: ID of the program
            microcycle_id: ID of the microcycle to generate content for
        """
        from app.db.database import async_session_maker

        logger.info(
            f"[_generate_session_content_async] START - program_id={program_id}, microcycle_id={microcycle_id}"
        )

        try:
            # Create a new DB session for reading program and sessions
            async with async_session_maker() as db:
                # Fetch program and microcycle
                program = await db.get(Program, program_id)
                microcycle = await db.get(Microcycle, microcycle_id)

                if not program or not microcycle:
                    logger.error(
                        f"[_generate_session_content_async] FAILED - program={program}, microcycle={microcycle}"
                    )
                    return

                # Get all sessions for this microcycle
                logger.info(
                    f"[_generate_session_content_async] Querying sessions for microcycle_id={microcycle.id}"
                )
                sessions_result = await db.execute(
                    select(Session)
                    .where(Session.microcycle_id == microcycle.id)
                    .order_by(Session.day_number)
                )
                sessions = list(sessions_result.scalars().all())

                logger.info(
                    f"[_generate_session_content_async] Found {len(sessions)} sessions to generate"
                )
                for s in sessions:
                    logger.info(
                        f"[_generate_session_content_async] Session id={s.id}, day_number={s.day_number}, type={s.session_type.value}, date={s.date}"
                    )
        except Exception as e:
            logger.exception(
                f"[_generate_session_content_async] FAILED to fetch sessions: {e}"
            )
            return

        # Track used movements to ensure variety
        used_movements = set()
        used_movement_groups = {}  # Track usage count by substitution_group
        used_main_patterns = {}  # Track main lift patterns by day
        used_accessory_movements = {}  # Track accessory movements by day
        used_circuit_ids = set()  # Track used circuits to avoid repetition

        # Track previous day's muscle volume for interference logic
        previous_day_volume = {}

        # Generate content for each session independently
        for idx, session in enumerate(sessions):
            logger.info(
                f"[_generate_session_content_async] ===== LOOP ITERATION {idx+1}/{len(sessions)} ====="
            )
            logger.info(
                f"[_generate_session_content_async] Processing session {session.id} - type={session.session_type}, day={session.day_number}"
            )

            # Skip recovery/rest sessions - they get default content
            if session.session_type == SessionType.RECOVERY:
                logger.info(
                    f"[_generate_session_content_async] Skipping RECOVERY session {session.id}, day={session.day_number}"
                )
                previous_day_volume = {}  # Recovery clears fatigue
                logger.info(
                    f"[_generate_session_content_async] [{idx+1}/{len(sessions)}] Finished skipping session {session.id}, continuing to next"
                )
                continue

            try:
                # Apply inter-session interference rules for main lift patterns
                logger.info(
                    f"[_generate_session_content_async] [{idx+1}/{len(sessions)}] Applying interference rules for session {session.id}"
                )
                async with async_session_maker() as db:
                    session = await self._apply_pattern_interference_rules(
                        db, session, used_main_patterns, microcycle
                    )
            except Exception as e:
                logger.error(
                    "Failed to apply pattern interference rules for session %s: %s",
                    session.id,
                    e,
                )

            try:
                # Generate and populate session with exercises
                # Each call creates its own DB session
                logger.info(
                    f"[_generate_session_content_async] [{idx+1}/{len(sessions)}] Calling populate_session_by_id for session {session.id}"
                )
                (
                    current_volume,
                    content,
                ) = await session_generator.populate_session_by_id(
                    session.id,
                    program_id,
                    microcycle_id,
                    used_movements=list(used_movements),
                    used_movement_groups=dict(used_movement_groups),
                    used_main_patterns=dict(used_main_patterns),
                    used_accessory_movements=dict(used_accessory_movements),
                    previous_day_volume=previous_day_volume,
                    used_circuit_ids=list(used_circuit_ids),
                )
                logger.info(
                    f"[_generate_session_content_async] [{idx+1}/{len(sessions)}] populate_session_by_id completed for session {session.id}, volume={current_volume}"
                )
            except ValueError as ve:
                logger.error(
                    "[_generate_session_content_async] ERROR - Session generation failed with ValueError",
                    extra={
                        "input_state": {
                            "session_id": session.id,
                            "day_number": session.day_number,
                            "session_type": session.session_type.value,
                            "microcycle_id": microcycle.id,
                            "is_deload": microcycle.is_deload,
                        },
                        "failure_context": {
                            "what_failed": "Session generation",
                            "why_failed": f"{type(ve).__name__}: {str(ve)}",
                            "exception_type": type(ve).__name__,
                            "exception_message": str(ve),
                        },
                    },
                    exc_info=True,
                )
                # Apply fallback for ValueError (e.g., too many missing movements)
                try:
                    await self._apply_session_fallback(session.id, str(ve))
                except Exception as fallback_error:
                    logger.error(
                        "[_generate_session_content_async] CRITICAL ERROR - Fallback application failed",
                        extra={
                            "input_state": {
                                "session_id": session.id,
                                "original_error": str(ve),
                            },
                            "failure_context": {
                                "what_failed": "Session fallback application",
                                "why_failed": f"{type(fallback_error).__name__}: {str(fallback_error)}",
                                "exception_type": type(fallback_error).__name__,
                                "exception_message": str(fallback_error),
                            },
                        },
                        exc_info=True,
                    )
                current_volume = {}
                content = {}
            except Exception as e:
                logger.error(
                    "[_generate_session_content_async] ERROR - Session generation failed with Exception",
                    extra={
                        "input_state": {
                            "session_id": session.id,
                            "day_number": session.day_number,
                            "session_type": session.session_type.value,
                            "microcycle_id": microcycle.id,
                            "is_deload": microcycle.is_deload,
                        },
                        "failure_context": {
                            "what_failed": "Session generation",
                            "why_failed": f"{type(e).__name__}: {str(e)}",
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                    },
                    exc_info=True,
                )
                # Apply fallback for general exceptions
                try:
                    await self._apply_session_fallback(session.id, str(e))
                except Exception as fallback_error:
                    logger.error(
                        "[_generate_session_content_async] CRITICAL ERROR - Fallback application failed",
                        extra={
                            "input_state": {
                                "session_id": session.id,
                                "original_error": str(e),
                            },
                            "failure_context": {
                                "what_failed": "Session fallback application",
                                "why_failed": f"{type(fallback_error).__name__}: {str(fallback_error)}",
                                "exception_type": type(fallback_error).__name__,
                                "exception_message": str(fallback_error),
                            },
                        },
                        exc_info=True,
                    )
                current_volume = {}
                content = {}

            # Update previous volume for next iteration
            if current_volume is None:
                logger.warning(
                    f"[_generate_session_content_async] Session {session.id} returned None volume, using empty dict"
                )
                current_volume = {}
            previous_day_volume = current_volume
            logger.info(
                f"[_generate_session_content_async] Completed session {session.id}, volume={current_volume}"
            )

            # Track used movements and movement groups
            if current_volume and content:
                session_movements = []
                main_patterns_used = []
                accessory_movements_used = []

                # Track movements from content dict (no DB query needed)
                main_exercises = content.get("main", [])
                logger.debug(
                    f"[_generate_session_content_async] Tracking {len(main_exercises)} main exercises"
                )
                for ex in main_exercises:
                    if isinstance(ex, dict):
                        name = ex.get("movement") or ex.get("movement_name")
                        if name:
                            session_movements.append(name)
                            logger.debug(
                                f"[_generate_session_content_async] Tracking main movement: {name}"
                            )

                # Track from accessory and finisher sections
                accessory_exercises = content.get("accessory") or []
                logger.debug(
                    f"[_generate_session_content_async] Tracking {len(accessory_exercises)} accessory exercises"
                )
                for ex in accessory_exercises:
                    if isinstance(ex, dict):
                        name = ex.get("movement") or ex.get("movement_name")
                        if name:
                            session_movements.append(name)
                            accessory_movements_used.append(name)
                            logger.debug(
                                f"[_generate_session_content_async] Tracking accessory movement: {name}"
                            )

                # Track from finisher section
                finisher = content.get("finisher")
                if isinstance(finisher, dict):
                    # Track circuit usage
                    if finisher.get("circuit_id"):
                        circuit_id = finisher.get("circuit_id")
                        used_circuit_ids.add(circuit_id)
                        logger.debug(
                            f"[_generate_session_content_async] Tracking used circuit: {circuit_id}"
                        )
                    
                    finisher_exercises = finisher.get("exercises", [])
                    logger.debug(
                        f"[_generate_session_content_async] Tracking {len(finisher_exercises)} finisher exercises"
                    )
                    for ex in finisher_exercises:
                        if isinstance(ex, dict):
                            name = ex.get("movement") or ex.get("movement_name")
                            if name:
                                session_movements.append(name)
                                accessory_movements_used.append(name)
                                logger.debug(
                                    f"[_generate_session_content_async] Tracking finisher movement: {name}"
                                )

                # Update tracking sets
                for movement_name in session_movements:
                    used_movements.add(movement_name)

                # Track main lift patterns for this session
                if session.intent_tags:
                    main_patterns_used = session.intent_tags[:2]
                    used_main_patterns[session.day_number] = main_patterns_used

                # Track accessory movements for this session
                used_accessory_movements[session.day_number] = accessory_movements_used

                # Update movement group usage counts (needs DB)
                async with async_session_maker() as db:
                    await self._update_movement_group_usage(
                        db, session_movements, used_movement_groups
                    )

            logger.info(
                f"[_generate_session_content_async] ===== END OF ITERATION {idx+1}/{len(sessions)} ====="
            )

        logger.info(
            f"[_generate_session_content_async] Completed all {len(sessions)} sessions in microcycle"
        )
        logger.info(
            f"[_generate_session_content_async] Loop finished - used_movements count: {len(used_movements)}"
        )
        # Generate Jerome notes for all sessions in microcycle after content is complete
        logger.info(
            "[_generate_session_content_async] All sessions generated, starting batched Jerome notes generation"
        )
        try:
            await self._generate_microcycle_jerome_notes(program, microcycle, sessions)
        except Exception as e:
            logger.error(
                f"[_generate_session_content_async] Failed to generate Jerome notes: {e}"
            )

    async def _apply_session_fallback(self, session_id: int, error_msg: str) -> None:
        """
        Apply fallback placeholder for a failed session generation.

        Args:
            session_id: ID of the session that failed
            error_msg: Error message to store in coach_notes
        """
        from app.db.database import async_session_maker
        from app.models.movement import Movement
        from app.models.program import SessionExercise, ExerciseRole

        logger.info(
            f"[_apply_session_fallback] START - Applying fallback for session {session_id}, error: {error_msg}"
        )

        try:
            async with async_session_maker() as db:
                # Fetch the failed session with microcycle relationship
                failed_session = await db.execute(
                    select(Session)
                    .where(Session.id == session_id)
                    .options(selectinload(Session.microcycle))
                )
                failed_session = failed_session.scalar_one_or_none()

                if not failed_session:
                    logger.warning(
                        f"[_apply_session_fallback] Session {session_id} not found in database"
                    )
                    return

                logger.info(
                    f"[_apply_session_fallback] Session found - id={failed_session.id}, "
                    f"day_number={failed_session.day_number}, date={failed_session.date}, "
                    f"session_type={failed_session.session_type.value}, microcycle_id={failed_session.microcycle_id}"
                )

                # Check if microcycle exists
                if not failed_session.microcycle:
                    logger.error(
                        f"[_apply_session_fallback] Session {session_id} has no microcycle relationship loaded. "
                        f"microcycle_id={failed_session.microcycle_id}"
                    )
                    return

                failed_session.coach_notes = (
                    f"Generation failed: {error_msg}. Please regenerate."
                )

                # Access program through microcycle relationship (FIX: was accessing failed_session.program_id which doesn't exist)
                parent_program = await db.get(
                    Program, failed_session.microcycle.program_id
                )
                if not parent_program:
                    logger.error(
                        f"[_apply_session_fallback] Program not found for microcycle {failed_session.microcycle_id}. "
                        f"Using default session duration."
                    )
                    failed_session.estimated_duration_minutes = (
                        get_default_session_duration()
                    )
                else:
                    logger.info(
                        f"[_apply_session_fallback] Parent program found - id={parent_program.id}, "
                        f"max_session_duration={parent_program.max_session_duration}"
                    )
                    # Use centralized default instead of hardcoded 45
                    failed_session.estimated_duration_minutes = (
                        parent_program.max_session_duration
                        if parent_program and parent_program.max_session_duration
                        else get_default_session_duration()
                    )

                # Find a safe fallback movement
                try:
                    fallback_movement = await db.execute(
                        select(Movement).where(Movement.name == "Back Squat").limit(1)
                    )
                    fallback_movement = fallback_movement.scalar_one_or_none()

                    if fallback_movement:
                        logger.info(
                            "[_apply_session_fallback] INFO - Applying fallback placeholder exercise",
                            extra={
                                "input_state": {
                                    "session_id": failed_session.id,
                                    "session_type": failed_session.session_type.value,
                                    "fallback_movement_id": fallback_movement.id,
                                    "fallback_movement_name": fallback_movement.name,
                                    "original_error": error_msg,
                                },
                                "failure_context": {
                                    "what_failed": "Session generation (using fallback)",
                                    "why_failed": error_msg,
                                },
                            },
                        )
                        placeholder_exercise = SessionExercise(
                            session_id=failed_session.id,
                            movement_id=fallback_movement.id,
                            exercise_role=ExerciseRole.MAIN,
                            order_in_session=1,
                            target_sets=1,
                            target_rep_range_min=10,
                            target_rep_range_max=10,
                            notes=f"Generation error: {error_msg}",
                        )
                        db.add(placeholder_exercise)
                    else:
                        logger.error(
                            "[_apply_session_fallback] ERROR - No fallback movement found",
                            extra={
                                "input_state": {
                                    "session_id": session_id,
                                    "fallback_movement_name": "Back Squat",
                                },
                                "failure_context": {
                                    "what_failed": "Fallback movement lookup",
                                    "why_failed": "Back Squat movement not found in database",
                                },
                            },
                            exc_info=False,
                        )
                except Exception as e:
                    logger.error(
                        "[_apply_session_fallback] ERROR - Fallback movement query failed",
                        extra={
                            "input_state": {
                                "session_id": session_id,
                                "fallback_movement_name": "Back Squat",
                            },
                            "failure_context": {
                                "what_failed": "Fallback movement database query",
                                "why_failed": f"{type(e).__name__}: {str(e)}",
                                "exception_type": type(e).__name__,
                                "exception_message": str(e),
                            },
                        },
                        exc_info=True,
                    )

                db.add(failed_session)
                await db.commit()
                logger.info(
                    f"[_apply_session_fallback] COMPLETED - Applied fallback placeholder for session {session_id}"
                )

        except Exception as e:
            logger.exception(
                f"[_apply_session_fallback] CRITICAL ERROR - Failed to apply fallback for session {session_id}: {e}"
            )
            # Attempt to rollback if there's an active transaction
            try:
                await db.rollback()
            except Exception as rollback_error:
                logger.error(
                    f"[_apply_session_fallback] Error during rollback: {rollback_error}"
                )

    async def _apply_pattern_interference_rules(
        self,
        db: AsyncSession,
        session: Session,
        used_main_patterns: dict[int, list[str]],
        microcycle: Microcycle,
    ) -> Session:
        """
        Apply inter-session interference rules for main lift patterns.

        Rules:
        1. No same main pattern on consecutive days (even with rest day between)
        2. No same main pattern on back-to-back training days
        3. Prioritize pattern diversity: squat -> hinge -> lunge rotation for lower body
        4. Enforce minimum 2-day gap for same main pattern

        Args:
            db: Database session
            session: Session to apply rules to
            used_main_patterns: Dict mapping day_number to list of main patterns used
            microcycle: Parent microcycle

        Returns:
            Session with updated intent_tags based on interference rules
        """
        if session.session_type == SessionType.RECOVERY:
            return session
        if session.session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            return session
        if session.session_type == SessionType.CUSTOM and "conditioning" in (
            session.intent_tags or []
        ):
            return session

        current_day = session.day_number
        current_patterns = session.intent_tags or []

        # Define pattern alternatives for intelligent substitution
        pattern_alternatives = {
            # Lower body pattern rotation
            "squat": ["hinge", "lunge"],
            "hinge": ["lunge","squat"],
            "lunge": ["squat", "hinge"],
            # Upper body pattern rotation
            "horizontal_push": ["vertical_push"],
            "vertical_push": ["horizontal_push"],
            "horizontal_pull": ["vertical_pull"],
            "vertical_pull": ["horizontal_pull"],
        }

        # Define auxiliary tags that should be preserved
        auxiliary_tags = {"prefer_finisher", "prefer_accessory", "prefer_circuit"}

        # Separate auxiliary tags from movement patterns
        movement_patterns = [p for p in current_patterns if p not in auxiliary_tags]
        current_auxiliary_tags = [p for p in current_patterns if p in auxiliary_tags]

        # Check for pattern conflicts and resolve them
        conflicting_patterns = []
        for pattern in movement_patterns[:2]:  # Only check main patterns (first 2)
            if self._has_pattern_conflict(pattern, current_day, used_main_patterns):
                conflicting_patterns.append(pattern)

        # Replace conflicting patterns with alternatives
        if conflicting_patterns:
            new_movement_patterns = movement_patterns.copy()

            for i, pattern in enumerate(movement_patterns[:2]):
                if pattern in conflicting_patterns:
                    # Find alternative pattern
                    alternative = self._find_alternative_pattern(
                        pattern, current_day, used_main_patterns, pattern_alternatives
                    )
                    if alternative:
                        new_movement_patterns[i] = alternative
                        logger.info(
                            f"Day {current_day}: Replaced conflicting pattern '{pattern}' "
                            f"with '{alternative}' due to interference rules"
                        )

            # Reconstruct intent_tags: auxiliary tags first, then movement patterns
            new_intent_tags = current_auxiliary_tags + new_movement_patterns

            # Update session intent_tags
            session.intent_tags = new_intent_tags
            db.add(session)
            await db.commit()
            await db.refresh(session)
            logger.info(f"Day {current_day}: Persisted updated intent_tags: {new_intent_tags}")

        return session

    def _has_pattern_conflict(
        self,
        pattern: str,
        current_day: int,
        used_main_patterns: dict[int, list[str]],
    ) -> bool:
        """
        Check if a pattern conflicts with interference rules.

        Args:
            pattern: Pattern to check (e.g., "squat")
            current_day: Current day number
            used_main_patterns: Dict of day -> patterns used

        Returns:
            True if pattern conflicts with interference rules
        """
        auxiliary_tags = {"prefer_finisher", "prefer_accessory", "prefer_circuit"}

        # Rule 1: No same pattern on consecutive training days
        prev_day = current_day - 1
        if prev_day in used_main_patterns:
            prev_patterns = [
                p for p in used_main_patterns[prev_day] if p not in auxiliary_tags
            ][:2]
            if pattern in prev_patterns:
                return True

        # Rule 2: No same pattern within 2 days (even with rest day between)
        for check_day in range(max(1, current_day - 2), current_day):
            if check_day in used_main_patterns:
                check_patterns = [
                    p for p in used_main_patterns[check_day] if p not in auxiliary_tags
                ][:2]
                if pattern in check_patterns:
                    return True

        # Rule 3: Limit pattern usage to max 2 times per week (7 days)
        pattern_count = 0
        week_start = max(1, current_day - 6)
        for check_day in range(week_start, current_day + 1):
            if check_day in used_main_patterns:
                check_patterns = [
                    p for p in used_main_patterns[check_day] if p not in auxiliary_tags
                ][:2]
                if pattern in check_patterns:
                    pattern_count += 1

        if pattern_count >= 2:  # Already used twice this week
            return True

        return False

    def _find_alternative_pattern(
        self,
        original_pattern: str,
        current_day: int,
        used_main_patterns: dict[int, list[str]],
        pattern_alternatives: dict[str, list[str]],
    ) -> str | None:
        """
        Find an alternative pattern that doesn't conflict with interference rules.

        Args:
            original_pattern: Pattern that conflicts
            current_day: Current day number
            used_main_patterns: Dict of day -> patterns used
            pattern_alternatives: Dict of pattern -> list of alternatives

        Returns:
            Alternative pattern or None if no suitable alternative found
        """
        alternatives = pattern_alternatives.get(original_pattern, [])

        for alternative in alternatives:
            if not self._has_pattern_conflict(
                alternative, current_day, used_main_patterns
            ):
                return alternative

        # Fallback: try all lower body patterns if original was lower body
        lower_body_patterns = ["squat", "hinge", "lunge"]
        upper_body_patterns = [
            "horizontal_push",
            "vertical_push",
            "horizontal_pull",
            "vertical_pull",
        ]

        if original_pattern in lower_body_patterns:
            for pattern in lower_body_patterns:
                if pattern != original_pattern and not self._has_pattern_conflict(
                    pattern, current_day, used_main_patterns
                ):
                    return pattern
        elif original_pattern in upper_body_patterns:
            for pattern in upper_body_patterns:
                if pattern != original_pattern and not self._has_pattern_conflict(
                    pattern, current_day, used_main_patterns
                ):
                    return pattern

        return None

    async def _generate_microcycle_jerome_notes(
        self,
        program: Program,
        microcycle: Microcycle,
        sessions: list[Session],
    ) -> None:
        """
        Generate coach notes for all sessions in a microcycle in a single batched operation.

        This method is called after all sessions in a microcycle have been generated,
        allowing for more efficient batched LLM calls instead of per-session generation.

        Args:
            program: Parent program with goals and settings
            microcycle: Parent microcycle with deload status
            sessions: List of all sessions in the microcycle
        """
        from app.db.database import async_session_maker
        from app.llm import get_llm_provider, LLMConfig, Message
        from app.config.settings import get_settings

        logger.info(
            f"[_generate_microcycle_jerome_notes] START - microcycle_id={microcycle.id}, sessions={len(sessions)}"
        )

        # Filter out recovery sessions (they get default notes)
        training_sessions = [
            s for s in sessions if s.session_type != SessionType.RECOVERY
        ]

        if not training_sessions:
            logger.info(
                "[_generate_microcycle_jerome_notes] No training sessions to generate notes for"
            )
            return

        # Build goal weights
        goal_weights = {
            "strength": 0,
            "hypertrophy": 0,
            "endurance": 0,
            "fat_loss": 0,
            "mobility": 0,
        }
        for goal, weight in [
            (program.goal_1.value, program.goal_weight_1),
            (program.goal_2.value, program.goal_weight_2),
            (program.goal_3.value, program.goal_weight_3),
        ]:
            if goal in goal_weights:
                goal_weights[goal] += weight

        # Generate notes in batches for efficiency
        # We'll process sessions in groups to avoid overly large prompts
        batch_size = 3
        settings = get_settings()

        for batch_start in range(0, len(training_sessions), batch_size):
            batch = training_sessions[batch_start : batch_start + batch_size]

            # Build batch prompt for LLM
            batch_summaries = []
            for session in batch:
                # Get session content to extract exercise information
                async with async_session_maker() as db:
                    session_with_exercises = await db.get(
                        Session, session.id, options=[selectinload(Session.exercises)]
                    )

                    if not session_with_exercises:
                        continue

                    # Extract exercise names from session
                    main_moves = []
                    accessory_moves = []

                    if session_with_exercises.exercises:
                        for ex in session_with_exercises.exercises:
                            if ex.movement:
                                if ex.exercise_role == ExerciseRole.MAIN:
                                    main_moves.append(ex.movement.name)
                                elif ex.exercise_role == ExerciseRole.ACCESSORY:
                                    accessory_moves.append(ex.movement.name)

                    goals_summary = ", ".join(
                        [f"{k}:{v}" for k, v in goal_weights.items() if v > 0]
                    )
                    intent_tags = session.intent_tags or []
                    summary = (
                        f"Session {session.day_number} ({session.session_type.value}): "
                        f"Patterns: {', '.join(intent_tags)}. "
                        f"Goals: {goals_summary}. "
                        f"Main: {', '.join(main_moves[:4])}. "
                    )
                    if accessory_moves:
                        summary += f"Accessories: {', '.join(accessory_moves[:4])}. "
                    if microcycle.is_deload:
                        summary += "Deload week. "

                    batch_summaries.append(summary)

            # Generate batch notes
            batch_prompt = (
                "Write 1-2 sentences in Jerome's voice for each session explaining "
                "why it fits the user's goals and recovery. "
                "Format your response as a JSON object with session day numbers as keys "
                'and the notes as values. Example: {"1": "Your note here", "2": "Your note here"}\n\n'
            )
            batch_prompt += "\n".join(batch_summaries)

            try:
                provider = get_llm_provider()
                config = LLMConfig(
                    model=settings.ollama_model, temperature=0.2, max_tokens=2000
                )
                messages = [Message(role="user", content=batch_prompt)]

                # Use the session_generator's retry logic via import
                response = await session_generator._call_llm_with_retry(
                    provider,
                    messages,
                    config,
                    session_type="batch",
                )

                if response and isinstance(response, dict):
                    # Update sessions with generated notes
                    async with async_session_maker() as db:
                        for session in batch:
                            day_num_str = str(session.day_number)
                            if day_num_str in response:
                                note = str(response[day_num_str])[:1100].rstrip()
                                session_to_update = await db.get(Session, session.id)
                                if session_to_update:
                                    session_to_update.coach_notes = note
                                    db.add(session_to_update)
                        await db.commit()

                    logger.info(
                        f"[_generate_microcycle_jerome_notes] Generated notes for batch "
                        f"{batch_start//batch_size + 1}: {len(batch)} sessions"
                    )
                else:
                    # Fallback to default notes for this batch
                    logger.warning(
                        "[_generate_microcycle_jerome_notes] WARNING - LLM response parsing failed, using fallback notes",
                        extra={
                            "input_state": {
                                "batch_size": len(batch),
                                "response_type": type(response).__name__,
                                "batch_start_index": batch_start,
                            },
                            "failure_context": {
                                "what_failed": "LLM batch notes response parsing",
                                "why_failed": "Response is not a dict or is empty",
                            },
                        },
                        exc_info=False,
                    )
                    await self._apply_fallback_notes(batch, microcycle.is_deload)

            except Exception as e:
                logger.error(
                    "[_generate_microcycle_jerome_notes] ERROR - LLM batch notes generation failed",
                    extra={
                        "input_state": {
                            "batch_size": len(batch),
                            "batch_start_index": batch_start,
                            "batch_index": batch_start // batch_size + 1,
                            "total_sessions": len(training_sessions),
                        },
                        "failure_context": {
                            "what_failed": "LLM batch notes generation",
                            "why_failed": f"{type(e).__name__}: {str(e)}",
                            "exception_type": type(e).__name__,
                            "exception_message": str(e),
                        },
                    },
                    exc_info=True,
                )
                await self._apply_fallback_notes(batch, microcycle.is_deload)

        logger.info(
            f"[_generate_microcycle_jerome_notes] COMPLETED - microcycle_id={microcycle.id}"
        )

    async def _apply_fallback_notes(
        self,
        sessions: list[Session],
        is_deload: bool,
    ) -> None:
        """
        Apply fallback coach notes when LLM generation fails.

        Args:
            sessions: List of sessions to update with fallback notes
            is_deload: Whether this is a deload microcycle
        """
        from app.db.database import async_session_maker

        logger.info(
            "[_apply_fallback_notes] INFO - Applying fallback coach notes",
            extra={
                "input_state": {
                    "sessions_count": len(sessions),
                    "is_deload": is_deload,
                },
                "failure_context": {
                    "what_failed": "LLM batch notes generation",
                    "why_failed": "Using generic fallback notes",
                },
            },
        )

        async with async_session_maker() as db:
            for session in sessions:
                session_to_update = await db.get(Session, session.id)
                if session_to_update:
                    if is_deload:
                        note = "Optimization-first deload session focused on recovery and quality."
                    else:
                        note = "Optimization-first session aligned to your goals and recovery."
                    session_to_update.coach_notes = note[:1100].rstrip()
                    db.add(session_to_update)
            await db.commit()

    async def _update_movement_group_usage(
        self,
        db: AsyncSession,
        session_movements: list[str],
        used_movement_groups: dict[str, int],
    ) -> None:
        """
        Update movement group usage counts for variety tracking.

        Args:
            db: Database session
            session_movements: List of movement names used in this session
            used_movement_groups: Dict tracking usage count by substitution_group
        """
        if not session_movements:
            return

        # Get movement objects to access substitution_group
        movements_result = await db.execute(
            select(Movement).where(Movement.name.in_(session_movements))
        )
        movements = {m.name: m for m in movements_result.scalars().all()}

        # Update group usage counts
        for movement_name in session_movements:
            movement = movements.get(movement_name)
            if movement and movement.substitution_group:
                group = movement.substitution_group
                used_movement_groups[group] = used_movement_groups.get(group, 0) + 1

    async def _create_microcycle(
        self,
        db: AsyncSession,
        user_id: int,
        program_id: int,
        mc_index: int,
        start_date: date,
        split_config: Dict[str, Any],
        is_deload: bool = False,
    ) -> Microcycle:
        """
        Create a microcycle with sessions based on split template.

        Args:
            db: Database session
            user_id: User ID who owns the program
            program_id: Parent program ID
            mc_index: Microcycle index (0-based)
            start_date: Microcycle start date
            split_config: Split template configuration from heuristics
            is_deload: Whether this is a deload microcycle

        Returns:
            Created Microcycle
        """
        days_per_cycle = split_config.get("days_per_cycle", 7)
        structure = split_config.get("structure", [])

        # First microcycle is active, others are planned
        status = MicrocycleStatus.ACTIVE if mc_index == 0 else MicrocycleStatus.PLANNED

        microcycle = Microcycle(
            program_id=program_id,
            sequence_number=mc_index + 1,  # 1-indexed
            start_date=start_date,
            length_days=days_per_cycle,
            status=status,
            is_deload=is_deload,
        )
        db.add(microcycle)
        await db.flush()  # Get microcycle.id

        # Create sessions from split template structure
        logger.info(
            f"[_create_microcycle] START Creating sessions for microcycle_id={microcycle.id}"
        )
        logger.info(
            f"[_create_microcycle] Structure has {len(structure)} day definitions"
        )

        created_sessions = []
        for day_def in structure:
            day_num = day_def.get("day", 1)
            day_type = day_def.get("type", "rest")
            focus_patterns = day_def.get("focus", [])

            # Calculate session date
            session_date = start_date + timedelta(days=day_num - 1)

            # Map day type to SessionType enum
            session_type = self._map_day_type_to_session_type(day_type)

            # Create session (even for rest days - they can have recovery activities)
            session = Session(
                user_id=user_id,
                microcycle_id=microcycle.id,
                date=session_date,
                day_number=day_num,
                session_type=session_type,
                intent_tags=focus_patterns,
            )
            db.add(session)
            created_sessions.append(session)
            logger.info(
                f"[_create_microcycle] Created session - day={day_num}, type={session_type.value}, focus={focus_patterns}"
            )

        logger.info(
            f"[_create_microcycle] END Created {len(created_sessions)} sessions for microcycle_id={microcycle.id}"
        )

        return microcycle

    def _resolve_preferred_microcycle_length_days(
        self, scheduling_prefs: dict[str, Any]
    ) -> int:
        preferred = scheduling_prefs.get("microcycle_length_days")
        if isinstance(preferred, int) and 7 <= preferred <= 14:
            return preferred
        return activity_distribution_config.default_microcycle_length_days

    def _partition_microcycle_lengths(
        self, total_days: int, preferred_length_days: int
    ) -> list[int]:
        if total_days <= 0:
            return []

        preferred_length_days = min(14, max(7, int(preferred_length_days)))
        count = max(1, int(round(total_days / preferred_length_days)))

        for _ in range(50):
            base = total_days // count
            remainder = total_days % count
            if base < 7:
                count = max(1, count - 1)
                continue
            if base > 14 or (base == 14 and remainder > 0):
                count += 1
                continue
            break

        base = total_days // count
        remainder = total_days % count
        lengths = [base + 1] * remainder + [base] * (count - remainder)

        logger.info(
            f"[_partition_microcycle_lengths] total_days={total_days}, preferred_length_days={preferred_length_days}"
        )
        logger.info(
            f"[_partition_microcycle_lengths] Creating {len(lengths)} microcycles with lengths: {lengths}"
        )

        return lengths

    def _pick_evenly_spaced_days(
        self, cycle_length_days: int, session_count: int
    ) -> list[int]:
        cycle_length_days = max(1, int(cycle_length_days))
        session_count = max(0, min(int(session_count), cycle_length_days))
        if session_count == 0:
            return []
        if session_count == cycle_length_days:
            return list(range(1, cycle_length_days + 1))

        step = cycle_length_days / session_count
        taken: set[int] = set()
        chosen: list[int] = []
        for k in range(session_count):
            ideal = int(round((k + 0.5) * step))
            day = min(cycle_length_days, max(1, ideal))
            while day in taken and day < cycle_length_days:
                day += 1
            while day in taken and day > 1:
                day -= 1
            taken.add(day)
            chosen.append(day)
        return sorted(chosen)

    def _build_freeform_split_config(
        self, cycle_length_days: int, days_per_week: int
    ) -> dict[str, Any]:
        cycle_length_days = min(14, max(7, int(cycle_length_days)))
        target_sessions = int(round(days_per_week * (cycle_length_days / 7.0)))
        target_sessions = max(2, min(target_sessions, cycle_length_days))
        training_days = set(
            self._pick_evenly_spaced_days(cycle_length_days, target_sessions)
        )
        structure: list[dict[str, Any]] = []
        for day in range(1, cycle_length_days + 1):
            if day in training_days:
                structure.append({"day": day, "type": "full_body", "focus": []})
            else:
                structure.append({"day": day, "type": "rest"})

        logger.info(
            f"[_build_freeform_split_config] Generated structure with {len(structure)} days"
        )
        logger.info(
            f"[_build_freeform_split_config] Training days: {sorted(training_days)}"
        )

        return {
            "days_per_cycle": cycle_length_days,
            "structure": structure,
            "training_days": len(training_days),
            "rest_days": cycle_length_days - len(training_days),
        }

    def _assign_freeform_day_types_and_focus(
        self, split_config: dict[str, Any], days_per_week: int
    ) -> dict[str, Any]:
        structure = [dict(d) for d in (split_config.get("structure") or [])]

        logger.info(
            f"[_assign_freeform_day_types_and_focus] Input structure length: {len(structure)}"
        )
        for idx, d in enumerate(structure):
            logger.info(f"[_assign_freeform_day_types_and_focus] Input day {idx}: {d}")

        lifting_indexes = [
            i
            for i, d in enumerate(structure)
            if (d.get("type") or "rest")
            not in {"rest", "recovery", "cardio", "mobility", "conditioning"}
        ]

        logger.info(
            f"[_assign_freeform_day_types_and_focus] Lifting indexes: {lifting_indexes}"
        )

        if days_per_week <= 3:
            type_cycle = ["full_body"]
        elif days_per_week == 4:
            type_cycle = ["upper", "lower", "upper", "lower", "full_body"]
        elif days_per_week == 5:
            type_cycle = ["upper", "lower", "full_body", "upper", "lower"]
        else:
            type_cycle = ["push", "pull", "legs", "upper", "lower", "full_body"]

        lower_cycle = ["squat", "hinge", "lunge"]
        push_cycle = ["horizontal_push", "vertical_push"]
        pull_cycle = ["horizontal_pull", "vertical_pull"]
        lower_idx = 0
        push_idx = 0
        pull_idx = 0

        for seq, i in enumerate(lifting_indexes):
            day_type = type_cycle[seq % len(type_cycle)]
            existing_focus = structure[i].get("focus") or []
            if not isinstance(existing_focus, list):
                existing_focus = []
            tags = [t for t in existing_focus if t.startswith("prefer_")]

            if day_type == "upper":
                patterns = [
                    push_cycle[push_idx % len(push_cycle)],
                    pull_cycle[pull_idx % len(pull_cycle)],
                ]
                push_idx += 1
                pull_idx += 1
            elif day_type in {"lower", "legs"}:
                patterns = [
                    lower_cycle[lower_idx % len(lower_cycle)],
                    lower_cycle[(lower_idx + 1) % len(lower_cycle)],
                ]
                lower_idx += 1
            elif day_type == "push":
                patterns = [
                    push_cycle[push_idx % len(push_cycle)],
                    push_cycle[(push_idx + 1) % len(push_cycle)],
                ]
                push_idx += 1
            elif day_type == "pull":
                patterns = [
                    pull_cycle[pull_idx % len(pull_cycle)],
                    pull_cycle[(pull_idx + 1) % len(pull_cycle)],
                ]
                pull_idx += 1
            else:
                patterns = [
                    lower_cycle[lower_idx % len(lower_cycle)],
                    push_cycle[push_idx % len(push_cycle)],
                    pull_cycle[pull_idx % len(pull_cycle)],
                ]
                lower_idx += 1
                push_idx += 1
                pull_idx += 1

            # Check if patterns qualify as FULL_BODY
            # Condition 1: BOTH push AND pull patterns (horizontal_push AND horizontal_pull, OR vertical_push AND vertical_pull)
            has_horizontal_push = "horizontal_push" in patterns
            has_horizontal_pull = "horizontal_pull" in patterns
            has_vertical_push = "vertical_push" in patterns
            has_vertical_pull = "vertical_pull" in patterns
            has_both_push_pull = (has_horizontal_push and has_horizontal_pull) or (
                has_vertical_push and has_vertical_pull
            )

            # Condition 2: BOTH upper AND lower movements
            has_lower = any(p in lower_cycle for p in patterns)
            has_upper = any(p in push_cycle + pull_cycle for p in patterns)
            has_both_upper_lower = has_upper and has_lower

            # Update day_type to FULL_BODY if either condition is met
            if has_both_push_pull or has_both_upper_lower:
                day_type = "full_body"

            structure[i]["type"] = day_type
            structure[i]["focus"] = patterns + tags

        split_config["structure"] = structure

        logger.info(
            f"[_assign_freeform_day_types_and_focus] Output structure length: {len(structure)}"
        )
        for idx, d in enumerate(structure):
            logger.info(f"[_assign_freeform_day_types_and_focus] Output day {idx}: {d}")

        return split_config

    def _apply_goal_based_cycle_distribution(
        self,
        split_config: dict[str, Any],
        goals: list[Any],
        days_per_week: int,
        cycle_length_days: int,
        max_session_duration: int,
        user_experience_level: str | None,
        scheduling_prefs: dict,
    ) -> dict[str, Any]:
        if not split_config or not split_config.get("structure"):
            return split_config

        structure = [dict(d) for d in split_config["structure"]]

        def is_rest_day(d: dict[str, Any]) -> bool:
            return (d.get("type") or "rest") == "rest"

        training_days_in_cycle = sum(1 for d in structure if not is_rest_day(d))

        integration_service = AllocationIntegrationService()
        allocation_context = integration_service.create_allocation_context(
            user_settings=scheduling_prefs,
            wizard_goals=goals,
            microcycle_id=0,
        )

        session_ids = list(range(training_days_in_cycle))
        session_types = [
            d.get("type") or "lifting" for d in structure if not is_rest_day(d)
        ]

        allocation_result = integration_service.allocate_session_types(
            context=allocation_context,
            session_ids=session_ids,
            session_types=session_types,
        )

        training_indexes = [i for i, d in enumerate(structure) if not is_rest_day(d)]
        for idx, training_idx in enumerate(training_indexes):
            session_intent = allocation_result.get_session_intent(idx)

            existing_focus = structure[training_idx].get("focus") or []
            if not isinstance(existing_focus, list):
                existing_focus = []

            movement_patterns = session_intent.movement_patterns
            auxiliary_tags = list(session_intent.auxiliary_tags)

            focus = []
            focus.extend(auxiliary_tags)
            focus.extend(movement_patterns)

            for tag in existing_focus:
                if tag not in auxiliary_tags:
                    focus.append(tag)

            structure[training_idx]["focus"] = focus

            # Update session type if allocation changed it (e.g. to cardio)
            if session_intent.session_type == "cardio_day":
                structure[training_idx]["type"] = "cardio"
            elif session_intent.session_type == "conditioning_day":
                structure[training_idx]["type"] = "conditioning"

        goal_weights_dict = {
            "strength": 0,
            "hypertrophy": 0,
            "endurance": 0,
            "fat_loss": 0,
            "mobility": 0,
        }
        for g in goals or []:
            goal_value = getattr(getattr(g, "goal", None), "value", None)
            weight_value = getattr(g, "weight", None)
            if goal_value in goal_weights_dict and isinstance(weight_value, int):
                goal_weights_dict[goal_value] = weight_value

        split_config["structure"] = structure
        split_config["training_days"] = sum(1 for d in structure if not is_rest_day(d))
        split_config["rest_days"] = sum(1 for d in structure if is_rest_day(d))
        split_config["goal_weights"] = goal_weights_dict
        split_config[
            "goal_bias_rationale"
        ] = activity_distribution_config.BIAS_RATIONALE

        logger.info(
            f"[_apply_goal_based_cycle_distribution] "
            f"Targets: accessory={allocation_result.targets['accessory']}, "
            f"finisher={allocation_result.targets['finisher']}, "
            f"cardio_days={allocation_result.targets['cardio_day']}"
        )
        logger.info(
            f"[_apply_goal_based_cycle_distribution] Final structure length: {len(structure)}"
        )
        for idx, d in enumerate(structure):
            logger.info(f"[_apply_goal_based_cycle_distribution] Final day {idx}: {d}")

        return split_config

    def _map_day_type_to_session_type(self, day_type: str) -> SessionType:
        """
        Map split template day type to SessionType enum.
        """
        mapping = {
            "upper": SessionType.UPPER,
            "lower": SessionType.LOWER,
            "push": SessionType.PUSH,
            "pull": SessionType.PULL,
            "legs": SessionType.LEGS,
            "full_body": SessionType.FULL_BODY,
            "cardio": SessionType.CARDIO,
            "mobility": SessionType.MOBILITY,
            "conditioning": SessionType.CUSTOM,
            "rest": SessionType.RECOVERY,
            "recovery": SessionType.RECOVERY,
        }
        return mapping.get(day_type.lower(), SessionType.CUSTOM)

    async def get_program(
        self,
        db: AsyncSession,
        program_id: int,
        user_id: int,
    ) -> Optional[Program]:
        """
        Retrieve a program with all microcycles and sessions.

        Args:
            db: Database session
            program_id: Program ID
            user_id: User ID

        Returns:
            Program object or None if not found
        """
        result = await db.execute(
            select(Program).where(
                and_(Program.id == program_id, Program.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def list_programs(
        self,
        db: AsyncSession,
        user_id: int,
        status: Optional[str] = None,
    ) -> list:
        """
        List all programs for user, optionally filtered by status.

        Args:
            db: Database session
            user_id: User ID
            status: Optional ProgramStatus filter

        Returns:
            List of Program objects
        """
        query = select(Program).where(Program.user_id == user_id)
        if status:
            query = query.where(Program.status == status)

        result = await db.execute(query.order_by(Program.created_at.desc()))
        return list(result.scalars().all())


# Singleton instance
program_service = ProgramService()
