"""Circuit Metrics Normalization Service.

This service implements the 50% normalization logic for circuits, ensuring that
circuit metrics are appropriately scaled relative to main lift baselines.

The normalization approach:
1. Calculate baseline metrics from main lifts (compound movements)
2. Apply circuit-specific modifiers based on type and structure
3. Normalize circuit metrics to 40-60% of main lift baseline
4. Validate and enforce the 50% target range
"""

from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Movement, Session, SessionExercise
from app.models.circuit import CircuitTemplate
from app.models.enums import CircuitType, ExerciseRole


@dataclass
class MainLiftBaseline:
    """Baseline metrics calculated from main lift movements.
    
    Attributes:
        avg_fatigue_factor: Average fatigue factor across all main lifts
        avg_stimulus_factor: Average stimulus factor across all main lifts
        avg_work_volume: Average work volume across all main lifts
        sample_size: Number of main lifts used for calculation
    """
    avg_fatigue_factor: float
    avg_stimulus_factor: float
    avg_work_volume: float
    sample_size: int


@dataclass
class NormalizedCircuitMetrics:
    """Normalized circuit metrics after applying 50% normalization.
    
    Attributes:
        fatigue_factor: Normalized fatigue factor (40-60% of baseline)
        stimulus_factor: Normalized stimulus factor (40-60% of baseline)
        effective_work_volume: Normalized work volume
        normalization_applied: Whether normalization was applied
        original_values: Original unnormalized values for reference
        modifiers_applied: List of modifiers that were applied
        validation_passed: Whether the normalized values pass validation
    """
    fatigue_factor: float
    stimulus_factor: float
    effective_work_volume: float
    normalization_applied: bool
    original_values: Dict[str, float]
    modifiers_applied: List[str]
    validation_passed: bool


class CircuitMetricsNormalizer:
    """Service for normalizing circuit metrics relative to main lift baselines.
    
    This class implements the 50% normalization strategy where circuits are
    scaled to represent approximately 50% of the stimulus and fatigue of
    main lifts, with circuit-specific modifiers applied.
    """
    
    # Circuit type modifiers (baseline reduction factors)
    # Higher values = closer to baseline (less reduction)
    CIRCUIT_TYPE_MODIFIERS: Dict[CircuitType, float] = {
        CircuitType.ROUNDS_FOR_TIME: 0.90,  # Time pressure = higher intensity
        CircuitType.AMRAP: 0.85,           # Continuous work = sustained effort
        CircuitType.LADDER: 0.88,           # Progressive intensity
        CircuitType.EMOM: 0.92,             # Structured intervals = moderate
        CircuitType.TABATA: 0.82,           # High intensity intervals
        CircuitType.CHIPPER: 0.87,          # Long format = endurance
        CircuitType.STATION: 0.95,          # Structured stations = closest to baseline
    }
    
    # Normalization target range (percentage of main lift baseline)
    NORMALIZATION_TARGET_MIN = 0.40  # 40% of baseline
    NORMALIZATION_TARGET_MAX = 0.60  # 60% of baseline
    NORMALIZATION_TARGET_CENTER = 0.50  # 50% of baseline
    
    # Rep efficiency factor for high-rep, low-weight circuits
    HIGH_REP_THRESHOLD = 15  # reps per exercise
    REP_EFFICIENCY_FACTOR = 0.5
    
    # Default fallback values if no baseline can be calculated
    DEFAULT_BASELINE = MainLiftBaseline(
        avg_fatigue_factor=1.5,
        avg_stimulus_factor=1.2,
        avg_work_volume=100.0,
        sample_size=0
    )
    
    def __init__(self, db: AsyncSession):
        """Initialize the normalizer with a database session.
        
        Args:
            db: Async SQLAlchemy session for database queries
        """
        self.db = db
    
    async def calculate_main_lift_baseline(
        self,
        limit: Optional[int] = None,
        min_sample_size: int = 10
    ) -> MainLiftBaseline:
        """Calculate baseline metrics from main lift movements.
        
        This function queries all sessions with exercises in the MAIN section,
        identifies main lift movements (compound AND (fatigue_factor > 0.6 OR is_complex_lift)),
        and calculates average metrics across all main lifts.
        
        Args:
            limit: Maximum number of sessions to query (None = no limit)
            min_sample_size: Minimum number of main lifts required for valid baseline
            
        Returns:
            MainLiftBaseline object with average metrics
            
        Raises:
            ValueError: If insufficient data to calculate baseline
            
        Example:
            >>> normalizer = CircuitMetricsNormalizer(db)
            >>> baseline = await normalizer.calculate_main_lift_baseline(limit=100)
            >>> print(f"Baseline fatigue: {baseline.avg_fatigue_factor}")
            >>> print(f"Sample size: {baseline.sample_size}")
        """
        # Query SessionExercise records for MAIN exercises
        stmt = (
            select(SessionExercise)
            .options(joinedload(SessionExercise.movement))
            .where(SessionExercise.exercise_role == ExerciseRole.MAIN)
            .limit(limit)
        )
        
        result = await self.db.execute(stmt)
        session_exercises = result.scalars().unique().all()
        
        if not session_exercises:
            raise ValueError(
                f"No main exercises found in database. "
                f"Cannot calculate main lift baseline."
            )
        
        # Filter for main lift movements
        main_lifts = []
        for se in session_exercises:
            if not se.movement:
                continue
            
            movement = se.movement
            
            # Main lift criteria: compound AND (fatigue_factor > 0.6 OR is_complex_lift)
            if movement.compound and (
                (movement.fatigue_factor or 0) > 0.6 or 
                getattr(movement, 'is_complex_lift', False)
            ):
                main_lifts.append(movement)
        
        if len(main_lifts) < min_sample_size:
            raise ValueError(
                f"Insufficient main lifts for baseline calculation. "
                f"Found {len(main_lifts)} main lifts, required at least {min_sample_size}."
            )
        
        # Calculate averages
        total_fatigue = sum(m.fatigue_factor for m in main_lifts)
        total_stimulus = sum(m.stimulus_factor for m in main_lifts)
        total_work_volume = sum(
            (m.fatigue_factor * m.stimulus_factor) for m in main_lifts
        )
        
        baseline = MainLiftBaseline(
            avg_fatigue_factor=total_fatigue / len(main_lifts),
            avg_stimulus_factor=total_stimulus / len(main_lifts),
            avg_work_volume=total_work_volume / len(main_lifts),
            sample_size=len(main_lifts)
        )
        
        return baseline
    
    async def normalize_circuit_metrics(
        self,
        circuit: CircuitTemplate,
        baseline: Optional[MainLiftBaseline] = None,
        force_normalization: bool = True
    ) -> NormalizedCircuitMetrics:
        """Normalize circuit metrics to 40-60% of main lift baseline.
        
        This function applies the 50% normalization strategy with circuit-specific
        modifiers:
        1. Apply circuit type modifier (RFT: 0.9, AMRAP: 0.85, LADDER: 0.88, EMOM: 0.92)
        2. Apply volume factor (min(1.0, circuit_volume / avg_main_volume))
        3. Apply rep efficiency factor (0.5 for high-rep, low-weight circuits)
        4. Validate normalized values are in 40-60% range of baseline
        
        Args:
            circuit: CircuitTemplate object to normalize
            baseline: MainLiftBaseline for normalization (calculated if None)
            force_normalization: Whether to force values into 40-60% range
            
        Returns:
            NormalizedCircuitMetrics object with normalized values and metadata
            
        Raises:
            ValueError: If circuit has invalid or missing data
            
        Example:
            >>> normalizer = CircuitMetricsNormalizer(db)
            >>> circuit = await db.get(CircuitTemplate, circuit_id)
            >>> normalized = await normalizer.normalize_circuit_metrics(circuit)
            >>> print(f"Normalized fatigue: {normalized.fatigue_factor}")
            >>> print(f"Validation passed: {normalized.validation_passed}")
        """
        # Store original values
        original_values = {
            'fatigue_factor': circuit.fatigue_factor,
            'stimulus_factor': circuit.stimulus_factor,
            'effective_work_volume': circuit.effective_work_volume or 0.0
        }
        
        modifiers_applied: List[str] = []
        
        # Calculate baseline if not provided
        if baseline is None:
            try:
                baseline = await self.calculate_main_lift_baseline()
                modifiers_applied.append(f"auto_baseline_n={baseline.sample_size}")
            except ValueError:
                baseline = self.DEFAULT_BASELINE
                modifiers_applied.append("default_baseline")
        
        # Step 1: Apply circuit type modifier
        circuit_type_modifier = self.CIRCUIT_TYPE_MODIFIERS.get(
            circuit.circuit_type,
            0.90  # Default modifier
        )
        modifiers_applied.append(
            f"circ_type_{circuit.circuit_type.value}_mod_{circuit_type_modifier}"
        )
        
        # Step 2: Apply volume factor
        circuit_volume = circuit.effective_work_volume or original_values['effective_work_volume']
        volume_factor = min(1.0, circuit_volume / baseline.avg_work_volume) if baseline.avg_work_volume > 0 else 1.0
        modifiers_applied.append(f"vol_factor_{volume_factor:.2f}")
        
        # Step 3: Apply rep efficiency factor for high-rep circuits
        rep_efficiency_factor = 1.0
        if circuit.exercises_json:
            # Check if circuit has high-rep, low-weight exercises
            high_rep_count = sum(
                1 for ex in circuit.exercises_json
                if (ex.get('reps') or 0) >= self.HIGH_REP_THRESHOLD
            )
            if high_rep_count > len(circuit.exercises_json) / 2:
                rep_efficiency_factor = self.REP_EFFICIENCY_FACTOR
                modifiers_applied.append(f"high_rep_eff_{rep_efficiency_factor}")
        
        # Step 4: Calculate normalized values
        # Target: 50% of baseline, adjusted by modifiers
        base_target = self.NORMALIZATION_TARGET_CENTER
        
        normalized_fatigue = (
            baseline.avg_fatigue_factor * 
            base_target * 
            circuit_type_modifier * 
            volume_factor * 
            rep_efficiency_factor
        )
        
        normalized_stimulus = (
            baseline.avg_stimulus_factor * 
            base_target * 
            circuit_type_modifier * 
            volume_factor * 
            rep_efficiency_factor
        )
        
        normalized_work_volume = (
            baseline.avg_work_volume * 
            base_target * 
            circuit_type_modifier
        )
        
        # Step 5: Validate and enforce normalization range
        validation_passed = True
        min_fatigue = baseline.avg_fatigue_factor * self.NORMALIZATION_TARGET_MIN
        max_fatigue = baseline.avg_fatigue_factor * self.NORMALIZATION_TARGET_MAX
        min_stimulus = baseline.avg_stimulus_factor * self.NORMALIZATION_TARGET_MIN
        max_stimulus = baseline.avg_stimulus_factor * self.NORMALIZATION_TARGET_MAX
        
        if force_normalization:
            # Clamp values to target range
            if normalized_fatigue < min_fatigue:
                normalized_fatigue = min_fatigue
                validation_passed = False
                modifiers_applied.append("clamped_min_fatigue")
            elif normalized_fatigue > max_fatigue:
                normalized_fatigue = max_fatigue
                validation_passed = False
                modifiers_applied.append("clamped_max_fatigue")
            
            if normalized_stimulus < min_stimulus:
                normalized_stimulus = min_stimulus
                validation_passed = False
                modifiers_applied.append("clamped_min_stimulus")
            elif normalized_stimulus > max_stimulus:
                normalized_stimulus = max_stimulus
                validation_passed = False
                modifiers_applied.append("clamped_max_stimulus")
        else:
            # Just check if within range
            validation_passed = (
                min_fatigue <= normalized_fatigue <= max_fatigue and
                min_stimulus <= normalized_stimulus <= max_stimulus
            )
        
        # Create result object
        result = NormalizedCircuitMetrics(
            fatigue_factor=normalized_fatigue,
            stimulus_factor=normalized_stimulus,
            effective_work_volume=normalized_work_volume,
            normalization_applied=True,
            original_values=original_values,
            modifiers_applied=modifiers_applied,
            validation_passed=validation_passed
        )
        
        return result
    
    async def apply_normalization_to_circuit(
        self,
        circuit: CircuitTemplate,
        baseline: Optional[MainLiftBaseline] = None,
        force_normalization: bool = True
    ) -> NormalizedCircuitMetrics:
        """Calculate and apply normalized metrics to a circuit.
        
        This is a convenience method that normalizes metrics and updates
        the circuit object in place.
        
        Args:
            circuit: CircuitTemplate object to normalize and update
            baseline: MainLiftBaseline for normalization (calculated if None)
            force_normalization: Whether to force values into 40-60% range
            
        Returns:
            NormalizedCircuitMetrics object with the applied values
        """
        normalized = await self.normalize_circuit_metrics(
            circuit=circuit,
            baseline=baseline,
            force_normalization=force_normalization
        )
        
        # Update circuit in place
        circuit.fatigue_factor = normalized.fatigue_factor
        circuit.stimulus_factor = normalized.stimulus_factor
        circuit.effective_work_volume = normalized.effective_work_volume
        
        return normalized
    
    async def batch_normalize_circuits(
        self,
        circuit_ids: List[int],
        baseline: Optional[MainLiftBaseline] = None,
        force_normalization: bool = True,
        commit_batch_size: int = 100
    ) -> Dict[str, Any]:
        """Normalize multiple circuits in batches.
        
        Args:
            circuit_ids: List of circuit IDs to normalize
            baseline: MainLiftBaseline for normalization (calculated once if None)
            force_normalization: Whether to force values into 40-60% range
            commit_batch_size: Number of circuits to commit per batch
            
        Returns:
            Dictionary with batch processing results:
                - total_processed: Total number of circuits processed
                - success_count: Number of successfully normalized circuits
                - error_count: Number of circuits that failed normalization
                - errors: List of error messages for failed circuits
        """
        results = {
            'total_processed': 0,
            'success_count': 0,
            'error_count': 0,
            'errors': []
        }
        
        # Calculate baseline once if not provided
        if baseline is None:
            try:
                baseline = await self.calculate_main_lift_baseline()
            except ValueError as e:
                results['errors'].append(f"Failed to calculate baseline: {str(e)}")
                return results
        
        # Process circuits in batches
        for i in range(0, len(circuit_ids), commit_batch_size):
            batch_ids = circuit_ids[i:i + commit_batch_size]
            
            for circuit_id in batch_ids:
                results['total_processed'] += 1
                
                try:
                    circuit = await self.db.get(CircuitTemplate, circuit_id)
                    if not circuit:
                        raise ValueError(f"Circuit {circuit_id} not found")
                    
                    await self.apply_normalization_to_circuit(
                        circuit=circuit,
                        baseline=baseline,
                        force_normalization=force_normalization
                    )
                    
                    results['success_count'] += 1
                    
                except Exception as e:
                    results['error_count'] += 1
                    results['errors'].append(
                        f"Circuit {circuit_id}: {str(e)}"
                    )
            
            # Commit batch
            await self.db.commit()
        
        return results
    
    def calculate_normalization_score(
        self,
        normalized: NormalizedCircuitMetrics,
        baseline: MainLiftBaseline
    ) -> Dict[str, Any]:
        """Calculate quality score for normalized metrics.
        
        Args:
            normalized: NormalizedCircuitMetrics object
            baseline: MainLiftBaseline used for normalization
            
        Returns:
            Dictionary with quality metrics:
                - fatigue_ratio: Normalized fatigue / baseline fatigue
                - stimulus_ratio: Normalized stimulus / baseline stimulus
                - within_range: Whether both ratios are within 40-60% range
                - deviation_from_target: Deviation from 50% target
                - score: Overall quality score (0-100)
        """
        fatigue_ratio = normalized.fatigue_factor / baseline.avg_fatigue_factor
        stimulus_ratio = normalized.stimulus_factor / baseline.avg_stimulus_factor
        
        within_range = (
            self.NORMALIZATION_TARGET_MIN <= fatigue_ratio <= self.NORMALIZATION_TARGET_MAX and
            self.NORMALIZATION_TARGET_MIN <= stimulus_ratio <= self.NORMALIZATION_TARGET_MAX
        )
        
        deviation_fatigue = abs(fatigue_ratio - self.NORMALIZATION_TARGET_CENTER)
        deviation_stimulus = abs(stimulus_ratio - self.NORMALIZATION_TARGET_CENTER)
        deviation_from_target = (deviation_fatigue + deviation_stimulus) / 2
        
        # Calculate score (100 = perfect, 0 = far from target)
        max_deviation = 0.5  # Maximum acceptable deviation
        score = max(0, 100 * (1 - (deviation_from_target / max_deviation)))
        
        return {
            'fatigue_ratio': fatigue_ratio,
            'stimulus_ratio': stimulus_ratio,
            'within_range': within_range,
            'deviation_from_target': deviation_from_target,
            'score': score
        }


# Convenience function for single-use normalization
async def normalize_single_circuit(
    db: AsyncSession,
    circuit_id: int,
    baseline: Optional[MainLiftBaseline] = None,
    force_normalization: bool = True
) -> NormalizedCircuitMetrics:
    """Convenience function to normalize a single circuit by ID.
    
    Args:
        db: Async SQLAlchemy session
        circuit_id: ID of circuit to normalize
        baseline: MainLiftBaseline for normalization (calculated if None)
        force_normalization: Whether to force values into 40-60% range
        
    Returns:
        NormalizedCircuitMetrics object
        
    Raises:
        ValueError: If circuit not found or normalization fails
        
    Example:
        >>> normalized = await normalize_single_circuit(db, circuit_id=42)
        >>> print(f"Fatigue: {normalized.fatigue_factor:.2f}")
        >>> print(f"Stimulus: {normalized.stimulus_factor:.2f}")
    """
    normalizer = CircuitMetricsNormalizer(db)
    
    circuit = await db.get(CircuitTemplate, circuit_id)
    if not circuit:
        raise ValueError(f"Circuit with ID {circuit_id} not found")
    
    normalized = await normalizer.apply_normalization_to_circuit(
        circuit=circuit,
        baseline=baseline,
        force_normalization=force_normalization
    )
    
    await db.commit()
    
    return normalized
