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

class ConstraintSolver:
    def __init__(self):
        pass
        
    def solve_session(self, request: OptimizationRequest) -> OptimizationResult:
        """
        Solve for the optimal set of movements that satisfy volume targets
        while minimizing fatigue and maximizing stimulus.
        """
        logger.info("=" * 80)
        logger.info("[ConstraintSolver.solve_session] Starting optimization")
        logger.info(f"  Available movements: {len(request.available_movements)}")
        logger.info(f"  Available circuits: {len(request.available_circuits)}")
        logger.info(f"  Target muscle volumes: {request.target_muscle_volumes}")
        logger.info(f"  Max fatigue: {request.max_fatigue}")
        logger.info(f"  Min stimulus: {request.min_stimulus}")
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
        volume_reduction_pct = activity_distribution_config.or_tools_volume_target_reduction_pct
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

        # C. Max Fatigue Constraint
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
        model.Add(fatigue_expr <= int(activity_distribution_config.or_tools_max_fatigue * 100))

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
        # Ensure 2-3 compound movements in main lifts, or 1 compound + 2 isolations
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
        
        # Either: 2-3 compounds OR 1 compound + 2+ isolations
        has_sufficient_compounds = total_compound >= 2
        has_sufficient_isolations = total_compound == 1 and total_isolation >= 2
        model.Add(has_sufficient_compounds + has_sufficient_isolations >= 1)
        
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
        logger.info("[ConstraintSolver.solve_session] Starting solver...")
        status = solver.Solve(model)
        logger.info(f"[ConstraintSolver.solve_session] Solver status: {solver.StatusName(status)}")
        
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
            logger.info(f"[ConstraintSolver.solve_session] Result: {status_str}")
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
        
        logger.warning("[ConstraintSolver.solve_session] No feasible solution found, returning INFEASIBLE")
        return OptimizationResult([], [], 0, 0, 0, "INFEASIBLE")
