"""
SessionGeneratorService - Generates workout session content using LLM.

Uses Ollama with llama3.1:8b to create exercise blocks for sessions
based on program goals, session type, and movement library.
"""
import logging
from typing import Any, TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import activity_distribution as activity_distribution_config
from app.config.settings import get_settings
from app.config.heuristics import DEFAULT_ACCESSORIES, TIME_FILLING
from app.services.time_estimation import get_default_session_duration
from app.models import (
    Movement,
    Session,
    Program,
    Microcycle,
    UserMovementRule,
    UserProfile,
    SessionExercise,
)
from app.models.circuit import CircuitTemplate
from app.models.circuit_extended import CircuitMelted
from app.models.enums import (
    SessionType,
    MovementRuleType,
    SkillLevel,
    ExerciseRole,
    MuscleRole,
)
from app.services.optimization import (
    ConstraintSolver,
    OptimizationRequest,
    SolverMovement,
    SolverCircuit,
)
from app.services.session_content_utils import DuplicateRemover

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
settings = get_settings()


class SessionGeneratorService:
    """
    Generates workout session content using LLM.

    Takes session shells (with type and intent_tags) and populates them
    with warmup, main, accessory, finisher, and cooldown exercise blocks.
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 2.0  # seconds
    RETRY_BACKOFF_MULTIPLIER = 2.0
    MAX_RETRY_DELAY = 10.0  # seconds

    def __init__(self):
        self.optimizer = ConstraintSolver()
        self._optimization_draft_status = (
            None  # Track optimization draft status for current session
        )

    async def populate_session_by_id(
        self,
        session_id: int,
        program_id: int,
        microcycle_id: int,
        used_movements: list[str] | None = None,
        used_movement_groups: dict[str, int] | None = None,
        used_main_patterns: dict[str, list[str]] | None = None,
        used_accessory_movements: dict[int, list[str]] | None = None,
        previous_day_volume: dict[str, int] | None = None,
        used_circuit_ids: list[int] | None = None,
    ) -> tuple[dict[str, int], dict[str, Any]]:
        """
        Generate and save exercise content to a session using IDs.

        Returns: (volume_dict, content_dict)
        - volume_dict: Muscle group -> volume mapping
        - content_dict: Full session content dict with exercises

        Refactored to NOT hold a database connection during LLM generation.
        """
        from app.db.database import async_session_maker

        logger.debug(
            f"[populate_session_by_id] session_id={session_id}, program_id={program_id}"
        )

        # 1. Fetch all necessary context (short DB transaction)
        context_data = {}
        async with async_session_maker() as db:
            from sqlalchemy.orm import selectinload

            session = await db.get(Session, session_id)
            if session:
                logger.info(
                    f"[populate_session_by_id] Fetched session {session_id} - intent_tags={session.intent_tags}"
                )
            program = await db.get(
                Program, program_id, options=[selectinload(Program.program_disciplines)]
            )
            microcycle = await db.get(Microcycle, microcycle_id)

            if not session or not program or not microcycle:
                logger.error(
                    f"[populate_session_by_id] Missing data: session={session is not None}, program={program is not None}, microcycle={microcycle is not None}"
                )
                return {}, {}

            # Fetch supporting data
            movements_by_pattern = await self._load_movements_by_pattern(db)
            movement_rules = await self._load_user_movement_rules_dict(
                db, program.user_id
            )
            user_profile = await db.get(UserProfile, program.user_id)
            all_movements = await self._load_all_movements(db)
            all_circuits = await self._load_all_circuits(db)

            # Load program disciplines from junction table
            program_disciplines = []
            for pd in program.program_disciplines:
                program_disciplines.append(
                    {"discipline": pd.discipline_type, "weight": pd.weight}
                )

            # Store in context (convert Enums to values for safety)
            context_data = {
                "program": {
                    "goal_1": program.goal_1,
                    "goal_2": program.goal_2,
                    "goal_3": program.goal_3,
                    "goal_weight_1": program.goal_weight_1,
                    "goal_weight_2": program.goal_weight_2,
                    "goal_weight_3": program.goal_weight_3,
                    "split_template": program.split_template,
                    "days_per_week": program.days_per_week,
                    "progression_style": program.progression_style,
                    "duration_weeks": program.duration_weeks,
                    "deload_every_n_microcycles": program.deload_every_n_microcycles,
                    "disciplines_json": program_disciplines,
                    "user_id": program.user_id,
                    "max_session_duration": program.max_session_duration,
                },
                "session": {
                    "id": session.id,
                    "session_type": session.session_type,
                    "intent_tags": session.intent_tags,
                    "day_number": session.day_number,
                },
                "microcycle": {
                    "is_deload": microcycle.is_deload,
                    "sequence_number": microcycle.sequence_number,
                },
                "movements_by_pattern": movements_by_pattern,
                "movement_rules": movement_rules,
                # Detach objects manually or use dictionaries
                "all_movements": all_movements,
                "all_circuits": all_circuits,
                "discipline_preferences": user_profile.discipline_preferences
                if user_profile
                else None,
                "scheduling_preferences": user_profile.scheduling_preferences
                if user_profile
                else None,
            }

        # 2. Generate Content (Long running, NO DB connection)
        fatigued_muscles = []
        if previous_day_volume:
            fatigued_muscles = [m for m, v in previous_day_volume.items() if v > 2]

        logger.debug(
            f"[populate_session_by_id] all_movements count in context_data: {len(context_data.get('all_movements', []))}"
        )
        content = await self.generate_session_exercises_offline(
            context_data,
            db=None,  # No DB session available in this phase
            used_movements=used_movements,
            used_movement_groups=used_movement_groups,
            used_accessory_movements=used_accessory_movements,
            fatigued_muscles=fatigued_muscles,
            used_circuit_ids=used_circuit_ids,
        )

        # Post-processing (duplicates removal)
        if used_accessory_movements:
            current_day = context_data["session"]["day_number"]
            previous_days = [
                d for d in used_accessory_movements.keys() if d < current_day
            ]
            if previous_days:
                last_day = max(previous_days)
                previous_accessories = used_accessory_movements.get(last_day) or []
                if previous_accessories:
                    content = (
                        DuplicateRemover.remove_cross_session_accessory_duplicates(
                            content,
                            set(previous_accessories),
                            context_data["session"]["session_type"],
                        )
                    )

        # 3. Save Results (Short DB transaction)
        current_session_volume = {}

        # Check if duration validation failed - LOG WARNING BUT CONTINUE SAVING
        if content.get("duration_validation_failed"):
            error_msg = content.get(
                "duration_validation_error", "Duration validation failed"
            )
            logger.warning(
                f"[populate_session_by_id] Session {session_id} duration validation failed: {error_msg}. Saving exercises anyway."
            )
            # Add warning to content notes instead of aborting
            if "reasoning" not in content:
                content["reasoning"] = error_msg
        # Continue to save exercises - don't early return

        async with async_session_maker() as db:
            session = await db.get(Session, session_id)
            if session:
                # Use centralized default instead of hardcoded 60
                session.estimated_duration_minutes = content.get(
                    "estimated_duration_minutes", get_default_session_duration()
                )
                
                # Check if we have a calculated duration from content (which should be more accurate)
                if content.get("estimated_duration_minutes"):
                     session.estimated_duration_minutes = content.get("estimated_duration_minutes")
                     logger.debug(f"[_save_session_exercises] Updated session duration to {session.estimated_duration_minutes}m from content")

                # coach_notes will be generated in batches at microcycle level via _generate_microcycle_jerome_notes()
                # Note: Circuit ID (finisher_circuit_id) is saved in _save_session_exercises()

                # Create movement map from context for ID lookup
                all_movements = context_data.get("all_movements", [])
                movement_map = {}
                for m in all_movements:
                    # Handle both object and dict just in case
                    m_name = getattr(m, "name", None) or m.get("name")
                    m_id = getattr(m, "id", None) or m.get("id")
                    if m_name and m_id:
                        movement_map[m_name] = m_id

                # Save normalized session exercises
                logger.info(
                    f"[populate_session_by_id] Saving {len(content.get('main', []))} main, {len(content.get('accessory') or [])} accessory, {len(content.get('warmup', []))} warmup, {len(content.get('cooldown', []))} cooldown exercises"
                )
                await self._save_session_exercises(
                    db,
                    session,
                    content,
                    movement_map,
                    context_data["program"]["user_id"],
                )

                db.add(session)
                await db.commit()
                await db.refresh(session, attribute_names=["exercises"])
                logger.info(
                    f"[populate_session_by_id] After commit/refresh: session has {len(session.exercises or [])} exercises"
                )

                # Calculate volume (needs DB for movement lookup)
                logger.debug(
                    f"[populate_session_by_id] Calculating session volume for session_id={session_id}"
                )
                current_session_volume = await self._calculate_session_volume(
                    db, session
                )
                logger.debug(
                    f"[populate_session_by_id] Calculated session volume: {current_session_volume}"
                )

        logger.debug(
            f"[populate_session_by_id] RETURN - session_id={session_id}, volume={current_session_volume}"
        )

        return current_session_volume, content

    async def generate_session_exercises_offline(
        self,
        context: dict,
        db: AsyncSession | None = None,
        used_movements: list[str] | None = None,
        used_movement_groups: dict[str, int] | None = None,
        used_accessory_movements: dict[int, list[str]] | None = None,
        fatigued_muscles: list[str] | None = None,
        used_circuit_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Generate exercise content without active DB session.
        """
        logger.info("-" * 80)
        logger.info("[generate_session_exercises_offline] ENTRY POINT")
        logger.debug(
            f"[generate_session_exercises_offline] Session ID: {context['session']['id']}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Session Type: {context['session']['session_type'].value}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Intent Tags: {context['session']['intent_tags'] or []}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Day Number: {context['session']['day_number']}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Used movements count: {len(used_movements) if used_movements else 0}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Fatigued muscles: {fatigued_muscles or []}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Used movement groups: {used_movement_groups}"
        )
        logger.info("-" * 80)

        session_type = context["session"]["session_type"]

        # Skip generation for rest/recovery sessions
        if session_type == SessionType.RECOVERY:
            logger.info(
                "[generate_session_exercises_offline] Session type is RECOVERY, returning recovery content"
            )
            logger.info("-" * 80)
            return self._get_recovery_session_content()

        movements_by_pattern = context["movements_by_pattern"]
        goal_weights = self._get_goal_weights(context["program"])
        logger.debug(
            f"[generate_session_exercises_offline] Goal weights: {goal_weights}"
        )

        # Build name to ID mapping from all_movements
        all_movements = context.get("all_movements", [])
        logger.info(
            f"[generate_session_exercises_offline] all_movements from context: {len(all_movements)} items"
        )

        # Extract movement rule IDs from dict format
        # movement_rules dict has keys: "avoid", "must_include", "prefer" containing movement names
        movement_rules_dict = context.get("movement_rules") or {}
        preferred_ids: list[int] = []
        hard_no_ids: list[int] = []
        hard_yes_ids: list[int] = []
        name_to_id = {}
        for m in all_movements:
            m_name = getattr(m, "name", None) or m.get("name")
            m_id = getattr(m, "id", None) or m.get("id")
            if m_name and m_id:
                name_to_id[m_name] = m_id

        # Extract IDs from movement rule names
        for name in movement_rules_dict.get("prefer", []):
            if name in name_to_id:
                preferred_ids.append(name_to_id[name])

        for name in movement_rules_dict.get("avoid", []):
            if name in name_to_id:
                hard_no_ids.append(name_to_id[name])

        for name in movement_rules_dict.get("must_include", []):
            if name in name_to_id:
                hard_yes_ids.append(name_to_id[name])

        logger.debug(
            f"[generate_session_exercises_offline] Movement rules - preferred_ids: {len(preferred_ids)}, hard_no_ids: {len(hard_no_ids)}, hard_yes_ids: {len(hard_yes_ids)}"
        )

        draft_content = None
        try:
            logger.info(
                "[generate_session_exercises_offline] Attempting to generate draft session offline..."
            )
            draft_result = await self._generate_draft_session_offline(
                context["all_movements"],
                session_type,
                used_movements,
                goal_weights=goal_weights,
                preferred_movement_ids=preferred_ids,
                excluded_movement_ids=hard_no_ids,
                required_movement_ids=hard_yes_ids,
                max_session_duration=context["program"]["max_session_duration"],
                all_circuits=context.get(
                    "all_circuits", []
                ),  # Pass circuits from context
            )
            if (
                draft_result.status in ["OPTIMAL", "FEASIBLE"]
                and draft_result.selected_movements
            ):
                draft_content = self._convert_optimization_result_to_content(
                    draft_result, session_type, all_movements
                )
                logger.debug(
                    f"[generate_session_exercises_offline] Generated optimal draft for session {context['session']['id']} with status {draft_result.status}"
                )
                logger.debug(
                    f"[generate_session_exercises_offline] Selected movements: {len(draft_result.selected_movements)}"
                )
            else:
                logger.debug(
                    f"[generate_session_exercises_offline] Draft generation returned status {draft_result.status}, no optimal solution found"
                )
                # Store optimization failure metadata for later use in content dict
                self._optimization_draft_status = {
                    "status": draft_result.status,
                    "pass_number": getattr(draft_result, "pass_number", None),
                    "pass_config": getattr(draft_result, "pass_config", None),
                    "optimization_failed": True,
                    "reason": f"Draft optimization failed with status: {draft_result.status}",
                }
        except Exception as e:
            logger.error(
                "[generate_session_exercises_offline] ERROR - OR-Tools draft generation failed",
                extra={
                    "input_state": {
                        "session_id": context["session"]["id"],
                        "session_type": session_type.value,
                        "intent_tags": context["session"]["intent_tags"] or [],
                        "total_movements_count": len(all_movements)
                        if all_movements
                        else 0,
                        "used_movements_count": len(used_movements)
                        if used_movements
                        else 0,
                        "goal_weights": goal_weights,
                        "preferred_movement_ids_count": len(preferred_ids),
                        "excluded_movement_ids_count": len(hard_no_ids),
                        "required_movement_ids_count": len(hard_yes_ids),
                        "max_session_duration": context["program"][
                            "max_session_duration"
                        ],
                        "movement_groups": used_movement_groups,
                        "fatigued_muscles": fatigued_muscles or [],
                    },
                    "failure_context": {
                        "what_failed": "OR-Tools draft generation",
                        "why_failed": f"{type(e).__name__}: {str(e)}",
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                },
                exc_info=True,
            )

        if session_type == SessionType.CUSTOM and "conditioning" in (
            context["session"]["intent_tags"] or []
        ):
            logger.info(
                "[generate_session_exercises_offline] Path: CUSTOM conditioning session"
            )
            all_movements = context.get("all_movements") or (
                db and await self._load_all_movements(db)
            )
            if not all_movements and db:
                all_movements = await self._load_all_movements(db)
            conditioning_names = self._get_conditioning_movement_names(all_movements)
            content = self._get_fast_conditioning_session_content(
                conditioning_names,
                context["program"]["max_session_duration"],
                all_movements,
            )
        elif session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            logger.debug(
                f"[generate_session_exercises_offline] Path: {session_type.value} session"
            )
            all_movements = context.get("all_movements") or (
                db and await self._load_all_movements(db)
            )
            if not all_movements and db:
                all_movements = await self._load_all_movements(db)
            content = self._get_fast_special_session_content(
                session_type, context["program"]["max_session_duration"], all_movements
            )
        elif draft_content:
            logger.info(
                "[generate_session_exercises_offline] Path: Building content from optimal draft"
            )
            all_movements = context.get("all_movements") or (
                db and await self._load_all_movements(db)
            )
            if not all_movements and db:
                all_movements = await self._load_all_movements(db)
            content = await self._build_fast_content_from_draft(
                draft_content,
                session_type,
                context["session"]["intent_tags"] or [],
                context["microcycle"]["is_deload"],
                goal_weights,
                all_movements,
                used_circuit_ids,
            )
        else:
            logger.info(
                "[generate_session_exercises_offline] Path: Using smart fallback session content"
            )
            all_movements = context.get("all_movements") or (
                db and await self._load_all_movements(db)
            )
            if not all_movements and db:
                all_movements = await self._load_all_movements(db)
            content = self._get_smart_fallback_session_content(
                session_type,
                context["session"]["intent_tags"] or [],
                movements_by_pattern,
                used_movements=used_movements,
                all_movements=all_movements,
                max_session_duration=context["program"]["max_session_duration"],
            )
            # Add optimization failure metadata if draft optimization failed
            if self._optimization_draft_status:
                content["optimization_metadata"] = self._optimization_draft_status
                content["optimization_warning"] = True
                content["optimization_warning_message"] = (
                    f"Optimization engine failed with status: {self._optimization_draft_status.get('status')}. "
                    f"Using fallback session generation. This may result in different exercise selection than expected."
                )
                logger.warning(
                    f"[generate_session_exercises_offline] Added optimization failure warning to content: {self._optimization_draft_status}"
                )
            # Reset draft status for next session
            self._optimization_draft_status = None
            if session_type not in {
                SessionType.CARDIO,
                SessionType.MOBILITY,
            } and not content.get("finisher"):
                logger.info(
                    "[generate_session_exercises_offline] No finisher found, attempting to build goal finisher"
                )
                # Only build finisher if db session is available
                if db:
                    finisher = await self._build_goal_finisher_with_db(
                        goal_weights,
                        session_type=session_type,
                        intent_tags=context["session"]["intent_tags"],
                        existing_circuit_ids=used_circuit_ids,
                        db=db,
                    )
                    if finisher:
                        logger.debug(
                            f"[generate_session_exercises_offline] Successfully added finisher: {finisher.get('type', 'unknown')}"
                        )
                        content["finisher"] = finisher
                    else:
                        logger.info(
                            "[generate_session_exercises_offline] No finisher could be built"
                        )
                else:
                    logger.debug(
                        "[generate_session_exercises_offline] No db session available, skipping finisher building"
                    )

        logger.debug(
            f"[generate_session_exercises_offline] Content keys before normalization: {list(content.keys())}"
        )
        content = await self._normalize_session_content(
            content, session_type, context["session"]["intent_tags"] or [], goal_weights
        )
        logger.debug(
            f"[generate_session_exercises_offline] Content keys after normalization: {list(content.keys())}"
        )
        logger.debug(
            f"[generate_session_exercises_offline] Estimated duration: {content.get('estimated_duration_minutes', 'N/A')} minutes"
        )
        # Jerome notes generation moved to batched microcycle-level generation in program.py
        logger.debug(
            f"[generate_session_exercises_offline] RETURN - Session ID: {context['session']['id']}, Content sections: {list(content.keys())}"
        )
        logger.info("-" * 80)
        return content

    async def _save_session_exercises(
        self,
        db: AsyncSession,
        session: Session,
        content: dict[str, Any],
        movement_map: dict[str, int],
        user_id: int,
    ) -> None:
        """
        Convert content dict to SessionExercise objects and save to DB using bulk operations.
        """
        from sqlalchemy import delete

        logger.info(
            f"[_save_session_exercises] START - session_id={session.id}, session_type={session.session_type}, content_keys={list(content.keys())}, main={len(content.get('main', []))}, accessory={len(content.get('accessory') or [])}"
        )

        # Check if this is a recovery session or has intentionally empty content
        if session.session_type == SessionType.RECOVERY:
            logger.info(
                f"[_save_session_exercises] Skipping save for RECOVERY session {session.id} - these have no exercises by design"
            )
            return

        # Check if content has any exercises before processing
        total_possible_exercises = (
            len(content.get("warmup") or [])
            + len(content.get("main") or [])
            + len(content.get("accessory") or [])
            + len(content.get("cooldown") or [])
        )
        finisher = content.get("finisher")
        if finisher and isinstance(finisher, dict):
            total_possible_exercises += len(finisher.get("exercises", []))

        if total_possible_exercises == 0:
            logger.warning(
                f"[_save_session_exercises] No exercises to save for session {session.id} (type={session.session_type}), skipping save"
            )
            return

        # Clear existing exercises for this session
        await db.execute(
            delete(SessionExercise).where(SessionExercise.session_id == session.id)
        )
        logger.info(
            f"[_save_session_exercises] Cleared existing exercises for session {session.id}"
        )

        # Update finisher circuit ID based on content
        finisher = content.get("finisher")
        if finisher and isinstance(finisher, dict):
            finisher_type = finisher.get("type")
            if finisher_type == "circuit" and finisher.get("circuit_id"):
                session.finisher_circuit_id = finisher.get("circuit_id")
                session.has_circuits = True
                logger.debug(
                    f"[_save_session_exercises] Set finisher_circuit_id={session.finisher_circuit_id}"
                )
            else:
                if session.finisher_circuit_id is not None:
                    logger.debug(
                        f"[_save_session_exercises] Clearing finisher_circuit_id (was {session.finisher_circuit_id}) - finisher is not a circuit type"
                    )
                    session.finisher_circuit_id = None
        else:
            if session.finisher_circuit_id is not None:
                logger.debug(
                    f"[_save_session_exercises] Clearing finisher_circuit_id (was {session.finisher_circuit_id}) - no finisher in content"
                )
                session.finisher_circuit_id = None

        session.has_circuits = bool(session.finisher_circuit_id)
        logger.debug(
            f"[_save_session_exercises] Updated has_circuits={session.has_circuits}"
        )

        order_counter = 1
        missing_movements = []
        total_exercises = 0
        exercises_to_save = []

        # Helper to process a section
        async def process_section(section_name: str, exercise_role: ExerciseRole):
            nonlocal \
                order_counter, \
                missing_movements, \
                total_exercises, \
                exercises_to_save
            exercises = content.get(section_name)
            if not exercises:
                return

            logger.debug(
                f"[_save_session_exercises] Processing section '{section_name}' with {len(exercises)} exercises"
            )

            for ex in exercises:
                total_exercises += 1
                movement_name = ex.get("movement")
                if not movement_name:
                    continue

                movement_id = movement_map.get(movement_name)
                if not movement_id:
                    missing_movements.append(movement_name)
                    continue

                # Create SessionExercise
                session_ex = SessionExercise(
                    session_id=session.id,
                    user_id=user_id,
                    movement_id=movement_id,
                    exercise_role=exercise_role,
                    order_in_session=order_counter,
                    target_sets=ex.get("sets") if ex.get("sets") is not None else 3,
                    target_rep_range_min=ex.get("rep_range_min")
                    or (ex.get("reps") if isinstance(ex.get("reps"), int) else None),
                    target_rep_range_max=ex.get("rep_range_max")
                    or (ex.get("reps") if isinstance(ex.get("reps"), int) else None),
                    target_rpe=float(ex.get("target_rpe"))
                    if ex.get("target_rpe")
                    else None,
                    target_duration_seconds=ex.get("duration_seconds"),
                    default_rest_seconds=ex.get("rest_seconds"),
                    notes=ex.get("notes"),
                    superset_group=None,
                )

                exercises_to_save.append(session_ex)
                order_counter += 1

        await process_section("warmup", ExerciseRole.WARMUP)
        await process_section("main", ExerciseRole.MAIN)
        await process_section("accessory", ExerciseRole.ACCESSORY)
        await process_section("cooldown", ExerciseRole.COOLDOWN)

        # Handle finisher separately as it might be a dict or list
        finisher = content.get("finisher")
        if finisher:
            if isinstance(finisher, dict) and finisher.get("exercises"):
                for ex in finisher.get("exercises"):
                    total_exercises += 1
                    movement_name = ex.get("movement")
                    if not movement_name:
                        continue
                    movement_id = movement_map.get(movement_name)
                    if not movement_id:
                        missing_movements.append(movement_name)
                        continue

                    session_ex = SessionExercise(
                        session_id=session.id,
                        user_id=user_id,
                        movement_id=movement_id,
                        exercise_role=ExerciseRole.FINISHER,
                        order_in_session=order_counter,
                        target_sets=ex.get("sets") if ex.get("sets") is not None else 1,
                        target_rep_range_min=ex.get("reps")
                        if isinstance(ex.get("reps"), int)
                        else None,
                        target_rep_range_max=ex.get("reps")
                        if isinstance(ex.get("reps"), int)
                        else None,
                        target_duration_seconds=ex.get("duration_seconds"),
                        notes=ex.get("notes"),
                    )
                    exercises_to_save.append(session_ex)
                    order_counter += 1

        # Log section lengths before validation
        warmup_section = content.get("warmup", [])
        main_section = content.get("main", [])
        accessory_section = content.get("accessory", [])
        cooldown_section = content.get("cooldown", [])
        finisher_section = content.get("finisher")

        section_lengths = {
            "warmup": len(warmup_section) if warmup_section else 0,
            "main": len(main_section) if main_section else 0,
            "accessory": len(accessory_section) if accessory_section else 0,
            "cooldown": len(cooldown_section) if cooldown_section else 0,
            "finisher": len(finisher_section.get("exercises", []))
            if isinstance(finisher_section, dict) and finisher_section.get("exercises")
            else 0,
        }

        logger.debug(
            f"[_save_session_exercises] Section lengths - warmup={section_lengths['warmup']}, main={section_lengths['main']}, "
            f"accessory={section_lengths['accessory']}, cooldown={section_lengths['cooldown']}, finisher={section_lengths['finisher']}"
        )
        logger.debug(
            f"[_save_session_exercises] Missing movements: {missing_movements}"
        )
        logger.debug(f"[_save_session_exercises] Session ID: {session.id}")

        # Bulk save all exercises at once
        if exercises_to_save:
            db.add_all(exercises_to_save)
            logger.info(
                f"[_save_session_exercises] Bulk saved {len(exercises_to_save)} exercises to session {session.id}"
            )
            if exercises_to_save:
                first_ex = exercises_to_save[0]
                logger.info(
                    f"[_save_session_exercises] First exercise: {first_ex.movement_id}, role={first_ex.exercise_role}, order={first_ex.order_in_session}"
                )
        else:
            error_msg = (
                f"Cannot save session with no exercises. Session ID: {session.id}. "
                f"Section lengths - warmup: {section_lengths['warmup']}, main: {section_lengths['main']}, "
                f"accessory: {section_lengths['accessory']}, cooldown: {section_lengths['cooldown']}, "
                f"finisher: {section_lengths['finisher']}. "
                f"Missing movements: {missing_movements}"
            )
            logger.error(f"[_save_session_exercises] {error_msg}")
            raise ValueError(error_msg)

        # Validate missing movements threshold (reduced from 50% to 15% for better data integrity)
        if missing_movements and total_exercises > 0:
            missing_percentage = len(missing_movements) / total_exercises
            if missing_percentage > 0.15:
                error_msg = f"Critical: {len(missing_movements)}/{total_exercises} movements not found in database: {missing_movements[:5]}"
                logger.error(f"[_save_session_exercises] {error_msg}")
                raise ValueError(error_msg)
            else:
                logger.warning(
                    f"[_save_session_exercises] {len(missing_movements)}/{total_exercises} movements not found (below 15% threshold): {missing_movements}"
                )

    async def _calculate_session_volume(
        self, db: AsyncSession, session: Session
    ) -> dict[str, int]:
        """Helper to calculate volume after session is saved."""
        current_session_volume = {}

        # 1. Calculate from SessionExercise (Preferred)
        # Always query DB to ensure we have the latest data and avoid lazy loading issues
        # especially after a commit where the session object might be expired
        from app.models.movement import MovementMuscleMap

        result = await db.execute(
            select(SessionExercise)
            .options(
                selectinload(SessionExercise.movement)
                .selectinload(Movement.muscle_maps)
                .selectinload(MovementMuscleMap.muscle)
            )
            .where(SessionExercise.session_id == session.id)
        )
        exercises = result.scalars().all()
        logger.debug(
            f"[_calculate_session_volume] Found {len(exercises)} exercises for session {session.id}"
        )

        if exercises:
            for ex in exercises:
                if not ex.movement:
                    continue

                weight = 1
                if ex.exercise_role == ExerciseRole.MAIN:
                    weight = 3
                elif ex.exercise_role == ExerciseRole.ACCESSORY:
                    weight = 2

                # Primary muscle
                mov = ex.movement
                p_muscle = (
                    str(mov.primary_muscle.value)
                    if hasattr(mov.primary_muscle, "value")
                    else str(mov.primary_muscle)
                )
                current_session_volume[p_muscle] = (
                    current_session_volume.get(p_muscle, 0) + weight
                )

                # Secondary muscles via muscle_maps
                if mov.muscle_maps:
                    for mm in mov.muscle_maps:
                        role_val = (
                            mm.role.value if hasattr(mm.role, "value") else mm.role
                        )
                        if role_val == MuscleRole.SECONDARY.value:
                            if mm.muscle:
                                sec = mm.muscle.slug
                                current_session_volume[sec] = (
                                    current_session_volume.get(sec, 0) + (weight // 2)
                                )

        # Process finisher circuit
        from app.models.circuit import CircuitTemplate

        if session.finisher_circuit_id:
            circuit = await db.get(CircuitTemplate, session.finisher_circuit_id)
            if circuit and circuit.muscle_volume:
                for muscle, volume in circuit.muscle_volume.items():
                    current_session_volume[muscle] = current_session_volume.get(
                        muscle, 0
                    ) + (volume // 2)

        logger.debug(
            f"[_calculate_session_volume] Session {session.id} volume: {current_session_volume}"
        )
        return current_session_volume

    async def _generate_draft_session_offline(
        self,
        all_movements: list[Movement],
        session_type: SessionType,
        used_movements: list[str] | None = None,
        goal_weights: dict[str, int] | None = None,
        preferred_movement_ids: list[int] | None = None,
        excluded_movement_ids: list[int] | None = None,
        required_movement_ids: list[int] | None = None,
        max_session_duration: int | None = None,
        all_circuits: list[Any] | None = None,
    ) -> Any:
        """
        Offline version of _generate_draft_session.
        """
        filtered_movements = self._filter_movements_for_session_type(
            all_movements, session_type
        )

        # Convert to DTOs for thread safety
        solver_movements = self._to_solver_movements(filtered_movements)

        # Use circuits from context (already loaded and converted)
        circuits = all_circuits or []
        solver_circuits = self._to_solver_circuits(circuits)

        targets = self._get_muscle_targets_for_session(session_type, goal_weights)

        excluded_ids: list[int] = list(excluded_movement_ids or [])
        if used_movements:
            name_to_id = {m.name: m.id for m in all_movements}
            for name in used_movements:
                if name in name_to_id:
                    excluded_ids.append(name_to_id[name])

        req = OptimizationRequest(
            available_movements=solver_movements,
            available_circuits=solver_circuits,
            target_muscle_volumes=targets,
            max_fatigue=activity_distribution_config.or_tools_max_fatigue,
            min_stimulus=TIME_FILLING["min_stimulus"],
            user_skill_level=SkillLevel.INTERMEDIATE,
            excluded_movement_ids=excluded_ids,
            required_movement_ids=list(required_movement_ids or []),
            # Use centralized default instead of hardcoded 60
            session_duration_minutes=max_session_duration
            or get_default_session_duration(),
            allow_complex_lifts=True,
            allow_circuits=True,
            goal_weights=goal_weights,
            preferred_movement_ids=preferred_movement_ids,
        )
        # Solve in a separate thread to avoid blocking the event loop
        import asyncio

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.optimizer.solve_session, req)

    async def _load_movements_by_pattern(
        self,
        db: AsyncSession,
    ) -> dict[str, list[str]]:
        """Load all movements grouped by their primary pattern."""
        result = await db.execute(select(Movement))
        movements = list(result.scalars().all())

        by_pattern: dict[str, list[str]] = {}
        for movement in movements:
            pattern = movement.pattern if movement.pattern else "other"
            if pattern not in by_pattern:
                by_pattern[pattern] = []
            by_pattern[pattern].append(movement.name)

        return by_pattern

    async def _load_user_movement_rules_dict(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict[str, list[str]]:
        """Load user's movement preferences as a dict of movement names.

        Returns:
            Dict with keys: "avoid", "must_include", "prefer" containing lists of movement names.
        """
        result = await db.execute(
            select(UserMovementRule, Movement)
            .join(Movement, UserMovementRule.movement_id == Movement.id)
            .where(UserMovementRule.user_id == user_id)
        )
        rules = result.all()

        by_rule_type: dict[str, list[str]] = {
            "avoid": [],
            "must_include": [],
            "prefer": [],
        }

        for rule, movement in rules:
            if rule.rule_type == MovementRuleType.HARD_NO:
                by_rule_type["avoid"].append(movement.name)
            elif rule.rule_type == MovementRuleType.HARD_YES:
                by_rule_type["must_include"].append(movement.name)
            elif rule.rule_type == MovementRuleType.PREFERRED:
                by_rule_type["prefer"].append(movement.name)

        return by_rule_type

    def _validate_and_complete_session(
        self, content: dict[str, Any], session_type: SessionType
    ) -> dict[str, Any]:
        """
        Validate LLM-generated session content and add missing required sections.

        For training sessions (non-RECOVERY, non-CARDIO), ensures:
        - warmup, main, cooldown exist
        - XOR: accessory OR finisher (but NOT both)
        - NO duplicate movements within the session

        Args:
            content: LLM-generated session content
            session_type: Type of session

        Returns:
            Validated and completed session content
        """
        # Recovery sessions don't need validation (rest days)
        if session_type == SessionType.RECOVERY:
            return content

        # Check required sections for training sessions
        if not content.get("warmup") or len(content.get("warmup", [])) == 0:
            logger.warning(
                f"Missing warmup for {session_type} session, will add empty warmup"
            )
            content["warmup"] = []

        if not content.get("main") or len(content.get("main", [])) == 0:
            logger.error(
                "[_validate_and_complete_session] ERROR - Missing main section",
                extra={
                    "input_state": {
                        "session_type": session_type.value,
                        "has_main": bool(content.get("main")),
                        "main_count": len(content.get("main", [])),
                    },
                    "failure_context": {
                        "what_failed": "Session content validation",
                        "why_failed": "Main section is empty or missing",
                    },
                },
                exc_info=False,
            )
            # Use fallback for main if completely missing
            fallback = self._get_fallback_session_content(session_type)
            content["main"] = fallback.get("main", [])

        if not content.get("cooldown") or len(content.get("cooldown", [])) == 0:
            logger.warning(
                f"Missing cooldown for {session_type} session, will add empty cooldown"
            )
            content["cooldown"] = []

        # CRITICAL: Remove duplicate movements within session
        content = DuplicateRemover.remove_intra_session_duplicates(
            content, session_type
        )

        return content

    async def _build_fast_content_from_draft(
        self,
        draft_content: dict[str, Any],
        session_type: SessionType,
        intent_tags: list[str],
        is_deload: bool,
        goal_weights: dict[str, int],
        all_movements: list[Movement] = None,
        used_circuit_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        content = dict(draft_content)

        # Generate warmup and cooldown based on main exercises
        main_exercises = content.get("main", [])
        if all_movements and main_exercises:
            warmup_cooldown = self._generate_warmup_cooldown(
                session_type, main_exercises, all_movements
            )
            if not content.get("warmup") or len(content.get("warmup", [])) == 0:
                content["warmup"] = warmup_cooldown["warmup"]
            if not content.get("cooldown") or len(content.get("cooldown", [])) == 0:
                content["cooldown"] = warmup_cooldown["cooldown"]

        return await self._normalize_session_content(
            content, session_type, intent_tags, goal_weights, used_circuit_ids
        )

    async def _normalize_session_content(
        self,
        content: dict[str, Any],
        session_type: SessionType,
        intent_tags: list[str],
        goal_weights: dict[str, int],
        used_circuit_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        normalized = self._validate_and_complete_session(dict(content), session_type)
        tags = set(intent_tags or [])
        is_conditioning_only = (
            session_type == SessionType.CUSTOM and "conditioning" in tags
        )
        is_middle_piece_only = (
            session_type in {SessionType.CARDIO, SessionType.MOBILITY}
            or is_conditioning_only
        )

        if is_middle_piece_only:
            normalized["accessory"] = None
            normalized["finisher"] = None
            normalized["circuit"] = None
            return normalized

        normalized = self._validate_mutual_exclusivity(normalized)

        accessory = normalized.get("accessory")
        if accessory is not None and not isinstance(accessory, list):
            logger.error(
                f"Invalid type for 'accessory' field: {type(accessory).__name__}. Expected list or None. Value: {accessory}"
            )
            has_accessory = False
        else:
            has_accessory = bool(accessory) and len(accessory) > 0
        has_circuit = normalized.get("circuit") is not None
        has_finisher = normalized.get("finisher") is not None

        if has_circuit:
            normalized["accessory"] = None
            normalized["finisher"] = None
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized

        if has_accessory and has_finisher:
            if self._prefer_finisher(goal_weights, tags):
                normalized["accessory"] = None
            else:
                normalized["finisher"] = None
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized

        if has_finisher:
            normalized["accessory"] = None
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized

        if has_accessory:
            # If prefer_finisher tag is present, convert accessory to finisher
            if self._prefer_finisher(goal_weights, tags):
                finisher = await self._build_goal_finisher(
                    goal_weights,
                    session_type=session_type,
                    intent_tags=tags,
                    existing_circuit_ids=used_circuit_ids,
                )
                if finisher:
                    normalized["finisher"] = finisher
                    normalized["accessory"] = None
                normalized["cooldown"] = normalized.get("cooldown") or []
                return normalized
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized

        block_type = self._decide_session_block_type(session_type, tags, goal_weights)

        if block_type == "circuit":
            circuit = await self._generate_circuit_block(
                session_type, tags, goal_weights
            )
            if circuit:
                normalized["circuit"] = circuit
                normalized["accessory"] = None
                normalized["finisher"] = None
                return normalized

        finisher = await self._build_goal_finisher(
            goal_weights,
            session_type=session_type,
            intent_tags=tags,
            existing_circuit_ids=used_circuit_ids,
        )
        if finisher:
            normalized["finisher"] = finisher
            normalized["accessory"] = None
            return normalized

        normalized["accessory"] = self._get_default_accessories(session_type)
        normalized["finisher"] = None
        return normalized

    def _prefer_finisher(self, goal_weights: dict[str, int], tags: set[str]) -> bool:
        if "prefer_finisher" in tags:
            return True
        if "prefer_accessory" in tags:
            return False

        logger.warning(
            f"[_prefer_finisher] No allocation tags present. "
            f"SessionTypeDistributor must set either 'prefer_finisher' or 'prefer_accessory'. "
            f"tags={tags}. Defaulting to Accessory."
        )
        return False

    def _decide_session_block_type(
        self,
        session_type: SessionType,
        intent_tags: set[str],
        goal_weights: dict[str, int],
    ) -> str:
        """
        Decide whether a session should have a circuit block or accessory block.

        Returns:
            "circuit" if session should use circuits, "accessory" otherwise
        """
        if "prefer_circuit" in intent_tags:
            return "circuit"
        if "prefer_accessory" in intent_tags:
            return "accessory"

        is_conditioning_session = session_type in {
            SessionType.CARDIO,
            SessionType.CUSTOM,
        }
        if is_conditioning_session and "conditioning" in intent_tags:
            return "circuit"

        return "accessory"

    def _validate_mutual_exclusivity(self, content: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure session doesn't have both accessories and circuits.

        Enforces XOR logic: either accessories OR circuits, never both.
        Prioritizes circuits over accessories if both are present.

        Returns:
            Normalized content with only accessories or only circuits
        """
        accessory = content.get("accessory")
        if accessory is not None and not isinstance(accessory, list):
            logger.error(
                f"Invalid type for 'accessory' field in _validate_mutual_exclusivity: {type(accessory).__name__}. Expected list or None. Value: {accessory}"
            )
            has_accessories = False
        else:
            has_accessories = bool(accessory) and len(accessory) > 0
        has_circuit = content.get("circuit") is not None

        if has_accessories and has_circuit:
            logger.warning(
                "Session has both accessories AND circuit - removing accessories to enforce mutual exclusivity"
            )
            content["accessory"] = None

        return content

    def _validate_allocation_compliance(
        self,
        content: dict[str, Any],
        intent_tags: set[str] | list[str],
        session_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Validate that generated content matches the allocated session type.

        Enforces that:
        - prefer_finisher tag → content has finisher (which contains a circuit), no accessory
        - prefer_accessory tag → content has accessory, no finisher

        Note: finisher and circuit are the same thing (a finisher contains a circuit).
        These are naming conventions differences, not mutually exclusive blocks.

        Args:
            content: Generated session content
            intent_tags: Allocation intent tags
            session_id: Optional session ID for error logging

        Returns:
            Validated content (unchanged if compliant)

        Raises:
            ValueError: If content doesn't match allocation
        """
        if isinstance(intent_tags, list):
            intent_tags = set(intent_tags)

        has_finisher = content.get("finisher") is not None

        accessory = content.get("accessory")
        if accessory is not None and not isinstance(accessory, list):
            logger.error(
                f"Invalid type for 'accessory' field: {type(accessory).__name__}"
            )
            has_accessory = False
        else:
            has_accessory = bool(accessory) and len(accessory) > 0

        prefer_finisher = "prefer_finisher" in intent_tags
        prefer_accessory = "prefer_accessory" in intent_tags

        if prefer_finisher and prefer_accessory:
            raise ValueError(
                f"[ALLOCATION_VIOLATION_002] Session {session_id or 'unknown'} has conflicting allocation tags. "
                f"Cannot have both 'prefer_finisher' and 'prefer_accessory'. Tags: {intent_tags}"
            )

        if not prefer_finisher and not prefer_accessory:
            raise ValueError(
                f"[ALLOCATION_VIOLATION_003] Session {session_id or 'unknown'} has no allocation tags. "
                f"SessionTypeDistributor must set prefer_finisher or prefer_accessory. Tags: {intent_tags}"
            )

        if prefer_finisher:
            if has_accessory:
                raise ValueError(
                    f"[ALLOCATION_VIOLATION_004] Session {session_id or 'unknown'} allocated as FINISHER "
                    f"but content has accessory block. Tags: {intent_tags}"
                )
            if not has_finisher:
                raise ValueError(
                    f"[ALLOCATION_VIOLATION_005] Session {session_id or 'unknown'} allocated as FINISHER "
                    f"but content has no finisher block. Tags: {intent_tags}"
                )

        if prefer_accessory:
            if has_finisher:
                raise ValueError(
                    f"[ALLOCATION_VIOLATION_006] Session {session_id or 'unknown'} allocated as ACCESSORY "
                    f"but content has finisher block. Tags: {intent_tags}"
                )
            if not has_accessory:
                raise ValueError(
                    f"[ALLOCATION_VIOLATION_007] Session {session_id or 'unknown'} allocated as ACCESSORY "
                    f"but content has no accessory block. Tags: {intent_tags}"
                )

        return content

    def _get_goal_weights(
        self, program_data: Program | dict[str, Any]
    ) -> dict[str, int]:
        """
        Extract goal weights from Program object or program info dict.

        Args:
            program_data: Either a Program object or dict with goal fields

        Returns:
            Dictionary mapping goal names to their weights
        """
        goal_weights = {
            "strength": 0,
            "hypertrophy": 0,
            "endurance": 0,
            "fat_loss": 0,
            "mobility": 0,
        }

        # Handle both Program object and dict
        if isinstance(program_data, dict):
            goals = [
                (program_data["goal_1"].value, program_data["goal_weight_1"]),
                (program_data["goal_2"].value, program_data["goal_weight_2"]),
                (program_data["goal_3"].value, program_data["goal_weight_3"]),
            ]
        else:
            goals = [
                (program_data.goal_1.value, program_data.goal_weight_1),
                (program_data.goal_2.value, program_data.goal_weight_2),
                (program_data.goal_3.value, program_data.goal_weight_3),
            ]

        for goal, weight in goals:
            if goal in goal_weights:
                goal_weights[goal] += weight
        return goal_weights

    async def _build_goal_finisher(
        self,
        goal_weights: dict[str, int],
        session_type: SessionType | None = None,
        intent_tags: set[str] | None = None,
        existing_circuit_ids: list[int] | None = None,
        db: AsyncSession | None = None,
    ) -> dict[str, Any] | None:
        """Build a finisher using circuit database with similarity scoring.

        Finishers should target SAME muscles/regions as main lifts to act as a burner.
        Uses similarity scoring instead of complementarity for circuit selection.

        Args:
            goal_weights: Training goal weights
            session_type: Session type for region filtering
            intent_tags: Movement patterns from main lifts (for similarity matching)
            existing_circuit_ids: Circuits to exclude
            db: Database session (creates one if not provided)

        Returns:
            Finisher dict with circuit data, or None if no suitable circuit found
        """
        from app.db.database import async_session_maker

        # Create db session if not provided
        should_close_db = db is None
        if should_close_db:
            async with async_session_maker() as db_session:
                return await self._build_goal_finisher_with_db(
                    goal_weights,
                    session_type,
                    intent_tags,
                    existing_circuit_ids,
                    db_session,
                )
        else:
            return await self._build_goal_finisher_with_db(
                goal_weights, session_type, intent_tags, existing_circuit_ids, db
            )

    async def _build_goal_finisher_with_db(
        self,
        goal_weights: dict[str, int],
        session_type: SessionType | None,
        intent_tags: set[str] | None,
        existing_circuit_ids: list[int] | None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Build a finisher using provided database session."""
        from app.services.circuit_comparison import CircuitComparisonService

        logger.info("-" * 80)
        logger.debug(
            f"[_build_goal_finisher_with_db] ENTRY - Session Type: {session_type.value if session_type else None}"
        )
        logger.debug(
            f"[_build_goal_finisher_with_db] Intent Tags: {list(intent_tags) if intent_tags else []}"
        )
        logger.debug(
            f"[_build_goal_finisher_with_db] Existing Circuit IDs: {existing_circuit_ids or []}"
        )
        logger.debug(f"[_build_goal_finisher_with_db] Goal Weights: {goal_weights}")
        logger.info("-" * 80)

        thresholds = activity_distribution_config.goal_finisher_thresholds

        fat_loss = goal_weights.get("fat_loss", 0)
        endurance = goal_weights.get("endurance", 0)

        logger.debug(
            f"[_build_goal_finisher_with_db] Goal weights - fat_loss={fat_loss}, endurance={endurance}"
        )
        logger.debug(
            f"[_build_goal_finisher_with_db] Thresholds - fat_loss_min={thresholds.get('fat_loss_min_weight')}, endurance_min={thresholds.get('endurance_min_weight')}"
        )

        # Check if finisher should be added
        if fat_loss < int(
            thresholds.get("fat_loss_min_weight", 999)
        ) and endurance < int(thresholds.get("endurance_min_weight", 999)):
            logger.info(
                "[_build_goal_finisher_with_db] Finisher thresholds not met, generating accessory block as fallback"
            )
            # Return accessory block structure instead of None
            accessory_block = {
                "type": "accessory",
                "exercises": [],
                "reason": "Finisher thresholds not met - using accessory fallback",
            }
            return accessory_block

        # Determine circuit type based on goals
        circuit_type = "AMRAP" if fat_loss >= endurance else "EMOM"
        logger.debug(
            f"[_build_goal_finisher_with_db] Circuit type determined: {circuit_type}"
        )

        # Try to get a circuit from database using similarity scoring
        try:
            circuit_service = CircuitComparisonService(db)

            # Determine target region from session type
            target_region = (
                self._get_primary_region_for_session_type(session_type)
                if session_type
                else "full body"
            )
            logger.debug(
                f"[_build_goal_finisher_with_db] Target region mapped: {target_region}"
            )

            # Get circuit recommendations with SIMILARITY scoring
            # For finishers, we want similar muscles/regions to main lifts
            logger.info(
                "[_build_goal_finisher_with_db] CALLING CircuitComparisonService.recommend_circuits_for_session()"
            )
            logger.debug(
                f"[_build_goal_finisher_with_db] Parameters - target_regions=[{target_region}], target_patterns={list(intent_tags) if intent_tags else None}, is_finisher=True"
            )

            recommendations = await circuit_service.recommend_circuits_for_session(
                circuit_ids=None,
                exclude_circuit_ids=existing_circuit_ids,
                target_regions=[target_region],
                target_patterns=list(intent_tags) if intent_tags else None,
                difficulty_tier=None,  # Remove bronze restriction
                max_equipment=None,  # Remove equipment restriction
                limit=10,
                is_finisher=True,  # This is key - use similarity scoring
            )

            logger.debug(
                f"[_build_goal_finisher_with_db] RETURN from recommend_circuits_for_session: {len(recommendations) if recommendations else 0} recommendations"
            )

            if recommendations:
                for i, rec in enumerate(recommendations[:3]):  # Log top 3
                    logger.debug(
                        f"[_build_goal_finisher_with_db] Recommendation {i+1}: circuit_id={rec.circuit_id}, reason={rec.reason}, similarity_score={rec.similarity_score:.3f}, complementary_score={rec.complementary_score:.3f}"
                    )

            if not recommendations or len(recommendations) == 0:
                logger.info(
                    "[_build_goal_finisher_with_db] No similar circuits found for finisher, using preset"
                )
                # Fall back to preset if no circuits available
                preset_name = "fat_loss" if fat_loss >= endurance else "endurance"
                preset = dict(
                    activity_distribution_config.goal_finisher_presets.get(
                        preset_name, {}
                    )
                )
                logger.debug(
                    f"[_build_goal_finisher_with_db] Using preset: {preset_name}, content: {preset}"
                )
                return preset

            # Select top recommendation
            selected_circuit = recommendations[0]
            logger.debug(
                f"[_build_goal_finisher_with_db] Selected top recommendation: circuit_id={selected_circuit.circuit_id}, similarity_score={selected_circuit.similarity_score:.3f}"
            )

            # Build finisher dict from circuit data
            finisher = {
                "type": "circuit",
                "circuit_id": selected_circuit.circuit_id,
                "circuit_type": circuit_type,
                "name": f"{circuit_type} Finisher",
                "reason": selected_circuit.reason,
                "similarity_score": selected_circuit.similarity_score,
                "primary_region": selected_circuit.metadata.get(
                    "primary_region", "full_body"
                ),
                "difficulty_tier": selected_circuit.metadata.get("difficulty_tier", 1),
                "exercises": [],
            }

            # Load circuit exercises
            circuit_id = selected_circuit.circuit_id
            logger.debug(
                f"[_build_goal_finisher_with_db] Loading melted exercises for circuit_id={circuit_id}"
            )
            melted_exercises = await self._get_circuit_melted_exercises(db, circuit_id)
            logger.debug(
                f"[_build_goal_finisher_with_db] Loaded {len(melted_exercises)} melted exercises"
            )

            # Load movements from database to get correct names
            movement_ids = [m.movement_id for m in melted_exercises if m.movement_id]
            movement_map = {}
            if movement_ids:
                movements_result = await db.execute(
                    select(Movement).where(Movement.id.in_(movement_ids))
                )
                movements = movements_result.scalars().all()
                movement_map = {m.id: m.name for m in movements}

            for melted in melted_exercises:
                # Use movement name from database if available
                movement_name = movement_map.get(
                    melted.movement_id, melted.movement_name
                )
                exercise_data = {
                    "movement": movement_name,
                    "movement_id": melted.movement_id,
                    "sequence": melted.exercise_sequence,
                    "metric_type": melted.metric_type.value,
                    "reps": melted.reps,
                    "distance_meters": melted.distance_meters,
                    "duration_seconds": melted.duration_seconds,
                    "calories": melted.calories,
                    "rest_seconds": melted.rest_seconds,
                    "notes": melted.notes,
                }
                finisher["exercises"].append(exercise_data)

            finisher["exercises"].sort(key=lambda x: x["sequence"])

            logger.debug(
                f"[_build_goal_finisher_with_db] Built finisher with {len(finisher['exercises'])} exercises"
            )
            logger.debug(
                f"[_build_goal_finisher_with_db] Finisher type: {finisher['type']}, circuit_type: {finisher['circuit_type']}"
            )
            logger.debug(
                f"[_build_goal_finisher_with_db] Primary region: {finisher['primary_region']}, difficulty tier: {finisher['difficulty_tier']}"
            )
            logger.debug(
                f"[_build_goal_finisher_with_db] RETURN - Finisher built successfully for circuit_id={circuit_id}"
            )
            logger.info("-" * 80)
            return finisher

        except Exception as e:
            logger.error(
                "[_build_goal_finisher_with_db] ERROR - Circuit database query failed",
                extra={
                    "input_state": {
                        "session_type": session_type.value,
                        "intent_tags": list(intent_tags),
                        "fat_loss_weight": fat_loss,
                        "endurance_weight": endurance,
                        "available_circuits_count": len(recommendations)
                    if "recommendations" in locals() and recommendations
                    else 0,
                    },
                    "failure_context": {
                        "what_failed": "Circuit database query",
                        "why_failed": f"{type(e).__name__}: {str(e)}",
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                },
                exc_info=True,
            )
            # Fall back to preset
            preset_name = "fat_loss" if fat_loss >= endurance else "endurance"
            preset = dict(
                activity_distribution_config.goal_finisher_presets.get(preset_name, {})
            )
            logger.info(
                "[_build_goal_finisher_with_db] WARNING - Falling back to preset finisher",
                extra={
                    "input_state": {
                        "preset_name": preset_name,
                    },
                    "failure_context": {
                        "what_failed": "Circuit database query",
                        "why_failed": "Using preset fallback due to circuit database failure",
                    },
                },
            )
            logger.info("-" * 80)
            return preset

    async def _generate_circuit_block(
        self,
        session_type: SessionType,
        intent_tags: set[str],
        goal_weights: dict[str, int],
        db: AsyncSession | None = None,
    ) -> dict[str, Any] | None:
        """
        Generate a circuit block for session.

        Uses relaxed constraints for circuit selection (no region limits, no pattern diversity limits).
        Circuits are selected atomically - all movements in the circuit are included together.

        Args:
            session_type: Session type for region filtering
            intent_tags: Movement patterns to match
            goal_weights: Training goal weights
            db: Database session (creates one if not provided)

        Returns:
            Circuit block dict with circuit metadata and exercises, or None if no suitable circuit found
        """
        # Create db session if not provided
        should_close_db = db is None
        if should_close_db:
            from app.db.database import async_session_maker

            async with async_session_maker() as db_session:
                return await self._generate_circuit_block_with_db(
                    session_type, intent_tags, goal_weights, db_session
                )
        else:
            return await self._generate_circuit_block_with_db(
                session_type, intent_tags, goal_weights, db
            )

    async def _generate_circuit_block_with_db(
        self,
        session_type: SessionType,
        intent_tags: set[str],
        goal_weights: dict[str, int],
        db: AsyncSession,
    ) -> dict[str, Any] | None:
        """Generate a circuit block using provided database session."""
        from app.services.circuit_comparison import CircuitComparisonService
        from app.models.circuit_extended import CircuitMacro
        from app.models.circuit import CircuitTemplate

        logger.info("-" * 80)
        logger.debug(
            f"[_generate_circuit_block_with_db] ENTRY - Session Type: {session_type.value}"
        )
        logger.debug(
            f"[_generate_circuit_block_with_db] Intent Tags: {list(intent_tags) if intent_tags else []}"
        )
        logger.debug(f"[_generate_circuit_block_with_db] Goal Weights: {goal_weights}")
        logger.info("-" * 80)

        try:
            circuit_service = CircuitComparisonService(db)

            # Get circuit recommendations
            target_region = self._get_primary_region_for_session_type(session_type)
            logger.debug(
                f"[_generate_circuit_block_with_db] Target region mapped: {target_region}"
            )
            logger.info(
                "[_generate_circuit_block_with_db] CALLING CircuitComparisonService.recommend_circuits_for_session()"
            )
            logger.debug(
                f"[_generate_circuit_block_with_db] Parameters - target_regions=[{target_region}], target_patterns={list(intent_tags) if intent_tags else None}, is_finisher=False"
            )

            recommendations = await circuit_service.recommend_circuits_for_session(
                circuit_ids=None,
                target_regions=[target_region],
                target_patterns=list(intent_tags) if intent_tags else None,
                difficulty_tier=None,
                max_equipment=None,
                limit=10,
                is_finisher=False,  # Circuit blocks use complementarity
            )

            logger.debug(
                f"[_generate_circuit_block_with_db] RETURN from recommend_circuits_for_session: {len(recommendations) if recommendations else 0} recommendations"
            )

            if recommendations:
                for i, rec in enumerate(recommendations[:3]):  # Log top 3
                    logger.debug(
                        f"[_generate_circuit_block_with_db] Recommendation {i+1}: circuit_id={rec.circuit_id}, reason={rec.reason}, similarity_score={rec.similarity_score:.3f}, complementary_score={rec.complementary_score:.3f}"
                    )

            if not recommendations or len(recommendations) == 0:
                logger.debug(
                    f"[_generate_circuit_block_with_db] No circuit recommendations found for {session_type} session, returning None"
                )
                logger.info("-" * 80)
                return None

            selected_circuit = recommendations[0]
            circuit_id = selected_circuit.circuit_id
            logger.debug(
                f"[_generate_circuit_block_with_db] Selected top recommendation: circuit_id={circuit_id}, complementary_score={selected_circuit.complementary_score:.3f}"
            )

            # Fetch full circuit details from database
            logger.debug(
                f"[_generate_circuit_block_with_db] Fetching full circuit details for circuit_id={circuit_id}"
            )
            stmt = (
                select(CircuitTemplate, CircuitMacro)
                .join(CircuitMacro, CircuitTemplate.id == CircuitMacro.circuit_id)
                .where(CircuitTemplate.id == circuit_id)
            )

            result = await db.execute(stmt)
            circuit_row = result.first()

            if not circuit_row:
                logger.error(
                    f"[_generate_circuit_block_with_db] Circuit {circuit_id} not found in database"
                )
                logger.info("-" * 80)
                return None

            circuit_template, circuit_macro = circuit_row
            logger.debug(
                f"[_generate_circuit_block_with_db] Found circuit: name='{circuit_template.name}', type={circuit_template.circuit_type}, primary_region={circuit_macro.primary_region.value}"
            )

            circuit_data = {
                "circuit_id": circuit_id,
                "name": circuit_template.name,
                "circuit_type": circuit_template.circuit_type,
                "difficulty_tier": circuit_macro.difficulty_tier,
                "estimated_duration_seconds": circuit_macro.estimated_duration_seconds,
                "default_rounds": circuit_macro.default_rounds,
                "primary_region": circuit_macro.primary_region,
                "primary_muscles": circuit_macro.primary_muscles,
                "fatigue_factor": circuit_macro.fatigue_factor,
                "stimulus_factor": circuit_macro.stimulus_factor,
                "exercises": [],
            }

            melted_exercises = await self._get_circuit_melted_exercises(db, circuit_id)
            logger.debug(
                f"[_generate_circuit_block_with_db] Loaded {len(melted_exercises)} melted exercises"
            )

            # Load movements from database to get correct names
            movement_ids = [m.movement_id for m in melted_exercises if m.movement_id]
            movement_map = {}
            if movement_ids:
                movements_result = await db.execute(
                    select(Movement).where(Movement.id.in_(movement_ids))
                )
                movements = movements_result.scalars().all()
                movement_map = {m.id: m.name for m in movements}

            for melted in melted_exercises:
                # Use movement name from database if available
                movement_name = movement_map.get(
                    melted.movement_id, melted.movement_name
                )
                exercise_data = {
                    "movement": movement_name,
                    "movement_id": melted.movement_id,
                    "sequence": melted.exercise_sequence,
                    "metric_type": melted.metric_type.value,
                    "reps": melted.reps,
                    "distance_meters": melted.distance_meters,
                    "duration_seconds": melted.duration_seconds,
                    "calories": melted.calories,
                    "rest_seconds": melted.rest_seconds,
                    "notes": melted.notes,
                }
                circuit_data["exercises"].append(exercise_data)

            circuit_data["exercises"].sort(key=lambda x: x["sequence"])

            logger.debug(
                f"[_generate_circuit_block_with_db] Built circuit block with {len(circuit_data['exercises'])} exercises"
            )
            logger.debug(
                f"[_generate_circuit_block_with_db] Circuit block details: name='{circuit_data['name']}', primary_region={circuit_data['primary_region'].value}, difficulty_tier={circuit_data['difficulty_tier']}"
            )
            logger.debug(
                f"[_generate_circuit_block_with_db] RETURN - Circuit block built successfully for circuit_id={circuit_id}"
            )
            logger.info("-" * 80)
            return circuit_data

        except Exception as e:
            logger.error(
                "[_generate_circuit_block_with_db] ERROR - Circuit block generation failed",
                extra={
                    "input_state": {
                        "session_type": session_type.value,
                        "intent_tags": list(intent_tags),
                        "goal_weights": goal_weights,
                        "primary_region": target_region,
                    },
                    "failure_context": {
                        "what_failed": "Circuit block generation",
                        "why_failed": f"{type(e).__name__}: {str(e)}",
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                },
                exc_info=True,
            )
            logger.info("-" * 80)
            return None

    def _get_primary_region_for_session_type(self, session_type: SessionType) -> str:
        """Map session type to primary circuit region."""
        region_map = {
            SessionType.UPPER: "upper body",
            SessionType.LOWER: "lower body",
            SessionType.PUSH: "upper body",
            SessionType.PULL: "upper body",
            SessionType.FULL_BODY: "full body",
            SessionType.CARDIO: "full body",
            SessionType.CUSTOM: "full body",
        }
        region = region_map.get(session_type, "full body")
        logger.debug(
            f"[_get_primary_region_for_session_type] Session Type: {session_type.value} -> Region: {region}"
        )
        return region

    async def _get_circuit_melted_exercises(self, db: AsyncSession, circuit_id: int):
        """Get melted exercises for a circuit using async database session."""
        try:
            from app.models.circuit_extended import CircuitMelted
            from sqlalchemy import select

            stmt = (
                select(CircuitMelted)
                .where(CircuitMelted.circuit_id == circuit_id)
                .order_by(CircuitMelted.exercise_sequence)
            )

            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                "[_get_circuit_melted_exercises] ERROR - Circuit melted exercises query failed",
                extra={
                    "input_state": {
                        "circuit_id": circuit_id,
                    },
                    "failure_context": {
                        "what_failed": "Circuit melted exercises database query",
                        "why_failed": f"{type(e).__name__}: {str(e)}",
                        "exception_type": type(e).__name__,
                        "exception_message": str(e),
                    },
                },
                exc_info=True,
            )
            return []

    def _get_fast_special_session_content(
        self,
        session_type: SessionType,
        max_session_duration: int | None,
        all_movements: list[Movement] = None,
    ) -> dict[str, Any]:
        # Use centralized default instead of hardcoded 30
        total_minutes = max_session_duration or get_default_session_duration()
        warmup = []
        cooldown = []

        if session_type == SessionType.MOBILITY:
            # Generate mobility session content from database movements
            mobility_movements = [
                m
                for m in (all_movements or [])
                if m.pattern and m.pattern.value in ["mobility", "stretch"]
            ]
            main = []
            if mobility_movements:
                main = [
                    {
                        "movement": mobility_movements[0].name,
                        "duration_seconds": 600,
                        "notes": "Full body mobility",
                    },
                ]
                if len(mobility_movements) > 1:
                    main.append(
                        {
                            "movement": mobility_movements[1].name,
                            "duration_seconds": max(300, total_minutes * 60),
                            "notes": "Mobility flow",
                        }
                    )
            else:
                main = [
                    {
                        "movement": "Generation Failed - No mobility movements found",
                        "duration_seconds": 300,
                        "notes": "Add mobility movements to database",
                    }
                ]

            # Generate cooldown based on main
            if all_movements:
                warmup_cooldown = self._generate_warmup_cooldown(
                    session_type, main, all_movements
                )
                warmup = warmup_cooldown["warmup"]
                cooldown = warmup_cooldown["cooldown"]

            return {
                "warmup": warmup,
                "main": main,
                "accessory": None,
                "finisher": None,
                "cooldown": cooldown,
                "estimated_duration_minutes": total_minutes,
                "reasoning": "Optimization-first mobility session",
            }

        # Cardio session - use multiple cardio/conditioning movements with distributed time
        cardio_patterns = ["cardio", "conditioning"]
        cardio_movements = [
            m
            for m in (all_movements or [])
            if m.pattern and m.pattern.value in cardio_patterns
        ]
        if cardio_movements:
            # Use 1-3 movements depending on total duration
            num_exercises = min(3, max(1, len(cardio_movements)))
            if total_minutes >= 60:
                num_exercises = max(
                    2, num_exercises
                )  # Use at least 2 for 60+ min sessions

            # Calculate base duration with proper rounding
            base_duration_seconds = round((total_minutes * 60) / num_exercises)

            main = []
            for i in range(min(num_exercises, len(cardio_movements))):
                m = cardio_movements[i]
                # Distribute any remainder to the first exercise
                if i == 0:
                    remainder_seconds = (total_minutes * 60) - (
                        base_duration_seconds * num_exercises
                    )
                    duration = base_duration_seconds + remainder_seconds
                else:
                    duration = base_duration_seconds
                main.append(
                    {
                        "movement": m.name,
                        "duration_seconds": duration,
                        "notes": f"Cardio exercise {i + 1}",
                    }
                )
        else:
            main = [
                {
                    "movement": "Generation Failed - No cardio movements found",
                    "duration_seconds": 300,
                    "notes": "Add cardio movements to database",
                }
            ]

        # Generate warmup/cooldown based on main
        if all_movements:
            warmup_cooldown = self._generate_warmup_cooldown(
                session_type, main, all_movements
            )
            warmup = warmup_cooldown["warmup"]
            cooldown = warmup_cooldown["cooldown"]

        return {
            "warmup": warmup,
            "main": main,
            "accessory": None,
            "finisher": None,
            "cooldown": cooldown,
            "estimated_duration_minutes": total_minutes,
            "reasoning": "Optimization-first cardio session",
        }

    def _get_fast_conditioning_session_content(
        self,
        conditioning_movement_names: list[str],
        max_session_duration: int | None,
        all_movements: list[Movement] = None,
    ) -> dict[str, Any]:
        # Use centralized default instead of hardcoded 45
        total_minutes = max_session_duration or get_default_session_duration()
        main_minutes = max(30, total_minutes)
        warmup = []
        cooldown = []

        candidates = list(dict.fromkeys(conditioning_movement_names or []))

        # Get actual movement objects from database
        if all_movements:
            valid_movements = []
            for name in candidates:
                movement = next((m for m in all_movements if m.name == name), None)
                if movement:
                    valid_movements.append(movement)
            candidates = [m.name for m in valid_movements]

        if len(candidates) < 5:
            # Add conditioning movements from database
            conditioning_patterns = ["conditioning", "cardio", "sled", "carry", "rope"]
            conditioning_db = [
                m
                for m in (all_movements or [])
                if m.pattern and m.pattern.value in conditioning_patterns
            ]
            for m in conditioning_db:
                if m.name not in candidates:
                    candidates.append(m.name)
            candidates = list(dict.fromkeys(candidates))

        selected = candidates[: max(5, min(8, len(candidates)))]
        per_station_seconds = max(120, int((main_minutes * 60) / max(5, len(selected))))
        main = [
            {
                "movement": name,
                "duration_seconds": per_station_seconds,
                "notes": "Conditioning station",
            }
            for name in selected
        ]

        # Generate warmup/cooldown based on main
        if all_movements:
            warmup_cooldown = self._generate_warmup_cooldown(
                SessionType.CUSTOM, main, all_movements
            )
            warmup = warmup_cooldown["warmup"]
            cooldown = warmup_cooldown["cooldown"]

        return {
            "warmup": warmup,
            "main": main,
            "accessory": None,
            "finisher": None,
            "cooldown": cooldown,
            "estimated_duration_minutes": total_minutes,
            "reasoning": "Optimization-first conditioning session",
        }

    def _get_conditioning_movement_names(self, movements: list[Movement]) -> list[str]:
        names: list[str] = []
        for m in movements:
            pattern = str(getattr(m, "pattern", "") or "")
            tags = getattr(m, "tags", []) or []
            if pattern == "conditioning" or (
                isinstance(tags, list) and "conditioning" in tags
            ):
                if getattr(m, "name", None):
                    names.append(m.name)
        return names

    def _get_default_accessories(
        self, session_type: SessionType
    ) -> list[dict[str, Any]]:
        """
        Get default accessory exercises based on session type.

        Args:
            session_type: Type of session

        Returns:
            List of accessory exercises
        """
        # Convert SessionType enum to string key format: SessionType.UPPER -> "SessionType.UPPER"
        key = f"SessionType.{session_type.value.upper()}"
        return DEFAULT_ACCESSORIES.get(
            key, DEFAULT_ACCESSORIES.get("SessionType.UPPER", [])
        )

    def _get_recovery_session_content(self) -> dict[str, Any]:
        """Return content for a rest/recovery day."""
        return {
            "warmup": [],
            "main": [],
            "accessory": [],
            "finisher": None,
            "cooldown": [],
            "estimated_duration_minutes": 0,
            "reasoning": "Rest day - no exercises.",
        }

    def _get_smart_fallback_session_content(
        self,
        session_type: SessionType,
        intent_tags: list[str],
        movements_by_pattern: dict[str, list[str]],
        used_movements: list[str] | None = None,
        all_movements: list[Movement] = None,
        max_session_duration: int | None = None,
    ) -> dict[str, Any]:
        """
        Return intelligent fallback content when LLM fails.

        Uses movement library and intent_tags to select real exercises
        instead of generic placeholders.

        Args:
            session_type: Type of session (FULL_BODY, UPPER, LOWER, etc.)
            intent_tags: Movement patterns for this session (e.g., ["squat", "horizontal_push"])
                         Also includes allocation tags like "prefer_finisher" or "prefer_accessory"
            movements_by_pattern: Dict mapping pattern names to available movements
            used_movements: List of movements to avoid (already used in microcycle)
            max_session_duration: Target session duration in minutes (for scaling exercises)

        Returns:
            Session content dict with real movement names
        """
        from app.services.time_estimation import TimeEstimationService

        # Check allocation tags to determine if we should generate finisher or accessory
        prefer_finisher = "prefer_finisher" in intent_tags
        prefer_accessory = "prefer_accessory" in intent_tags

        # Filter intent tags to only movement patterns (not allocation tags)
        movement_tags = [
            tag
            for tag in intent_tags
            if tag not in ("prefer_finisher", "prefer_accessory")
        ]

        # Preferred accessory movements by pattern
        preferred_accessories = {
            "squat": ["Leg Extension", "Leg Curl", "Calf Raise", "Walking Lunge"],
            "hinge": ["Leg Curl", "Leg Extension", "Hip Thrust", "Back Extension"],
            "lunge": ["Leg Extension", "Calf Raise", "Split Squat", "Step Up"],
            "horizontal_push": ["Lateral Raise", "Face Pull", "Tricep Pushdown", "Fly"],
            "horizontal_pull": [
                "Bicep Curl",
                "Face Pull",
                "Rear Delt Fly",
                "Hammer Curl",
            ],
            "vertical_push": [
                "Lateral Raise",
                "Face Pull",
                "Tricep Extension",
                "Upright Row",
            ],
            "vertical_pull": ["Bicep Curl", "Hammer Curl", "Preacher Curl", "Shrug"],
        }

        # Build main exercises from movement tags
        main_exercises = []
        # Initialize set with passed movements
        used_movements_set = set(used_movements) if used_movements else set()

        for tag in movement_tags[:3]:  # Max 3 main lifts
            if tag in movements_by_pattern and movements_by_pattern[tag]:
                # Find an unused movement for this pattern
                for movement_name in movements_by_pattern[tag]:
                    if movement_name not in used_movements_set:
                        main_exercises.append(
                            {
                                "movement": movement_name,
                                "sets": 4,
                                "rep_range_min": 6,
                                "rep_range_max": 10,
                                "target_rpe": 7,
                                "rest_seconds": 120,
                            }
                        )
                        used_movements_set.add(movement_name)
                        break

        # If we couldn't build main exercises, fall back to hardcoded
        if not main_exercises:
            logger.error(
                "[_get_smart_fallback_session_content] ERROR - Pattern matching failed for all intent tags",
                extra={
                    "input_state": {
                        "session_type": session_type.value,
                        "intent_tags": intent_tags,
                        "movement_tags": movement_tags,
                        "prefer_finisher": prefer_finisher,
                        "prefer_accessory": prefer_accessory,
                        "movements_by_pattern_keys": list(movements_by_pattern.keys()),
                        "used_movements_count": len(used_movements_set)
                        if used_movements_set
                        else 0,
                        "max_session_duration": max_session_duration,
                    },
                    "failure_context": {
                        "what_failed": "Smart fallback pattern matching",
                        "why_failed": "No matching movements found for any intent tags",
                    },
                },
                exc_info=False,
            )
            return self._get_fallback_session_content(session_type, all_movements)

        # Initialize finisher and accessory blocks
        finisher_block = None
        accessory_exercises = []

        # Build either finisher or accessories based on allocation tags
        if prefer_finisher:
            # Generate a circuit/finisher block
            # Use conditioning/cardio movements if available, otherwise create metabolic finisher
            finisher_movements = []
            conditioning_patterns = ["conditioning", "cardio", "plyometric", "mobility"]

            # Look for conditioning-style movements first
            for pattern in conditioning_patterns:
                if pattern in movements_by_pattern and movements_by_pattern[pattern]:
                    for movement_name in movements_by_pattern[pattern][
                        :2
                    ]:  # Take up to 2
                        if movement_name not in used_movements_set:
                            finisher_movements.append(
                                {
                                    "movement": movement_name,
                                    "reps": 10,
                                    "rest_seconds": 30,
                                }
                            )
                            used_movements_set.add(movement_name)

            # If no conditioning movements found, create a metabolic finisher from compound movements
            if not finisher_movements:
                for tag in movement_tags[:2]:
                    if tag in movements_by_pattern and movements_by_pattern[tag]:
                        for movement_name in movements_by_pattern[tag]:
                            if movement_name not in used_movements_set:
                                finisher_movements.append(
                                    {
                                        "movement": movement_name,
                                        "reps": 8,
                                        "rest_seconds": 30,
                                    }
                                )
                                used_movements_set.add(movement_name)
                                break

            if finisher_movements:
                finisher_block = {
                    "type": "circuit",
                    "circuit_type": "AMRAP",
                    "name": "Smart Fallback Finisher",
                    "duration_minutes": 8,
                    "exercises": finisher_movements,
                }
        elif prefer_accessory:
            # Build accessory exercises based on primary patterns
            for tag in movement_tags[:2]:  # Accessories for first 2 patterns
                if tag in preferred_accessories:
                    for acc_name in preferred_accessories[tag]:
                        if acc_name not in used_movements_set:
                            accessory_exercises.append(
                                {
                                    "movement": acc_name,
                                    "sets": 3,
                                    "rep_range_min": 10,
                                    "rep_range_max": 15,
                                    "target_rpe": 7,
                                    "rest_seconds": 60,
                                }
                            )
                            used_movements_set.add(acc_name)
                            break
        else:
            # No allocation tag - default to accessories for backward compatibility
            for tag in movement_tags[:2]:  # Accessories for first 2 patterns
                if tag in preferred_accessories:
                    for acc_name in preferred_accessories[tag]:
                        if acc_name not in used_movements_set:
                            accessory_exercises.append(
                                {
                                    "movement": acc_name,
                                    "sets": 3,
                                    "rep_range_min": 10,
                                    "rep_range_max": 15,
                                    "target_rpe": 7,
                                    "rest_seconds": 60,
                                }
                            )
                            used_movements_set.add(acc_name)
                            break

        # Generate warmup and cooldown based on main exercises
        warmup_cooldown = self._generate_warmup_cooldown(
            session_type, main_exercises, all_movements
        )

        # Scale exercises to fit within max_session_duration if provided
        if max_session_duration and (
            main_exercises or accessory_exercises or finisher_block
        ):
            time_service = TimeEstimationService()
            time_budget_minutes = max_session_duration

            current_duration = time_service.estimate_session_time_with_transitions(
                warmup=[],
                main=main_exercises,
                accessory=accessory_exercises if accessory_exercises else None,
                circuit=finisher_block if finisher_block else None,
                finisher=finisher_block if finisher_block else None,
                cooldown=[],
                block_order=["main", "accessory"]
                if accessory_exercises
                else ["main", "finisher"],
            )
            estimated_duration_minutes = current_duration.total_minutes

            if estimated_duration_minutes > time_budget_minutes:
                scale_factor = time_budget_minutes / estimated_duration_minutes
                for ex in main_exercises:
                    ex["sets"] = max(1, int(ex["sets"] * scale_factor))
                for ex in accessory_exercises:
                    ex["sets"] = max(1, int(ex["sets"] * scale_factor))

        # Use TimeEstimationService for accurate duration calculation
        time_service = TimeEstimationService()

        # Calculate accurate duration using TimeEstimationService
        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=warmup_cooldown["warmup"],
            main=main_exercises,
            accessory=accessory_exercises if accessory_exercises else None,
            circuit=finisher_block if finisher_block else None,
            finisher=finisher_block if finisher_block else None,
            cooldown=warmup_cooldown["cooldown"],
            intent="hypertrophy",  # Default intent
        )

        # Build reasoning message
        allocation_type = (
            "finisher"
            if prefer_finisher
            else "accessory"
            if prefer_accessory
            else "accessory (default)"
        )
        reasoning = f"Smart fallback session - LLM unavailable. Selected exercises based on {', '.join(movement_tags)} patterns. Using {allocation_type} block."

        return {
            "warmup": warmup_cooldown["warmup"],
            "main": main_exercises,
            "accessory": accessory_exercises if accessory_exercises else None,
            "finisher": finisher_block,
            "cooldown": warmup_cooldown["cooldown"],
            "estimated_duration_minutes": estimated_duration.total_minutes,
            "reasoning": reasoning,
        }

    def _get_fallback_session_content(
        self, session_type: SessionType, available_movements: list[Movement] = None
    ) -> dict[str, Any]:
        """Return basic fallback content when smart fallback also fails."""
        # Basic fallback based on session type
        fallbacks = {
            SessionType.UPPER: {
                "main": [
                    {
                        "movement": "Barbell Bench Press",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 120,
                    },
                    {
                        "movement": "Barbell Row",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 120,
                    },
                    {
                        "movement": "Overhead Press",
                        "sets": 3,
                        "rep_range_min": 8,
                        "rep_range_max": 10,
                        "target_rpe": 7,
                        "rest_seconds": 90,
                    },
                ],
                "accessory": [
                    {
                        "movement": "Lateral Raise",
                        "sets": 3,
                        "rep_range_min": 12,
                        "rep_range_max": 15,
                        "target_rpe": 7,
                        "rest_seconds": 60,
                    },
                    {
                        "movement": "Bicep Curl",
                        "sets": 3,
                        "rep_range_min": 10,
                        "rep_range_max": 12,
                        "target_rpe": 7,
                        "rest_seconds": 60,
                    },
                ],
                "finisher": None,
                "reasoning": "Fallback upper body session - LLM generation failed.",
            },
            SessionType.LOWER: {
                "main": [
                    {
                        "movement": "Back Squat",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 150,
                    },
                    {
                        "movement": "Romanian Deadlift",
                        "sets": 4,
                        "rep_range_min": 8,
                        "rep_range_max": 10,
                        "target_rpe": 7,
                        "rest_seconds": 120,
                    },
                ],
                "accessory": [
                    {
                        "movement": "Walking Lunge",
                        "sets": 3,
                        "rep_range_min": 10,
                        "rep_range_max": 12,
                        "target_rpe": 7,
                        "rest_seconds": 90,
                    },
                    {
                        "movement": "Leg Curl",
                        "sets": 3,
                        "rep_range_min": 10,
                        "rep_range_max": 12,
                        "target_rpe": 7,
                        "rest_seconds": 60,
                    },
                ],
                "finisher": None,
                "reasoning": "Fallback lower body session - LLM generation failed.",
            },
            SessionType.FULL_BODY: {
                "main": [
                    {
                        "movement": "Back Squat",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 150,
                    },
                    {
                        "movement": "Barbell Bench Press",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 120,
                    },
                    {
                        "movement": "Barbell Row",
                        "sets": 4,
                        "rep_range_min": 6,
                        "rep_range_max": 8,
                        "target_rpe": 7.5,
                        "rest_seconds": 120,
                    },
                ],
                "accessory": [
                    {
                        "movement": "Lateral Raise",
                        "sets": 3,
                        "rep_range_min": 12,
                        "rep_range_max": 15,
                        "target_rpe": 7,
                        "rest_seconds": 60,
                    },
                    {
                        "movement": "Leg Curl",
                        "sets": 3,
                        "rep_range_min": 10,
                        "rep_range_max": 12,
                        "target_rpe": 7,
                        "rest_seconds": 60,
                    },
                ],
                "finisher": None,
                "reasoning": "Fallback full body session - LLM generation failed.",
            },
        }

        # Default fallback for other session types (PPL, etc.)
        default = {
            "main": [
                {
                    "movement": "Back Squat",
                    "sets": 4,
                    "rep_range_min": 8,
                    "rep_range_max": 10,
                    "target_rpe": 7,
                    "rest_seconds": 120,
                },
                {
                    "movement": "Barbell Bench Press",
                    "sets": 4,
                    "rep_range_min": 8,
                    "rep_range_max": 10,
                    "target_rpe": 7,
                    "rest_seconds": 120,
                },
            ],
            "accessory": [
                {
                    "movement": "Lateral Raise",
                    "sets": 3,
                    "rep_range_min": 12,
                    "rep_range_max": 15,
                    "target_rpe": 7,
                    "rest_seconds": 60,
                },
            ],
            "finisher": None,
            "reasoning": "Fallback session - LLM generation failed.",
        }

        fallback_content = fallbacks.get(session_type, default)

        # Add warmup/cooldown if we have available movements
        if available_movements:
            warmup_cooldown = self._generate_warmup_cooldown(
                session_type, fallback_content["main"], available_movements
            )
            fallback_content["warmup"] = warmup_cooldown["warmup"]
            fallback_content["cooldown"] = warmup_cooldown["cooldown"]
        else:
            fallback_content["warmup"] = []
            fallback_content["cooldown"] = []

        # Use TimeEstimationService for accurate duration calculation
        from app.services.time_estimation import TimeEstimationService

        time_service = TimeEstimationService()

        # Calculate accurate duration using TimeEstimationService
        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=fallback_content["warmup"],
            main=fallback_content["main"],
            accessory=fallback_content.get("accessory"),
            circuit=None,
            finisher=None,
            cooldown=fallback_content["cooldown"],
            intent="hypertrophy",  # Default intent
        )

        fallback_content[
            "estimated_duration_minutes"
        ] = estimated_duration.total_minutes

        return fallback_content

    async def _load_all_movements(self, db: AsyncSession) -> list[Movement]:
        """Load all movements from the database."""
        result = await db.execute(select(Movement))
        movements = list(result.scalars().all())
        logger.debug(f"[_load_all_movements] Loaded {len(movements)} movements")
        return movements

    async def _load_all_circuits(self, db: AsyncSession) -> list[SolverCircuit]:
        """Load all circuits and convert to SolverCircuit format."""
        from app.services.optimization import SolverCircuit
        from app.models.circuit import CircuitTemplate
        from app.models.circuit_extended import CircuitMacro

        # Load circuits with macro data
        stmt = select(CircuitTemplate, CircuitMacro).join(
            CircuitMacro, CircuitTemplate.id == CircuitMacro.circuit_id
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            SolverCircuit(
                id=c.id,
                name=c.name,
                primary_muscle=self._get_circuit_primary_muscle(c),
                fatigue_factor=c.fatigue_factor if c.fatigue_factor else 1.0,
                stimulus_factor=c.stimulus_factor if c.stimulus_factor else 1.0,
                effective_work_volume=c.effective_work_volume
                if c.effective_work_volume
                else 0.0,
                circuit_type=c.circuit_type,
                duration_seconds=c.estimated_work_seconds
                if c.estimated_work_seconds
                else 600,
                primary_region=macro.primary_region.value if macro else None,
                pattern_diversity_score=macro.pattern_diversity_score if macro else 0.0,
                equipment_complexity=macro.equipment_complexity if macro else 0,
            )
            for c, macro in rows
        ]

    async def _populate_circuit_block(
        self,
        db: AsyncSession,
        circuit_id: int,
        session_id: int,
        user_id: int,
        order_offset: int,
        exercise_role: ExerciseRole,
    ) -> tuple[list[dict], dict[str, Any]]:
        """
        Populate a circuit block by loading ALL circuit movements in correct order.

        Returns:
            - List of exercise dictionaries (one per circuit movement)
            - Circuit metadata dict with duration info
        """
        from app.models.circuit_extended import CircuitMacro

        # Load circuit with melted exercises and macro metrics
        stmt = (
            select(CircuitTemplate, CircuitMelted, CircuitMacro)
            .join(CircuitMelted, CircuitTemplate.id == CircuitMelted.circuit_id)
            .outerjoin(CircuitMacro, CircuitTemplate.id == CircuitMacro.circuit_id)
            .where(CircuitTemplate.id == circuit_id)
            .order_by(CircuitMelted.exercise_sequence)
        )

        result = await db.execute(stmt)
        rows = result.all()

        if not rows:
            logger.warning(
                f"[SessionGeneratorService._populate_circuit_block] No movements found for circuit_id={circuit_id}"
            )
            return [], {}

        circuit_meta = {}
        exercises = []
        for circuit, melted, macro in rows:
            if not circuit_meta:
                circuit_meta = {
                    "estimated_duration_seconds": macro.estimated_duration_seconds
                    if macro
                    else circuit.default_duration_seconds,
                    "default_duration_seconds": circuit.default_duration_seconds,
                    "default_rounds": macro.default_rounds
                    if macro
                    else circuit.default_rounds,
                    "circuit_type": circuit.circuit_type.value
                    if hasattr(circuit.circuit_type, "value")
                    else circuit.circuit_type,
                }

            exercise = {
                "movement_id": melted.movement_id,
                "movement_name": melted.movement_name,
                "metric_type": melted.metric_type.value
                if melted.metric_type
                else "reps",
                "sets": melted.reps if melted.reps else 1,
                "reps": melted.reps if melted.reps else None,
                "distance_meters": melted.distance_meters
                if melted.distance_meters
                else None,
                "duration_seconds": melted.duration_seconds
                if melted.duration_seconds
                else None,
                "calories": melted.calories if melted.calories else None,
                "rest_seconds": melted.rest_seconds if melted.rest_seconds else 0,
                "notes": melted.notes,
                "exercise_role": exercise_role.value,
                "order_in_session": order_offset + len(exercises) + 1,
            }
            exercises.append(exercise)

        logger.info(
            f"[SessionGeneratorService._populate_circuit_block] Loaded {len(exercises)} movements for circuit_id={circuit_id}"
        )
        return exercises, circuit_meta

    def _get_circuit_primary_muscle(self, circuit: CircuitTemplate) -> str:
        """Determine the primary muscle for a circuit based on muscle_volume."""
        if circuit.muscle_volume:
            sorted_muscles = sorted(
                circuit.muscle_volume.items(), key=lambda x: x[1], reverse=True
            )
            if sorted_muscles:
                return sorted_muscles[0][0]  # muscle with highest volume
        return "full_body"  # fallback

    def _detect_session_template(self, session: Session) -> str:
        """
        Detect which block template to use for a session.

        Templates:
        - Template 1: Normal lifting (warmup → main lifts → circuits → cooldown)
        - Template 2: Cardio day (warmup → 1-3 cardio movements → cooldown)
        - Template 3: Conditioning day (warmup → 4-6 conditioning movements → cooldown)
        - Template 4: Mobility only day (warmup → 8-12 mobility movements → cooldown)

        Returns:
            Template name: "normal", "cardio", "conditioning", or "mobility"
        """
        session_type = session.session_type
        intent_tags = session.intent_tags or []

        logger.info(
            f"[SessionGeneratorService._detect_session_template] Session type={session_type}, intent_tags={intent_tags}"
        )

        # Template 2: Cardio day
        if session_type == SessionType.CARDIO or "cardio" in intent_tags:
            logger.info(
                "[SessionGeneratorService._detect_session_template] Using Template 2: Cardio day"
            )
            return "cardio"

        # Template 3: Conditioning day
        if session_type == SessionType.RECOVERY or "conditioning" in intent_tags:
            logger.info(
                "[SessionGeneratorService._detect_session_template] Using Template 3: Conditioning day"
            )
            return "conditioning"

        # Template 4: Mobility only day
        if session_type == SessionType.MOBILITY or any(
            tag in ["mobility", "stretch"] for tag in intent_tags
        ):
            logger.info(
                "[SessionGeneratorService._detect_session_template] Using Template 4: Mobility only day"
            )
            return "mobility"

        # Template 1: Normal lifting (default)
        # Structure: warmup → main lifts → accessories → cooldown
        # - finisher_circuit_id: finisher circuit added in addition to main + accessories
        has_finisher_circuit = (
            hasattr(session, "finisher_circuit_id")
            and session.finisher_circuit_id is not None
        )

        if has_finisher_circuit:
            logger.info(
                "[SessionGeneratorService._detect_session_template] Using Template 1: Normal lifting with finisher circuit (in addition to accessories)"
            )
        else:
            logger.info(
                "[SessionGeneratorService._detect_session_template] Using Template 1: Normal lifting (standard accessories)"
            )

        return "normal"

    def _get_block_order_for_template(self, template: str) -> list[str]:
        """
        Get block order for a given template.

        Args:
            template: Template name ("normal", "cardio", "conditioning", "mobility")

        Returns:
            List of block types in order (e.g., ["warmup", "main", "circuit", "cooldown"])
        """
        if template == "normal":
            # Template 1: warmup → main lifts → circuit OR accessories → cooldown
            return ["warmup", "main", "circuit", "accessory", "cooldown"]
        elif template == "cardio":
            # Template 2: warmup → cardio movements → cooldown
            return ["warmup", "main", "cooldown"]
        elif template == "conditioning":
            # Template 3: warmup → conditioning movements → cooldown
            return ["warmup", "main", "cooldown"]
        elif template == "mobility":
            # Template 4: warmup → mobility movements → cooldown
            return ["warmup", "main", "cooldown"]
        else:
            logger.warning(
                f"[SessionGeneratorService._get_block_order_for_template] Unknown template: {template}, using normal"
            )
            return ["warmup", "main", "cooldown"]












    def _get_muscle_targets_for_session(
        self, session_type: SessionType, goal_weights: dict[str, int] | None = None
    ) -> dict[str, int]:
        """Define muscle volume targets based on session type.

        Targets are set to allow 4-5 main exercises for 60-minute sessions.
        Note: The optimizer applies a 20% volume reduction, so targets are set higher
        to account for this (target * 0.8 = actual sets).

        Args:
            session_type: The type of session being generated
            goal_weights: Optional goal weights dict (e.g., {"strength": 5, "hypertrophy": 3, "fat_loss": 2})
                         Higher strength weight increases volume targets slightly.
        """
        # Calculate strength multiplier based on goal weights (default: 1.0)
        strength_multiplier = 1.0
        if goal_weights:
            strength_weight = goal_weights.get("strength", 0)
            if strength_weight >= 4:
                strength_multiplier = 1.15  # 15% more volume for high strength focus
            elif strength_weight >= 2:
                strength_multiplier = 1.05  # 5% more volume for moderate strength focus

        # Apply multiplier to base targets (use rounding for better results)
        def apply_multiplier(value: int) -> int:
            return round(value * strength_multiplier)

        # Uses exact Enum string values from PrimaryMuscle
        if session_type == SessionType.UPPER:
            # 5 muscles × 4 sets = 20 sets → after 20% reduction = 16 sets (4-5 exercises @ 3-4 sets)
            return {
                "chest": apply_multiplier(4),
                "lats": apply_multiplier(4),
                "side_delts": apply_multiplier(4),
                "biceps": apply_multiplier(4),
                "triceps": apply_multiplier(4),
            }
        elif session_type == SessionType.LOWER:
            # 4 muscles × 4 sets = 16 sets → after 20% reduction = ~13 sets (3-4 exercises @ 3-4 sets)
            return {
                "quadriceps": apply_multiplier(4),
                "hamstrings": apply_multiplier(4),
                "glutes": apply_multiplier(4),
                "calves": apply_multiplier(4),
            }
        elif session_type == SessionType.PUSH:
            # 4 muscles × 4 sets = 16 sets → after 20% reduction = ~13 sets (3-4 exercises @ 3-4 sets)
            return {
                "chest": apply_multiplier(4),
                "front_delts": apply_multiplier(4),
                "triceps": apply_multiplier(4),
                "quadriceps": apply_multiplier(4),
            }
        elif session_type == SessionType.PULL:
            # 4 muscles × 4 sets = 16 sets → after 20% reduction = ~13 sets (3-4 exercises @ 3-4 sets)
            return {
                "lats": apply_multiplier(4),
                "biceps": apply_multiplier(4),
                "hamstrings": apply_multiplier(4),
                "rear_delts": apply_multiplier(4),
            }
        elif session_type == SessionType.FULL_BODY:
            # 5 muscles with varying priority → ~16 sets total → after 20% reduction = ~13 sets (4 exercises @ 3 sets)
            return {
                "quadriceps": apply_multiplier(4),
                "hamstrings": apply_multiplier(3),
                "chest": apply_multiplier(4),
                "lats": apply_multiplier(3),
                "side_delts": apply_multiplier(4),
            }
        return {}

    def _filter_movements_for_session_type(
        self, movements: list[Movement], session_type: SessionType
    ) -> list[Movement]:
        """Filter movements that are appropriate for the session type.

        Excludes mobility, cardio, and stretch patterns from main lifts.
        """
        lower_regions = ["anterior lower", "posterior lower", "lower body"]
        upper_regions = ["anterior upper", "posterior upper", "shoulder", "upper body"]

        # Patterns to exclude from main lifts
        excluded_patterns = {"mobility", "cardio", "stretch"}

        filtered = []
        for m in movements:
            # Handle Enum or string
            region = (
                str(m.primary_region.value)
                if hasattr(m.primary_region, "value")
                else str(m.primary_region)
            )
            pattern = (
                str(m.pattern.value) if hasattr(m.pattern, "value") else str(m.pattern)
            )

            # Exclude mobility/cardio/stretch patterns from main lifts
            if pattern in excluded_patterns:
                continue

            if session_type == SessionType.LOWER:
                if region in lower_regions or region == "full body":
                    filtered.append(m)
            elif session_type == SessionType.UPPER:
                if region in upper_regions:
                    filtered.append(m)
            else:
                # Full body, Push, Pull - keeping it simple for now, allow all or refine later
                filtered.append(m)

        return filtered

    def _to_solver_movements(self, movements: list[Movement]) -> list[SolverMovement]:
        """Convert SQLAlchemy models to picklable DTOs for the solver thread."""
        return [
            SolverMovement(
                id=m.id,
                name=m.name,
                primary_muscle=str(m.primary_muscle.value)
                if hasattr(m.primary_muscle, "value")
                else str(m.primary_muscle),
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift,
            )
            for m in movements
        ]

    def _to_solver_circuits(self, circuits: list[SolverCircuit]) -> list[SolverCircuit]:
        """Circuits are already in SolverCircuit format."""
        return circuits

    def _filter_circuits_for_session_type(
        self, circuits: list[SolverCircuit], session_type: SessionType
    ) -> list[SolverCircuit]:
        """Filter circuits that are appropriate for session type."""
        if session_type in {
            SessionType.CARDIO,
            SessionType.MOBILITY,
            SessionType.RECOVERY,
        }:
            return []
        return circuits

    def _generate_warmup_cooldown(
        self,
        session_type: SessionType,
        main_exercises: list[dict],
        available_movements: list[Movement],
    ) -> dict:
        """
        Generate warmup and cooldown based on main exercises' muscles and patterns.

        Warmup: Short cardio + mobility movements for the patterns used
        Cooldown: Stretch movements for the muscles used
        Fatigue is ignored for warmup/cooldown.
        """
        from app.models.enums import MovementPattern

        # Extract patterns and muscles from main exercises
        patterns_used = set()
        muscles_used = set()

        for exercise in main_exercises:
            movement_name = exercise.get("movement")
            movement = next(
                (m for m in available_movements if m.name == movement_name), None
            )
            if movement:
                if movement.pattern:
                    patterns_used.add(movement.pattern.value)
                if movement.primary_muscle:
                    muscles_used.add(movement.primary_muscle.value)

        warmup = []
        cooldown = []

        # Add short cardio for warmup (ignore fatigue)
        cardio_movements = [
            m for m in available_movements if m.pattern and m.pattern.value == "cardio"
        ]
        if cardio_movements:
            cardio = cardio_movements[0]
            warmup.append(
                {
                    "movement": cardio.name,
                    "sets": 1,
                    "duration_seconds": 300,
                    "notes": "Light cardio to raise body temperature",
                }
            )

        # Add mobility movements based on patterns used
        mobility_patterns_map = {
            MovementPattern.SQUAT.value: ["mobility", "squat"],
            MovementPattern.HINGE.value: ["mobility", "hinge"],
            MovementPattern.LUNGE.value: ["mobility", "lunge"],
            MovementPattern.HORIZONTAL_PUSH.value: ["mobility", "horizontal_push"],
            MovementPattern.VERTICAL_PUSH.value: ["mobility", "vertical_push"],
            MovementPattern.HORIZONTAL_PULL.value: ["mobility", "horizontal_pull"],
            MovementPattern.VERTICAL_PULL.value: ["mobility", "vertical_pull"],
        }

        for pattern in patterns_used:
            target_patterns = mobility_patterns_map.get(pattern, ["mobility"])
            mobility_movements = [
                m
                for m in available_movements
                if m.pattern and m.pattern.value in target_patterns
            ]
            if mobility_movements:
                mobility = mobility_movements[0]
                warmup.append(
                    {
                        "movement": mobility.name,
                        "sets": 2,
                        "reps": 10,
                        "notes": f"Mobility for {pattern} pattern",
                    }
                )
                break  # Just add one mobility movement

        # Add stretch movements for cooldown based on muscles used
        stretch_movements = [
            m for m in available_movements if m.pattern and m.pattern.value == "stretch"
        ]

        for muscle in muscles_used:
            muscle_stretches = [
                m
                for m in stretch_movements
                if m.primary_muscle and m.primary_muscle.value == muscle
            ]
            if muscle_stretches:
                stretch = muscle_stretches[0]
                cooldown.append(
                    {
                        "movement": stretch.name,
                        "duration_seconds": 180,
                        "notes": f"Stretch for {muscle}",
                    }
                )

        # If no specific stretches, add general stretches
        if not cooldown and stretch_movements:
            for stretch in stretch_movements[:3]:
                cooldown.append(
                    {
                        "movement": stretch.name,
                        "duration_seconds": 180,
                        "notes": "General stretch",
                    }
                )

        return {"warmup": warmup, "cooldown": cooldown}

    def _convert_optimization_result_to_content(
        self,
        result: Any,
        session_type: SessionType,
        available_movements: list[Movement],
    ) -> dict[str, Any]:
        """Convert OptimizationResult to session content dict."""

        main_exercises = []
        accessory_exercises = []

        # Heuristic to split into Main vs Accessory
        # Compound + High Fatigue -> Main
        # Isolation / Low Fatigue -> Accessory

        for m in result.selected_movements:
            is_main = m.compound and (m.fatigue_factor > 0.6 or m.is_complex_lift)

            exercise = {
                "movement": m.name,
                "sets": 3,
                "rep_range_min": 8 if is_main else 10,
                "rep_range_max": 10 if is_main else 15,
                "target_rpe": 8 if is_main else 7,
                "rest_seconds": 120 if is_main else 60,
                "notes": "Optimized selection",
            }

            if is_main:
                main_exercises.append(exercise)
            else:
                accessory_exercises.append(exercise)

        # If no main, move biggest accessory to main
        if not main_exercises and accessory_exercises:
            main_exercises.append(accessory_exercises.pop(0))

        # Fallback for failed generation (Infeasible or Timeout)
        if not main_exercises:
            main_exercises.append(
                {
                    "movement": "Generation Failed",
                    "sets": 0,
                    "rep_range_min": 0,
                    "rep_range_max": 0,
                    "target_rpe": 0,
                    "rest_seconds": 0,
                    "notes": f"Could not generate valid session. Status: {result.status}. Please try regenerating or editing manually.",
                }
            )

        # Generate warmup and cooldown based on main exercises
        warmup_cooldown = self._generate_warmup_cooldown(
            session_type, main_exercises, available_movements
        )

        # Use TimeEstimationService for accurate duration calculation
        from app.services.time_estimation import TimeEstimationService

        time_service = TimeEstimationService()

        # Calculate accurate duration using TimeEstimationService
        estimated_duration = time_service.estimate_session_time_with_transitions(
            warmup=warmup_cooldown["warmup"],
            main=main_exercises,
            accessory=accessory_exercises,
            circuit=None,
            finisher=None,
            cooldown=warmup_cooldown["cooldown"],
            intent="hypertrophy",  # Default intent
        )

        # Log duration breakdown for verification
        logger.info("[_convert_optimization_result_to_content] DURATION BREAKDOWN:")
        logger.info(
            f"  Warmup: {estimated_duration.warmup_minutes} min ({len(warmup_cooldown.get('warmup', []))} exercises)"
        )
        logger.info(
            f"  Main: {estimated_duration.main_minutes} min ({len(main_exercises)} exercises)"
        )
        logger.info(
            f"  Accessory: {estimated_duration.accessory_minutes} min ({len(accessory_exercises)} exercises)"
        )
        logger.info(
            f"  Cooldown: {estimated_duration.cooldown_minutes} min ({len(warmup_cooldown.get('cooldown', []))} exercises)"
        )
        logger.info(
            f"  TRANSITIONS: {estimated_duration.total_minutes - (estimated_duration.warmup_minutes + estimated_duration.main_minutes + estimated_duration.accessory_minutes + estimated_duration.cooldown_minutes):.1f} min"
        )
        logger.info(f"  TOTAL: {estimated_duration.total_minutes:.1f} min")
        logger.info(
            f"[_convert_optimization_result_to_content] OR Tools result: {len(result.selected_movements)} movements, {result.estimated_duration} min"
        )

        return {
            "warmup": warmup_cooldown["warmup"],
            "main": main_exercises,
            "accessory": accessory_exercises,
            "finisher": None,
            "cooldown": warmup_cooldown["cooldown"],
            "estimated_duration_minutes": estimated_duration.total_minutes,
            "reasoning": f"Optimization Engine generated session. Status: {result.status}. Stimulus: {result.total_stimulus:.2f}, Fatigue: {result.total_fatigue:.2f}",
        }


# Singleton instance
session_generator = SessionGeneratorService()
