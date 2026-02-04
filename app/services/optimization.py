"""
Optimization Service using Google OR-Tools.
Implements a Constraint Satisfaction Problem (CSP) solver for workout generation.
"""
from typing import List, Dict
from dataclasses import dataclass
from ortools.sat.python import cp_model
from app.models.enums import SkillLevel, CircuitType
from app.config import activity_distribution as activity_distribution_config
import logging

logger = logging.getLogger(__name__)

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

                result.pass_number = pass_config['pass_number']
                result.pass_config = pass_config['description']
                return result
            else:
                logger.warning(f"✗ Pass {pass_config['pass_number']} FAILED - {pass_config['description']}")

        logger.error("[ConstraintSolver.solve_session_with_progressive_relaxation] All passes failed, returning INFEASIBLE")
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

        # D. Max Duration Constraint
        # Assume 1 set = 2 mins + 2 mins rest = 4 mins
        # Variable sets: 2-5 sets = 8-20 mins per movement
        # Use average 3.5 sets for duration calculation
        AVG_SETS_PER_MOVEMENT = (MIN_SETS_PER_MOVEMENT + MAX_SETS_PER_MOVEMENT) / 2
        MINS_PER_MOVEMENT = int(AVG_SETS_PER_MOVEMENT * 4)
        
        movement_duration = sum(
            movement_vars[m.id] * MINS_PER_MOVEMENT
            for m in request.available_movements
            if m.id in movement_vars
        )
        
        circuit_duration = 0
        if request.allow_circuits and request.available_circuits:
            circuit_duration = sum(
                circuit_vars[c.id] * (c.duration_seconds / 60)  # convert to minutes
                for c in request.available_circuits
                if c.id in circuit_vars
            )
        
        duration_expr = movement_duration + circuit_duration
        model.Add(duration_expr <= request.session_duration_minutes)
        
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
            estimated_duration = (len(selected_movements) * MINS_PER_MOVEMENT) + (sum(c.duration_seconds for c in selected_circuits) // 60)
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
        logger.info(f"  Input parameters summary:")
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
            logger.info(f"[ConstraintSolver.solve_session] Optimization completed")
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
