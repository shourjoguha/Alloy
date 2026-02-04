"""Time estimation service for session duration calculation."""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionTimeBreakdown:
    """Breakdown of session time by component."""
    warmup_minutes: int
    main_minutes: int
    accessory_minutes: int
    circuit_minutes: int
    finisher_minutes: int
    cooldown_minutes: int
    total_minutes: int


class TimeEstimationService:
    """Service for calculating session and exercise durations."""
    
    def __init__(self, config: dict | None = None):
        """
        Initialize with time estimation config.
        
        Args:
            config: Time estimation config from heuristic_configs
        """
        self.config = config or self._default_config()
    
    def _default_config(self) -> dict:
        """Default time estimation configuration."""
        return {
            "warmup": {
                "base_minutes": 5,
                "per_exercise_minutes": 1
            },
            "cooldown": {
                "base_minutes": 5,
                "per_stretch_minutes": 1
            },
            "transition_between_exercises_seconds": 45,
            "set_execution_time": {
                "by_rep_range": {
                    "1-3": 15,
                    "4-6": 25,
                    "7-10": 35,
                    "11-15": 45,
                    "16-20": 55,
                    "21+": 70
                },
                "by_metric_type": {
                    "reps": "use_rep_range",
                    "time": "use_target_duration",
                    "time_under_tension": "use_target_duration",
                    "distance": 60
                }
            },
            "rest_seconds_by_role": {
                "warmup": 30,
                "main": {
                    "strength": 180,
                    "hypertrophy": 90,
                    "endurance": 45
                },
                "accessory": 60,
                "skill": 90,
                "finisher": 30,
                "cooldown": 15
            },
            "superset_rest_reduction_percent": 50,
            "circuit_rest_between_rounds_seconds": 60
        }
    
    def _get_set_execution_time(
        self,
        reps: int | None,
        metric_type: str = "reps",
        target_duration_seconds: int | None = None
    ) -> int:
        """Get execution time for a single set in seconds."""
        set_config = self.config.get("set_execution_time", {})
        
        if metric_type in ["time", "time_under_tension"]:
            return target_duration_seconds or 45
        
        if metric_type == "distance":
            return set_config.get("by_metric_type", {}).get("distance", 60)
        
        # For reps, look up by range
        if reps is None:
            return 35  # Default
        
        rep_ranges = set_config.get("by_rep_range", {})
        
        if reps <= 3:
            return rep_ranges.get("1-3", 15)
        elif reps <= 6:
            return rep_ranges.get("4-6", 25)
        elif reps <= 10:
            return rep_ranges.get("7-10", 35)
        elif reps <= 15:
            return rep_ranges.get("11-15", 45)
        elif reps <= 20:
            return rep_ranges.get("16-20", 55)
        else:
            return rep_ranges.get("21+", 70)
    
    def _get_rest_time(
        self,
        role: str,
        intent: str = "hypertrophy",
        is_superset: bool = False
    ) -> int:
        """Get rest time for an exercise in seconds."""
        rest_config = self.config.get("rest_seconds_by_role", {})
        
        if role == "main":
            main_rest = rest_config.get("main", {})
            if isinstance(main_rest, dict):
                rest = main_rest.get(intent, 90)
            else:
                rest = main_rest
        else:
            rest = rest_config.get(role, 60)
        
        if is_superset:
            reduction = self.config.get("superset_rest_reduction_percent", 50)
            rest = int(rest * (1 - reduction / 100))
        
        return rest
    
    def estimate_exercise_time(
        self,
        sets: int,
        reps: int | None = None,
        rest_seconds: int | None = None,
        role: str = "main",
        intent: str = "hypertrophy",
        metric_type: str = "reps",
        target_duration_seconds: int | None = None,
        is_superset: bool = False
    ) -> int:
        """
        Estimate time for a single exercise in seconds.
        
        Args:
            sets: Number of sets
            reps: Reps per set (for rep-based exercises)
            rest_seconds: Override rest time
            role: Exercise role (warmup, main, accessory, etc.)
            intent: Training intent (strength, hypertrophy, endurance)
            metric_type: How exercise is measured
            target_duration_seconds: For time-based exercises
            is_superset: Whether exercise is part of a superset
            
        Returns:
            Total time in seconds
        """
        # Set execution time
        set_time = self._get_set_execution_time(reps, metric_type, target_duration_seconds)
        
        # Rest time (between sets, not after last set)
        if rest_seconds is not None:
            rest = rest_seconds
        else:
            rest = self._get_rest_time(role, intent, is_superset)
        
        # Total = (set time × sets) + (rest × (sets - 1))
        total_seconds = (set_time * sets) + (rest * max(0, sets - 1))
        
        return total_seconds
    
    def estimate_block_time(
        self,
        exercises: list[dict],
        role: str,
        intent: str = "hypertrophy"
    ) -> int:
        """
        Estimate time for a block of exercises in minutes.
        
        Args:
            exercises: List of exercise dicts with sets, reps, etc.
            role: Block role (main, accessory, etc.)
            intent: Training intent
            
        Returns:
            Total time in minutes (rounded up)
        """
        if not exercises:
            return 0
        
        total_seconds = 0
        transition_time = self.config.get("transition_between_exercises_seconds", 45)
        
        # Group supersets
        superset_groups: dict[int | None, list[dict]] = {}
        for ex in exercises:
            group = ex.get("superset_group")
            if group not in superset_groups:
                superset_groups[group] = []
            superset_groups[group].append(ex)
        
        for group, group_exercises in superset_groups.items():
            is_superset = group is not None and len(group_exercises) > 1
            
            for ex in group_exercises:
                ex_time = self.estimate_exercise_time(
                    sets=ex.get("sets", 3),
                    reps=ex.get("reps") or ex.get("rep_range_max"),
                    rest_seconds=ex.get("rest_seconds"),
                    role=role,
                    intent=intent,
                    metric_type=ex.get("metric_type", "reps"),
                    target_duration_seconds=ex.get("target_duration_seconds"),
                    is_superset=is_superset
                )
                total_seconds += ex_time
            
            # Add transition between exercise groups
            total_seconds += transition_time
        
        # Convert to minutes (round up)
        return (total_seconds + 59) // 60
    
    def estimate_warmup_time(self, exercises: list[dict]) -> int:
        """Estimate warmup time in minutes."""
        config = self.config.get("warmup", {})
        base = config.get("base_minutes", 5)
        per_ex = config.get("per_exercise_minutes", 1)
        
        return base + (len(exercises) * per_ex)
    
    def estimate_cooldown_time(self, stretches: list[dict]) -> int:
        """Estimate cooldown time in minutes."""
        config = self.config.get("cooldown", {})
        base = config.get("base_minutes", 5)
        per_stretch = config.get("per_stretch_minutes", 1)
        
        return base + (len(stretches) * per_stretch)
    
    def estimate_finisher_time(self, finisher: dict | None) -> int:
        """Estimate finisher time in minutes."""
        if not finisher:
            return 0
        
        # If duration is specified, use it
        if finisher.get("duration_minutes"):
            return finisher["duration_minutes"]
        
        # Otherwise estimate based on type
        finisher_type = finisher.get("type", "").lower()
        
        if "emom" in finisher_type:
            return finisher.get("rounds", 10)  # EMOM = 1 min per round
        elif "amrap" in finisher_type:
            return finisher.get("duration_minutes", 8)
        elif "circuit" in finisher_type:
            rounds = finisher.get("rounds", 3)
            exercises = finisher.get("exercises", [])
            # Rough estimate: 30 sec per exercise per round + rest
            circuit_rest = self.config.get("circuit_rest_between_rounds_seconds", 60)
            return ((len(exercises) * 30 * rounds) + (circuit_rest * (rounds - 1))) // 60
        else:
            return 5  # Default finisher time
    
    def estimate_session_time(
        self,
        warmup: list[dict] | None = None,
        main: list[dict] | None = None,
        accessory: list[dict] | None = None,
        circuit: dict | None = None,
        finisher: dict | None = None,
        cooldown: list[dict] | None = None,
        intent: str = "hypertrophy"
    ) -> SessionTimeBreakdown:
        """
        Estimate total session time with breakdown.
        
        Args:
            warmup: Warmup exercises
            main: Main exercises
            accessory: Accessory exercises (mutually exclusive with circuit)
            circuit: Circuit block (mutually exclusive with accessory)
            finisher: Finisher block
            cooldown: Cooldown stretches
            intent: Training intent
            
        Returns:
            SessionTimeBreakdown with component and total times
        """
        warmup_time = self.estimate_warmup_time(warmup or [])
        main_time = self.estimate_block_time(main or [], "main", intent)
        
        # Mutually exclusive: either circuit OR accessory, never both
        if circuit:
            circuit_time = self.estimate_circuit_time(circuit)
            accessory_time = 0
        else:
            accessory_time = self.estimate_block_time(accessory or [], "accessory", intent)
            circuit_time = 0
        
        finisher_time = self.estimate_finisher_time(finisher)
        cooldown_time = self.estimate_cooldown_time(cooldown or [])
        
        total = warmup_time + main_time + circuit_time + accessory_time + finisher_time + cooldown_time
        
        return SessionTimeBreakdown(
            warmup_minutes=warmup_time,
            main_minutes=main_time,
            accessory_minutes=accessory_time,
            circuit_minutes=circuit_time,
            finisher_minutes=finisher_time,
            cooldown_minutes=cooldown_time,
            total_minutes=total
        )
    
    def estimate_circuit_time(self, circuit: dict | None) -> int:
        """
        Estimate duration for a circuit block.
        
        Uses the circuit's estimated_duration_seconds for accurate time calculation.
        
        Args:
            circuit: Circuit block dict with circuit metadata
            
        Returns:
            Duration in minutes
        """
        if not circuit:
            return 0
        
        duration_seconds = circuit.get("estimated_duration_seconds")
        if duration_seconds:
            return int(duration_seconds / 60)
        
        default_duration = circuit.get("default_duration_seconds", 1500)
        return int(default_duration / 60)

    def calculate_session_duration(self, session) -> SessionTimeBreakdown:
        """
        Estimate duration for a session object with relational exercises.

        Args:
            session: Session model instance with exercises loaded

        Returns:
            SessionTimeBreakdown
        """
        # Group exercises by section
        warmup = []
        main = []
        accessory = []
        cooldown = []
        finisher_exercises = []

        # Sort by order to ensure correct sequence
        exercises = sorted(session.exercises, key=lambda x: x.order_in_session)

        for ex in exercises:
            # Convert to dict format expected by estimation methods
            ex_dict = {
                "sets": ex.target_sets,
                "reps": ex.target_rep_range_max, # Use max for estimation
                "rest_seconds": ex.default_rest_seconds,
                "metric_type": "time" if ex.target_duration_seconds else "reps",
                "target_duration_seconds": ex.target_duration_seconds,
                "superset_group": ex.superset_group,
                "role": ex.exercise_role.value if hasattr(ex.exercise_role, 'value') else ex.exercise_role
            }

            section = ex.exercise_role.value if hasattr(ex.exercise_role, 'value') else ex.exercise_role

            if section == "warmup":
                warmup.append(ex_dict)
            elif section == "main":
                main.append(ex_dict)
            elif section == "accessory":
                accessory.append(ex_dict)
            elif section == "cooldown":
                cooldown.append(ex_dict)
            elif section == "finisher":
                finisher_exercises.append(ex_dict)

        # Construct finisher dict if needed
        finisher = None
        if finisher_exercises:
            # Check for circuit details
            c_type = "circuit"
            c_rounds = 1
            c_duration = None

            if hasattr(session, 'finisher_circuit') and session.finisher_circuit:
                fc = session.finisher_circuit
                c_type = fc.circuit_type.value if hasattr(fc.circuit_type, 'value') else fc.circuit_type
                c_rounds = fc.default_rounds or 1
                if fc.default_duration_seconds:
                    c_duration = fc.default_duration_seconds // 60

            finisher = {
                "type": c_type,
                "exercises": finisher_exercises,
                "rounds": c_rounds,
                "duration_minutes": c_duration
            }

        return self.estimate_session_time(
            warmup=warmup,
            main=main,
            accessory=accessory,
            finisher=finisher,
            cooldown=cooldown,
            intent=session.intent_tags[0] if session.intent_tags else "hypertrophy"
        )

    def estimate_session_time_with_transitions(
        self,
        warmup: list[dict] | None = None,
        main: list[dict] | None = None,
        accessory: list[dict] | None = None,
        circuit: dict | None = None,
        finisher: dict | None = None,
        cooldown: list[dict] | None = None,
        intent: str = "hypertrophy",
        block_order: list[str] | None = None
    ) -> SessionTimeBreakdown:
        """
        Estimate total session time accounting for transitions between blocks.

        Args:
            warmup: Warmup exercises
            main: Main exercises
            accessory: Accessory exercises
            circuit: Circuit block
            finisher: Finisher block
            cooldown: Cooldown stretches
            intent: Training intent
            block_order: List of block types in order (e.g., ["warmup", "main", "circuit", "cooldown"])

        Returns:
            SessionTimeBreakdown with component and total times including transitions
        """
        # Calculate individual block times
        warmup_time = self.estimate_warmup_time(warmup or [])
        main_time = self.estimate_block_time(main or [], "main", intent)

        # Mutually exclusive: either circuit OR accessory, never both
        if circuit:
            circuit_time = self.estimate_circuit_time(circuit)
            accessory_time = 0
        else:
            accessory_time = self.estimate_block_time(accessory or [], "accessory", intent)
            circuit_time = 0

        finisher_time = self.estimate_finisher_time(finisher)
        cooldown_time = self.estimate_cooldown_time(cooldown or [])

        # Calculate transitions between blocks (2 minutes per transition)
        transition_seconds = 120  # 2 minutes in seconds
        transition_minutes = 0

        if block_order:
            # Count number of transitions = number of blocks - 1
            num_blocks = len([b for b in block_order if b and b != "empty"])
            if num_blocks > 1:
                transition_minutes = (num_blocks - 1) * (transition_seconds // 60)
                logger.info(f"[TimeEstimationService.estimate_session_time_with_transitions] {num_blocks} blocks, {transition_minutes} min transitions")

        total = warmup_time + main_time + circuit_time + accessory_time + finisher_time + cooldown_time + transition_minutes

        return SessionTimeBreakdown(
            warmup_minutes=warmup_time,
            main_minutes=main_time,
            accessory_minutes=accessory_time,
            circuit_minutes=circuit_time,
            finisher_minutes=finisher_time,
            cooldown_minutes=cooldown_time,
            total_minutes=total
        )

    def estimate_block_time_by_type(
        self,
        exercises: list[dict],
        block_type: str,
        intent: str = "hypertrophy"
    ) -> int:
        """
        Estimate time for a block based on its type.

        Args:
            exercises: List of exercise dicts
            block_type: Block type (warmup, main, accessory, cooldown, circuit)
            intent: Training intent

        Returns:
            Time in minutes
        """
        if not exercises:
            return 0

        if block_type == "warmup":
            return self.estimate_warmup_time(exercises)
        elif block_type == "cooldown":
            return self.estimate_cooldown_time(exercises)
        elif block_type == "circuit":
            # For circuits, the first dict may have circuit metadata
            if exercises and isinstance(exercises[0], dict):
                circuit_data = exercises[0].get("circuit_metadata", {})
                return self.estimate_circuit_time(circuit_data)
            return 0
        else:
            # main, accessory, finisher use block_time
            role = "main" if block_type == "main" else block_type
            return self.estimate_block_time(exercises, role, intent)
            
    async def estimate_session_duration_async(
        self,
        db: Any,
        user_id: int,
        session_id: int,
    ) -> dict:
        """
        Estimate duration for a session stored in DB.
        
        Returns dict matching SessionTimeBreakdown fields.
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.program import Session, SessionExercise, ExerciseRole
        from app.models.circuit import CircuitTemplate
        
        result = await db.execute(
            select(Session)
            .options(
                selectinload(Session.exercises).selectinload(SessionExercise.movement),
                selectinload(Session.finisher_circuit).selectinload(CircuitTemplate.melted_exercises)
            )
            .where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return {"total_minutes": 0}
            
        # Convert SessionExercise to ExerciseBlock format
        def session_exercise_to_block(ex: SessionExercise) -> dict:
            return {
                "movement": ex.movement.name if ex.movement else "Unknown",
                "sets": ex.target_sets,
                "rep_range_min": ex.target_rep_range_min,
                "rep_range_max": ex.target_rep_range_max,
                "target_rpe": ex.target_rpe,
                "duration_seconds": ex.target_duration_seconds,
                "rest_seconds": ex.default_rest_seconds,
                "notes": ex.notes
            }
        
        # Organize exercises by role
        warmup = []
        main = []
        accessory = []
        cooldown = []
        finisher = None
        
        for ex in session.exercises or []:
            block = session_exercise_to_block(ex)
            if ex.exercise_role == ExerciseRole.WARMUP:
                warmup.append(block)
            elif ex.exercise_role == ExerciseRole.MAIN:
                main.append(block)
            elif ex.exercise_role == ExerciseRole.ACCESSORY:
                accessory.append(block)
            elif ex.exercise_role == ExerciseRole.COOLDOWN:
                cooldown.append(block)
            elif ex.exercise_role == ExerciseRole.FINISHER:
                if not finisher:
                    finisher = {"exercises": []}
                finisher["exercises"].append(block)
        
        breakdown = self.estimate_session_time(
            warmup=warmup,
            main=main,
            accessory=accessory,
            circuit=None,
            finisher=finisher,
            cooldown=cooldown,
            intent="hypertrophy"
        )
        
        return {
            "total_minutes": breakdown.total_minutes,
            "breakdown": {
                "warmup_minutes": breakdown.warmup_minutes,
                "main_minutes": breakdown.main_minutes,
                "accessory_minutes": breakdown.accessory_minutes,
                "finisher_minutes": breakdown.finisher_minutes,
                "cooldown_minutes": breakdown.cooldown_minutes
            },
            "confidence": "medium"
        }

    async def estimate_microcycle_duration(
        self,
        db: Any,
        user_id: int,
        microcycle_id: int,
    ) -> dict:
        """
        Estimate duration stats for a microcycle.
        """
        from sqlalchemy import select
        from app.models.program import Session
        
        result = await db.execute(select(Session).where(Session.microcycle_id == microcycle_id))
        sessions = result.scalars().all()
        
        total_minutes = 0
        for session in sessions:
            est = await self.estimate_session_duration(db, user_id, session.id)
            total_minutes += est["total_minutes"]
            
        count = len(sessions)
        avg = total_minutes / count if count > 0 else 0
        
        return {
            "session_count": count,
            "total_hours": round(total_minutes / 60, 1),
            "daily_average_minutes": round(avg)
        }


# Singleton instance
time_estimation_service = TimeEstimationService()
