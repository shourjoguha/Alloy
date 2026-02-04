"""
AdaptationService - Adapts sessions based on user feedback and constraints.

Responsible for:
- Parsing and applying movement rule constraints (forbidden moves, injury restrictions)
- Adapting sessions based on soreness and recovery signals
- Suggesting exercise substitutions via LLM
- Managing optional session sections (warmup, finisher, conditioning)
- Enforcing user preferences (enjoyable activities weighting)
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.user import (
    UserMovementRule, UserEnjoyableActivity
)
from app.models.movement import Movement
from app.models.program import Session, Microcycle, Program, SessionExercise
from app.schemas.daily import AdaptationRequest


class AdaptationService:
    """
    Adapts workout sessions in real-time based on user state.
    
    Constraints applied:
    - Movement rules (forbidden exercises, injury restrictions)
    - Soreness feedback (avoid sore body parts)
    - Recovery status (adjust volume if low recovery)
    - User preferences (weight enjoyable activities, avoid disliked)
    
    Adaptations may include:
    - Removing/substituting exercises
    - Adding/removing optional sections (warmup, finisher)
    - Adjusting sets/reps based on recovery
    - Suggesting alternative movements
    """
    
    async def adapt_session(
        self,
        db: AsyncSession,
        user_id: int,
        session_id: int,
        request: AdaptationRequest,
    ) -> Dict[str, Any]:
        """
        Adapt a session based on user state and constraints.
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID
            request: Adaptation request (soreness, recovery_signal, notes)
        
        Returns:
            Dict with adapted_patterns (list), removed_patterns (list), 
            added_sections (list), notes (str)
        
        Raises:
            ValueError: If session not found
        """
        # Fetch session and movements
        session_result = await db.execute(
            select(Session)
            .join(Microcycle)
            .join(Program)
            .where(
                and_(
                    Session.id == session_id,
                    Program.user_id == user_id
                )
            )
        )
        session = session_result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Check if session has circuits
        has_circuit = session.finisher_circuit_id
        
        if has_circuit:
            return await self._adapt_circuit_session(db, session, user_id, request)
        
        # Fall back to existing accessory adaptation logic
        patterns_result = await db.execute(
            select(SessionExercise).options(joinedload(SessionExercise.movement)).where(
                SessionExercise.session_id == session_id
            )
        )
        patterns = list(patterns_result.scalars().all())
        
        # Load constraints
        rules = await self._get_movement_rules(db, user_id)
        recovery = await self._assess_recovery(db, user_id, request)
        
        # Adapt patterns
        adapted = []
        removed = []
        for pattern in patterns:
            # Check movement rules
            forbidden = self._is_movement_forbidden(pattern.movement, rules)
            if forbidden:
                removed.append({"movement": pattern.movement, "reason": f"Forbidden: {forbidden}"})
                continue
            
            # Check soreness
            soreness_dict = {s.body_part: s.level for s in request.soreness or []}
            affected_by_soreness = self._check_soreness_conflict(pattern, soreness_dict)
            if affected_by_soreness:
                removed.append({"movement": pattern.movement, "reason": f"Conflicts with soreness: {affected_by_soreness}"})
                continue
            
            # Adjust sets/reps based on recovery
            adjusted = self._adjust_volume(pattern, recovery)
            adapted.append(adjusted)
        
        # Add optional sections based on recovery
        added_sections = []
        if recovery.get("recovery_score", 50) > 70:
            added_sections.append("conditioning")
        if recovery.get("recovery_score", 50) < 40:
            added_sections.append("extra_warmup")
        
        return {
            "adapted_patterns": adapted,
            "removed_patterns": removed,
            "added_sections": added_sections,
            "recovery_score": recovery.get("recovery_score"),
            "notes": f"Adapted {len(adapted)} patterns, removed {len(removed)}, added {len(added_sections)} sections",
        }
    
    async def _adapt_circuit_session(
        self,
        db: AsyncSession,
        session: Session,
        user_id: int,
        request: AdaptationRequest,
    ) -> Dict[str, Any]:
        """
        Adapt a session that contains circuits.
        
        Circuits are treated as atomic units - entire circuit is removed/replaced, 
        not individual exercises.
        
        Args:
            db: Database session
            session: Session model
            user_id: User ID
            request: Adaptation request
        
        Returns:
            Dict with adaptation results
        """
        from app.models.circuit import CircuitTemplate
        
        # Get circuit IDs
        circuit_ids = []
        if session.finisher_circuit_id:
            circuit_ids.append(session.finisher_circuit_id)
        
        # Load circuits
        circuits = []
        for circuit_id in circuit_ids:
            result = await db.execute(
                select(CircuitTemplate).where(CircuitTemplate.id == circuit_id)
            )
            circuit = result.scalar_one_or_none()
            if circuit:
                circuits.append(circuit)
        
        # Load constraints
        rules = await self._get_movement_rules(db, user_id)
        recovery = await self._assess_recovery(db, user_id, request)
        
        # Check if circuits conflict with soreness or movement rules
        removed_circuits = []
        kept_circuits = []
        
        soreness_dict = {s.body_part: s.level for s in request.soreness or []}
        
        for circuit in circuits:
            # Check if any movement in circuit is forbidden
            from app.models.circuit_extended import CircuitMelted
            melted_result = await db.execute(
                select(CircuitMelted).where(CircuitMelted.circuit_id == circuit.id)
            )
            melted_exercises = melted_result.scalars().all()
            
            circuit_conflict = False
            conflict_reason = ""
            
            for melted in melted_exercises:
                if melted.movement:
                    forbidden = self._is_movement_forbidden(melted.movement.name, rules)
                    if forbidden:
                        circuit_conflict = True
                        conflict_reason = f"Contains forbidden movement: {forbidden}"
                        break
                    
                    # Check soreness conflict
                    affected = self._check_soreness_conflict(
                        melted.movement, soreness_dict
                    )
                    if affected:
                        circuit_conflict = True
                        conflict_reason = f"Conflicts with soreness: {affected}"
                        break
            
            if circuit_conflict:
                removed_circuits.append({
                    "circuit_id": circuit.id,
                    "circuit_name": circuit.name,
                    "reason": conflict_reason
                })
            else:
                kept_circuits.append(circuit)
        
        # Suggest alternative circuits if any were removed
        suggested_alternatives = []
        if removed_circuits:
            from app.models.circuit_extended import CircuitMacro
            alternatives_result = await db.execute(
                select(CircuitTemplate)
                .join(CircuitMacro, CircuitMacro.circuit_id == CircuitTemplate.id)
                .where(
                    and_(
                        CircuitTemplate.id.notin_(circuit_ids),
                        CircuitTemplate.circuit_type == circuits[0].circuit_type if circuits else None
                    )
                )
                .limit(5)
            )
            suggested_alternatives = alternatives_result.scalars().all()
        
        return {
            "adapted_circuits": kept_circuits,
            "removed_circuits": removed_circuits,
            "suggested_alternatives": [
                {
                    "circuit_id": c.id,
                    "circuit_name": c.name,
                    "circuit_type": c.circuit_type.value
                }
                for c in suggested_alternatives
            ],
            "recovery_score": recovery.get("recovery_score"),
            "notes": f"Adapted {len(kept_circuits)} circuits, removed {len(removed_circuits)} circuits",
        }
    
    async def suggest_exercise_substitution(
        self,
        db: AsyncSession,
        user_id: int,
        movement: str,
        context: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Suggest alternative exercises using substitution_group matching.
        
        Uses the substitution_group field to find biomechanically similar movements
        that can serve as substitutes. This is safer and faster than LLM-based
        suggestions while still providing intelligent alternatives.
        
        Args:
            db: Database session
            user_id: User ID
            movement: Movement to substitute
            context: Optional context (goal, intensity, equipment)
        
        Returns:
            Dict with suggested_movements (list of movement names), reasoning (str)
        """
        from app.models.movement import Movement
        from sqlalchemy import select
        
        context = context or {}
        
        # Find the original movement
        result = await db.execute(
            select(Movement).where(Movement.name == movement)
        )
        original_movement = result.scalar_one_or_none()
        
        if not original_movement:
            return {
                "original_movement": movement,
                "suggested_movements": [],
                "reasoning": f"Original movement '{movement}' not found in database.",
            }
        
        # Get substitution_group from original movement
        substitution_group = original_movement.substitution_group
        
        if not substitution_group:
            return {
                "original_movement": movement,
                "suggested_movements": [],
                "reasoning": f"Movement '{movement}' has no substitution_group defined. Manual review needed.",
            }
        
        # Find all movements in the same substitution_group (excluding original)
        result = await db.execute(
            select(Movement).where(
                Movement.substitution_group == substitution_group,
                Movement.name != movement
            )
        )
        alternatives = list(result.scalars().all())
        
        # Filter by user preferences and constraints
        # 1. Avoid movements marked as HARD_NO
        forbidden_result = await db.execute(
            select(Movement)
            .join(Movement.user_rules)
            .where(Movement.user_rules.user_id == user_id)
        )
        forbidden_movements = {m.name for m in forbidden_result.scalars().all()}
        
        # 2. Filter by equipment availability if provided in context
        required_equipment = context.get("equipment", "").lower() if context.get("equipment") else ""
        filtered_alternatives = []
        
        for alt in alternatives:
            # Skip forbidden movements
            if alt.name in forbidden_movements:
                continue
            
            # Skip if equipment constraints specified and not met
            if required_equipment:
                # Simple check: if equipment field exists, skip if doesn't match
                # MVP: basic filtering, can be enhanced with proper equipment joins
                if not self._meets_equipment_constraint(alt, required_equipment):
                    continue
            
            filtered_alternatives.append(alt.name)
        
        # Sort by CNS load (prefer lower CNS load for substitutions)
        # This makes substitutions less taxing than original
        cns_order = {"very_low": 0, "low": 1, "moderate": 2, "high": 3, "very_high": 4}
        filtered_alternatives.sort(
            key=lambda m_name: cns_order.get(
                next((alt.cns_load.value for alt in alternatives if alt.name == m_name), 
                     "moderate"),
                2
            )
        )
        
        reasoning_parts = [
            f"Found {len(filtered_alternatives)} alternatives in substitution group '{substitution_group}'.",
            "Alternatives sorted by CNS load preference (lower preferred)."
        ]
        
        if required_equipment:
            reasoning_parts.append(f"Filtered by available equipment: {required_equipment}")
        
        if forbidden_movements:
            reasoning_parts.append(f"Excluded {len(forbidden_movements)} user-forbidden movements")
        
        return {
            "original_movement": movement,
            "suggested_movements": filtered_alternatives[:5],  # Limit to top 5
            "reasoning": " ".join(reasoning_parts),
            "substitution_group": substitution_group,
        }
    
    def _meets_equipment_constraint(
        self,
        movement: "Movement",
        required_equipment: str,
    ) -> bool:
        """
        Check if movement meets equipment constraints.
        
        MVP: Basic check based on movement name patterns.
        Can be enhanced with proper equipment joins.
        
        Args:
            movement: Movement to check
            required_equipment: Required equipment string (e.g., "barbell", "dumbbell")
        
        Returns:
            True if movement meets constraints, False otherwise
        """
        movement_lower = movement.name.lower()
        required_lower = required_equipment.lower()
        
        # Common equipment patterns in movement names
        equipment_patterns = {
            "barbell": ["barbell", "bb ", " bb"],
            "dumbbell": ["dumbbell", "db ", " db"],
            "kettlebell": ["kettlebell", "kb ", " kb", "kettle"],
            "machine": ["machine", "cable", "lat pulldown", "leg press"],
            "bodyweight": ["bodyweight", "pushup", "pullup", "plank", "dip", "lunge"],
            "cable": ["cable", "lat pulldown", "crossover"],
        }
        
        # Check if movement matches required equipment
        patterns = equipment_patterns.get(required_lower, [required_lower])
        return any(pattern in movement_lower for pattern in patterns)
    
    async def apply_movement_rule(
        self,
        db: AsyncSession,
        user_id: int,
        movement_id: int,
        rule_type: str,
        reason: str,
    ) -> "UserMovementRule":
        """
        Create or update a movement rule for user.
        
        Args:
            db: Database session
            user_id: User ID
            movement_id: Movement ID
            rule_type: Rule type (hard_no, hard_yes, preferred)
            reason: Reason for the rule
        
        Returns:
            Created/updated UserMovementRule
        """
        from app.models.enums import MovementRuleType, RuleCadence
        
        # Check if rule exists
        existing = await db.execute(
            select(UserMovementRule).where(
                and_(
                    UserMovementRule.user_id == user_id,
                    UserMovementRule.movement_id == movement_id
                )
            )
        )
        rule = existing.scalar_one_or_none()
        
        if rule:
            rule.rule_type = MovementRuleType(rule_type)
            rule.notes = reason
        else:
            rule = UserMovementRule(
                user_id=user_id,
                movement_id=movement_id,
                rule_type=MovementRuleType(rule_type),
                cadence=RuleCadence.PER_MICROCYCLE,
                notes=reason,
            )
            db.add(rule)
        
        await db.commit()
        return rule
    
    def _is_movement_forbidden(self, movement: Any, rules: List[Dict]) -> Optional[str]:
        """
        Check if movement violates any rules.
        
        Args:
            movement: Movement object with ID
            rules: List of rule dicts
        
        Returns:
            Reason if forbidden, None otherwise
        """
        movement_id = getattr(movement, "id", None)
        
        if movement_id is None:
            return None

        for rule in rules:
            if rule.get("rule_type") != "hard_no":
                continue

            if rule.get("movement_id") == movement_id:
                return rule.get("reason", "Rule violation")
        
        return None
    
    def _check_soreness_conflict(
        self,
        pattern: "SessionExercise",
        soreness_data: Dict[str, int],
    ) -> Optional[str]:
        """
        Check if movement conflicts with reported soreness.
        
        Args:
            pattern: Movement pattern
            soreness_data: Dict of body_part -> soreness_level (0-10)
        
        Returns:
            Body part if conflict, None otherwise
        """
        if not soreness_data:
            return None
        
        movement_name = getattr(getattr(pattern, "movement", None), "name", None) or ""
        movement_lower = movement_name.lower()
        for body_part, level in soreness_data.items():
            # Simple heuristic: if body part mentioned in movement name and soreness > 6
            if level > 6 and body_part.lower() in movement_lower:
                return body_part
        
        return None
    
    def _adjust_volume(
        self,
        pattern: "SessionExercise",
        recovery: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Adjust sets/reps based on recovery status.
        
        Args:
            pattern: Movement pattern
            recovery: Recovery assessment dict
        
        Returns:
            Adjusted pattern dict
        """
        recovery_score = recovery.get("recovery_score", 50)
        
        adjusted = {
            "movement": getattr(getattr(pattern, "movement", None), "name", None),
            "sets": pattern.target_sets,
            "rep_range_min": pattern.target_rep_range_min,
            "rep_range_max": pattern.target_rep_range_max,
            "rpe": pattern.target_rpe,
        }
        
        if recovery_score < 40:
            # Low recovery: reduce sets, increase reps
            adjusted["sets"] = max(2, pattern.target_sets - 1)
            if adjusted["rep_range_min"] is not None:
                adjusted["rep_range_min"] = min(20, adjusted["rep_range_min"] + 1)
            if adjusted["rep_range_max"] is not None:
                adjusted["rep_range_max"] = min(20, adjusted["rep_range_max"] + 2)
            if adjusted["rpe"] is not None:
                adjusted["rpe"] = max(5, adjusted["rpe"] - 1)
            adjusted["note"] = "Volume reduced due to low recovery"
        elif recovery_score > 75:
            # High recovery: increase sets or reps
            adjusted["sets"] = pattern.target_sets + 1
            adjusted["note"] = "Volume increased due to strong recovery"
        
        return adjusted
    
    async def _get_movement_rules(self, db: AsyncSession, user_id: int) -> List[Dict]:
        """
        Fetch all movement rules for user.
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            List of rule dicts
        """
        result = await db.execute(
            select(UserMovementRule).where(UserMovementRule.user_id == user_id)
        )
        rules = list(result.scalars().all())
        
        return [
            {
                "movement_id": r.movement_id,
                "rule_type": r.rule_type.value if hasattr(r.rule_type, 'value') else r.rule_type,
                "reason": r.notes or "",
            }
            for r in rules
        ]
    
    async def _get_user_preferences(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """
        Fetch user preferences (enjoyable activities, etc).
        
        Args:
            db: Database session
            user_id: User ID
        
        Returns:
            Dict of preferences
        """
        result = await db.execute(
            select(UserEnjoyableActivity).where(UserEnjoyableActivity.user_id == user_id)
        )
        activities = list(result.scalars().all())
        
        enjoyable = [str(a.activity_type.value) if hasattr(a.activity_type, 'value') else str(a.activity_type) for a in activities if a.enabled]
        
        return {
            "enjoyable_activities": enjoyable,
        }
    
    async def _assess_recovery(
        self,
        db: AsyncSession,
        user_id: int,
        request: AdaptationRequest,
    ) -> Dict[str, Any]:
        """
        Assess overall recovery status.
        
        Args:
            db: Database session
            user_id: User ID
            request: Adaptation request with recovery signals
        
        Returns:
            Recovery assessment dict with recovery_score (0-100)
        """
        components = []
        
        # Recovery signal from request
        if request.recovery:
            sleep_hours = request.recovery.sleep_hours or 7
            sleep_score = min(100, (sleep_hours / 8) * 100)  # 8 hours = 100%
            energy = request.recovery.energy_level or 5
            stress = 100 - (request.recovery.stress_level or 5) * 10  # Higher stress = lower recovery
            components = [sleep_score, energy * 10, stress]
        
        # Soreness impact (negative)
        if request.soreness:
            max_soreness = max([s.level for s in request.soreness])
            soreness_impact = (5 - max_soreness) * 20  # 5 level scale -> 0-100
            components.append(soreness_impact)
        
        # Calculate average
        recovery_score = int(sum(components) / len(components)) if components else 50
        
        return {
            "recovery_score": max(0, min(100, recovery_score)),
            "components": components,
        }


# Singleton instance
adaptation_service = AdaptationService()
