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
        # ENTRY POINT LOGGING
        logger.info("=" * 80)
        logger.info(f"[generate_session_exercises] ENTRY POINT - Session ID: {session.id}")
        logger.info(f"[generate_session_exercises] User ID: {program.user_id}")
        logger.info(f"[generate_session_exercises] Session Type: {session.session_type.value}")
        logger.info(f"[generate_session_exercises] Intent Tags: {session.intent_tags or []}")
        logger.info(f"[generate_session_exercises] Day Number: {session.day_number}")
        logger.info(f"[generate_session_exercises] Microcycle Deload: {microcycle.is_deload}")
        logger.info(f"[generate_session_exercises] Used Movements Count: {len(used_movements) if used_movements else 0}")
        logger.info(f"[generate_session_exercises] Fatigued Muscles: {fatigued_muscles or []}")
        logger.info("=" * 80)
        
        # Skip generation for rest/recovery sessions
        if session.session_type == SessionType.RECOVERY:
            logger.info("[generate_session_exercises] Session type is RECOVERY, returning recovery content")
            return self._get_recovery_session_content()
        
        # Load movement library grouped by pattern
        movements_by_pattern = await self._load_movements_by_pattern(db)
        all_movements = await self._load_all_movements(db)
        goal_weights = self._get_goal_weights_for_program(program)
        
        # LOG GOAL WEIGHTS
        logger.info(f"[generate_session_exercises] Goal Weights: {goal_weights}")
        
        # Generate optimal draft using Constraint Solver
        draft_content = None
        try:
            logger.info("[generate_session_exercises] Attempting to generate optimal draft session...")
            draft_result = await self._generate_draft_session(db, session, used_movements, goal_weights=goal_weights, max_session_duration=program.max_session_duration)
            if draft_result.status in ["OPTIMAL", "FEASIBLE"] and draft_result.selected_movements:
                draft_content = self._convert_optimization_result_to_content(draft_result, session.session_type, all_movements)
                logger.info(f"[generate_session_exercises] Generated optimal draft for session {session.id} with status {draft_result.status}")
                logger.info(f"[generate_session_exercises] Selected movements: {len(draft_result.selected_movements)}")
            else:
                logger.info(f"[generate_session_exercises] Draft generation returned status {draft_result.status}, no optimal solution found")
        except Exception as e:
            logger.warning(f"[generate_session_exercises] Failed to generate draft session: {e}", exc_info=True)

        if session.session_type == SessionType.CUSTOM and "conditioning" in (session.intent_tags or []):
            logger.info("[generate_session_exercises] Path: CUSTOM conditioning session")
            all_movements = await self._load_all_movements(db)
            conditioning_names = self._get_conditioning_movement_names(all_movements)
            content = self._get_fast_conditioning_session_content(conditioning_names, program.max_session_duration, all_movements)
        elif session.session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            logger.info(f"[generate_session_exercises] Path: {session.session_type.value} session")
            all_movements = await self._load_all_movements(db)
            content = self._get_fast_special_session_content(session.session_type, program.max_session_duration, all_movements)
        elif draft_content:
            logger.info("[generate_session_exercises] Path: Building content from optimal draft")
            content = await self._build_fast_content_from_draft(
                draft_content,
                session.session_type,
                session.intent_tags or [],
                microcycle.is_deload,
                goal_weights,
                all_movements,
            )
        else:
            logger.info("[generate_session_exercises] Path: Using smart fallback session content")
            content = self._get_smart_fallback_session_content(
                session.session_type,
                session.intent_tags or [],
                movements_by_pattern,
                used_movements=used_movements,
                all_movements=all_movements,
            )
            if session.session_type not in {SessionType.CARDIO, SessionType.MOBILITY} and not content.get("finisher"):
                logger.info("[generate_session_exercises] No finisher found, attempting to build goal finisher")
                finisher = await self._build_goal_finisher(
                    goal_weights,
                    session_type=session.session_type,
                    intent_tags=session.intent_tags,
                    existing_circuit_ids=None
                )
                if finisher:
                    logger.info(f"[generate_session_exercises] Successfully added finisher: {finisher.get('type', 'unknown')}")
                    content["finisher"] = finisher
                else:
                    logger.info("[generate_session_exercises] No finisher could be built")

        logger.info(f"[generate_session_exercises] Content keys before normalization: {list(content.keys())}")
        content = await self._normalize_session_content(content, session.session_type, session.intent_tags or [], goal_weights)
        logger.info(f"[generate_session_exercises] Content keys after normalization: {list(content.keys())}")
        logger.info(f"[generate_session_exercises] Estimated duration: {content.get('estimated_duration_minutes', 'N/A')} minutes")
        # Jerome notes generation moved to batched microcycle-level generation in program.py
        logger.info(f"[generate_session_exercises] RETURN - Session ID: {session.id}, Content sections: {list(content.keys())}")
        logger.info("=" * 80)
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
        
        logger.info("=" * 80)
        logger.info(f"[populate_session_by_id] ENTRY POINT")
        logger.info(f"[populate_session_by_id] session_id={session_id}, program_id={program_id}, microcycle_id={microcycle_id}")
        logger.info(f"[populate_session_by_id] Used movements count: {len(used_movements) if used_movements else 0}")
        logger.info(f"[populate_session_by_id] Used movement groups: {used_movement_groups}")
        logger.info(f"[populate_session_by_id] Previous day volume: {previous_day_volume}")
        logger.info("=" * 80)
        
        # 1. Fetch all necessary context (short DB transaction)
        context_data = {}
        async with async_session_maker() as db:
            from sqlalchemy.orm import selectinload
            session = await db.get(Session, session_id)
            program = await db.get(Program, program_id, options=[selectinload(Program.program_disciplines)])
            microcycle = await db.get(Microcycle, microcycle_id)
            
            if not session or not program or not microcycle:
                logger.error(f"[populate_session_by_id] FAILED - session={session}, program={program}, microcycle={microcycle}")
                logger.info("=" * 80)
                return {}
            
            logger.info(f"[populate_session_by_id] Fetched session: id={session.id}, type={session.session_type.value}, day={session.day_number}")
            logger.info(f"[populate_session_by_id] Session intent tags: {session.intent_tags or []}")
            logger.info(f"[populate_session_by_id] Program: id={program.id}, user_id={program.user_id}, split={program.split_template}")
            logger.info(f"[populate_session_by_id] Program goals: {program.goal_1}, {program.goal_2}, {program.goal_3}")
            logger.info(f"[populate_session_by_id] Program goal weights: {program.goal_weight_1}, {program.goal_weight_2}, {program.goal_weight_3}")
            logger.info(f"[populate_session_by_id] Microcycle: is_deload={microcycle.is_deload}, sequence={microcycle.sequence_number}")
            
            # Fetch supporting data
            logger.info(f"[populate_session_by_id] Loading supporting data...")
            movements_by_pattern = await self._load_movements_by_pattern(db)
            logger.info(f"[populate_session_by_id] Loaded {len(movements_by_pattern)} movement patterns")
            movement_rules = await self._load_user_movement_rules_dict(db, program.user_id)
            logger.info(f"[populate_session_by_id] Loaded movement rules: avoid={len(movement_rules.get('avoid', []))}, must_include={len(movement_rules.get('must_include', []))}, prefer={len(movement_rules.get('prefer', []))}")
            user_profile = await db.get(UserProfile, program.user_id)
            all_movements = await self._load_all_movements(db)
            logger.info(f"[populate_session_by_id] Loaded {len(all_movements)} total movements")
            
            # Load program disciplines from junction table
            program_disciplines = []
            for pd in program.program_disciplines:
                program_disciplines.append({
                    "discipline": pd.discipline_type,
                    "weight": pd.weight
                })
            logger.info(f"[populate_session_by_id] Loaded {len(program_disciplines)} program disciplines: {program_disciplines}")
            
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
            logger.info(f"[populate_session_by_id] Context data built with {len(context_data)} sections")

        # 2. Generate Content (Long running, NO DB connection)
        # We pass the context data instead of DB objects where possible
        logger.info("[populate_session_by_id] Generating content (offline, no DB connection)...")
        
        # Determine fatigued muscles
        fatigued_muscles = []
        if previous_day_volume:
            fatigued_muscles = [m for m, v in previous_day_volume.items() if v > 2]
        logger.info(f"[populate_session_by_id] Fatigued muscles determined: {fatigued_muscles}")

        logger.info("[populate_session_by_id] CALLING generate_session_exercises_offline()...")
        content = await self.generate_session_exercises_offline(
            context_data,
            used_movements,
            used_movement_groups,
            used_accessory_movements,
            fatigued_muscles
        )
        logger.info(f"[populate_session_by_id] RETURN from generate_session_exercises_offline: {list(content.keys())}")
        
        logger.info(f"[populate_session_by_id] Generated content sections: {list(content.keys())}")
        logger.info(f"[populate_session_by_id] Estimated duration: {content.get('estimated_duration_minutes', 'N/A')} minutes")
        
        # Post-processing (duplicates removal)
        logger.info("[populate_session_by_id] Checking for cross-session accessory duplicates...")
        if used_accessory_movements:
            current_day = context_data["session"]["day_number"]
            previous_days = [d for d in used_accessory_movements.keys() if d < current_day]
            logger.info(f"[populate_session_by_id] Previous days with accessories: {previous_days}")
            if previous_days:
                last_day = max(previous_days)
                previous_accessories = used_accessory_movements.get(last_day) or []
                logger.info(f"[populate_session_by_id] Previous day {last_day} accessories: {previous_accessories}")
                if previous_accessories:
                    content = self._remove_cross_session_accessory_duplicates(
                        content, set(previous_accessories), context_data["session"]["session_type"]
                    )
                    logger.info(f"[populate_session_by_id] Removed duplicate accessories from content")

        # 3. Save Results (Short DB transaction)
        current_session_volume = {}
        logger.info("[populate_session_by_id] SAVING to database...")
        logger.info(f"[populate_session_by_id] Saving session estimated_duration_minutes={content.get('estimated_duration_minutes', 60)}")
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
                # Note: Circuit IDs (main_circuit_id, finisher_circuit_id) are saved in _save_session_exercises()
                
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
                logger.info(f"[populate_session_by_id] Calculating session volume for session_id={session_id}")
                current_session_volume = await self._calculate_session_volume(db, session)
                logger.info(f"[populate_session_by_id] Calculated session volume: {current_session_volume}")
        
        logger.info(f"[populate_session_by_id] RETURN - session_id={session_id}, volume={current_session_volume}")
        logger.info("=" * 80)
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
        logger.info("-" * 80)
        logger.info(f"[generate_session_exercises_offline] ENTRY POINT")
        logger.info(f"[generate_session_exercises_offline] Session ID: {context['session']['id']}")
        logger.info(f"[generate_session_exercises_offline] Session Type: {context['session']['session_type'].value}")
        logger.info(f"[generate_session_exercises_offline] Intent Tags: {context['session']['intent_tags'] or []}")
        logger.info(f"[generate_session_exercises_offline] Day Number: {context['session']['day_number']}")
        logger.info(f"[generate_session_exercises_offline] Used movements count: {len(used_movements) if used_movements else 0}")
        logger.info(f"[generate_session_exercises_offline] Fatigued muscles: {fatigued_muscles or []}")
        logger.info(f"[generate_session_exercises_offline] Used movement groups: {used_movement_groups}")
        logger.info("-" * 80)
        
        session_type = context["session"]["session_type"]
        
        # Skip generation for rest/recovery sessions
        if session_type == SessionType.RECOVERY:
            logger.info("[generate_session_exercises_offline] Session type is RECOVERY, returning recovery content")
            logger.info("-" * 80)
            return self._get_recovery_session_content()
            
        movements_by_pattern = context["movements_by_pattern"]
        goal_weights = self._get_goal_weights_for_program_info(context["program"])
        logger.info(f"[generate_session_exercises_offline] Goal weights: {goal_weights}")
        
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
        
        logger.info(f"[generate_session_exercises_offline] Movement rules - preferred_ids: {len(preferred_ids)}, hard_no_ids: {len(hard_no_ids)}, hard_yes_ids: {len(hard_yes_ids)}")
        
        draft_content = None
        try:
            logger.info("[generate_session_exercises_offline] Attempting to generate draft session offline...")
            draft_result = await self._generate_draft_session_offline(
                context["all_movements"], 
                session_type, 
                used_movements,
                goal_weights=goal_weights,
                preferred_movement_ids=preferred_ids,
                excluded_movement_ids=hard_no_ids,
                required_movement_ids=hard_yes_ids,
                max_session_duration=context["program"]["max_session_duration"],
            )
            if draft_result.status in ["OPTIMAL", "FEASIBLE"] and draft_result.selected_movements:
                draft_content = self._convert_optimization_result_to_content(draft_result, session_type)
                logger.info(f"[generate_session_exercises_offline] Generated optimal draft for session {context['session']['id']} with status {draft_result.status}")
                logger.info(f"[generate_session_exercises_offline] Selected movements: {len(draft_result.selected_movements)}")
            else:
                logger.info(f"[generate_session_exercises_offline] Draft generation returned status {draft_result.status}, no optimal solution found")
        except Exception as e:
            logger.warning(f"[generate_session_exercises_offline] Failed to generate draft session: {e}", exc_info=True)
        
        if session_type == SessionType.CUSTOM and "conditioning" in (context["session"]["intent_tags"] or []):
            logger.info("[generate_session_exercises_offline] Path: CUSTOM conditioning session")
            all_movements = context.get("all_movements") or await self._load_all_movements(db)
            conditioning_names = self._get_conditioning_movement_names(all_movements)
            content = self._get_fast_conditioning_session_content(conditioning_names, context["program"]["max_session_duration"], all_movements)
        elif session_type in {SessionType.CARDIO, SessionType.MOBILITY}:
            logger.info(f"[generate_session_exercises_offline] Path: {session_type.value} session")
            all_movements = context.get("all_movements") or await self._load_all_movements(db)
            content = self._get_fast_special_session_content(session_type, context["program"]["max_session_duration"], all_movements)
        elif draft_content:
            logger.info("[generate_session_exercises_offline] Path: Building content from optimal draft")
            all_movements = context.get("all_movements") or await self._load_all_movements(db)
            content = await self._build_fast_content_from_draft(
                draft_content,
                session_type,
                context["session"]["intent_tags"] or [],
                context["microcycle"]["is_deload"],
                goal_weights,
                all_movements,
            )
        else:
            logger.info("[generate_session_exercises_offline] Path: Using smart fallback session content")
            all_movements = context.get("all_movements") or await self._load_all_movements(db)
            content = self._get_smart_fallback_session_content(
                session_type,
                context["session"]["intent_tags"] or [],
                movements_by_pattern,
                used_movements=used_movements,
                all_movements=all_movements,
            )
            if session_type not in {SessionType.CARDIO, SessionType.MOBILITY} and not content.get("finisher"):
                logger.info("[generate_session_exercises_offline] No finisher found, attempting to build goal finisher")
                finisher = await self._build_goal_finisher(
                    goal_weights,
                    session_type=session_type,
                    intent_tags=context["session"]["intent_tags"],
                    existing_circuit_ids=None
                )
                if finisher:
                    logger.info(f"[generate_session_exercises_offline] Successfully added finisher: {finisher.get('type', 'unknown')}")
                    content["finisher"] = finisher
                else:
                    logger.info("[generate_session_exercises_offline] No finisher could be built")

        logger.info(f"[generate_session_exercises_offline] Content keys before normalization: {list(content.keys())}")
        content = await self._normalize_session_content(content, session_type, context["session"]["intent_tags"] or [], goal_weights)
        logger.info(f"[generate_session_exercises_offline] Content keys after normalization: {list(content.keys())}")
        logger.info(f"[generate_session_exercises_offline] Estimated duration: {content.get('estimated_duration_minutes', 'N/A')} minutes")
        # Jerome notes generation moved to batched microcycle-level generation in program.py
        logger.info(f"[generate_session_exercises_offline] RETURN - Session ID: {context['session']['id']}, Content sections: {list(content.keys())}")
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
        
        logger.info(f"[_save_session_exercises] START - session_id={session.id}, content_keys={list(content.keys())}")
        
        # Clear existing exercises for this session
        await db.execute(delete(SessionExercise).where(SessionExercise.session_id == session.id))
        
        logger.info(f"[_save_session_exercises] Cleared existing exercises for session {session.id}")
        
        # Update circuit IDs based on content
        # Clear circuit IDs if no circuits are present in content
        circuit_block = content.get("circuit")
        if circuit_block and isinstance(circuit_block, dict) and circuit_block.get("circuit_id"):
            # Circuit block exists, set main_circuit_id
            session.main_circuit_id = circuit_block.get("circuit_id")
            session.has_circuits = True
            logger.info(f"[_save_session_exercises] Set main_circuit_id={session.main_circuit_id}")
        else:
            # No circuit block, clear main_circuit_id
            if session.main_circuit_id is not None:
                logger.info(f"[_save_session_exercises] Clearing main_circuit_id (was {session.main_circuit_id})")
                session.main_circuit_id = None
        
        # Check finisher circuit
        finisher = content.get("finisher")
        if finisher and isinstance(finisher, dict):
            finisher_type = finisher.get("type")
            if finisher_type == "circuit" and finisher.get("circuit_id"):
                # Finisher is a circuit, set finisher_circuit_id
                session.finisher_circuit_id = finisher.get("circuit_id")
                session.has_circuits = True
                logger.info(f"[_save_session_exercises] Set finisher_circuit_id={session.finisher_circuit_id}")
            else:
                # Finisher exists but is not a circuit, clear finisher_circuit_id
                if session.finisher_circuit_id is not None:
                    logger.info(f"[_save_session_exercises] Clearing finisher_circuit_id (was {session.finisher_circuit_id}) - finisher is not a circuit type")
                    session.finisher_circuit_id = None
        else:
            # No finisher, clear finisher_circuit_id
            if session.finisher_circuit_id is not None:
                logger.info(f"[_save_session_exercises] Clearing finisher_circuit_id (was {session.finisher_circuit_id}) - no finisher in content")
                session.finisher_circuit_id = None
        
        # Update has_circuits flag
        session.has_circuits = bool(session.main_circuit_id or session.finisher_circuit_id)
        logger.info(f"[_save_session_exercises] Updated has_circuits={session.has_circuits}")
        
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
        max_session_duration: int | None = None,
    ) -> Any:
        """
        Offline version of _generate_draft_session.
        """
        filtered_movements = self._filter_movements_for_session_type(all_movements, session_type)
        
        # Convert to DTOs for thread safety
        solver_movements = self._to_solver_movements(filtered_movements)
        
        # Load circuits for offline mode (needed for finishers and circuit blocks)
        circuits = self._load_all_circuits()
        solver_circuits = self._to_solver_circuits(circuits)
        
        targets = self._get_muscle_targets_for_session(session_type)
        
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
            min_stimulus=2.0,
            user_skill_level=SkillLevel.INTERMEDIATE,
            excluded_movement_ids=excluded_ids,
            required_movement_ids=list(required_movement_ids or []),
            session_duration_minutes=max_session_duration or 60,
            allow_complex_lifts=True,
            allow_circuits=True,
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
            logger.warning(f"Missing warmup for {session_type} session, will add empty warmup")
            content["warmup"] = []
        
        if not content.get("main") or len(content.get("main", [])) == 0:
            logger.error(f"Missing main section for {session_type} session!")
            # Use fallback for main if completely missing
            fallback = self._get_fallback_session_content(session_type)
            content["main"] = fallback.get("main", [])
        
        if not content.get("cooldown") or len(content.get("cooldown", [])) == 0:
            logger.warning(f"Missing cooldown for {session_type} session, will add empty cooldown")
            content["cooldown"] = []
        
        # CRITICAL: Remove duplicate movements within the session
        content = self._remove_intra_session_duplicates(content, session_type)
        
        return content

    async def _build_fast_content_from_draft(
        self,
        draft_content: dict[str, Any],
        session_type: SessionType,
        intent_tags: list[str],
        is_deload: bool,
        goal_weights: dict[str, int],
        all_movements: list[Movement] = None,
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
        
        return await self._normalize_session_content(content, session_type, intent_tags, goal_weights)
    
    async def _normalize_session_content(
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
            normalized["circuit"] = None
            return normalized
        
        normalized = self._validate_mutual_exclusivity(normalized)
        
        has_accessory = bool(normalized.get("accessory")) and len(normalized.get("accessory", [])) > 0
        has_circuit = normalized.get("circuit") is not None
        has_finisher = normalized.get("finisher") is not None
        
        if has_circuit:
            normalized["accessory"] = None
            normalized["finisher"] = None
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized
        
        if has_accessory and has_finisher:
            return normalized
        
        if has_finisher:
            if not normalized.get("accessory"):
                normalized["accessory"] = None
            return normalized
        
        if has_accessory:
            if self._prefer_finisher(goal_weights, tags):
                finisher = await self._build_goal_finisher(
                    goal_weights,
                    session_type=session_type,
                    intent_tags=tags,
                    existing_circuit_ids=None
                )
                if not finisher:
                    if goal_weights.get("endurance", 0) >= goal_weights.get("fat_loss", 0):
                        finisher = dict(activity_distribution_config.goal_finisher_presets.get("endurance", {}))
                    else:
                        finisher = dict(activity_distribution_config.goal_finisher_presets.get("fat_loss", {}))
                if finisher:
                    normalized["finisher"] = finisher
            normalized["cooldown"] = normalized.get("cooldown") or []
            return normalized
        
        block_type = self._decide_session_block_type(session_type, tags, goal_weights)
        
        if block_type == "circuit":
            circuit = await self._generate_circuit_block(session_type, tags, goal_weights)
            if circuit:
                normalized["circuit"] = circuit
                normalized["accessory"] = None
                normalized["finisher"] = None
                return normalized
        
        finisher = await self._build_goal_finisher(
            goal_weights,
            session_type=session_type,
            intent_tags=tags,
            existing_circuit_ids=None
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
        fat_loss = goal_weights.get("fat_loss", 0)
        endurance = goal_weights.get("endurance", 0)
        strength = goal_weights.get("strength", 0)
        hypertrophy = goal_weights.get("hypertrophy", 0)
        finisher_pressure = fat_loss + endurance
        accessory_pressure = strength + hypertrophy
        return finisher_pressure > accessory_pressure or "conditioning" in tags or "cardio" in tags
    
    def _decide_session_block_type(self, session_type: SessionType, intent_tags: set[str], goal_weights: dict[str, int]) -> str:
        """
        Decide whether a session should have a circuit block or accessory block.
        
        Returns:
            "circuit" if session should use circuits, "accessory" otherwise
        """
        if "prefer_circuit" in intent_tags:
            return "circuit"
        if "prefer_accessory" in intent_tags:
            return "accessory"
        
        is_conditioning_session = session_type in {SessionType.CARDIO, SessionType.CUSTOM}
        if is_conditioning_session and "conditioning" in intent_tags:
            return "circuit"
        
        fat_loss = goal_weights.get("fat_loss", 0)
        endurance = goal_weights.get("endurance", 0)
        strength = goal_weights.get("strength", 0)
        hypertrophy = goal_weights.get("hypertrophy", 0)
        
        circuit_pressure = fat_loss + endurance
        accessory_pressure = strength + hypertrophy
        
        if circuit_pressure > accessory_pressure:
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
        has_accessories = bool(content.get("accessory")) and len(content.get("accessory", [])) > 0
        has_circuit = content.get("circuit") is not None
        
        if has_accessories and has_circuit:
            logger.warning("Session has both accessories AND circuit - removing accessories to enforce mutual exclusivity")
            content["accessory"] = None
        
        return content

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

    async def _build_goal_finisher(
        self, 
        goal_weights: dict[str, int],
        session_type: SessionType | None = None,
        intent_tags: set[str] | None = None,
        existing_circuit_ids: list[int] | None = None,
        db: AsyncSession | None = None
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
                    goal_weights, session_type, intent_tags, existing_circuit_ids, db_session
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
        db: AsyncSession
    ) -> dict[str, Any] | None:
        """Build a finisher using provided database session."""
        from app.services.circuit_comparison import CircuitComparisonService
        
        logger.info("-" * 80)
        logger.info(f"[_build_goal_finisher_with_db] ENTRY - Session Type: {session_type.value if session_type else None}")
        logger.info(f"[_build_goal_finisher_with_db] Intent Tags: {list(intent_tags) if intent_tags else []}")
        logger.info(f"[_build_goal_finisher_with_db] Existing Circuit IDs: {existing_circuit_ids or []}")
        logger.info(f"[_build_goal_finisher_with_db] Goal Weights: {goal_weights}")
        logger.info("-" * 80)
        
        thresholds = activity_distribution_config.goal_finisher_thresholds
        
        fat_loss = goal_weights.get("fat_loss", 0)
        endurance = goal_weights.get("endurance", 0)
        
        logger.info(f"[_build_goal_finisher_with_db] Goal weights - fat_loss={fat_loss}, endurance={endurance}")
        logger.info(f"[_build_goal_finisher_with_db] Thresholds - fat_loss_min={thresholds.get('fat_loss_min_weight')}, endurance_min={thresholds.get('endurance_min_weight')}")
        
        # Check if finisher should be added
        if fat_loss < int(thresholds.get("fat_loss_min_weight", 999)) and \
           endurance < int(thresholds.get("endurance_min_weight", 999)):
            logger.info("[_build_goal_finisher_with_db] Finisher thresholds not met, returning None")
            return None
        
        # Determine circuit type based on goals
        circuit_type = "AMRAP" if fat_loss >= endurance else "EMOM"
        logger.info(f"[_build_goal_finisher_with_db] Circuit type determined: {circuit_type}")
        
        # Try to get a circuit from database using similarity scoring
        try:
            circuit_service = CircuitComparisonService(db)
            
            # Determine target region from session type
            target_region = self._get_primary_region_for_session_type(session_type) if session_type else "full body"
            logger.info(f"[_build_goal_finisher_with_db] Target region mapped: {target_region}")
            
            # Get circuit recommendations with SIMILARITY scoring
            # For finishers, we want similar muscles/regions to main lifts
            logger.info("[_build_goal_finisher_with_db] CALLING CircuitComparisonService.recommend_circuits_for_session()")
            logger.info(f"[_build_goal_finisher_with_db] Parameters - target_regions=[{target_region}], target_patterns={list(intent_tags) if intent_tags else None}, is_finisher=True")
            
            recommendations = await circuit_service.recommend_circuits_for_session(
                circuit_ids=existing_circuit_ids,
                target_regions=[target_region],
                target_patterns=list(intent_tags) if intent_tags else None,
                difficulty_tier=None,  # Remove bronze restriction
                max_equipment=None,  # Remove equipment restriction
                limit=10,
                is_finisher=True  # This is key - use similarity scoring
            )
            
            logger.info(f"[_build_goal_finisher_with_db] RETURN from recommend_circuits_for_session: {len(recommendations) if recommendations else 0} recommendations")
            
            if recommendations:
                for i, rec in enumerate(recommendations[:3]):  # Log top 3
                    logger.info(f"[_build_goal_finisher_with_db] Recommendation {i+1}: circuit_id={rec.circuit_id}, reason={rec.reason}, similarity_score={rec.similarity_score:.3f}, complementary_score={rec.complementary_score:.3f}")
            
            if not recommendations or len(recommendations) == 0:
                logger.info("[_build_goal_finisher_with_db] No similar circuits found for finisher, using preset")
                # Fall back to preset if no circuits available
                preset_name = "fat_loss" if fat_loss >= endurance else "endurance"
                preset = dict(activity_distribution_config.goal_finisher_presets.get(preset_name, {}))
                logger.info(f"[_build_goal_finisher_with_db] Using preset: {preset_name}, content: {preset}")
                return preset
            
            # Select top recommendation
            selected_circuit = recommendations[0]
            logger.info(f"[_build_goal_finisher_with_db] Selected top recommendation: circuit_id={selected_circuit.circuit_id}, similarity_score={selected_circuit.similarity_score:.3f}")
            
            # Build finisher dict from circuit data
            finisher = {
                "type": "circuit",
                "circuit_id": selected_circuit.circuit_id,
                "circuit_type": circuit_type,
                "name": f"{circuit_type} Finisher",
                "reason": selected_circuit.reason,
                "similarity_score": selected_circuit.similarity_score,
                "primary_region": selected_circuit.metadata.get("primary_region", "full_body"),
                "difficulty_tier": selected_circuit.metadata.get("difficulty_tier", 1),
                "exercises": []
            }
            
            # Load circuit exercises
            circuit_id = selected_circuit.circuit_id
            logger.info(f"[_build_goal_finisher_with_db] Loading melted exercises for circuit_id={circuit_id}")
            melted_exercises = await self._get_circuit_melted_exercises(db, circuit_id)
            logger.info(f"[_build_goal_finisher_with_db] Loaded {len(melted_exercises)} melted exercises")
            
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
                movement_name = movement_map.get(melted.movement_id, melted.movement_name)
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
                    "notes": melted.notes
                }
                finisher["exercises"].append(exercise_data)
            
            finisher["exercises"].sort(key=lambda x: x["sequence"])
            
            logger.info(f"[_build_goal_finisher_with_db] Built finisher with {len(finisher['exercises'])} exercises")
            logger.info(f"[_build_goal_finisher_with_db] Finisher type: {finisher['type']}, circuit_type: {finisher['circuit_type']}")
            logger.info(f"[_build_goal_finisher_with_db] Primary region: {finisher['primary_region']}, difficulty tier: {finisher['difficulty_tier']}")
            logger.info(f"[_build_goal_finisher_with_db] RETURN - Finisher built successfully for circuit_id={circuit_id}")
            logger.info("-" * 80)
            return finisher
            
        except Exception as e:
            logger.error(f"[_build_goal_finisher_with_db] ERROR building finisher from circuit database: {e}", exc_info=True)
            # Fall back to preset
            preset_name = "fat_loss" if fat_loss >= endurance else "endurance"
            preset = dict(activity_distribution_config.goal_finisher_presets.get(preset_name, {}))
            logger.info(f"[_build_goal_finisher_with_db] Falling back to preset: {preset_name} due to exception")
            logger.info("-" * 80)
            return preset
    
    async def _generate_circuit_block(
        self,
        session_type: SessionType,
        intent_tags: set[str],
        goal_weights: dict[str, int],
        db: AsyncSession | None = None
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
        db: AsyncSession
    ) -> dict[str, Any] | None:
        """Generate a circuit block using provided database session."""
        from app.services.circuit_comparison import CircuitComparisonService
        from app.models.circuit_extended import CircuitMacro
        from app.models.circuit import CircuitTemplate
        from sqlalchemy import select
        
        logger.info("-" * 80)
        logger.info(f"[_generate_circuit_block_with_db] ENTRY - Session Type: {session_type.value}")
        logger.info(f"[_generate_circuit_block_with_db] Intent Tags: {list(intent_tags) if intent_tags else []}")
        logger.info(f"[_generate_circuit_block_with_db] Goal Weights: {goal_weights}")
        logger.info("-" * 80)
        
        try:
            circuit_service = CircuitComparisonService(db)
            
            # Get circuit recommendations
            target_region = self._get_primary_region_for_session_type(session_type)
            logger.info(f"[_generate_circuit_block_with_db] Target region mapped: {target_region}")
            logger.info(f"[_generate_circuit_block_with_db] CALLING CircuitComparisonService.recommend_circuits_for_session()")
            logger.info(f"[_generate_circuit_block_with_db] Parameters - target_regions=[{target_region}], target_patterns={list(intent_tags) if intent_tags else None}, is_finisher=False")
            
            recommendations = await circuit_service.recommend_circuits_for_session(
                circuit_ids=None,
                target_regions=[target_region],
                target_patterns=list(intent_tags) if intent_tags else None,
                difficulty_tier=None,
                max_equipment=None,
                limit=10,
                is_finisher=False  # Circuit blocks use complementarity
            )
            
            logger.info(f"[_generate_circuit_block_with_db] RETURN from recommend_circuits_for_session: {len(recommendations) if recommendations else 0} recommendations")
            
            if recommendations:
                for i, rec in enumerate(recommendations[:3]):  # Log top 3
                    logger.info(f"[_generate_circuit_block_with_db] Recommendation {i+1}: circuit_id={rec.circuit_id}, reason={rec.reason}, similarity_score={rec.similarity_score:.3f}, complementary_score={rec.complementary_score:.3f}")
            
            if not recommendations or len(recommendations) == 0:
                logger.info(f"[_generate_circuit_block_with_db] No circuit recommendations found for {session_type} session, returning None")
                logger.info("-" * 80)
                return None
            
            selected_circuit = recommendations[0]
            circuit_id = selected_circuit.circuit_id
            logger.info(f"[_generate_circuit_block_with_db] Selected top recommendation: circuit_id={circuit_id}, complementary_score={selected_circuit.complementary_score:.3f}")
            
            # Fetch full circuit details from database
            logger.info(f"[_generate_circuit_block_with_db] Fetching full circuit details for circuit_id={circuit_id}")
            stmt = select(CircuitTemplate, CircuitMacro).join(
                CircuitMacro, CircuitTemplate.id == CircuitMacro.circuit_id
            ).where(CircuitTemplate.id == circuit_id)
            
            result = await db.execute(stmt)
            circuit_row = result.first()
            
            if not circuit_row:
                logger.error(f"[_generate_circuit_block_with_db] Circuit {circuit_id} not found in database")
                logger.info("-" * 80)
                return None
            
            circuit_template, circuit_macro = circuit_row
            logger.info(f"[_generate_circuit_block_with_db] Found circuit: name='{circuit_template.name}', type={circuit_template.circuit_type}, primary_region={circuit_macro.primary_region.value}")
            
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
                "exercises": []
            }
            
            melted_exercises = await self._get_circuit_melted_exercises(db, circuit_id)
            logger.info(f"[_generate_circuit_block_with_db] Loaded {len(melted_exercises)} melted exercises")
            
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
                movement_name = movement_map.get(melted.movement_id, melted.movement_name)
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
                    "notes": melted.notes
                }
                circuit_data["exercises"].append(exercise_data)
            
            circuit_data["exercises"].sort(key=lambda x: x["sequence"])
            
            logger.info(f"[_generate_circuit_block_with_db] Built circuit block with {len(circuit_data['exercises'])} exercises")
            logger.info(f"[_generate_circuit_block_with_db] Circuit block details: name='{circuit_data['name']}', primary_region={circuit_data['primary_region'].value}, difficulty_tier={circuit_data['difficulty_tier']}")
            logger.info(f"[_generate_circuit_block_with_db] RETURN - Circuit block built successfully for circuit_id={circuit_id}")
            logger.info("-" * 80)
            return circuit_data
            
        except Exception as e:
            logger.error(f"[_generate_circuit_block_with_db] ERROR generating circuit block: {e}", exc_info=True)
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
        logger.info(f"[_get_primary_region_for_session_type] Session Type: {session_type.value} -> Region: {region}")
        return region
    
    async def _get_circuit_melted_exercises(self, db: AsyncSession, circuit_id: int):
        """Get melted exercises for a circuit using async database session."""
        try:
            from app.models.circuit_extended import CircuitMelted
            from sqlalchemy import select
            
            stmt = select(CircuitMelted).where(
                CircuitMelted.circuit_id == circuit_id
            ).order_by(CircuitMelted.exercise_sequence)
            
            result = await db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting circuit melted exercises: {e}")
            return []

    def _get_fast_special_session_content(
        self,
        session_type: SessionType,
        max_session_duration: int | None,
        all_movements: list[Movement] = None,
    ) -> dict[str, Any]:
        total_minutes = max_session_duration or 30
        warmup = []
        cooldown = []

        if session_type == SessionType.MOBILITY:
            # Generate mobility session content from database movements
            mobility_movements = [
                m for m in (all_movements or [])
                if m.pattern and m.pattern.value in ["mobility", "stretch"]
            ]
            main = []
            if mobility_movements:
                main = [
                    {"movement": mobility_movements[0].name, "duration_seconds": 600, "notes": "Full body mobility"},
                ]
                if len(mobility_movements) > 1:
                    main.append({"movement": mobility_movements[1].name, "duration_seconds": max(300, (total_minutes - 15) * 60), "notes": "Mobility flow"})
            else:
                main = [{"movement": "Generation Failed - No mobility movements found", "duration_seconds": 300, "notes": "Add mobility movements to database"}]
            
            # Generate cooldown based on main
            if all_movements:
                warmup_cooldown = self._generate_warmup_cooldown(session_type, main, all_movements)
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

        # Cardio session
        cardio_movements = [
            m for m in (all_movements or [])
            if m.pattern and m.pattern.value == "cardio"
        ]
        if cardio_movements:
            main = [
                {"movement": cardio_movements[0].name, "duration_seconds": max(600, (total_minutes - 10) * 60), "notes": "Cardio workout"},
            ]
        else:
            main = [{"movement": "Generation Failed - No cardio movements found", "duration_seconds": 300, "notes": "Add cardio movements to database"}]
        
        # Generate warmup/cooldown based on main
        if all_movements:
            warmup_cooldown = self._generate_warmup_cooldown(session_type, main, all_movements)
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
        total_minutes = max_session_duration or 45
        main_minutes = max(30, total_minutes - 10)
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
                m for m in (all_movements or [])
                if m.pattern and m.pattern.value in conditioning_patterns
            ]
            for m in conditioning_db:
                if m.name not in candidates:
                    candidates.append(m.name)
            candidates = list(dict.fromkeys(candidates))

        selected = candidates[: max(5, min(8, len(candidates)))]
        per_station_seconds = max(120, int((main_minutes * 60) / max(5, len(selected))))
        main = [{"movement": name, "duration_seconds": per_station_seconds, "notes": "Conditioning station"} for name in selected]
        
        # Generate warmup/cooldown based on main
        if all_movements:
            warmup_cooldown = self._generate_warmup_cooldown(SessionType.CUSTOM, main, all_movements)
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
            "notes": "Replacement for duplicate exercise"
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
        all_movements: list[Movement] = None,
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
            return self._get_fallback_session_content(session_type, all_movements)
        
        # Generate warmup and cooldown based on main exercises
        warmup_cooldown = self._generate_warmup_cooldown(
            session_type, main_exercises, all_movements
        )
        
        # Estimate duration: main (25-30) + accessory (10-15) + warmup/cooldown (10) = ~50 min
        estimated_duration = (len(main_exercises) * 10) + (len(accessory_exercises) * 5) + 10
        
        return {
            "warmup": warmup_cooldown["warmup"],
            "main": main_exercises,
            "accessory": accessory_exercises if accessory_exercises else None,
            "finisher": None,
            "cooldown": warmup_cooldown["cooldown"],
            "estimated_duration_minutes": estimated_duration,
            "reasoning": f"Smart fallback session - LLM unavailable. Selected exercises based on {', '.join(intent_tags)} patterns.",
        }
    
    def _get_fallback_session_content(self, session_type: SessionType, available_movements: list[Movement] = None) -> dict[str, Any]:
        """Return basic fallback content when smart fallback also fails."""
        # Basic fallback based on session type
        fallbacks = {
            SessionType.UPPER: {
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
                "estimated_duration_minutes": 45,
                "reasoning": "Fallback upper body session - LLM generation failed.",
            },
            SessionType.LOWER: {
                "main": [
                    {"movement": "Back Squat", "sets": 4, "rep_range_min": 6, "rep_range_max": 8, "target_rpe": 7.5, "rest_seconds": 150},
                    {"movement": "Romanian Deadlift", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
                ],
                "accessory": [
                    {"movement": "Walking Lunge", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 90},
                    {"movement": "Leg Curl", "sets": 3, "rep_range_min": 10, "rep_range_max": 12, "target_rpe": 7, "rest_seconds": 60},
                ],
                "finisher": None,
                "estimated_duration_minutes": 45,
                "reasoning": "Fallback lower body session - LLM generation failed.",
            },
            SessionType.FULL_BODY: {
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
                "estimated_duration_minutes": 50,
                "reasoning": "Fallback full body session - LLM generation failed.",
            },
        }
        
        # Default fallback for other session types (PPL, etc.)
        default = {
            "main": [
                {"movement": "Back Squat", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
                {"movement": "Barbell Bench Press", "sets": 4, "rep_range_min": 8, "rep_range_max": 10, "target_rpe": 7, "rest_seconds": 120},
            ],
            "accessory": [
                {"movement": "Lateral Raise", "sets": 3, "rep_range_min": 12, "rep_range_max": 15, "target_rpe": 7, "rest_seconds": 60},
            ],
            "finisher": None,
            "estimated_duration_minutes": 40,
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
            fallback_content["estimated_duration_minutes"] += 10
        else:
            fallback_content["warmup"] = []
            fallback_content["cooldown"] = []
        
        return fallback_content

    async def _load_all_movements(self, db: AsyncSession) -> list[Movement]:
        """Load all movements from the database."""
        result = await db.execute(select(Movement))
        return list(result.scalars().all())
    
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
                effective_work_volume=c.effective_work_volume if c.effective_work_volume else 0.0,
                circuit_type=c.circuit_type,
                duration_seconds=c.estimated_work_seconds if c.estimated_work_seconds else 600,
                primary_region=m.primary_region.value if m else None,
                pattern_diversity_score=m.pattern_diversity_score if m else 0.0,
                equipment_complexity=m.equipment_complexity if m else 0
            )
            for c, m in rows
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
            region = str(m.primary_region.value) if hasattr(m.primary_region, 'value') else str(m.primary_region)
            pattern = str(m.pattern.value) if hasattr(m.pattern, 'value') else str(m.pattern)
            
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
    
    async def _get_mobility_warmup_movements(
        self,
        db: AsyncSession,
        primary_region: str | None = None,
        patterns: list[str] | None = None,
        limit: int = 3
    ) -> list[Movement]:
        """Get mobility movements from database for warm-up.
        
        Queries the movement database for mobility movements that can be used
        in warm-up sections. Filters by region and patterns if provided.
        
        Args:
            db: Database session
            primary_region: Target body region for mobility movements
            patterns: Movement patterns to focus on
            limit: Maximum number of movements to return
            
        Returns:
            List of mobility Movement objects from database
        """
        from app.models.enums import MovementPattern
        
        # Query mobility movements
        stmt = select(Movement).where(
            Movement.pattern == MovementPattern.MOBILITY
        ).limit(limit * 2)  # Get more to filter later
        
        try:
            result = await db.execute(stmt)
            all_mobility = result.scalars().all()
            
            # Filter by region if provided
            if primary_region:
                filtered = []
                for m in all_mobility:
                    region = str(m.primary_region.value) if hasattr(m.primary_region, 'value') else str(m.primary_region)
                    # Simple region matching - can be refined
                    if primary_region.lower() in region.lower() or region.lower() in primary_region.lower():
                        filtered.append(m)
                all_mobility = filtered
            
            # Filter by patterns if provided
            if patterns:
                pattern_filtered = []
                for m in all_mobility:
                    pattern = str(m.pattern.value) if hasattr(m.pattern, 'value') else str(m.pattern)
                    # Include if mobility matches any related pattern
                    if pattern == "mobility":
                        pattern_filtered.append(m)
                all_mobility = pattern_filtered
            
            # Return limited number
            return all_mobility[:limit]
            
        except Exception as e:
            logger.error(f"Error getting mobility warmup movements: {e}")
            return []

    async def _generate_draft_session(
        self, 
        db: AsyncSession, 
        session: Session,
        used_movements: list[str] | None = None,
        goal_weights: dict[str, int] | None = None,
        max_session_duration: int | None = None,
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
            session_duration_minutes=max_session_duration or 60,
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

    def _generate_warmup_cooldown(
        self,
        session_type: SessionType,
        main_exercises: list[dict],
        available_movements: list[Movement]
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
            movement = next((m for m in available_movements if m.name == movement_name), None)
            if movement:
                if movement.pattern:
                    patterns_used.add(movement.pattern.value)
                if movement.primary_muscle:
                    muscles_used.add(movement.primary_muscle.value)
        
        warmup = []
        cooldown = []
        
        # Add short cardio for warmup (ignore fatigue)
        cardio_movements = [
            m for m in available_movements 
            if m.pattern and m.pattern.value == "cardio"
        ]
        if cardio_movements:
            cardio = cardio_movements[0]
            warmup.append({
                "movement": cardio.name,
                "sets": 1,
                "duration_seconds": 300,
                "notes": "Light cardio to raise body temperature"
            })
        
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
                m for m in available_movements
                if m.pattern and m.pattern.value in target_patterns
            ]
            if mobility_movements:
                mobility = mobility_movements[0]
                warmup.append({
                    "movement": mobility.name,
                    "sets": 2,
                    "reps": 10,
                    "notes": f"Mobility for {pattern} pattern"
                })
                break  # Just add one mobility movement
        
        # Add stretch movements for cooldown based on muscles used
        stretch_movements = [
            m for m in available_movements
            if m.pattern and m.pattern.value == "stretch"
        ]
        
        for muscle in muscles_used:
            muscle_stretches = [
                m for m in stretch_movements
                if m.primary_muscle and m.primary_muscle.value == muscle
            ]
            if muscle_stretches:
                stretch = muscle_stretches[0]
                cooldown.append({
                    "movement": stretch.name,
                    "duration_seconds": 180,
                    "notes": f"Stretch for {muscle}"
                })
        
        # If no specific stretches, add general stretches
        if not cooldown and stretch_movements:
            for stretch in stretch_movements[:3]:
                cooldown.append({
                    "movement": stretch.name,
                    "duration_seconds": 180,
                    "notes": "General stretch"
                })
        
        return {
            "warmup": warmup,
            "cooldown": cooldown
        }

    def _convert_optimization_result_to_content(self, result: Any, session_type: SessionType, available_movements: list[Movement]) -> dict[str, Any]:
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
        
        # Generate warmup and cooldown based on main exercises
        warmup_cooldown = self._generate_warmup_cooldown(
            session_type, main_exercises, available_movements
        )
        
        return {
            "warmup": warmup_cooldown["warmup"],
            "main": main_exercises,
            "accessory": accessory_exercises,
            "finisher": None,
            "cooldown": warmup_cooldown["cooldown"],
            "estimated_duration_minutes": result.estimated_duration + 10,  # +10 for warmup/cooldown
            "reasoning": f"Optimization Engine generated session. Status: {result.status}. Stimulus: {result.total_stimulus:.2f}, Fatigue: {result.total_fatigue:.2f}"
        }


# Singleton instance
session_generator = SessionGeneratorService()
