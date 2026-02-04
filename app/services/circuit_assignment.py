"""
Circuit Assignment Service

Handles atomic circuit assignment to sessions with mutual exclusivity constraints.
"""

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.program import Session, SessionExercise
from app.models.circuit import CircuitTemplate
from app.models.circuit_extended import CircuitMelted, CircuitMacro
from app.models.program import ExerciseRole

logger = logging.getLogger(__name__)


class CircuitAssignmentService:
    """
    Service for atomic circuit assignment to sessions.
    
    Ensures atomic constraint: All circuit exercises are added or none.
    Enforces mutual exclusivity: Sessions can have circuits OR accessories, never both.
    """
    
    def __init__(self):
        pass
    
    async def assign_circuit_to_session(
        self,
        db: AsyncSession,
        session_id: int,
        circuit_id: int,
        circuit_role: str = "MAIN_CIRCUIT",
        rounds: int | None = None,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """
        Atomically assign a circuit to a session.
        
        Atomic behavior:
        1. Validate session and circuit exist
        2. Load circuit exercises from CircuitMelted
        3. Calculate order_in_session for new exercises
        4. Optionally remove conflicting existing exercises
        5. Insert all new SessionExercise records
        6. Update session.finisher_circuit_id
        7. Update session duration estimates and has_circuits flag
        8. Commit transaction (all-or-nothing)
        
        Args:
            db: Database session
            session_id: Session to assign circuit to
            circuit_id: Circuit template to assign
            circuit_role: Only "FINISHER_CIRCUIT" is supported
            rounds: Optional override for circuit rounds
            replace_existing: Whether to replace existing exercises of same role
        
        Returns:
            Dictionary with assignment details including exercises added and metadata
        
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails (transaction rolls back)
        """
        try:
            # 1. Validate session exists
            session_result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # 2. Validate circuit exists
            circuit_result = await db.execute(
                select(CircuitTemplate).where(CircuitTemplate.id == circuit_id)
            )
            circuit = circuit_result.scalar_one_or_none()
            if not circuit:
                raise ValueError(f"Circuit {circuit_id} not found")
            
            # 3. Load circuit exercises
            melted_result = await db.execute(
                select(CircuitMelted)
                .where(CircuitMelted.circuit_id == circuit_id)
                .order_by(CircuitMelted.exercise_sequence)
            )
            melted_exercises = melted_result.scalars().all()
            
            if not melted_exercises:
                raise ValueError(f"Circuit {circuit_id} has no exercises")
            
            # 4. Load circuit macro data
            macro_result = await db.execute(
                select(CircuitMacro).where(CircuitMacro.circuit_id == circuit_id)
            )
            macro = macro_result.scalar_one_or_none()
            
            # 5. Validate mutual exclusivity
            existing_exercises_result = await db.execute(
                select(SessionExercise).where(
                    and_(
                        SessionExercise.session_id == session_id,
                        SessionExercise.exercise_role == ExerciseRole.ACCESSORY
                    )
                )
            )
            has_accessories = existing_exercises_result.scalars().first() is not None
            
            if has_accessories and not replace_existing:
                raise ValueError(
                    f"Session {session_id} has accessories. "
                    "Set replace_existing=True to remove accessories and add circuit."
                )
            
            # 6. Remove conflicting exercises if requested
            if has_accessories and replace_existing:
                await db.execute(
                    select(SessionExercise).where(
                        and_(
                            SessionExercise.session_id == session_id,
                            SessionExercise.exercise_role == ExerciseRole.ACCESSORY
                        )
                    )
                )
                await db.execute(
                    SessionExercise.__table__.delete().where(
                        and_(
                            SessionExercise.session_id == session_id,
                            SessionExercise.exercise_role == ExerciseRole.ACCESSORY
                        )
                    )
                )
                logger.info(f"Removed accessories from session {session_id} for circuit assignment")
            
            # 7. Calculate order_in_session
            existing_count_result = await db.execute(
                select(SessionExercise).where(
                    SessionExercise.session_id == session_id
                )
            )
            existing_count = len(existing_count_result.scalars().all())
            
            # 8. Create SessionExercise records for circuit
            new_exercises = []
            for melted in melted_exercises:
                exercise = SessionExercise(
                    user_id=session.user_id,
                    session_id=session_id,
                    movement_id=melted.movement_id,
                    circuit_id=circuit_id,
                    exercise_role=ExerciseRole.MAIN_LIFT if circuit_role == "MAIN_CIRCUIT" else ExerciseRole.FINISHER,
                    order_in_session=existing_count + melted.exercise_sequence,
                    target_sets=rounds or circuit.default_rounds,
                    target_rep_range_min=melted.reps,
                    target_rep_range_max=melted.reps,
                    target_duration_seconds=melted.duration_seconds,
                    default_rest_seconds=melted.rest_seconds,
                    substitution_allowed=False,
                )
                db.add(exercise)
                new_exercises.append(exercise)
            
            # 9. Update session circuit references
            session.finisher_circuit_id = circuit_id
            
            # 10. Update session has_circuits flag
            session.has_circuits = True
            
            # 11. Update duration estimates
            circuit_duration = macro.estimated_duration_seconds if macro else circuit.default_duration_seconds or 1500
            circuit_minutes = circuit_duration / 60
            
            session.finisher_duration_minutes = circuit_minutes
            
            # 12. Update total duration
            session.estimated_duration_minutes = (
                (session.warmup_duration_minutes or 0) +
                (session.main_duration_minutes or 0) +
                (session.accessory_duration_minutes or 0) +
                (session.finisher_duration_minutes or 0) +
                (session.cooldown_duration_minutes or 0)
            )
            
            # 13. Commit transaction
            await db.commit()
            
            logger.info(
                f"Assigned circuit {circuit_id} to session {session_id} "
                f"with {len(new_exercises)} exercises"
            )
            
            # 14. Build response
            return {
                "session_id": session_id,
                "circuit_id": circuit_id,
                "circuit_role": circuit_role,
                "exercises_added": len(new_exercises),
                "exercises": [
                    {
                        "id": ex.id,
                        "session_id": ex.session_id,
                        "movement_id": ex.movement_id,
                        "movement_name": melted.movement_name,
                        "exercise_role": ex.exercise_role.value,
                        "order_in_session": ex.order_in_session,
                        "target_sets": ex.target_sets,
                        "target_rep_range_min": ex.target_rep_range_min,
                        "target_rep_range_max": ex.target_rep_range_max,
                        "circuit_id": ex.circuit_id,
                    }
                    for ex, melted in zip(new_exercises, melted_exercises)
                ],
                "total_duration_minutes": session.estimated_duration_minutes,
                "circuit_metadata": {
                    "name": circuit.name,
                    "circuit_type": circuit.circuit_type.value,
                    "default_rounds": circuit.default_rounds,
                    "estimated_duration_seconds": circuit_duration,
                    "difficulty_tier": circuit.difficulty_tier,
                    "primary_muscles": macro.primary_muscles if macro else [],
                    "primary_region": macro.primary_region if macro else "full_body",
                }
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error assigning circuit {circuit_id} to session {session_id}: {e}")
            raise
    
    async def get_available_circuits_for_session(
        self,
        db: AsyncSession,
        session_id: int,
        circuit_type: str | None = None,
        difficulty_tier: int | None = None,
        primary_region: str | None = None,
        exclude_used: bool = True,
        max_duration_minutes: int | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Get circuit recommendations for a session.
        
        Uses CircuitComparisonService for filtering and scoring.
        
        Args:
            db: Database session
            session_id: Session to get recommendations for
            circuit_type: Optional filter by circuit type
            difficulty_tier: Optional filter by difficulty (1-4)
            primary_region: Optional filter by body region
            exclude_used: Whether to exclude circuits with movements already in session
            max_duration_minutes: Optional filter by duration
            limit: Max results (default: 10)
        
        Returns:
            Dictionary with session info and circuit recommendations
        """
        try:
            from app.services.circuit_comparison import CircuitComparisonService
            
            # Load session
            session_result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            # Get existing movement IDs if exclude_used
            existing_movement_ids = set()
            if exclude_used:
                existing_result = await db.execute(
                    select(SessionExercise.movement_id).where(
                        SessionExercise.session_id == session_id
                    )
                )
                existing_movement_ids = set(existing_result.scalars().all())
            
            # Get available circuits with macro data
            circuits_query = (
                select(CircuitTemplate)
                .options(selectinload(CircuitTemplate.melted_exercises))
                .join(CircuitMacro, CircuitMacro.circuit_id == CircuitTemplate.id)
            )
            
            if circuit_type:
                circuits_query = circuits_query.where(CircuitTemplate.circuit_type == circuit_type)
            
            if difficulty_tier:
                circuits_query = circuits_query.where(CircuitTemplate.difficulty_tier == difficulty_tier)
            
            if primary_region:
                circuits_query = circuits_query.where(CircuitMacro.primary_region == primary_region)
            
            if max_duration_minutes:
                circuits_query = circuits_query.where(
                    CircuitMacro.estimated_duration_seconds <= max_duration_minutes * 60
                )
            
            circuits_result = await db.execute(circuits_query)
            circuits = circuits_result.scalars().all()
            
            # Filter out circuits with used movements
            available_circuits = []
            for circuit in circuits:
                circuit_movement_ids = {
                    melted.movement_id for melted in circuit.melted_exercises
                    if melted.movement_id is not None
                }
                
                if exclude_used and circuit_movement_ids & existing_movement_ids:
                    continue
                
                available_circuits.append(circuit)
            
            # Score and sort circuits using CircuitComparisonService
            circuit_comparison = CircuitComparisonService(db)
            recommendations = []
            for circuit in available_circuits[:limit * 2]:
                try:
                    similarity_result = await circuit_comparison.calculate_circuit_similarity_score(
                        circuit.id, circuit.id
                    )
                    compatibility_score = similarity_result.similarity_score
                except Exception:
                    compatibility_score = 0.5
                
                macro = next(
                    (m for m in circuit.macro_metrics if m.circuit_id == circuit.id),
                    None
                )
                
                recommendations.append({
                    "circuit": {
                        "id": circuit.id,
                        "name": circuit.name,
                        "description": circuit.description,
                        "circuit_type": circuit.circuit_type.value,
                        "difficulty_tier": circuit.difficulty_tier,
                        "estimated_duration_seconds": macro.estimated_duration_seconds if macro else 1500,
                        "primary_region": macro.primary_region if macro else "full_body",
                        "primary_muscles": macro.primary_muscles if macro else [],
                    },
                    "compatibility_score": compatibility_score,
                    "fit_reason": f"Compatible with {session.session_type.value} session",
                    "muscle_overlap": 0.0,
                    "equipment_needed": macro.required_equipment if macro else [],
                    "estimated_total_duration": (session.estimated_duration_minutes or 0) + (
                        (macro.estimated_duration_seconds / 60) if macro else 25
                    ),
                })
            
            # Sort by compatibility score
            recommendations.sort(key=lambda x: x["compatibility_score"], reverse=True)
            recommendations = recommendations[:limit]
            
            return {
                "session": {
                    "id": session.id,
                    "session_type": session.session_type.value,
                    "date": session.date.isoformat(),
                    "current_duration_minutes": session.estimated_duration_minutes,
                    "intent_tags": session.intent_tags or [],
                },
                "recommendations": recommendations,
                "total_available": len(available_circuits),
                "filters_applied": {
                    "exclude_used": exclude_used,
                    "max_duration_minutes": max_duration_minutes,
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting available circuits for session {session_id}: {e}")
            raise
    
    async def preview_circuit_assignment(
        self,
        db: AsyncSession,
        session_id: int,
        circuit_id: int,
        circuit_role: str = "MAIN_CIRCUIT",
        rounds: int | None = None,
    ) -> dict[str, Any]:
        """
        Preview circuit assignment without committing.
        
        Args:
            db: Database session
            session_id: Session to preview assignment for
            circuit_id: Circuit template to preview
            circuit_role: Either "MAIN_CIRCUIT" or "FINISHER_CIRCUIT"
            rounds: Optional override for circuit rounds
        
        Returns:
            Dictionary with preview changes and warnings
        """
        try:
            # Load session and circuit
            session_result = await db.execute(
                select(Session).where(Session.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            
            circuit_result = await db.execute(
                select(CircuitTemplate).where(CircuitTemplate.id == circuit_id)
            )
            circuit = circuit_result.scalar_one_or_none()
            
            # Load circuit exercises
            melted_result = await db.execute(
                select(CircuitMelted)
                .where(CircuitMelted.circuit_id == circuit_id)
                .order_by(CircuitMelted.exercise_sequence)
            )
            melted_exercises = melted_result.scalars().all()
            
            # Load circuit macro
            macro_result = await db.execute(
                select(CircuitMacro).where(CircuitMacro.circuit_id == circuit_id)
            )
            macro = macro_result.scalar_one_or_none()
            
            # Check for conflicts
            existing_accessories_result = await db.execute(
                select(SessionExercise).where(
                    and_(
                        SessionExercise.session_id == session_id,
                        SessionExercise.exercise_role == ExerciseRole.ACCESSORY
                    )
                )
            )
            has_accessories = existing_accessories_result.scalars().first() is not None
            
            warnings = []
            if has_accessories:
                warnings.append("Session has accessories - they will be removed if circuit is assigned")
            
            # Calculate impact
            circuit_duration = (macro.estimated_duration_seconds if macro else 1500) / 60
            new_duration = (session.estimated_duration_minutes or 0) + circuit_duration
            
            if new_duration > 60:
                warnings.append(f"Session will exceed 60 minutes by {new_duration - 60:.0f} minutes")
            
            return {
                "preview": {
                    "circuit": {
                        "id": circuit.id,
                        "name": circuit.name,
                        "exercises_count": len(melted_exercises)
                    },
                    "changes": {
                        "exercises_to_add": len(melted_exercises),
                        "exercises_to_remove": 0,
                        "accessories_to_remove": 1 if has_accessories else 0,
                    },
                    "resulting_session": {
                        "total_exercises": len(melted_exercises),
                        "estimated_duration_minutes": new_duration,
                        "muscle_coverage": macro.muscle_engagement_score if macro else 0.5,
                    }
                },
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Error previewing circuit assignment: {e}")
            raise


circuit_assignment_service = CircuitAssignmentService()
