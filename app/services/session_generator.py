"""
SessionGeneratorService - Generates workout session content using LLM.

Uses Ollama with llama3.1:8b to create exercise blocks for sessions
based on program goals, session type, and movement library.
"""

import asyncio
import httpx
import json
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import activity_distribution as activity_distribution_config
from app.config.settings import get_settings
from app.llm import get_llm_provider, LLMConfig, Message
from app.models import Movement, Session, Program, Microcycle, UserMovementRule, UserProfile, SessionExercise
from app.models.circuit import CircuitTemplate
from app.models.enums import SessionType, MovementRuleType, SkillLevel, ExerciseRole, MuscleRole
from app.services.optimization import ConstraintSolver, OptimizationRequest, SolverMovement, SolverCircuit

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
    
    async def _call_llm_with_retry(
        self,
        provider,
        messages: list,
        config,
        session_id: int | None = None,
        session_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Call LLM with exponential backoff retry logic.
        
        Args:
            provider: LLM provider instance
            messages: List of messages for the LLM
            config: LLM configuration
            session_id: Optional session ID for logging context
            session_type: Optional session type for logging context
            
        Returns:
            Parsed JSON response from LLM
            
        Raises:
            Exception: After all retries exhausted
        """
        last_exception = None
        delay = self.INITIAL_RETRY_DELAY
        
        for attempt in range(self.MAX_RETRIES):
            try:
                start_time = time.time()
                response = await provider.chat(messages, config)
                elapsed = time.time() - start_time
                
                # Parse response
                if response.structured_data:
                    content = response.structured_data
                else:
                    content = json.loads(response.content)
                
                # Log success
                if attempt > 0:
                    logger.info(
                        f"LLM call succeeded on attempt {attempt + 1}/{self.MAX_RETRIES} "
                        f"after {elapsed:.1f}s (session_id={session_id}, type={session_type})"
                    )
                
                return content
                
            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    f"LLM request timed out on attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"(session_id={session_id}, type={session_type}). "
                    f"Retrying in {delay:.1f}s..."
                )
                
            except httpx.ConnectError as e:
                last_exception = e
                logger.warning(
                    f"Cannot connect to Ollama on attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"(session_id={session_id}, type={session_type}). "
                    f"Base URL: {provider.base_url}. Retrying in {delay:.1f}s..."
                )
                
            except json.JSONDecodeError as e:
                last_exception = e
                content_preview = getattr(response, 'content', 'N/A')[:200] if 'response' in locals() else 'N/A'
                logger.warning(
                    f"LLM returned invalid JSON on attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"(session_id={session_id}, type={session_type}). "
                    f"Content preview: {content_preview}. Retrying in {delay:.1f}s..."
                )
                
            except httpx.HTTPStatusError as e:
                # Don't retry on HTTP errors (4xx/5xx from Ollama)
                logger.error(
                    f"Ollama returned HTTP {e.response.status_code} "
                    f"(session_id={session_id}, type={session_type}): {e.response.text[:200]}"
                )
                raise
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Unexpected error on attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"(session_id={session_id}, type={session_type}): "
                    f"{type(e).__name__}: {str(e)[:200]}. Retrying in {delay:.1f}s..."
                )
            
            # Don't sleep after last attempt
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay = min(delay * self.RETRY_BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)
        
        # All retries exhausted
        logger.error(
            f"LLM call failed after {self.MAX_RETRIES} attempts "
            f"(session_id={session_id}, type={session_type}). "
            f"Last error: {type(last_exception).__name__}: {last_exception}"
        )
        raise last_exception
    
    async def generate_session_exercises(
        self,
        db: AsyncSession,
        session: Session,
        program: Program,
        microcycle: Microcycle,
        used_movements: list[str] | None = None,
        used_movement_groups: dict[str, int] | None = None,
        used_accessory_movements: dict[int, list[str]] | None = None,
        fatigued_muscles: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate exercise content for a session.
        
        Args:
            db: Database session
            session: Session model with type and intent_tags set
            program: Parent program with goals and settings
            microcycle: Parent microcycle with deload status
            used_movements: List of movements already used in this microcycle
            used_movement_groups: Dict tracking usage count by substitution_group
            used_accessory_movements: Dict mapping day_number to accessory movements used
            fatigued_muscles: List of muscles fatigued from previous session
            
        Returns:
            Dict with warmup, main, accessory, finisher, cooldown blocks
        """
        # Skip generation for rest/recovery sessions
        if session.session_type == SessionType.RECOVERY:
            return self._get_recovery_session_content()
        
        # Load movement library grouped by pattern
        movements_by_pattern = await self._load_movements_by_pattern(db)
        goal_weights = self._get_goal_weights_for_program(program)
        
        # Generate optimal draft using Constraint Solver
        draft_content = None
        try:
            draft_result = await self._generate_draft_session(db, session, used_movements, goal_weights=goal_weights)
            if draft_result.status in ["OPTIMAL", "FEASIBLE"] and draft_result.selected_movements:
                draft_content = self._convert_optimization_result_to_content(draft_result, session.session_type)
                logger.info(f"Generated optimal draft for session {session.id}")
        except Exception as e:
            logger.warning(f"Failed to generate draft session: {e}")

        if session.session_type == SessionType.CUSTOM and "conditioning" in (session.intent_tags or []):
            all_movements = await self._load_all_movements(db)
            conditioning_names = self._get_conditioning_movement_names(all_movements)
            content = self._get_fast_conditioning_session_content(conditioning_names, program.max_session_duration)
        elif session.session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            content = self._get_fast_special_session_content(session.session_type, program.max_session_duration)
        elif draft_content:
            content = self._build_fast_content_from_draft(
                draft_content,
                session.session_type,
                session.intent_tags or [],
                microcycle.is_deload,
                goal_weights,
            )
        else:
            content = self._get_smart_fallback_session_content(
                session.session_type,
                session.intent_tags or [],
                movements_by_pattern,
                used_movements=used_movements,
            )
            if session.session_type not in {SessionType.CARDIO, SessionType.MOBILITY} and not content.get("finisher"):
                finisher = self._build_goal_finisher(goal_weights)
                if finisher:
                    content["finisher"] = finisher

        content = self._normalize_session_content(content, session.session_type, session.intent_tags or [], goal_weights)
        # Jerome notes generation moved to batched microcycle-level generation in program.py
        return content
    
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
    ) -> dict[str, int]:
        """
        Generate and save exercise content to a session using IDs.
        
        Refactored to NOT hold a database connection during LLM generation.
        """
        from app.db.database import async_session_maker
        
        logger.info(f"[populate_session_by_id] START - session_id={session_id}, program_id={program_id}, microcycle_id={microcycle_id}")
        
        # 1. Fetch all necessary context (short DB transaction)
        context_data = {}
        async with async_session_maker() as db:
            from sqlalchemy.orm import selectinload
            session = await db.get(Session, session_id)
            program = await db.get(Program, program_id, options=[selectinload(Program.program_disciplines)])
            microcycle = await db.get(Microcycle, microcycle_id)
            
            if not session or not program or not microcycle:
                logger.error(f"[populate_session_by_id] FAILED - session={session}, program={program}, microcycle={microcycle}")
                return {}
            
            logger.info(f"[populate_session_by_id] Fetched session type={session.session_type}, day={session.day_number}")
            
            # Fetch supporting data
            movements_by_pattern = await self._load_movements_by_pattern(db)
            movement_rules = await self._load_user_movement_rules_dict(db, program.user_id)
            user_profile = await db.get(UserProfile, program.user_id)
            all_movements = await self._load_all_movements(db)
            
            # Load program disciplines from junction table
            program_disciplines = []
            for pd in program.program_disciplines:
                program_disciplines.append({
                    "discipline": pd.discipline_type,
                    "weight": pd.weight
                })
            
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
                "discipline_preferences": user_profile.discipline_preferences if user_profile else None,
                "scheduling_preferences": user_profile.scheduling_preferences if user_profile else None,
            }

        # 2. Generate Content (Long running, NO DB connection)
        # We pass the context data instead of DB objects where possible
        
        # Determine fatigued muscles
        fatigued_muscles = []
        if previous_day_volume:
            fatigued_muscles = [m for m, v in previous_day_volume.items() if v > 2]

        content = await self.generate_session_exercises_offline(
            context_data,
            used_movements,
            used_movement_groups,
            used_accessory_movements,
            fatigued_muscles
        )
        
        logger.info(f"[populate_session_by_id] Generated content: {list(content.keys())}")
        
        # Post-processing (duplicates removal)
        if used_accessory_movements:
            current_day = context_data["session"]["day_number"]
            previous_days = [d for d in used_accessory_movements.keys() if d < current_day]
            if previous_days:
                last_day = max(previous_days)
                previous_accessories = used_accessory_movements.get(last_day) or []
                if previous_accessories:
                    content = self._remove_cross_session_accessory_duplicates(
                        content, set(previous_accessories), context_data["session"]["session_type"]
                    )

        # 3. Save Results (Short DB transaction)
        current_session_volume = {}
        logger.info("[populate_session_by_id] SAVING to database...")
        async with async_session_maker() as db:
            session = await db.get(Session, session_id)
            if session:
                # session.warmup_json = content.get("warmup") # DEPRECATED
                # session.main_json = content.get("main") # DEPRECATED
                # session.accessory_json = content.get("accessory") # DEPRECATED
                # session.finisher_json = content.get("finisher") # DEPRECATED
                # session.cooldown_json = content.get("cooldown") # DEPRECATED
                session.estimated_duration_minutes = content.get("estimated_duration_minutes", 60)
                # coach_notes will be generated in batches at microcycle level via _generate_microcycle_jerome_notes()
                
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
                await self._save_session_exercises(
                    db,
                    session,
                    content,
                    movement_map,
                    context_data["program"]["user_id"]
                )

                db.add(session)
                await db.commit()
                
                # Calculate volume (needs DB for movement lookup)
                current_session_volume = await self._calculate_session_volume(db, session)
        
        return current_session_volume

    async def generate_session_exercises_offline(
        self,
        context: dict,
        used_movements: list[str] | None = None,
        used_movement_groups: dict[str, int] | None = None,
        used_accessory_movements: dict[int, list[str]] | None = None,
        fatigued_muscles: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Generate exercise content without active DB session.
        """
        session_type = context["session"]["session_type"]
        
        # Skip generation for rest/recovery sessions
        if session_type == SessionType.RECOVERY:
            return self._get_recovery_session_content()
            
        movements_by_pattern = context["movements_by_pattern"]
        goal_weights = self._get_goal_weights_for_program_info(context["program"])
        
        # Extract movement rule IDs from dict format
        # movement_rules dict has keys: "avoid", "must_include", "prefer" containing movement names
        movement_rules_dict = context.get("movement_rules") or {}
        preferred_ids: list[int] = []
        hard_no_ids: list[int] = []
        hard_yes_ids: list[int] = []
        
        # Build name to ID mapping from all_movements
        all_movements = context.get("all_movements", [])
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
        
        # Generate optimal draft
        draft_context = ""
        draft_content = None
        try:
            draft_result = await self._generate_draft_session_offline(
                context["all_movements"], 
                session_type, 
                used_movements,
                goal_weights=goal_weights,
                preferred_movement_ids=preferred_ids,
                excluded_movement_ids=hard_no_ids,
                required_movement_ids=hard_yes_ids,
            )
            if draft_result.status in ["OPTIMAL", "FEASIBLE"] and draft_result.selected_movements:
                draft_content = self._convert_optimization_result_to_content(draft_result, session_type)
                logger.info(f"Generated optimal draft for session {context['session']['id']}")
        except Exception as e:
            logger.warning(f"Failed to generate draft session: {e}")
        if session_type == SessionType.CUSTOM and "conditioning" in (context["session"]["intent_tags"] or []):
            conditioning_names = self._get_conditioning_movement_names(context["all_movements"])
            content = self._get_fast_conditioning_session_content(conditioning_names, context["program"]["max_session_duration"])
        elif session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            content = self._get_fast_special_session_content(session_type, context["program"]["max_session_duration"])
        elif draft_content:
            content = self._build_fast_content_from_draft(
                draft_content,
                session_type,
                context["session"]["intent_tags"] or [],
                context["microcycle"]["is_deload"],
                goal_weights,
            )
        else:
            content = self._get_smart_fallback_session_content(
                session_type,
                context["session"]["intent_tags"] or [],
                movements_by_pattern,
                used_movements=used_movements,
            )
            if session_type not in {SessionType.CARDIO, SessionType.MOBILITY} and not content.get("finisher"):
                finisher = self._build_goal_finisher(goal_weights)
                if finisher:
                    content["finisher"] = finisher

        content = self._normalize_session_content(content, session_type, context["session"]["intent_tags"] or [], goal_weights)
        # Jerome notes generation moved to batched microcycle-level generation in program.py
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
        
        logger.info(f"[_save_session_exercises] START - session_id={session.id}, content_keys={list(content.keys())}")
        
        # Clear existing exercises for this session
        await db.execute(delete(SessionExercise).where(SessionExercise.session_id == session.id))
        
        logger.info(f"[_save_session_exercises] Cleared existing exercises for session {session.id}")
        
        order_counter = 1
        missing_movements = []
        total_exercises = 0
        exercises_to_save = []
        
        # Helper to process a section
        async def process_section(section_name: str, exercise_role: ExerciseRole):
            nonlocal order_counter, missing_movements, total_exercises, exercises_to_save
            exercises = content.get(section_name)
            if not exercises:
                return
            
            logger.info(f"[_save_session_exercises] Processing section '{section_name}' with {len(exercises)} exercises")
            
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
                    target_rep_range_min=ex.get("rep_range_min") or (ex.get("reps") if isinstance(ex.get("reps"), int) else None),
                    target_rep_range_max=ex.get("rep_range_max") or (ex.get("reps") if isinstance(ex.get("reps"), int) else None),
                    target_rpe=float(ex.get("target_rpe")) if ex.get("target_rpe") else None,
                    target_duration_seconds=ex.get("duration_seconds"),
                    default_rest_seconds=ex.get("rest_seconds"),
                    notes=ex.get("notes"),
                    superset_group=None
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
                        target_rep_range_min=ex.get("reps") if isinstance(ex.get("reps"), int) else None,
                        target_rep_range_max=ex.get("reps") if isinstance(ex.get("reps"), int) else None,
                        target_duration_seconds=ex.get("duration_seconds"),
                        notes=ex.get("notes"),
                    )
                    exercises_to_save.append(session_ex)
                    order_counter += 1
        
        # Bulk save all exercises at once
        if exercises_to_save:
            db.add_all(exercises_to_save)
            logger.info(f"[_save_session_exercises] Bulk saved {len(exercises_to_save)} exercises")
        else:
            logger.warning(f"[_save_session_exercises] No exercises to save. Missing movements: {missing_movements[:10]}")
        
        # Validate missing movements threshold
        if missing_movements and total_exercises > 0:
            missing_percentage = len(missing_movements) / total_exercises
            if missing_percentage > 0.25:
                error_msg = f"Critical: {len(missing_movements)}/{total_exercises} movements not found in database: {missing_movements[:5]}"
                logger.error(f"[_save_session_exercises] {error_msg}")
                raise ValueError(error_msg)
            else:
                logger.warning(f"[_save_session_exercises] {len(missing_movements)} movements not found: {missing_movements}")

    async def _calculate_session_volume(self, db: AsyncSession, session: Session) -> dict[str, int]:
        """Helper to calculate volume after session is saved."""
        current_session_volume = {}
        
        # 1. Calculate from SessionExercise (Preferred)
        # Always query DB to ensure we have the latest data and avoid lazy loading issues
        # especially after a commit where the session object might be expired
        from app.models.movement import MovementMuscleMap
        
        result = await db.execute(
            select(SessionExercise)
            .options(
                selectinload(SessionExercise.movement).selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
            )
            .where(SessionExercise.session_id == session.id)
        )
        exercises = result.scalars().all()
        
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
                p_muscle = str(mov.primary_muscle.value) if hasattr(mov.primary_muscle, 'value') else str(mov.primary_muscle)
                current_session_volume[p_muscle] = current_session_volume.get(p_muscle, 0) + weight
                
                # Secondary muscles via muscle_maps
                if mov.muscle_maps:
                    for mm in mov.muscle_maps:
                        role_val = mm.role.value if hasattr(mm.role, 'value') else mm.role
                        if role_val == MuscleRole.SECONDARY.value:
                            if mm.muscle:
                                sec = mm.muscle.slug
                                current_session_volume[sec] = current_session_volume.get(sec, 0) + (weight // 2)
        else:
            # Fallback to JSON (Legacy support)
            all_movements = []
            if session.main_json:
                all_movements.extend([(m["movement"], 3) for m in session.main_json if "movement" in m])
            if session.accessory_json:
                all_movements.extend([(m["movement"], 2) for m in session.accessory_json if "movement" in m])
            if session.finisher_json and session.finisher_json.get("exercises"):
                all_movements.extend([(m["movement"], 1) for m in session.finisher_json["exercises"] if "movement" in m])
                
            if all_movements:
                names = [m[0] for m in all_movements]
                unique_names = list(set(names))
                
                from app.models.movement import MovementMuscleMap
                result = await db.execute(
                    select(Movement)
                    .options(
                        selectinload(Movement.muscle_maps).selectinload(MovementMuscleMap.muscle)
                    )
                    .where(Movement.name.in_(unique_names))
                )
                found_movements = {m.name: m for m in result.scalars().all()}
                
                for name, weight in all_movements:
                    mov = found_movements.get(name)
                    if mov:
                        p_muscle = str(mov.primary_muscle.value) if hasattr(mov.primary_muscle, 'value') else str(mov.primary_muscle)
                        current_session_volume[p_muscle] = current_session_volume.get(p_muscle, 0) + weight
                        
                        if mov.muscle_maps:
                            for mm in mov.muscle_maps:
                                role_val = mm.role.value if hasattr(mm.role, 'value') else mm.role
                                if role_val == MuscleRole.SECONDARY.value:
                                    if mm.muscle:
                                        sec = mm.muscle.slug
                                        current_session_volume[sec] = current_session_volume.get(sec, 0) + (weight // 2)

        # Process circuits (main_circuit_id, finisher_circuit_id)
        from app.models.circuit import CircuitTemplate
        if session.main_circuit_id:
            circuit = await db.get(CircuitTemplate, session.main_circuit_id)
            if circuit and circuit.muscle_volume:
                for muscle, volume in circuit.muscle_volume.items():
                    current_session_volume[muscle] = current_session_volume.get(muscle, 0) + volume
        
        if session.finisher_circuit_id:
            circuit = await db.get(CircuitTemplate, session.finisher_circuit_id)
            if circuit and circuit.muscle_volume:
                for muscle, volume in circuit.muscle_volume.items():
                    current_session_volume[muscle] = current_session_volume.get(muscle, 0) + (volume // 2)
                    
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
    ) -> Any:
        """
        Offline version of _generate_draft_session.
        """
        filtered_movements = self._filter_movements_for_session_type(all_movements, session_type)
        
        # Convert to DTOs for thread safety
        solver_movements = self._to_solver_movements(filtered_movements)
        
        targets = self._get_muscle_targets_for_session(session_type)
        
        excluded_ids: list[int] = list(excluded_movement_ids or [])
        if used_movements:
            name_to_id = {m.name: m.id for m in all_movements}
            for name in used_movements:
                if name in name_to_id:
                    excluded_ids.append(name_to_id[name])

        req = OptimizationRequest(
            available_movements=solver_movements,
            available_circuits=[],
            target_muscle_volumes=targets,
            max_fatigue=activity_distribution_config.or_tools_max_fatigue,
            min_stimulus=2.0,
            user_skill_level=SkillLevel.INTERMEDIATE,
            excluded_movement_ids=excluded_ids,
            required_movement_ids=list(required_movement_ids or []),
            session_duration_minutes=60,
            allow_complex_lifts=True,
            allow_circuits=False,
            goal_weights=goal_weights,
            preferred_movement_ids=preferred_movement_ids,
        )
        # Solve in a separate thread to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.optimizer.solve_session, req)

    # Kept for backward compatibility if needed, but not used by populate_session_by_id anymore
    async def populate_session(
        self,
        db: AsyncSession,
        session: Session,
        program: Program,
        microcycle: Microcycle,
        used_movements: list[str] | None = None,
        used_movement_groups: dict[str, int] | None = None,
        used_accessory_movements: dict[int, list[str]] | None = None,
        previous_day_volume: dict[str, int] | None = None,
    ) -> dict[str, int]:
        """
        Generate and save exercise content to a session.
        
        Args:
            db: Database session
            session: Session to populate
            program: Parent program
            microcycle: Parent microcycle
            used_movements: List of movements already used in this microcycle
            used_movement_groups: Dict tracking usage count by substitution_group
            used_accessory_movements: Dict mapping day_number to accessory movements used
            previous_day_volume: Volume dict from previous session (muscle -> volume)
            
        Returns:
            Dict of muscle volume generated in this session (muscle -> volume)
        """
        # Determine fatigued muscles from previous day
        fatigued_muscles = []
        if previous_day_volume:
            # Threshold: > 2 units of volume (e.g. 1 main lift) causes interference
            fatigued_muscles = [m for m, v in previous_day_volume.items() if v > 2]
            
        content = await self.generate_session_exercises(
            db, session, program, microcycle, used_movements, used_movement_groups, used_accessory_movements, fatigued_muscles
        )
        
        if used_accessory_movements:
            current_day = session.day_number
            previous_days = [d for d in used_accessory_movements.keys() if d < current_day]
            if previous_days:
                last_day = max(previous_days)
                previous_accessories = used_accessory_movements.get(last_day) or []
                if previous_accessories:
                    content = self._remove_cross_session_accessory_duplicates(
                        content, set(previous_accessories), session.session_type
                    )
        
        # Update session fields
        session.estimated_duration_minutes = content.get("estimated_duration_minutes", 60)
        # coach_notes will be generated in batches at microcycle level via _generate_microcycle_jerome_notes()
        
        # Populate SessionExercises
        all_movement_names = set()
        for section in ["warmup", "main", "accessory", "cooldown"]:
            if section in content and content[section]:
                for ex in content[section]:
                    if "movement" in ex:
                        all_movement_names.add(ex["movement"])
        
        if content.get("finisher") and isinstance(content["finisher"], dict) and content["finisher"].get("exercises"):
             for ex in content["finisher"]["exercises"]:
                if "movement" in ex:
                    all_movement_names.add(ex["movement"])

        movement_map = {}
        if all_movement_names:
            stmt = select(Movement.name, Movement.id).where(Movement.name.in_(list(all_movement_names)))
            result = await db.execute(stmt)
            movement_map = {name: id for name, id in result.all()}
            
        await self._save_session_exercises(db, session, content, movement_map, program.user_id)
        
        db.add(session)
        await db.flush()
        
        # Calculate volume for this session to pass to next day
        return await self._calculate_session_volume(db, session)
    
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
    
    async def _load_user_movement_rules(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> list[tuple[UserMovementRule, Movement]]:
        """Load user's movement preferences (HARD_NO, HARD_YES, PREFERRED).
        
        Returns:
            List of tuples (UserMovementRule, Movement) for all rules for this user.
        """
        result = await db.execute(
            select(UserMovementRule, Movement)
            .join(Movement, UserMovementRule.movement_id == Movement.id)
            .where(UserMovementRule.user_id == user_id)
        )
        return result.all()
    
    async def _load_user_movement_rules_dict(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict[str, list[str]]:
        """Load user's movement preferences as a dict of movement names.
        
        Returns:
            Dict with keys: "avoid", "must_include", "prefer" containing lists of movement names.
        """
        rules = await self._load_user_movement_rules(db, user_id)
        
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
        - EITHER accessory OR finisher exists
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
            logger.warning(f"Missing warmup for {session_type} session, adding default")
            content["warmup"] = [
                {"movement": "Dynamic Stretching", "sets": 2, "reps": 10, "notes": "Full body prep"},
                {"movement": "Light Cardio", "duration_seconds": 300, "notes": "5 min warm-up"},
            ]
        
        if not content.get("main") or len(content.get("main", [])) == 0:
            logger.error(f"Missing main section for {session_type} session!")
            # Use fallback for main if completely missing
            fallback = self._get_fallback_session_content(session_type)
            content["main"] = fallback.get("main", [])
        
        if not content.get("cooldown") or len(content.get("cooldown", [])) == 0:
            logger.warning(f"Missing cooldown for {session_type} session, adding default")
            content["cooldown"] = [
                {"movement": "Static Stretching", "duration_seconds": 300, "notes": "Focus on trained muscles"},
                {"movement": "Foam Rolling", "duration_seconds": 180, "notes": "Target tight areas"},
            ]
        
        # CRITICAL: Remove duplicate movements within the session
        content = self._remove_intra_session_duplicates(content, session_type)
        
        return content

    def _build_fast_content_from_draft(
        self,
        draft_content: dict[str, Any],
        session_type: SessionType,
        intent_tags: list[str],
        is_deload: bool,
        goal_weights: dict[str, int],
    ) -> dict[str, Any]:
        from app.llm.optimization import PromptCache

        content = dict(draft_content)

        if not content.get("warmup") or len(content.get("warmup", [])) < 2:
            content["warmup"] = PromptCache.get_pattern_based_warmup(intent_tags or [], session_type)

        if not content.get("cooldown") or len(content.get("cooldown", [])) < 2:
            content["cooldown"] = PromptCache.get_pattern_based_cooldown(intent_tags or [])
        return self._normalize_session_content(content, session_type, intent_tags, goal_weights)
    
    def _normalize_session_content(
        self,
        content: dict[str, Any],
        session_type: SessionType,
        intent_tags: list[str],
        goal_weights: dict[str, int],
    ) -> dict[str, Any]:
        normalized = self._validate_and_complete_session(dict(content), session_type)
        tags = set(intent_tags or [])
        is_conditioning_only = session_type == SessionType.CUSTOM and "conditioning" in tags
        is_middle_piece_only = session_type in {SessionType.CARDIO, SessionType.MOBILITY} or is_conditioning_only
        
        if is_middle_piece_only:
            normalized["accessory"] = None
            normalized["finisher"] = None
            return normalized
        
        has_accessory = bool(normalized.get("accessory")) and len(normalized.get("accessory", [])) > 0
        has_finisher = normalized.get("finisher") is not None
        
        if has_accessory and has_finisher:
            if self._prefer_finisher(goal_weights, tags):
                normalized["accessory"] = None
            else:
                normalized["finisher"] = None
            return normalized
        
        if has_finisher:
            normalized["accessory"] = None
            return normalized
        
        if has_accessory:
            if self._prefer_finisher(goal_weights, tags):
                finisher = self._build_goal_finisher(goal_weights)
                if not finisher:
                    if goal_weights.get("endurance", 0) >= goal_weights.get("fat_loss", 0):
                        finisher = dict(activity_distribution_config.goal_finisher_presets.get("endurance", {}))
                    else:
                        finisher = dict(activity_distribution_config.goal_finisher_presets.get("fat_loss", {}))
                if finisher:
                    normalized["finisher"] = finisher
                    normalized["accessory"] = None
                    return normalized
            normalized["finisher"] = None
            return normalized
        
        finisher = self._build_goal_finisher(goal_weights)
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
        fat_loss = goal_weights.get("fat_loss", 0)
        endurance = goal_weights.get("endurance", 0)
        strength = goal_weights.get("strength", 0)
        hypertrophy = goal_weights.get("hypertrophy", 0)
        finisher_pressure = fat_loss + endurance
        accessory_pressure = strength + hypertrophy
        return finisher_pressure > accessory_pressure or "conditioning" in tags or "cardio" in tags

    def _get_goal_weights_for_program(self, program: Program) -> dict[str, int]:
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
        return goal_weights

    def _get_goal_weights_for_program_info(self, program_info: dict[str, Any]) -> dict[str, int]:
        goal_weights = {
            "strength": 0,
            "hypertrophy": 0,
            "endurance": 0,
            "fat_loss": 0,
            "mobility": 0,
        }
        for goal, weight in [
            (program_info["goal_1"].value, program_info["goal_weight_1"]),
            (program_info["goal_2"].value, program_info["goal_weight_2"]),
            (program_info["goal_3"].value, program_info["goal_weight_3"]),
        ]:
            if goal in goal_weights:
                goal_weights[goal] += weight
        return goal_weights

    async def _generate_jerome_notes(
        self,
        session_type: SessionType,
        intent_tags: list[str],
        goal_weights: dict[str, int],
        content: dict[str, Any],
        is_deload: bool,
    ) -> str:
        main_moves = [ex.get("movement") for ex in (content.get("main") or []) if ex.get("movement")]
        accessory_moves = [ex.get("movement") for ex in (content.get("accessory") or []) if ex.get("movement")]
        finisher_type = content.get("finisher", {}).get("type") if content.get("finisher") else None
        goals_summary = ", ".join([f"{k}:{v}" for k, v in goal_weights.items() if v > 0])
        summary = f"Type: {session_type.value}. Patterns: {', '.join(intent_tags)}. Goals: {goals_summary}."

        prompt = "Write 1-2 sentences in Jerome's voice explaining why this session fits the user's goals and recovery. "
        prompt += f"{summary} Main: {', '.join(main_moves[:4])}. "
        if accessory_moves:
            prompt += f"Accessories: {', '.join(accessory_moves[:4])}. "
        if finisher_type:
            prompt += f"Finisher: {finisher_type}. "
        if is_deload:
            prompt += "Deload week. "

        try:
            provider = get_llm_provider()
            config = LLMConfig(model=settings.ollama_model, temperature=0.2, max_tokens=1200)
            messages = [Message(role="user", content=prompt)]
            response = await self._call_llm_with_retry(
                provider,
                messages,
                config,
                session_type=session_type.value,
            )
            if response:
                return str(response)[:1100].rstrip()
        except Exception:
            pass

        note = "Optimization-first session aligned to your goals and recovery."
        if is_deload:
            note = "Optimization-first deload session focused on recovery and quality."
        return note[:1100].rstrip()

    def _build_goal_finisher(self, goal_weights: dict[str, int]) -> dict[str, Any] | None:
        thresholds = activity_distribution_config.goal_finisher_thresholds
        presets = activity_distribution_config.goal_finisher_presets
        if goal_weights.get("fat_loss", 0) >= int(thresholds.get("fat_loss_min_weight", 999)):
            return dict(presets.get("fat_loss", {}))
        if goal_weights.get("endurance", 0) >= int(thresholds.get("endurance_min_weight", 999)):
            return dict(presets.get("endurance", {}))
        return None

    def _get_fast_special_session_content(
        self,
        session_type: SessionType,
        max_session_duration: int | None,
    ) -> dict[str, Any]:
        total_minutes = max_session_duration or 30
        warmup = [{"movement": "Easy Cardio", "duration_seconds": 300, "notes": "Build pace"}]
        cooldown = [{"movement": "Static Stretching", "duration_seconds": 300, "notes": "Full body"}]

        if session_type == SessionType.MOBILITY:
            main = [
                {"movement": "Dynamic Stretching", "duration_seconds": 600, "notes": "Full body"},
                {"movement": "Mobility Flow", "duration_seconds": max(300, (total_minutes - 15) * 60)},
            ]
            return {
                "warmup": warmup,
                "main": main,
                "accessory": None,
                "finisher": None,
                "cooldown": cooldown,
                "estimated_duration_minutes": total_minutes,
                "reasoning": "Optimization-first mobility session",
            }

        main = [
            {"movement": "Cardio Intervals", "duration_seconds": max(600, (total_minutes - 10) * 60)},
        ]
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
    ) -> dict[str, Any]:
        total_minutes = max_session_duration or 45
        main_minutes = max(30, total_minutes - 10)
        warmup = [
            {"movement": "Easy Cardio", "duration_seconds": 300, "notes": "Build pace"},
            {"movement": "Dynamic Stretching", "duration_seconds": 300, "notes": "Prep joints"},
        ]
        cooldown = [{"movement": "Static Stretching", "duration_seconds": 300, "notes": "Full body"}]

        candidates = list(dict.fromkeys(conditioning_movement_names or []))
        if len(candidates) < 5:
            candidates.extend(["Sled Push", "Sled Pull", "Battle Ropes", "Farmer Carry", "Air Bike"])
            candidates = list(dict.fromkeys(candidates))

        selected = candidates[: max(5, min(8, len(candidates)))]
        per_station_seconds = max(120, int((main_minutes * 60) / max(5, len(selected))))
        main = [{"movement": name, "duration_seconds": per_station_seconds, "notes": "Conditioning station"} for name in selected]

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
            if pattern == "conditioning" or (isinstance(tags, list) and "conditioning" in tags):
                if getattr(m, "name", None):
                    names.append(m.name)
        return names
    
    def _remove_intra_session_duplicates(
        self, content: dict[str, Any], session_type: SessionType
    ) -> dict[str, Any]:
        """
        Remove duplicate movements within a single session across all sections.
        Intelligently replaces removed exercises to preserve muscle group coverage.
        
        Priority order: main > accessory > finisher > warmup > cooldown
        If a movement appears in multiple sections, keep it in the highest priority section
        and replace it in lower priority sections with similar muscle group exercises.
        
        Args:
            content: Session content dict
            session_type: Type of session
            
        Returns:
            Session content with duplicates removed and intelligent replacements
        """
        # Track all movements used in the session
        used_movements = set()
        removed_exercises = []  # Track what was removed for replacement
        
        # Priority order for sections (main work takes precedence)
        sections_priority = [
            ("main", content.get("main", [])),
            ("accessory", content.get("accessory", [])),
            ("finisher", self._extract_finisher_exercises(content.get("finisher"))),
            ("warmup", content.get("warmup", [])),
            ("cooldown", content.get("cooldown", [])),
        ]
        
        # Process each section in priority order
        for section_name, exercises in sections_priority:
            if not exercises:
                continue
                
            # Filter out duplicates from this section
            filtered_exercises = []
            for exercise in exercises:
                movement_name = exercise.get("movement", "").strip()
                if movement_name and movement_name not in used_movements:
                    filtered_exercises.append(exercise)
                    used_movements.add(movement_name)
                elif movement_name in used_movements:
                    logger.warning(
                        f"Removed duplicate movement '{movement_name}' from {section_name} section "
                        f"(already exists in higher priority section)"
                    )
                    # Track removed exercise for potential replacement
                    removed_exercises.append({
                        "section": section_name,
                        "exercise": exercise,
                        "original_movement": movement_name
                    })
            
            # Update the content with filtered exercises
            if section_name == "finisher":
                # Special handling for finisher structure
                if content.get("finisher"):
                    if filtered_exercises:
                        content["finisher"]["exercises"] = filtered_exercises
                    else:
                        # Don't remove finisher yet - we'll add replacements later
                        content["finisher"]["exercises"] = []
            else:
                content[section_name] = filtered_exercises
        
        # INTELLIGENT REPLACEMENT: Find alternatives for removed exercises
        if removed_exercises:
            content = self._replace_removed_exercises(
                content, removed_exercises, used_movements, session_type
            )
        
        # Clean up empty sections after replacement attempts
        if content.get("finisher") and not content["finisher"].get("exercises"):
            content["finisher"] = None
        
        # Validate that we still have required sections after deduplication
        if not content.get("main"):
            logger.error(f"All main exercises were duplicates! Adding fallback for {session_type}")
            fallback = self._get_fallback_session_content(session_type)
            content["main"] = fallback.get("main", [])
        
        return content
    
    def _replace_removed_exercises(
        self,
        content: dict[str, Any],
        removed_exercises: list[dict],
        used_movements: set[str],
        session_type: SessionType,
    ) -> dict[str, Any]:
        """
        Intelligently replace removed duplicate exercises to preserve muscle group coverage.
        
        Replacement hierarchy:
        1. Same primary muscle, different movement
        2. Same secondary muscle, different movement  
        3. Same movement pattern, different movement
        4. Complementary muscle (antagonist)
        5. Skip if no suitable replacement found
        
        Args:
            content: Session content dict
            removed_exercises: List of removed exercise info
            used_movements: Set of movements already used in session
            session_type: Type of session
            
        Returns:
            Session content with intelligent replacements added
        """
        # Define muscle group relationships for intelligent replacement
        muscle_alternatives = {
            # Rear delts alternatives (primary focus)
            "rear_delts": ["Face Pull", "Reverse Fly", "Band Pull-Apart", "Prone Y Raise", "Cable Reverse Fly"],
            # Chest alternatives
            "chest": ["Push-Up", "Dumbbell Fly", "Cable Fly", "Incline Push-Up", "Chest Dip"],
            # Back alternatives  
            "lats": ["Lat Pulldown", "Pull-Up", "Chin-Up", "Cable Row", "T-Bar Row"],
            "upper_back": ["Face Pull", "Shrug", "Upright Row", "High Pull", "Band Pull-Apart"],
            # Shoulder alternatives
            "front_delts": ["Front Raise", "Arnold Press", "Pike Push-Up", "Handstand Push-Up"],
            "side_delts": ["Lateral Raise", "Upright Row", "Cable Lateral Raise", "Dumbbell Lateral Raise"],
            # Arm alternatives
            "biceps": ["Bicep Curl", "Hammer Curl", "Cable Curl", "Chin-Up", "Preacher Curl"],
            "triceps": ["Tricep Extension", "Close-Grip Push-Up", "Tricep Dip", "Overhead Extension"],
            # Leg alternatives
            "quadriceps": ["Leg Extension", "Lunge", "Step-Up", "Wall Sit", "Jump Squat"],
            "hamstrings": ["Leg Curl", "Romanian Deadlift", "Good Morning", "Glute Ham Raise"],
            "glutes": ["Hip Thrust", "Glute Bridge", "Clamshell", "Monster Walk", "Bulgarian Split Squat"],
            "calves": ["Calf Raise", "Jump Rope", "Calf Press", "Single Leg Calf Raise"],
        }
        
        # Movement pattern alternatives
        pattern_alternatives = {
            "horizontal_push": ["Push-Up", "Dumbbell Fly", "Cable Fly"],
            "horizontal_pull": ["Cable Row", "Band Pull-Apart", "Inverted Row"],
            "vertical_push": ["Pike Push-Up", "Handstand Push-Up", "Arnold Press"],
            "vertical_pull": ["Pull-Up", "Lat Pulldown", "High Pull"],
        }
        
        # Process each removed exercise
        for removed_info in removed_exercises:
            section_name = removed_info["section"]
            original_exercise = removed_info["exercise"]
            original_movement = removed_info["original_movement"]
            
            # Skip if section no longer exists or is empty
            if section_name == "finisher":
                if not content.get("finisher"):
                    continue
            
            # Find replacement movement
            replacement_movement = self._find_replacement_movement(
                original_movement, muscle_alternatives, pattern_alternatives, used_movements
            )
            
            if replacement_movement:
                # Create replacement exercise with similar parameters
                replacement_exercise = self._create_replacement_exercise(
                    original_exercise, replacement_movement, section_name
                )
                
                # Add replacement to appropriate section
                if section_name == "finisher":
                    if content.get("finisher"):
                        if "exercises" not in content["finisher"]:
                            content["finisher"]["exercises"] = []
                        content["finisher"]["exercises"].append(replacement_exercise)
                else:
                    if section_name not in content:
                        content[section_name] = []
                    content[section_name].append(replacement_exercise)
                
                # Track the new movement as used
                used_movements.add(replacement_movement)
                
                logger.info(
                    f"Replaced removed '{original_movement}' in {section_name} section "
                    f"with '{replacement_movement}' to preserve muscle group coverage"
                )
            else:
                logger.warning(
                    f"Could not find suitable replacement for '{original_movement}' "
                    f"in {section_name} section - muscle group coverage may be reduced"
                )
        
        return content
    
    def _find_replacement_movement(
        self,
        original_movement: str,
        muscle_alternatives: dict[str, list[str]],
        pattern_alternatives: dict[str, list[str]],
        used_movements: set[str],
    ) -> str | None:
        """
        Find the best replacement movement using hierarchy of muscle/pattern matching.
        
        Args:
            original_movement: Name of the removed movement
            muscle_alternatives: Dict mapping muscle groups to alternative exercises
            pattern_alternatives: Dict mapping movement patterns to alternatives
            used_movements: Set of movements already used in session
            
        Returns:
            Name of replacement movement or None if no suitable replacement found
        """
        # Simple muscle group mapping based on common exercise names
        # In a full implementation, this would query the Movement model
        movement_to_muscles = {
            "Face Pull": ["rear_delts", "upper_back"],
            "Lateral Raise": ["side_delts"],
            "Bicep Curl": ["biceps"],
            "Tricep Extension": ["triceps"],
            "Leg Extension": ["quadriceps"],
            "Leg Curl": ["hamstrings"],
            "Calf Raise": ["calves"],
            "Push-Up": ["chest", "front_delts", "triceps"],
            "Pull-Up": ["lats", "biceps"],
            "Barbell Row": ["lats", "upper_back", "rear_delts"],
            "Barbell Bench Press": ["chest", "front_delts", "triceps"],
        }
        
        # Get muscle groups for original movement
        original_muscles = movement_to_muscles.get(original_movement, [])
        
        # Try to find replacement by muscle group priority
        for muscle in original_muscles:
            if muscle in muscle_alternatives:
                for alternative in muscle_alternatives[muscle]:
                    if alternative not in used_movements and alternative != original_movement:
                        return alternative
        
        # Fallback: try pattern-based alternatives (simplified) - only if no muscle match found
        if not original_muscles:  # Only use pattern fallback if we couldn't identify muscles
            movement_to_pattern = {
                "Face Pull": "horizontal_pull",
                "Barbell Row": "horizontal_pull", 
                "Push-Up": "horizontal_push",
                "Barbell Bench Press": "horizontal_push",
                "Pull-Up": "vertical_pull",
                "Overhead Press": "vertical_push",
            }
            
            original_pattern = movement_to_pattern.get(original_movement)
            if original_pattern and original_pattern in pattern_alternatives:
                for alternative in pattern_alternatives[original_pattern]:
                    if alternative not in used_movements and alternative != original_movement:
                        return alternative
        
        return None
    
    def _remove_cross_session_accessory_duplicates(
        self,
        content: dict[str, Any],
        previous_accessories: set[str],
        session_type: SessionType,
    ) -> dict[str, Any]:
        used_movements_session: set[str] = set()
        
        for section_name in ["main", "accessory", "warmup", "cooldown"]:
            for ex in content.get(section_name) or []:
                name = (ex.get("movement") or "").strip()
                if name:
                    used_movements_session.add(name)
        
        finisher_struct = content.get("finisher")
        finisher_exercises = []
        if finisher_struct and isinstance(finisher_struct, dict):
            for ex in finisher_struct.get("exercises") or []:
                name = (ex.get("movement") or "").strip()
                if name:
                    used_movements_session.add(name)
                    finisher_exercises.append(ex)
        
        used_movements_session.update(previous_accessories)
        
        removed_exercises: list[dict] = []
        new_accessories: list[dict] = []
        
        for ex in content.get("accessory") or []:
            movement_name = (ex.get("movement") or "").strip()
            if movement_name and movement_name in previous_accessories:
                removed_exercises.append(
                    {
                        "section": "accessory",
                        "exercise": ex,
                        "original_movement": movement_name,
                    }
                )
            else:
                new_accessories.append(ex)
        
        content["accessory"] = new_accessories
        
        new_finisher_exercises: list[dict] = []
        for ex in finisher_exercises:
            movement_name = (ex.get("movement") or "").strip()
            if movement_name and movement_name in previous_accessories:
                removed_exercises.append(
                    {
                        "section": "finisher",
                        "exercise": ex,
                        "original_movement": movement_name,
                    }
                )
            else:
                new_finisher_exercises.append(ex)
        
        if finisher_struct and isinstance(finisher_struct, dict):
            finisher_struct["exercises"] = new_finisher_exercises
            content["finisher"] = finisher_struct
        
        if removed_exercises:
            content = self._replace_removed_exercises(
                content, removed_exercises, used_movements_session, session_type
            )
        
        return content
    
    def _create_replacement_exercise(
        self,
        original_exercise: dict,
        replacement_movement: str,
        section_name: str,
    ) -> dict:
        """
        Create a replacement exercise with appropriate parameters for the section.
        
        Args:
            original_exercise: Original exercise dict
            replacement_movement: Name of replacement movement
            section_name: Section where replacement will be added
            
        Returns:
            New exercise dict with replacement movement and appropriate parameters
        """
        # Base replacement exercise
        replacement = {
            "movement": replacement_movement,
            "notes": f"Replacement for duplicate exercise"
        }
        
        # Copy relevant parameters from original, with section-appropriate defaults
        if section_name in ["main"]:
            # Main exercises: higher intensity, longer rest
            replacement.update({
                "sets": original_exercise.get("sets", 4),
                "rep_range_min": original_exercise.get("rep_range_min", 6),
                "rep_range_max": original_exercise.get("rep_range_max", 8),
                "target_rpe": original_exercise.get("target_rpe", 7.5),
                "rest_seconds": original_exercise.get("rest_seconds", 120),
            })
        elif section_name in ["accessory"]:
            # Accessory exercises: moderate intensity, shorter rest
            replacement.update({
                "sets": original_exercise.get("sets", 3),
                "rep_range_min": original_exercise.get("rep_range_min", 10),
                "rep_range_max": original_exercise.get("rep_range_max", 15),
                "target_rpe": original_exercise.get("target_rpe", 7),
                "rest_seconds": original_exercise.get("rest_seconds", 60),
            })
        elif section_name in ["finisher"]:
            # Finisher exercises: higher reps, minimal rest
            replacement.update({
                "reps": original_exercise.get("reps", 15),
                "duration_seconds": original_exercise.get("duration_seconds"),
            })
        elif section_name in ["warmup", "cooldown"]:
            # Warmup/cooldown: time-based or light reps
            replacement.update({
                "sets": original_exercise.get("sets", 2),
                "reps": original_exercise.get("reps", 10),
                "duration_seconds": original_exercise.get("duration_seconds", 60),
            })
        
        return replacement
    
    def _extract_finisher_exercises(self, finisher: dict | None) -> list[dict]:
        """Extract exercises list from finisher structure."""
        if not finisher or not isinstance(finisher, dict):
            return []
        return finisher.get("exercises", [])
    
    def _get_default_accessories(self, session_type: SessionType) -> list[dict[str, Any]]:
        """
        Get default accessory exercises based on session type.
        
        Args:
            session_type: Type of session
            
        Returns:
            List of accessory exercises
        """
        # Default accessories by session type
        defaults = {
            SessionType.UPPER: [
                {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Face Pull"},
                {"movement": "Face Pull", "sets": 3, "rep_range_min": 15, "rep_range_max": 20, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Bicep Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Tricep Extension"},
                {"movement": "Tricep Extension", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, 
                 "target_rpe": 7, "rest_seconds": 60},
            ],
            SessionType.LOWER: [
                {"movement": "Leg Extension", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Leg Curl"},
                {"movement": "Leg Curl", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Calf Raise", "sets": 4, "rep_range_min": 15, "rep_range_max": 20, 
                 "target_rpe": 8, "rest_seconds": 45},
            ],
            SessionType.PUSH: [
                {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Tricep Extension", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, 
                 "target_rpe": 7, "rest_seconds": 60},
            ],
            SessionType.PULL: [
                {"movement": "Face Pull", "sets": 3, "rep_range_min": 15, "rep_range_max": 20, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Bicep Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Hammer Curl"},
                {"movement": "Hammer Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, 
                 "target_rpe": 7, "rest_seconds": 60},
            ],
            SessionType.LEGS: [
                {"movement": "Leg Extension", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Leg Curl"},
                {"movement": "Leg Curl", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Calf Raise", "sets": 4, "rep_range_min": 15, "rep_range_max": 20, 
                 "target_rpe": 8, "rest_seconds": 45},
            ],
            SessionType.FULL_BODY: [
                {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60, "superset_with": "Face Pull"},
                {"movement": "Face Pull", "sets": 3, "rep_range_min": 15, "rep_range_max": 20, 
                 "target_rpe": 7, "rest_seconds": 60},
                {"movement": "Leg Curl", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, 
                 "target_rpe": 7, "rest_seconds": 60},
            ],
        }
        
        # Return session-specific defaults or generic upper body accessories
        return defaults.get(session_type, defaults[SessionType.UPPER])
    
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
    ) -> dict[str, Any]:
        """
        Return intelligent fallback content when LLM fails.
        
        Uses movement library and intent_tags to select real exercises
        instead of generic placeholders.
        
        Args:
            session_type: Type of session (FULL_BODY, UPPER, LOWER, etc.)
            intent_tags: Movement patterns for this session (e.g., ["squat", "horizontal_push"])
            movements_by_pattern: Dict mapping pattern names to available movements
            used_movements: List of movements to avoid (already used in microcycle)
        
        Returns:
            Session content dict with real movement names
        """
        # Preferred accessory movements by pattern
        preferred_accessories = {
            "squat": ["Leg Extension", "Leg Curl", "Calf Raise", "Walking Lunge"],
            "hinge": ["Leg Curl", "Leg Extension", "Hip Thrust", "Back Extension"],
            "lunge": ["Leg Extension", "Calf Raise", "Split Squat", "Step Up"],
            "horizontal_push": ["Lateral Raise", "Face Pull", "Tricep Pushdown", "Fly"],
            "horizontal_pull": ["Bicep Curl", "Face Pull", "Rear Delt Fly", "Hammer Curl"],
            "vertical_push": ["Lateral Raise", "Face Pull", "Tricep Extension", "Upright Row"],
            "vertical_pull": ["Bicep Curl", "Hammer Curl", "Preacher Curl", "Shrug"],
        }
        
        # Build main exercises from intent tags
        main_exercises = []
        # Initialize set with passed movements
        used_movements_set = set(used_movements) if used_movements else set()
        
        for tag in intent_tags[:3]:  # Max 3 main lifts
            if tag in movements_by_pattern and movements_by_pattern[tag]:
                # Find an unused movement for this pattern
                for movement_name in movements_by_pattern[tag]:
                    if movement_name not in used_movements_set:
                        main_exercises.append({
                            "movement": movement_name,
                            "sets": 4,
                            "rep_range_min": 6,
                            "rep_range_max": 10,
                            "target_rpe": 7,
                            "rest_seconds": 120,
                        })
                        used_movements_set.add(movement_name)
                        break
        
        # Build accessory exercises based on primary patterns
        accessory_exercises = []
        
        for tag in intent_tags[:2]:  # Accessories for first 2 patterns
            if tag in preferred_accessories:
                for acc_name in preferred_accessories[tag]:
                    if acc_name not in used_movements_set:
                        accessory_exercises.append({
                            "movement": acc_name,
                            "sets": 3,
                            "rep_range_min": 10,
                            "rep_range_max": 15,
                            "target_rpe": 7,
                            "rest_seconds": 60,
                        })
                        used_movements_set.add(acc_name)
                        break
        
        # If we couldn't build main exercises, fall back to hardcoded
        if not main_exercises:
            return self._get_fallback_session_content(session_type)
        
        # Build warmup based on session type
        warmup = [
            {"movement": "Dynamic Stretching", "sets": 1, "duration_seconds": 180, "notes": "Full body mobility"},
        ]
        
        # Add pattern-specific warmup
        if any(p in intent_tags for p in ["squat", "hinge", "lunge"]):
            warmup.append({"movement": "Goblet Squat", "sets": 2, "reps": 8, "notes": "Light weight warmup"})
        if any(p in intent_tags for p in ["horizontal_push", "vertical_push"]):
            warmup.append({"movement": "Push-Up", "sets": 2, "reps": 10, "notes": "Warmup sets"})
        if any(p in intent_tags for p in ["horizontal_pull", "vertical_pull"]):
            warmup.append({"movement": "Inverted Row", "sets": 2, "reps": 8, "notes": "Light warmup"})
        
        # Build cooldown
        cooldown = [
            {"movement": "Static Stretching", "duration_seconds": 300, "notes": "Focus on trained muscles"},
        ]
        
        # Estimate duration: warmup (10) + main (25-30) + accessory (10-15) + cooldown (5) = ~55 min
        estimated_duration = 10 + (len(main_exercises) * 10) + (len(accessory_exercises) * 5) + 5
        
        return {
            "warmup": warmup,
            "main": main_exercises,
            "accessory": accessory_exercises if accessory_exercises else None,
            "finisher": None,
            "cooldown": cooldown,
            "estimated_duration_minutes": estimated_duration,
            "reasoning": f"Smart fallback session - LLM unavailable. Selected exercises based on {', '.join(intent_tags)} patterns.",
        }
    
    def _get_fallback_session_content(self, session_type: SessionType) -> dict[str, Any]:
        """Return basic fallback content when smart fallback also fails."""
        # Basic fallback based on session type
        fallbacks = {
            SessionType.UPPER: {
                "warmup": [
                    {"movement": "Arm Circles", "sets": 2, "reps": 10},
                    {"movement": "Band Pull-Aparts", "sets": 2, "reps": 15},
                ],
                "main": [
                    {"movement": "Barbell Bench Press", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 120},
                    {"movement": "Barbell Row", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 120},
                    {"movement": "Overhead Press", "sets": 3, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 90},
                ],
                "accessory": [
                    {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, "target_rpe": 7, "rest_seconds": 60},
                    {"movement": "Bicep Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 60},
                ],
                "finisher": None,
                "cooldown": [
                    {"movement": "Static Stretching", "duration_seconds": 300},
                ],
                "estimated_duration_minutes": 55,
                "reasoning": "Fallback upper body session - LLM generation failed.",
            },
            SessionType.LOWER: {
                "warmup": [
                    {"movement": "Dynamic Stretching", "sets": 1, "duration_seconds": 180},
                    {"movement": "Goblet Squat", "sets": 2, "reps": 8},
                ],
                "main": [
                    {"movement": "Back Squat", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 150},
                    {"movement": "Romanian Deadlift", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
                ],
                "accessory": [
                    {"movement": "Walking Lunge", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 90},
                    {"movement": "Leg Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 60},
                ],
                "finisher": None,
                "cooldown": [
                    {"movement": "Hip Flexor Stretch", "duration_seconds": 120},
                    {"movement": "Static Stretching", "duration_seconds": 180},
                ],
                "estimated_duration_minutes": 55,
                "reasoning": "Fallback lower body session - LLM generation failed.",
            },
            SessionType.FULL_BODY: {
                "warmup": [
                    {"movement": "Dynamic Stretching", "sets": 1, "duration_seconds": 180},
                    {"movement": "Goblet Squat", "sets": 2, "reps": 8},
                ],
                "main": [
                    {"movement": "Back Squat", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 150},
                    {"movement": "Barbell Bench Press", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 120},
                    {"movement": "Barbell Row", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 120},
                ],
                "accessory": [
                    {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, "target_rpe": 7, "rest_seconds": 60},
                    {"movement": "Leg Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 60},
                ],
                "finisher": None,
                "cooldown": [
                    {"movement": "Static Stretching", "duration_seconds": 300},
                ],
                "estimated_duration_minutes": 60,
                "reasoning": "Fallback full body session - LLM generation failed.",
            },
        }
        
        # Default fallback for other session types (PPL, etc.)
        default = {
            "warmup": [
                {"movement": "Dynamic Stretching", "sets": 1, "duration_seconds": 180},
            ],
            "main": [
                {"movement": "Back Squat", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
                {"movement": "Barbell Bench Press", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
            ],
            "accessory": [
                {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, "target_rpe": 7, "rest_seconds": 60},
            ],
            "finisher": None,
            "cooldown": [
                {"movement": "Static Stretching", "duration_seconds": 300},
            ],
            "estimated_duration_minutes": 50,
            "reasoning": "Fallback session - LLM generation failed.",
        }
        
        return fallbacks.get(session_type, default)

    async def _load_all_movements(self, db: AsyncSession) -> list[Movement]:
        """Load all movements from the database."""
        result = await db.execute(select(Movement))
        return list(result.scalars().all())
    
    async def _load_all_circuits(self, db: AsyncSession) -> list[SolverCircuit]:
        """Load all circuits and convert to SolverCircuit format."""
        from app.services.optimization import SolverCircuit
        from app.models.circuit import CircuitTemplate
        
        result = await db.execute(select(CircuitTemplate))
        circuits = list(result.scalars().all())
        
        return [
            SolverCircuit(
                id=c.id,
                name=c.name,
                primary_muscle=self._get_circuit_primary_muscle(c),
                fatigue_factor=c.fatigue_factor if c.fatigue_factor else 1.0,
                stimulus_factor=c.stimulus_factor if c.stimulus_factor else 1.0,
                effective_work_volume=c.effective_work_volume if c.effective_work_volume else 0.0,
                circuit_type=c.circuit_type,
                duration_seconds=c.estimated_work_seconds if c.estimated_work_seconds else 600
            )
            for c in circuits
        ]
    
    def _get_circuit_primary_muscle(self, circuit: CircuitTemplate) -> str:
        """Determine the primary muscle for a circuit based on muscle_volume."""
        if circuit.muscle_volume:
            sorted_muscles = sorted(circuit.muscle_volume.items(), key=lambda x: x[1], reverse=True)
            if sorted_muscles:
                return sorted_muscles[0][0]  # muscle with highest volume
        return "full_body"  # fallback

    def _get_muscle_targets_for_session(self, session_type: SessionType) -> dict[str, int]:
        """Define muscle volume targets based on session type."""
        # Uses exact Enum string values from PrimaryMuscle
        if session_type == SessionType.UPPER:
            return {
                "chest": 1, 
                "lats": 1, 
                "side_delts": 1, 
                "biceps": 1, 
                "triceps": 1
            }
        elif session_type == SessionType.LOWER:
            return {
                "quadriceps": 1, 
                "hamstrings": 1, 
                "glutes": 1, 
                "calves": 1
            }
        elif session_type == SessionType.PUSH:
            return {
                "chest": 1, 
                "front_delts": 1, 
                "triceps": 1, 
                "quadriceps": 1
            }
        elif session_type == SessionType.PULL:
            return {
                "lats": 1, 
                "biceps": 1, 
                "hamstrings": 1, 
                "rear_delts": 1
            }
        elif session_type == SessionType.FULL_BODY:
            return {
                "quadriceps": 1, 
                "hamstrings": 1, 
                "chest": 1, 
                "lats": 1, 
                "side_delts": 1
            }
        return {}
        
    def _filter_movements_for_session_type(self, movements: list[Movement], session_type: SessionType) -> list[Movement]:
        """Filter movements that are appropriate for the session type."""
        
        lower_regions = ["anterior lower", "posterior lower", "lower body"]
        upper_regions = ["anterior upper", "posterior upper", "shoulder", "upper body"]
        
        filtered = []
        for m in movements:
            # Handle Enum or string
            region = str(m.primary_region.value) if hasattr(m.primary_region, 'value') else str(m.primary_region)
            
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
                primary_muscle=str(m.primary_muscle.value) if hasattr(m.primary_muscle, 'value') else str(m.primary_muscle),
                fatigue_factor=m.fatigue_factor,
                stimulus_factor=m.stimulus_factor,
                compound=m.compound,
                is_complex_lift=m.is_complex_lift
            )
            for m in movements
        ]
    
    def _to_solver_circuits(self, circuits: list[SolverCircuit]) -> list[SolverCircuit]:
        """Circuits are already in SolverCircuit format."""
        return circuits
    
    def _filter_circuits_for_session_type(self, circuits: list[SolverCircuit], session_type: SessionType) -> list[SolverCircuit]:
        """Filter circuits that are appropriate for session type."""
        if session_type in {SessionType.CARDIO, SessionType.MOBILITY, SessionType.RECOVERY}:
            return []
        return circuits

    async def _generate_draft_session(
        self, 
        db: AsyncSession, 
        session: Session,
        used_movements: list[str] | None = None,
        goal_weights: dict[str, int] | None = None,
    ) -> Any:
        """
        Generate a draft session using the Optimization Engine (OR-Tools).
        This serves as the 'Draft Generator' in the Chain of Reasoning.
        """
        # Load all movements for the solver
        all_movements = await self._load_all_movements(db)
        
        # Load all circuits (if available)
        all_circuits = await self._load_all_circuits(db)
        
        # Load user movement rules (HARD_NO, HARD_YES, PREFERRED)
        movement_rules = await self._load_user_movement_rules(db, session.program.user_id)
        preferred_ids: list[int] = []
        hard_no_ids: list[int] = []
        hard_yes_ids: list[int] = []
        for rule, movement in movement_rules:
            if rule.rule_type == MovementRuleType.PREFERRED:
                preferred_ids.append(movement.id)
            elif rule.rule_type == MovementRuleType.HARD_NO:
                hard_no_ids.append(movement.id)
            elif rule.rule_type == MovementRuleType.HARD_YES:
                hard_yes_ids.append(movement.id)
        
        # Filter movements based on session type
        filtered_movements = self._filter_movements_for_session_type(all_movements, session.session_type)
        
        # Filter circuits based on session type
        filtered_circuits = self._filter_circuits_for_session_type(all_circuits, session.session_type)
        
        # Convert to DTOs for thread safety
        solver_movements = self._to_solver_movements(filtered_movements)
        solver_circuits = self._to_solver_circuits(filtered_circuits)
        
        # Determine targets based on session type
        targets = self._get_muscle_targets_for_session(session.session_type)
        
        # Map used_movements (names) to excluded_movement_ids for Variety
        excluded_ids = list(hard_no_ids)  # Start with HARD_NO movements
        if used_movements:
            name_to_id = {m.name: m.id for m in all_movements}
            for name in used_movements:
                if name in name_to_id:
                    excluded_ids.append(name_to_id[name])

        # Build request
        req = OptimizationRequest(
            available_movements=solver_movements,
            available_circuits=solver_circuits,
            target_muscle_volumes=targets,
            max_fatigue=activity_distribution_config.or_tools_max_fatigue,
            min_stimulus=2.0,
            user_skill_level=SkillLevel.INTERMEDIATE,
            excluded_movement_ids=excluded_ids,
            required_movement_ids=hard_yes_ids,
            session_duration_minutes=60,
            allow_complex_lifts=True,
            allow_circuits=True,
            goal_weights=goal_weights,
            preferred_movement_ids=preferred_ids,
        )
        
        # Solve in a separate thread to avoid blocking the event loop
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.optimizer.solve_session, req)

    def _format_draft_for_llm(self, draft_content: dict) -> str:
        """Format the draft session content into a string for the LLM prompt."""
        lines = ["Based on mathematical optimization, here is a starting point:"]
        
        if draft_content.get("main"):
            lines.append("Main Lifts:")
            for ex in draft_content["main"]:
                lines.append(f"- {ex['movement']} ({ex['sets']} sets)")
        
        if draft_content.get("accessory"):
            lines.append("Accessories:")
            for ex in draft_content["accessory"]:
                lines.append(f"- {ex['movement']} ({ex['sets']} sets)")
                
        return "\n".join(lines)

    def _convert_optimization_result_to_content(self, result: Any, session_type: SessionType) -> dict[str, Any]:
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
                "notes": "Optimized selection"
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
            main_exercises.append({
                "movement": "Generation Failed",
                "sets": 0,
                "rep_range_min": 0,
                "rep_range_max": 0,
                "target_rpe": 0,
                "rest_seconds": 0,
                "notes": f"Could not generate valid session. Status: {result.status}. Please try regenerating or editing manually."
            })
            
        return {
            "warmup": [
                {"movement": "Dynamic Stretching", "sets": 1, "duration_seconds": 300, "notes": "General prep"},
                {"movement": "Light Cardio", "duration_seconds": 300, "notes": "Raise body temp"}
            ],
            "main": main_exercises,
            "accessory": accessory_exercises,
            "finisher": None,
            "cooldown": [
                {"movement": "Static Stretching", "duration_seconds": 300, "notes": "Full body"}
            ],
            "estimated_duration_minutes": result.estimated_duration + 10, # +10 for warmup/cool
            "reasoning": f"Optimization Engine generated session. Status: {result.status}. Stimulus: {result.total_stimulus:.2f}, Fatigue: {result.total_fatigue:.2f}"
        }


# Singleton instance
session_generator = SessionGeneratorService()
