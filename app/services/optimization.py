"""
Optimization Service using Google OR-Tools.
Implements a Constraint Satisfaction Problem (CSP) solver for workout generation.
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from ortools.sat.python import cp_model
from app.models.enums import SkillLevel, CircuitType
from app.config import activity_distribution as activity_distribution_config
from app.config.heuristics import TIME_ESTIMATION, TIME_CONSTRAINT_TOLERANCE_PERCENT, GOAL_DOSE_HEURISTICS
from app.services.time_estimation import (
    TimeEstimationService,
    get_default_session_duration,
    get_tolerance_buffer,
)
import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

or_tools_log_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "or_tools.log")
or_tools_handler = logging.FileHandler(or_tools_log_file)
or_tools_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(or_tools_handler)


@dataclass
class OptimizationMetrics:
    """Track optimization metrics for monitoring and alerting."""
    total_attempts: int = 0
    successful_optimizations: int = 0  # OPTIMAL or FEASIBLE
    failed_optimizations: int = 0  # INFEASIBLE
    pass_success_counts: Dict[int, int] = field(default_factory=dict)  # Track which passes succeed
    last_failure_timestamp: Optional[datetime] = None
    last_failure_details: Optional[Dict] = None
    failure_count_by_reason: Dict[str, int] = field(default_factory=dict)

    def record_attempt(self, result_status: str, pass_number: int = None, failure_details: Dict = None):
        """Record an optimization attempt."""
        self.total_attempts += 1
        if result_status in ["OPTIMAL", "FEASIBLE"]:
            self.successful_optimizations += 1
            if pass_number is not None:
                self.pass_success_counts[pass_number] = self.pass_success_counts.get(pass_number, 0) + 1
        elif result_status == "INFEASIBLE":
            self.failed_optimizations += 1
            self.last_failure_timestamp = datetime.now()
            if failure_details:
                self.last_failure_details = failure_details
                # Categorize failure by primary reason if available
                reason = failure_details.get("primary_violation", "unknown")
                self.failure_count_by_reason[reason] = self.failure_count_by_reason.get(reason, 0) + 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_optimizations / self.total_attempts) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.failed_optimizations / self.total_attempts) * 100

    def get_summary(self) -> Dict:
        """Get a summary of optimization metrics."""
        return {
            "total_attempts": self.total_attempts,
            "successful_optimizations": self.successful_optimizations,
            "failed_optimizations": self.failed_optimizations,
            "success_rate": round(self.success_rate, 2),
            "failure_rate": round(self.failure_rate, 2),
            "pass_success_counts": self.pass_success_counts,
            "last_failure_timestamp": self.last_failure_timestamp.isoformat() if self.last_failure_timestamp else None,
            "failure_count_by_reason": self.failure_count_by_reason,
        }


# Global metrics instance (thread-safe via threading.Lock)
_optimization_metrics = OptimizationMetrics()
_metrics_lock = threading.Lock()


def get_optimization_metrics() -> Dict:
    """Get current optimization metrics (thread-safe)."""
    with _metrics_lock:
        return _optimization_metrics.get_summary()


def reset_optimization_metrics():
    """Reset optimization metrics (useful for testing)."""
    with _metrics_lock:
        global _optimization_metrics
        _optimization_metrics = OptimizationMetrics()

@dataclass
class SolverMovement:
    """Simplified movement data for solver (picklable)."""
    id: int
    name: str
    primary_muscle: str
    fatigue_factor: float
    stimulus_factor: float
    compound: bool
    is_complex_lift: bool

@dataclass
class SolverCircuit:
    """Normalized circuit for optimization solver (parallel to SolverMovement)."""
    id: int
    name: str
    primary_muscle: str
    fatigue_factor: float
    stimulus_factor: float
    effective_work_volume: float
    circuit_type: CircuitType
    duration_seconds: int
    primary_region: str | None = None
    pattern_diversity_score: float = 0.0
    equipment_complexity: int = 0

@dataclass
class OptimizationRequest:
    available_movements: List[SolverMovement]
    available_circuits: List[SolverCircuit]
    target_muscle_volumes: Dict[str, int]  # e.g., {"quadriceps": 4, "hamstrings": 3}
    max_fatigue: float
    min_stimulus: float
    user_skill_level: SkillLevel
    excluded_movement_ids: List[int]
    required_movement_ids: List[int]
    session_duration_minutes: int
    allow_complex_lifts: bool
    allow_circuits: bool = True
    goal_weights: Dict[str, int] | None = None
    preferred_movement_ids: List[int] | None = None

@dataclass
class OptimizationResult:
    selected_movements: List[SolverMovement]
    selected_circuits: List[SolverCircuit]
    total_fatigue: float
    total_stimulus: float
    estimated_duration: int
    status: str  # "OPTIMAL", "FEASIBLE", "INFEASIBLE"
    pass_number: int = 1  # Track which pass succeeded
    pass_config: str = ""  # Config used for successful pass

class ConstraintSolver:
    def __init__(self):
        pass

    def solve_session_with_progressive_relaxation(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Solve with progressively relaxed constraints across multiple passes.

        Pass 1: Original strict constraints
        Pass 2: Relax fatigue by 50%
        Pass 3: Relax volume by 30%
        Pass 4: Relax compound requirement (1 compound + 1 isolation min)
        Pass 5: Minimum constraints (just ensure at least 2 movements)

        Returns the first feasible solution found, logging pass success data.
        """
        passes = [
            {
                "pass_number": 1,
                "fatigue_multiplier": 1.0,
                "volume_reduction_pct": activity_distribution_config.or_tools_volume_target_reduction_pct,
                "min_compound": 2,
                "min_isolation_if_one_compound": 2,
                "description": "Original strict constraints"
            },
            {
                "pass_number": 2,
                "fatigue_multiplier": 1.5,  # Relax fatigue by 50%
                "volume_reduction_pct": activity_distribution_config.or_tools_volume_target_reduction_pct,
                "min_compound": 2,
                "min_isolation_if_one_compound": 2,
                "description": "Relax fatigue by 50%"
            },
            {
                "pass_number": 3,
                "fatigue_multiplier": 1.5,  # Keep relaxed fatigue
                "volume_reduction_pct": 0.3,  # Relax volume by 30%
                "min_compound": 2,
                "min_isolation_if_one_compound": 2,
                "description": "Relax volume by 30%"
            },
            {
                "pass_number": 4,
                "fatigue_multiplier": 1.5,
                "volume_reduction_pct": 0.3,
                "min_compound": 1,  # Relax compound requirement
                "min_isolation_if_one_compound": 1,  # Relax isolation requirement
                "description": "Relax compound requirement (1 compound + 1 isolation min)"
            },
            {
                "pass_number": 5,
                "fatigue_multiplier": 2.0,  # Maximum fatigue relaxation
                "volume_reduction_pct": 0.5,  # Maximum volume relaxation
                "min_compound": 0,  # No compound requirement
                "min_isolation_if_one_compound": 0,
                "description": "Minimum constraints (at least 2 movements)"
            },
        ]

        logger.info("=" * 80)
        logger.info("[ConstraintSolver.solve_session_with_progressive_relaxation] Starting progressive constraint relaxation")
        logger.info(f"  Total passes to attempt: {len(passes)}")
        logger.info(f"  Session duration target: {request.session_duration_minutes} minutes")
        logger.info("=" * 80)

        for pass_config in passes:
            logger.info(f"--- Attempting Pass {pass_config['pass_number']}: {pass_config['description']} ---")
            result = self._solve_with_pass_config(request, pass_config)

            if result.status in ["OPTIMAL", "FEASIBLE"]:
                logger.info(f"✓ Pass {pass_config['pass_number']} SUCCEEDED")
                logger.info(f"  Config used: {pass_config['description']}")
                logger.info(f"  Selected {len(result.selected_movements)} movements, {len(result.selected_circuits)} circuits")
                logger.info(f"  Estimated duration: {result.estimated_duration} minutes")

                # Log pass success data for manual review
                self._log_pass_success(pass_config, result, request)

                # Record metrics (thread-safe)
                with _metrics_lock:
                    _optimization_metrics.record_attempt(result.status, pass_config['pass_number'])

                result.pass_number = pass_config['pass_number']
                result.pass_config = pass_config['description']
                return result
            else:
                logger.warning(f"✗ Pass {pass_config['pass_number']} FAILED - {pass_config['description']}")

        logger.error("[ConstraintSolver.solve_session_with_progressive_relaxation] All passes failed, returning INFEASIBLE")
        # Log detailed constraint violation information for debugging
        failure_details = self._log_infeasible_constraints(request, passes)

        # Record metrics (thread-safe)
        with _metrics_lock:
            _optimization_metrics.record_attempt("INFEASIBLE", failure_details=failure_details)

        # Alert on consecutive failures or high failure rate
        with _metrics_lock:
            if _optimization_metrics.failure_rate > 50 and _optimization_metrics.total_attempts > 10:
                logger.error(f"[OPTIMIZATION_ALERT] High failure rate detected: {_optimization_metrics.failure_rate:.1f}% "
                            f"({_optimization_metrics.failed_optimizations}/{_optimization_metrics.total_attempts} attempts)")

        return OptimizationResult([], [], 0, 0, 0, "INFEASIBLE", 5, "All passes failed")

    def _solve_with_pass_config(self, request: OptimizationRequest, pass_config: dict) -> OptimizationResult:
        """Solve with a specific pass configuration."""
        return self._solve_session_internal(
            request,
            fatigue_multiplier=pass_config["fatigue_multiplier"],
            volume_reduction_pct=pass_config["volume_reduction_pct"],
            min_compound=pass_config["min_compound"],
            min_isolation_if_one_compound=pass_config["min_isolation_if_one_compound"]
        )

    def _log_pass_success(self, pass_config: dict, result: OptimizationResult, request: OptimizationRequest):
        """Log pass success data for manual review."""
        log_entry = {
                "pass_number": pass_config["pass_number"],
                "description": pass_config["description"],
                "fatigue_multiplier": pass_config["fatigue_multiplier"],
                "volume_reduction_pct": pass_config["volume_reduction_pct"],
                "min_compound": pass_config["min_compound"],
                "session_type": getattr(request, 'session_type', 'unknown'),
                "session_duration_minutes": request.session_duration_minutes,
                "selected_movements_count": len(result.selected_movements),
                "selected_circuits_count": len(result.selected_circuits),
                "total_fatigue": result.total_fatigue,
                "total_stimulus": result.total_stimulus,
                "estimated_duration": result.estimated_duration,
                "goal_weights": request.goal_weights
        }

        logger.info(f"[PASS_SUCCESS_DATA] {log_entry}")

        # TODO: Save to database or persistent log file for manual review
        # This data can be used to inform decisions over time about which constraints are too strict

    def _log_infeasible_constraints(self, request: OptimizationRequest, attempted_passes: list) -> dict:
        """Log detailed constraint violation information when optimization fails.

        Returns:
            dict: Failure details for metrics tracking
        """
        logger.error("=" * 80)
        logger.error("[ConstraintSolver._log_infeasible_constraints] OPTIMIZATION FAILED - INFEASIBLE")
        logger.error("=" * 80)
        logger.error(f"  Available movements: {len(request.available_movements)}")
        logger.error(f"  Available circuits: {len(request.available_circuits)}")
        logger.error(f"  Target muscle volumes: {request.target_muscle_volumes}")
        logger.error(f"  Max fatigue limit: {request.max_fatigue}")
        logger.error(f"  Min stimulus required: {request.min_stimulus}")
        logger.error(f"  Session duration target: {request.session_duration_minutes} minutes")
        logger.error(f"  Allow complex lifts: {request.allow_complex_lifts}")
        logger.error(f"  Allow circuits: {request.allow_circuits}")
        logger.error(f"  User skill level: {request.user_skill_level}")
        logger.error(f"  Goal weights: {request.goal_weights}")
        logger.error(f"  Excluded movement IDs: {request.excluded_movement_ids}")
        logger.error(f"  Required movement IDs: {request.required_movement_ids}")
        logger.error(f"  Preferred movement IDs: {request.preferred_movement_ids}")

        # Log movement breakdown by muscle group
        muscle_groups = {}
        for m in request.available_movements:
            muscle = m.primary_muscle
            if muscle not in muscle_groups:
                muscle_groups[muscle] = []
            muscle_groups[muscle].append({
                "id": m.id,
                "name": m.name,
                "compound": m.compound,
                "fatigue_factor": m.fatigue_factor,
                "stimulus_factor": m.stimulus_factor
            })

        logger.error("  Movement breakdown by muscle group:")
        for muscle, movements in muscle_groups.items():
            target = request.target_muscle_volumes.get(muscle, 0)
            logger.error(f"    {muscle}: {len(movements)} available, target {target} sets")

        # Log circuit breakdown
        if request.available_circuits:
            logger.error("  Circuit breakdown:")
            for c in request.available_circuits:
                logger.error(f"    {c.name} (id={c.id}, muscle={c.primary_muscle}, fatigue={c.fatigue_factor:.2f}, duration={c.duration_seconds}s)")

        # Log attempted pass configurations
        logger.error(f"  Attempted {len(attempted_passes)} constraint relaxation passes:")
        for pass_config in attempted_passes:
            logger.error(f"    Pass {pass_config['pass_number']}: {pass_config['description']}")
            logger.error(f"      Fatigue multiplier: {pass_config['fatigue_multiplier']}")
            logger.error(f"      Volume reduction: {pass_config['volume_reduction_pct'] * 100:.0f}%")
            logger.error(f"      Min compound: {pass_config['min_compound']}")

        # Calculate total available fatigue and stimulus
        total_available_fatigue = sum(m.fatigue_factor for m in request.available_movements)
        total_available_stimulus = sum(m.stimulus_factor for m in request.available_movements)
        total_circuit_fatigue = sum(c.fatigue_factor for c in request.available_circuits)
        total_circuit_stimulus = sum(c.stimulus_factor for c in request.available_circuits)

        logger.error(f"  Total available fatigue (movements): {total_available_fatigue:.2f}")
        logger.error(f"  Total available stimulus (movements): {total_available_stimulus:.2f}")
        logger.error(f"  Total available fatigue (circuits): {total_circuit_fatigue:.2f}")
        logger.error(f"  Total available stimulus (circuits): {total_circuit_stimulus:.2f}")
        logger.error(f"  Total available fatigue (combined): {total_available_fatigue + total_circuit_fatigue:.2f}")
        logger.error(f"  Total available stimulus (combined): {total_available_stimulus + total_circuit_stimulus:.2f}")

        # Identify potential constraint violations
        violations = []

        # Check if fatigue constraint is too tight
        if total_available_fatigue + total_circuit_fatigue < request.max_fatigue:
            violations.append("Fatigue constraint: Even selecting ALL movements and circuits would not meet max fatigue limit")

        # Check if stimulus constraint is too tight
        if total_available_stimulus + total_circuit_stimulus < request.min_stimulus:
            violations.append("Stimulus constraint: Even selecting ALL movements and circuits would not meet min stimulus requirement")

        # Check if volume targets are too high
        for muscle, target_sets in request.target_muscle_volumes.items():
            available_for_muscle = len(muscle_groups.get(muscle, []))
            if available_for_muscle == 0:
                violations.append(f"Volume constraint: No movements available for {muscle} (target: {target_sets} sets)")
            elif available_for_muscle * 5 < target_sets:  # 5 is max sets per movement
                violations.append(f"Volume constraint: Not enough movements for {muscle} (available: {available_for_muscle}, max possible: {available_for_muscle * 5}, target: {target_sets} sets)")

        # Check if compound requirement can be met
        compound_count = sum(1 for m in request.available_movements if m.compound)
        if compound_count < 2:
            violations.append(f"Compound constraint: Only {compound_count} compound movements available (need at least 2)")

        # Check if duration constraint is too tight
        avg_minutes_per_movement = 5  # Conservative estimate
        max_possible_duration = len(request.available_movements) * avg_minutes_per_movement
        min_required_duration = request.session_duration_minutes * 0.7  # 70% of target (with tolerance)
        if max_possible_duration < min_required_duration:
            violations.append(f"Duration constraint: Not enough movements to meet minimum duration (max possible: {max_possible_duration}min, min required: {min_required_duration:.0f}min)")

        if violations:
            logger.error("  Detected potential constraint violations:")
            for i, violation in enumerate(violations, 1):
                logger.error(f"    {i}. {violation}")
        else:
            logger.error("  No obvious constraint violations detected - may be complex interaction of multiple constraints")

        logger.error("=" * 80)

        # Return failure details for metrics tracking
        primary_violation = violations[0].split(":")[0].strip() if violations else "unknown_complex"
        return {
            "available_movements": len(request.available_movements),
            "available_circuits": len(request.available_circuits),
            "target_muscle_volumes": request.target_muscle_volumes,
            "max_fatigue": request.max_fatigue,
            "min_stimulus": request.min_stimulus,
            "session_duration_minutes": request.session_duration_minutes,
            "user_skill_level": str(request.user_skill_level),
            "goal_weights": request.goal_weights,
            "violations": violations,
            "primary_violation": primary_violation,
            "muscle_groups": {muscle: len(movements) for muscle, movements in muscle_groups.items()},
            "total_available_fatigue": total_available_fatigue + total_circuit_fatigue,
            "total_available_stimulus": total_available_stimulus + total_circuit_stimulus,
            "compound_count": compound_count,
        }

    def _solve_session_internal(
        self,
        request: OptimizationRequest,
        fatigue_multiplier: float = 1.0,
        volume_reduction_pct: float = 0.2,
        min_compound: int = 2,
        min_isolation_if_one_compound: int = 2,
    ) -> OptimizationResult:
        """
        Internal solve method with configurable constraints.

        Args:
            fatigue_multiplier: Multiplier for max fatigue (1.0 = original, 1.5 = 50% relaxed)
            volume_reduction_pct: Percentage to reduce volume targets (0.2 = 20% reduction)
            min_compound: Minimum number of compound movements required
            min_isolation_if_one_compound: Min isolations if only 1 compound
        """
        logger.info("=" * 80)
        logger.info("[ConstraintSolver._solve_session_internal] Starting optimization")
        logger.info(f"  Available movements: {len(request.available_movements)}")
        logger.info(f"  Available circuits: {len(request.available_circuits)}")
        logger.info(f"  Target muscle volumes: {request.target_muscle_volumes}")
        logger.info(f"  Max fatigue multiplier: {fatigue_multiplier}")
        logger.info(f"  Volume reduction pct: {volume_reduction_pct}")
        logger.info(f"  Min compound required: {min_compound}")
        logger.info(f"  Skill level: {request.user_skill_level}")
        logger.info(f"  Session duration: {request.session_duration_minutes} minutes")
        logger.info(f"  Allow circuits: {request.allow_circuits}")
        logger.info(f"  Allow complex lifts: {request.allow_complex_lifts}")
        logger.info(f"  Goal weights: {request.goal_weights}")
        logger.info(f"  Solver timeout: {activity_distribution_config.or_tools_solver_timeout_seconds} seconds")
        logger.info("=" * 80)
        
        # Create fresh model and solver for each request to avoid memory leaks
        # and performance degradation from accumulating variables
        model = cp_model.CpModel()
        solver = cp_model.CpSolver()

        # 1. Variables
        # x[i] is a boolean variable indicating if movement i is selected
        movement_vars = {}
        circuit_vars = {}
        
        for m in request.available_movements:
            # Skip if explicitly excluded
            if m.id in request.excluded_movement_ids:
                continue
            
            # Skip if skill level mismatch (Hard Guardrail)
            # Simple hierarchy check would go here
            
            movement_vars[m.id] = model.NewBoolVar(f'movement_{m.id}')
        
        # Add circuit variables if allowed
        if request.allow_circuits and request.available_circuits:
            for c in request.available_circuits:
                circuit_vars[c.id] = model.NewBoolVar(f'circuit_{c.id}')
            
        if not movement_vars and not circuit_vars:
            logger.warning("[ConstraintSolver.solve_session] No variables available, returning INFEASIBLE")
            return OptimizationResult([], [], 0, 0, 0, "INFEASIBLE")

        # 2. Constraints

        # Set a time limit for solver to prevent hanging
        solver.parameters.max_time_in_seconds = float(activity_distribution_config.or_tools_solver_timeout_seconds)
        
        # A. Required Movements
        for m_id in request.required_movement_ids:
            if m_id in movement_vars:
                model.Add(movement_vars[m_id] == 1)
                
        # B. Volume Targets (Sets)
        # Use configurable min/max sets per movement (2-5 range)
        MIN_SETS_PER_MOVEMENT = activity_distribution_config.or_tools_min_sets_per_movement
        MAX_SETS_PER_MOVEMENT = activity_distribution_config.or_tools_max_sets_per_movement

        # Reduce volume targets by configured percentage to make them easier to meet
        reduced_target_volumes = {
            muscle: int(target_sets * (1 - volume_reduction_pct))
            for muscle, target_sets in request.target_muscle_volumes.items()
        }

        # Create sets variables for each movement (allows flexible sets 2-5)
        sets_vars = {}
        for m in request.available_movements:
            if m.id in movement_vars:
                sets_vars[m.id] = model.NewIntVar(MIN_SETS_PER_MOVEMENT, MAX_SETS_PER_MOVEMENT, f'sets_{m.id}')

        for muscle, reduced_target in reduced_target_volumes.items():
            relevant_sets_expr = []

            # Add movement sets expressions
            for m in request.available_movements:
                if m.id not in movement_vars or m.id not in sets_vars:
                    continue
                if m.primary_muscle == muscle:
                    relevant_sets_expr.append(sets_vars[m.id])

            # Add circuit variables
            if request.allow_circuits and request.available_circuits:
                for c in request.available_circuits:
                    if c.id not in circuit_vars:
                        continue
                    if c.primary_muscle == muscle:
                        # Assume circuits provide 3 sets
                        relevant_sets_expr.append(circuit_vars[c.id] * 3)

            if relevant_sets_expr:
                # Total sets >= Reduced target
                model.Add(sum(relevant_sets_expr) >= reduced_target)

        # C. Max Fatigue Constraint (with multiplier)
        movement_fatigue = sum(
            movement_vars[m.id] * int(m.fatigue_factor * 100)
            for m in request.available_movements
            if m.id in movement_vars
        )

        circuit_fatigue = 0
        if request.allow_circuits and request.available_circuits:
            circuit_fatigue = sum(
                circuit_vars[c.id] * int(c.fatigue_factor * 100)
                for c in request.available_circuits
                if c.id in circuit_vars
            )

        fatigue_expr = movement_fatigue + circuit_fatigue
        max_fatigue_limit = int(activity_distribution_config.or_tools_max_fatigue * 100 * fatigue_multiplier)
        logger.info(f"  Max fatigue constraint: {max_fatigue_limit / 100:.2f} (multiplier: {fatigue_multiplier})")
        model.Add(fatigue_expr <= max_fatigue_limit)
        
        # Min Stimulus Constraint
        movement_stimulus = sum(
            movement_vars[m.id] * int(m.stimulus_factor * 100)
            for m in request.available_movements
            if m.id in movement_vars
        )
        
        circuit_stimulus = 0
        if request.allow_circuits and request.available_circuits:
            circuit_stimulus = sum(
                circuit_vars[c.id] * int(c.stimulus_factor * 100)
                for c in request.available_circuits
                if c.id in circuit_vars
            )
        
        stimulus_expr = movement_stimulus + circuit_stimulus
        min_stimulus_limit = int(request.min_stimulus * 100)
        logger.info(f"  Min stimulus constraint: {min_stimulus_limit / 100:.2f}")
        model.Add(stimulus_expr >= min_stimulus_limit)

        # D. Max Duration Constraint (TimeEstimationService logic)
        # Uses TimeEstimationService for accurate time estimation with actual goal-based rep ranges
        time_estimator = TimeEstimationService()
        
        # Estimate time per movement based on realistic set counts and rest periods
        avg_sets = (MIN_SETS_PER_MOVEMENT + MAX_SETS_PER_MOVEMENT) / 2
        avg_sets_int = int(avg_sets)
        strength_weight = (request.goal_weights or {}).get("strength", 0)
        hypertrophy_weight = (request.goal_weights or {}).get("hypertrophy", 0)
        intent = "strength" if strength_weight > hypertrophy_weight else "hypertrophy"
        
        # Get actual rep range and rest time based on training intent from GOAL_DOSE_HEURISTICS
        # Use weighted average when both goals have significant weights (mixed training)
        strength_heuristics = GOAL_DOSE_HEURISTICS["strength"]
        hypertrophy_heuristics = GOAL_DOSE_HEURISTICS["hypertrophy"]
        strength_rep_range = strength_heuristics["rep_range"]
        hypertrophy_rep_range = hypertrophy_heuristics["rep_range"]
        strength_rest_range = strength_heuristics["rest_seconds"]
        hypertrophy_rest_range = hypertrophy_heuristics["rest_seconds"]
        
        if strength_weight > 0 and hypertrophy_weight > 0:
            # Mixed training: weighted average of strength and hypertrophy parameters
            total_weight = strength_weight + hypertrophy_weight
            
            # Weighted average for reps and rest
            avg_reps = int((
                (strength_rep_range[0] + strength_rep_range[1]) / 2 * strength_weight +
                (hypertrophy_rep_range[0] + hypertrophy_rep_range[1]) / 2 * hypertrophy_weight
            ) / total_weight)
            
            avg_rest_seconds = int((
                (strength_rest_range[0] + strength_rest_range[1]) / 2 * strength_weight +
                (hypertrophy_rest_range[0] + hypertrophy_rest_range[1]) / 2 * hypertrophy_weight
            ) / total_weight)
            
            rep_range_str = f"[{strength_rep_range[0]}-{strength_rep_range[1]}] mixed with [{hypertrophy_rep_range[0]}-{hypertrophy_rep_range[1]}]"
            rest_range_str = f"[{strength_rest_range[0]}-{strength_rest_range[1]}] mixed with [{hypertrophy_rest_range[0]}-{hypertrophy_rest_range[1]}]"
        else:
            # Single goal: use heuristics directly
            goal_heuristics = GOAL_DOSE_HEURISTICS.get(intent, GOAL_DOSE_HEURISTICS["hypertrophy"])
            rep_range = goal_heuristics.get("rep_range", [6, 15])
            avg_reps = (rep_range[0] + rep_range[1]) // 2  # Use midpoint of rep range
            
            rest_range = goal_heuristics.get("rest_seconds", [60, 120])
            avg_rest_seconds = (rest_range[0] + rest_range[1]) // 2  # Use midpoint of rest range
            rep_range_str = f"{rep_range[0]}-{rep_range[1]}"
            rest_range_str = f"{rest_range[0]}-{rest_range[1]}"
        
        # Use TimeEstimationService for accurate exercise time calculation
        seconds_per_movement = time_estimator.estimate_exercise_time(
            sets=avg_sets_int,
            reps=avg_reps,  # Use actual goal-based rep range
            rest_seconds=avg_rest_seconds,  # Use actual goal-based rest time
            role="main",
            intent=intent,
            metric_type="reps",
            is_superset=False
        )
        
        # Add transition time only between movements (not after last one)
        transition_seconds = TIME_ESTIMATION.get("transition_between_exercises_seconds", 45)
        total_seconds_per_movement = seconds_per_movement + transition_seconds
        
        # Convert to tenths of a minute for OR-Tools (requires integer coefficients)
        # 1 minute = 10 tenths, so we multiply by 10/60 = 1/6
        tenths_per_movement = round(total_seconds_per_movement / 6)  # 6 seconds = 0.1 minute = 1 tenth
        
        # Log for debugging
        minutes_per_movement = tenths_per_movement / 10
        logger.info(f"[ConstraintSolver] Time calculation: sets={avg_sets_int}, reps={avg_reps} (range {rep_range_str}), rest={avg_rest_seconds}s (range {rest_range_str}), transition={transition_seconds}s")
        logger.info(f"[ConstraintSolver] seconds_per_movement={seconds_per_movement}s + {transition_seconds}s transition = {total_seconds_per_movement}s = {minutes_per_movement:.1f} minutes per movement")
        
        # Use tenths of minute for integer constraints
        movement_duration_tenths = sum(
            movement_vars[m.id] * tenths_per_movement
            for m in request.available_movements
            if m.id in movement_vars
        )
        
        circuit_duration_tenths = 0
        if request.allow_circuits and request.available_circuits:
            circuit_duration_tenths = sum(
                circuit_vars[c.id] * round((c.duration_seconds / 60) * 10)  # convert to tenths of minute
                for c in request.available_circuits
                if c.id in circuit_vars
            )
        
        # Total duration in tenths of minute
        duration_expr_tenths = movement_duration_tenths + circuit_duration_tenths
        
        # Apply tolerance buffer to duration constraint
        # This allows the optimizer to find solutions within an acceptable range
        # instead of requiring exact duration match
        target_duration = request.session_duration_minutes or get_default_session_duration()
        
        # Calculate warmup and cooldown time that will be added to the session
        # Based on typical warmup/cooldown structure from _generate_warmup_cooldown
        # Warmup: 5 min base + (1-2 exercises × 1 min each) = ~6-7 min
        # Cooldown: 5 min base + (2-3 stretches × 1 min each) = ~7-8 min
        # Total warmup + cooldown: ~13-15 min
        warmup_cooldown_minutes = 15  # Conservative estimate
        
        # Adjust target duration to account for warmup/cooldown
        # The optimizer should select movements that fit within (target - warmup_cooldown)
        adjusted_target_duration = target_duration - warmup_cooldown_minutes
        min_duration, max_duration = get_tolerance_buffer(adjusted_target_duration)
        
        # Convert min and max duration (with tolerance) to tenths of minute
        min_duration_tenths = int(min_duration * 10)
        max_duration_tenths = int(max_duration * 10)
        logger.info(f"[ConstraintSolver] Duration constraint: target={target_duration} min, warmup+cooldown={warmup_cooldown_minutes}min, adjusted_target={adjusted_target_duration} min, min={min_duration:.1f} min, max={max_duration:.1f} min ({TIME_CONSTRAINT_TOLERANCE_PERCENT}% buffer)")
        model.Add(duration_expr_tenths >= min_duration_tenths)
        model.Add(duration_expr_tenths <= max_duration_tenths)
        
        # E. Compound Movement Constraints
        # Ensure minimum compound movements based on pass config
        compound_vars = [
            movement_vars[m.id]
            for m in request.available_movements
            if m.id in movement_vars and m.compound
        ]
        total_compound = sum(compound_vars)

        isolation_vars = [
            movement_vars[m.id]
            for m in request.available_movements
            if m.id in movement_vars and not m.compound
        ]
        total_isolation = sum(isolation_vars)

        # Ensure minimum compound movements based on pass config
        model.Add(total_compound >= min_compound)
        
        # F. Circuit Diversity Constraints
        # NOTE: Relaxed circuit selection - no region limits, no pattern diversity limits
        # Circuits are selected atomically (all-or-nothing) with only fatigue/duration constraints
        # Original diversity constraints commented out for more flexible circuit selection:
        #
        # if request.allow_circuits and request.available_circuits and len(request.available_circuits) > 1:
        #     # Constraint: Max 1 circuit per body region to promote variety
        #     region_vars = {}
        #     for c in request.available_circuits:
        #         if c.id not in circuit_vars:
        #             continue
        #         if c.primary_region not in region_vars:
        #             region_vars[c.primary_region] = []
        #         region_vars[c.primary_region].append(circuit_vars[c.id])
        #     
        #     # At most one circuit per region
        #     for region, c_vars in region_vars.items():
        #         if len(c_vars) > 1:
        #             model.Add(sum(c_vars) <= 1)
        #     
        #     # Constraint: Promote pattern diversity (max 1 low-diversity circuit)
        #     low_diversity_threshold = 0.3
        #     low_diversity_circuits = [
        #         c.id for c in request.available_circuits
        #         if c.id in circuit_vars and c.pattern_diversity_score < low_diversity_threshold
        #     ]
        #     if len(low_diversity_circuits) > 0:
        #         low_diversity_vars = [circuit_vars[cid] for cid in low_diversity_circuits]
        #         model.Add(sum(low_diversity_vars) <= 1)
        
        goal_weights = request.goal_weights or {}
        strength_pressure = goal_weights.get("strength", 0) + goal_weights.get("hypertrophy", 0)
        cardio_pressure = goal_weights.get("fat_loss", 0) + goal_weights.get("endurance", 0)
        if strength_pressure == 0 and cardio_pressure == 0:
            strength_pressure = 1

        preferred_ids = set(request.preferred_movement_ids or [])
        preference_bonus_pct = activity_distribution_config.preference_deviation_pct

        objective_terms = []
        for m in request.available_movements:
            if m.id not in movement_vars:
                continue
            base_score = int(m.stimulus_factor * 100) * max(1, strength_pressure)
            if m.id in preferred_ids:
                base_score += int(base_score * preference_bonus_pct)
            objective_terms.append(movement_vars[m.id] * base_score)

        if request.allow_circuits and request.available_circuits:
            for c in request.available_circuits:
                if c.id not in circuit_vars:
                    continue
                strength_score = int(c.stimulus_factor * 100) * max(0, strength_pressure)
                cardio_minutes = max(1, int(c.duration_seconds // 60))
                cardio_score = cardio_minutes * 10 * max(0, cardio_pressure)
                objective_terms.append(circuit_vars[c.id] * (strength_score + cardio_score))

        # Add duration maximization to objective
        # This incentivizes solver to get as much duration as possible within constraints
        # Keep duration constraints (min/max with tolerance) as validation
        duration_weight = 100  # Weight duration higher than stimulus to make it primary objective
        objective_terms.append(duration_expr_tenths * duration_weight)

        model.Maximize(sum(objective_terms))

        # 3. Solve
        logger.info("[ConstraintSolver._solve_session_internal] Starting solver...")
        status = solver.Solve(model)
        logger.info(f"[ConstraintSolver._solve_session_internal] Solver status: {solver.StatusName(status)}")

        # 4. Result
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            selected_movements = []
            selected_circuits = []
            total_fatigue = 0.0
            total_stimulus = 0.0

            # Process movements
            for m in request.available_movements:
                if m.id in movement_vars and solver.Value(movement_vars[m.id]):
                    selected_movements.append(m)
                    total_fatigue += m.fatigue_factor
                    total_stimulus += m.stimulus_factor

            # Process circuits
            if request.allow_circuits and request.available_circuits:
                for c in request.available_circuits:
                    if c.id in circuit_vars and solver.Value(circuit_vars[c.id]):
                        selected_circuits.append(c)
                        total_fatigue += c.fatigue_factor
                        total_stimulus += c.stimulus_factor

            status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
            logger.info(f"[ConstraintSolver._solve_session_internal] Result: {status_str}")
            logger.info(f"  Selected movements: {len(selected_movements)}")
            logger.info(f"  Selected circuits: {len(selected_circuits)}")
            logger.info(f"  Total fatigue: {total_fatigue:.2f}")
            logger.info(f"  Total stimulus: {total_stimulus:.2f}")
            
            # Calculate warmup and cooldown durations
            # Based on typical warmup/cooldown structure from _generate_warmup_cooldown
            # Warmup: 5 min base + (1-2 exercises × 1 min each) = ~6-7 min
            # Cooldown: 5 min base + (2-3 stretches × 1 min each) = ~7-8 min
            # Total warmup + cooldown: ~13-15 min
            warmup_cooldown_minutes = 15  # Conservative estimate for warmup + cooldown
            
            movement_duration = (len(selected_movements) * minutes_per_movement)
            circuit_duration = (sum(c.duration_seconds for c in selected_circuits) // 60)
            estimated_duration = movement_duration + circuit_duration + warmup_cooldown_minutes
            
            logger.info(f"  Duration breakdown: warmup+cooldown={warmup_cooldown_minutes}min, movements={movement_duration:.1f}min, circuits={circuit_duration}min")
            logger.info(f"  Estimated duration: {estimated_duration} minutes")
            logger.info("=" * 80)
            return OptimizationResult(
                selected_movements=selected_movements,
                selected_circuits=selected_circuits,
                total_fatigue=total_fatigue,
                total_stimulus=total_stimulus,
                estimated_duration=estimated_duration,
                status=status_str
            )

        logger.warning("[ConstraintSolver._solve_session_internal] No feasible solution found, returning INFEASIBLE")
        return OptimizationResult([], [], 0, 0, 0, "INFEASIBLE")

    def solve_session(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Backward-compatible wrapper for original solve_session method.
        Uses progressive constraint relaxation with multiple passes.
        """
        # Entry logging with input parameters summary
        logger.info("=" * 80)
        logger.info("[ConstraintSolver.solve_session] Starting optimization session")
        logger.info("  Input parameters summary:")
        logger.info(f"    Available movements: {len(request.available_movements)}")
        logger.info(f"    Available circuits: {len(request.available_circuits)}")
        logger.info(f"    Target muscle volumes: {request.target_muscle_volumes}")
        logger.info(f"    Max fatigue: {request.max_fatigue}")
        logger.info(f"    Min stimulus: {request.min_stimulus}")
        logger.info(f"    User skill level: {request.user_skill_level}")
        logger.info(f"    Excluded movement IDs: {request.excluded_movement_ids}")
        logger.info(f"    Required movement IDs: {request.required_movement_ids}")
        logger.info(f"    Session duration: {request.session_duration_minutes} minutes")
        logger.info(f"    Allow complex lifts: {request.allow_complex_lifts}")
        logger.info(f"    Allow circuits: {request.allow_circuits}")
        logger.info(f"    Goal weights: {request.goal_weights}")
        logger.info(f"    Preferred movement IDs: {request.preferred_movement_ids}")
        logger.info("=" * 80)

        try:
            # Solve with progressive constraint relaxation
            result = self.solve_session_with_progressive_relaxation(request)

            # Status logging when solution is returned
            logger.info("=" * 80)
            logger.info("[ConstraintSolver.solve_session] Optimization completed")
            logger.info(f"  Solution status: {result.status}")
            logger.info(f"  Selected movements: {len(result.selected_movements)}")
            logger.info(f"  Selected circuits: {len(result.selected_circuits)}")
            logger.info(f"  Total fatigue: {result.total_fatigue:.2f}")
            logger.info(f"  Total stimulus: {result.total_stimulus:.2f}")
            logger.info(f"  Estimated duration: {result.estimated_duration} minutes")
            logger.info(f"  Pass number: {result.pass_number}")
            logger.info(f"  Pass config: {result.pass_config}")
            logger.info("=" * 80)

            if result.status == "OPTIMAL":
                logger.info("[ConstraintSolver.solve_session] Solution found: OPTIMAL - Best possible solution found")
            elif result.status == "FEASIBLE":
                logger.info("[ConstraintSolver.solve_session] Solution found: FEASIBLE - Valid solution found, may not be optimal")
            elif result.status == "INFEASIBLE":
                logger.warning("[ConstraintSolver.solve_session] Solution status: INFEASIBLE - No valid solution exists")
            else:
                logger.warning(f"[ConstraintSolver.solve_session] Solution status: {result.status} - Unknown status")

            return result

        except Exception as e:
            # Error logging if exception occurs
            logger.error("=" * 80)
            logger.error("[ConstraintSolver.solve_session] Exception occurred during optimization")
            logger.error(f"  Error type: {type(e).__name__}")
            logger.error(f"  Error message: {str(e)}")
            logger.error(f"  Input parameters: available_movements={len(request.available_movements)}, "
                        f"available_circuits={len(request.available_circuits)}, "
                        f"session_duration={request.session_duration_minutes}")
            logger.error("=" * 80)
            raise
        except Exception as e:
            # Error logging if exception occurs
            logger.error("=" * 80)
            logger.error("[ConstraintSolver.solve_session] Exception occurred during optimization")
            logger.error(f"  Error type: {type(e).__name__}")
            logger.error(f"  Error message: {str(e)}")
            logger.error(f"  Input parameters: available_movements={len(request.available_movements)}, "
                        f"available_circuits={len(request.available_circuits)}, "
                        f"session_duration={request.session_duration_minutes}")
            logger.error("=" * 80)
            raise
