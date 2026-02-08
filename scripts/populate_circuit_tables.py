"""
Populate circuits_melted and circuits_macro tables from circuit_templates.

This script:
1. Populates circuits_melted table from exercises_json
2. Calculates and populates circuits_macro table with 50% normalized metrics
3. Extracts pattern and region information for circuit comparability
4. Validates data integrity

Usage:
    python scripts/populate_circuit_tables.py --dry-run  # Preview changes
    python scripts/populate_circuit_tables.py --verbose  # Detailed logging
    python scripts/populate_circuit_tables.py            # Execute population
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db
from app.models import Movement, MovementMuscleMap
from app.models.circuit import CircuitTemplate
from app.models.circuit_extended import CircuitMelted, CircuitMacro
from app.models.enums import CircuitType, MetricType, MovementTier, PrimaryRegion, MuscleRole, MovementPattern
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer, MainLiftBaseline


class CircuitTablePopulator:
    """Service for populating circuit tables with normalized metrics."""
    
    def __init__(self, db: AsyncSession, verbose: bool = False, dry_run: bool = False):
        """Initialize populator with database session.
        
        Args:
            db: Async SQLAlchemy session
            verbose: Enable detailed logging
            dry_run: Preview changes without executing
        """
        self.db = db
        self.verbose = verbose
        self.dry_run = dry_run
        self.normalizer = CircuitMetricsNormalizer(db)
        self.stats = {
            'circuits_processed': 0,
            'melted_created': 0,
            'macro_created': 0,
            'errors': 0
        }
    
    def log(self, message: str, force: bool = False):
        """Log message if verbose or forced."""
        if self.verbose or force:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
    
    async def populate_circuits_melted(self) -> int:
        """Populate circuits_melted table from circuit_templates.exercises_json.
        
        Returns:
            Number of melted records created
        """
        self.log("Starting circuits_melted population...")
        
        # Get all circuits with exercises_json
        stmt = select(CircuitTemplate).where(
            CircuitTemplate.exercises_json.isnot(None)
        )
        result = await self.db.execute(stmt)
        circuits = result.scalars().all()
        
        self.log(f"Found {len(circuits)} circuits with exercises_json")
        
        created_count = 0
        
        for circuit in circuits:
            if not circuit.exercises_json:
                self.log(f"Skipping circuit {circuit.id}: empty exercises_json", force=True)
                continue
            
            try:
                # Check if already populated
                check_stmt = select(func.count(CircuitMelted.id)).where(
                    CircuitMelted.circuit_id == circuit.id
                )
                result = await self.db.execute(check_stmt)
                count = result.scalar()
                
                if count > 0:
                    self.log(f"Skipping circuit {circuit.id}: already populated ({count} exercises)")
                    continue
                
                # Create melted records for each exercise
                exercise_sequence = 0
                for exercise in circuit.exercises_json:
                    # Skip exercises without any metric values
                    has_metric = any([
                        exercise.get('reps'),
                        exercise.get('distance_meters'),
                        exercise.get('duration_seconds'),
                        exercise.get('calories')
                    ])
                    
                    if not has_metric:
                        self.log(f"Skipping exercise in circuit {circuit.id}: no metric values")
                        continue
                    
                    # Validate movement_id exists before using it
                    movement_id = exercise.get('movement_id')
                    movement_name = exercise.get('movement_name')
                    
                    if movement_id:
                        try:
                            stmt = select(Movement).where(Movement.id == movement_id)
                            result = await self.db.execute(stmt)
                            movement = result.scalar_one_or_none()
                            if movement:
                                movement_name = movement.name
                            else:
                                self.log(f"Exercise in circuit {circuit.id} has invalid movement_id {movement_id}, setting to None")
                                movement_id = None
                        except Exception as e:
                            self.log(f"Error validating movement_id {movement_id}: {e}")
                            movement_id = None
                    
                    if not movement_name:
                        self.log(f"Skipping exercise in circuit {circuit.id}: no movement name")
                        continue
                    
                    exercise_sequence += 1
                    
                    melted = CircuitMelted(
                        circuit_id=circuit.id,
                        movement_id=movement_id,
                        exercise_sequence=exercise_sequence,
                        movement_name=movement_name,
                        metric_type=self._parse_metric_type(exercise.get('metric_type')),
                        reps=exercise.get('reps'),
                        distance_meters=exercise.get('distance_meters'),
                        duration_seconds=exercise.get('duration_seconds'),
                        calories=exercise.get('calories'),
                        rest_seconds=exercise.get('rest_seconds'),
                        notes=exercise.get('notes'),
                        rx_weight_male=exercise.get('rx_weight_male'),
                        rx_weight_female=exercise.get('rx_weight_female'),
                        created_at=datetime.utcnow().timestamp()
                    )
                    
                    if not self.dry_run:
                        self.db.add(melted)
                    
                    created_count += 1
                
                self.log(f"Created {len(circuit.exercises_json)} melted records for circuit {circuit.id}")
                self.stats['melted_created'] += len(circuit.exercises_json)
                self.stats['circuits_processed'] += 1
                
            except Exception as e:
                self.log(f"Error processing circuit {circuit.id}: {e}", force=True)
                self.stats['errors'] += 1
                continue
        
        if not self.dry_run:
            await self.db.commit()
        
        return created_count
    
    async def populate_circuits_macro(self) -> int:
        """Populate circuits_macro table with normalized aggregated metrics.
        
        Returns:
            Number of macro records created
        """
        self.log("Starting circuits_macro population with normalization...")
        
        # Calculate main lift baseline for normalization
        try:
            baseline = await self.normalizer.calculate_main_lift_baseline(limit=500)
            self.log(f"Main lift baseline calculated from {baseline.sample_size} lifts", force=True)
            self.log(f"  Avg fatigue: {baseline.avg_fatigue_factor:.3f}", force=True)
            self.log(f"  Avg stimulus: {baseline.avg_stimulus_factor:.3f}", force=True)
            self.log(f"  Avg work volume: {baseline.avg_work_volume:.2f}", force=True)
        except Exception as e:
            self.log(f"Error calculating baseline: {e}", force=True)
            self.log("Using default baseline values", force=True)
            baseline = None
        
        # Get all circuits
        stmt = select(CircuitTemplate)
        result = await self.db.execute(stmt)
        circuits = result.scalars().all()
        
        self.log(f"Processing {len(circuits)} circuits for macro metrics")
        
        created_count = 0
        
        for circuit in circuits:
            try:
                # Check if already populated (outside transaction)
                check_stmt = select(CircuitMacro).where(
                    CircuitMacro.circuit_id == circuit.id
                )
                result = await self.db.execute(check_stmt)
                existing = result.scalar_one_or_none()
                
                if existing:
                    self.log(f"Skipping circuit {circuit.id}: macro already exists")
                    continue
                
                # Get melted exercises for aggregation
                melted_stmt = select(CircuitMelted).where(
                    CircuitMelted.circuit_id == circuit.id
                ).order_by(CircuitMelted.exercise_sequence)
                result = await self.db.execute(melted_stmt)
                melted_exercises = result.scalars().all()
                
                if not melted_exercises:
                    self.log(f"Skipping circuit {circuit.id}: no melted exercises found")
                    continue
                
                # Apply 50% normalization
                normalized = await self.normalizer.apply_normalization_to_circuit(
                    circuit=circuit,
                    baseline=baseline,
                    force_normalization=True
                )
                
                # Extract pattern and region information
                pattern_info = await self._extract_pattern_info(melted_exercises)
                region_info = await self._extract_region_info(melted_exercises)
                muscle_info = await self._extract_muscle_info(melted_exercises)
                equipment_info = await self._extract_equipment_info(melted_exercises)
                
                # Convert integer difficulty_tier to MovementTier enum
                tier_map = {1: MovementTier.BRONZE, 2: MovementTier.SILVER, 3: MovementTier.GOLD, 4: MovementTier.DIAMOND}
                difficulty_tier = tier_map.get(circuit.difficulty_tier, MovementTier.BRONZE)
                
                # Create macro record
                macro = CircuitMacro(
                    circuit_id=circuit.id,
                    total_exercises=len(melted_exercises),
                    unique_movements=len(set(ex.movement_id for ex in melted_exercises if ex.movement_id)),
                    total_reps=sum(ex.reps or 0 for ex in melted_exercises),
                    total_distance_meters=sum(ex.distance_meters or 0 for ex in melted_exercises),
                    total_work_seconds=sum(ex.duration_seconds or 0 for ex in melted_exercises),
                    total_rest_seconds=sum(ex.rest_seconds or 0 for ex in melted_exercises),
                    estimated_duration_seconds=circuit.estimated_work_seconds or 0,
                    difficulty_tier=difficulty_tier,
                    min_recovery_hours=circuit.min_recovery_hours or 24,
                    max_rx_weight_male=max((ex.rx_weight_male or 0) for ex in melted_exercises) if any(ex.rx_weight_male for ex in melted_exercises) else None,
                    max_rx_weight_female=max((ex.rx_weight_female or 0) for ex in melted_exercises) if any(ex.rx_weight_female for ex in melted_exercises) else None,
                    primary_muscles=muscle_info['primary_muscles'],
                    muscle_engagement_score=muscle_info['engagement_score'],
                    required_equipment=equipment_info['equipment_ids'],
                    equipment_complexity=equipment_info['complexity'],
                    movement_pattern_counts=pattern_info['pattern_counts'],
                    pattern_diversity_score=pattern_info['diversity_score'],
                    primary_region=region_info['dominant_region'],
                    region_diversity_score=region_info.get('diversity_score', 0.0),
                    metabolic_profile=self._calculate_metabolic_profile(circuit, pattern_info),
                    estimated_calories_per_hour=self._estimate_calories_per_hour(circuit),
                    space_requirement_meters=self._estimate_space_requirement(melted_exercises),
                    station_count=1,  # Default to 1 station
                    default_rounds=circuit.default_rounds,
                    circuit_type_intensity=self._get_circuit_type_intensity(circuit.circuit_type),
                    data_completeness_score=self._calculate_data_completeness(circuit, melted_exercises),
                    validation_errors=[],
                    created_at=datetime.utcnow().timestamp(),
                    updated_at=datetime.utcnow().timestamp()
                )
                
                if not self.dry_run:
                    self.db.add(macro)
                
                self.log(
                    f"Created macro for circuit {circuit.id}: "
                    f"fatigue={normalized.fatigue_factor:.3f}, "
                    f"stimulus={normalized.stimulus_factor:.3f}, "
                    f"primary_pattern={pattern_info['dominant_pattern']}"
                )
                
                created_count += 1
                self.stats['macro_created'] += 1
                
            except Exception as e:
                self.log(f"Error creating macro for circuit {circuit.id}: {e}", force=True)
                self.stats['errors'] += 1
                continue
        
        if not self.dry_run:
            await self.db.commit()
        
        return created_count
    
    async def _extract_pattern_info(self, melted_exercises: List[CircuitMelted]) -> Dict:
        """Extract movement pattern information from melted exercises.
        
        Args:
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Dict with pattern counts, dominant pattern, and diversity score
        """
        pattern_counts: Dict[str, int] = {}
        
        for ex in melted_exercises:
            if not ex.movement_id:
                continue
            
            # Get movement to access pattern field
            stmt = select(Movement).where(Movement.id == ex.movement_id)
            result = await self.db.execute(stmt)
            movement = result.scalar_one_or_none()
            
            if movement and movement.pattern:
                pattern = movement.pattern.value if hasattr(movement.pattern, 'value') else movement.pattern
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        # Calculate dominant pattern
        dominant_pattern = max(pattern_counts, key=pattern_counts.get) if pattern_counts else "squat"
        
        # Calculate Simpson's diversity index
        total = sum(pattern_counts.values())
        if total == 0:
            diversity_score = 0.0
        else:
            # Simpson's diversity: 1 - sum(p_i^2) where p_i is proportion
            proportions = [count / total for count in pattern_counts.values()]
            diversity_score = 1.0 - sum(p * p for p in proportions)
        
        return {
            'pattern_counts': pattern_counts,
            'dominant_pattern': dominant_pattern,
            'diversity_score': diversity_score
        }
    
    async def _extract_region_info(self, melted_exercises: List[CircuitMelted]) -> Dict:
        """Extract body region information from melted exercises.
        
        Args:
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Dict with region counts and dominant region
        """
        region_counts: Dict[str, int] = {}
        
        for ex in melted_exercises:
            if not ex.movement_id:
                continue
            
            # Get movement to access region field
            stmt = select(Movement).where(Movement.id == ex.movement_id)
            result = await self.db.execute(stmt)
            movement = result.scalar_one_or_none()
            
            if movement and movement.primary_region:
                region = movement.primary_region.value if hasattr(movement.primary_region, 'value') else movement.primary_region
                region_counts[region] = region_counts.get(region, 0) + 1
        
        # Determine dominant region
        if region_counts:
            dominant_region = max(region_counts, key=region_counts.get)
        else:
            dominant_region = "full body"
        
        # Calculate Simpson's diversity index for regions
        total = sum(region_counts.values())
        if total == 0:
            diversity_score = 0.0
        else:
            proportions = [count / total for count in region_counts.values()]
            diversity_score = 1.0 - sum(p * p for p in proportions)
        
        return {
            'region_counts': region_counts,
            'dominant_region': dominant_region,
            'diversity_score': diversity_score
        }
    
    async def _extract_muscle_info(self, melted_exercises: List[CircuitMelted]) -> Dict:
        """Extract muscle engagement information from melted exercises.
        
        Args:
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Dict with primary muscles list and engagement score
        """
        primary_muscles: Set[str] = set()
        muscle_scores: Dict[str, float] = {}
        
        for ex in melted_exercises:
            if not ex.movement_id:
                continue
            
            # Get movement's primary muscle
            stmt = select(Movement).where(Movement.id == ex.movement_id)
            result = await self.db.execute(stmt)
            movement = result.scalar_one_or_none()
            
            if movement:
                primary_muscles.add(movement.primary_muscle)
                
                # Score based on fatigue_factor
                muscle_scores[movement.primary_muscle] = max(
                    muscle_scores.get(movement.primary_muscle, 0),
                    movement.fatigue_factor or 0
                )
        
        # Calculate engagement score (normalized 0-1)
        if muscle_scores:
            max_score = max(muscle_scores.values())
            engagement_score = sum(muscle_scores.values()) / max_score if max_score > 0 else 0
        else:
            engagement_score = 0.0
        
        return {
            'primary_muscles': list(primary_muscles),
            'engagement_score': min(engagement_score, 1.0)
        }
    
    async def _extract_equipment_info(self, melted_exercises: List[CircuitMelted]) -> Dict:
        """Extract equipment requirements from melted exercises.
        
        Args:
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Dict with equipment IDs list and complexity score
        """
        from app.models.movement import MovementEquipment
        
        equipment_ids: Set[int] = set()
        
        for ex in melted_exercises:
            if not ex.movement_id:
                continue
            
            # Get movement's equipment using the MovementEquipment junction table
            stmt = (
                select(MovementEquipment.equipment_id)
                .where(MovementEquipment.movement_id == ex.movement_id)
            )
            result = await self.db.execute(stmt)
            equipment_ids.update(row[0] for row in result if row[0] is not None)
        
        return {
            'equipment_ids': sorted(equipment_ids),
            'complexity': len(equipment_ids)
        }
    
    def _calculate_metabolic_profile(self, circuit: CircuitTemplate, pattern_info: Dict) -> Dict:
        """Calculate metabolic profile based on circuit type and patterns.
        
        Args:
            circuit: CircuitTemplate object
            pattern_info: Pattern information from _extract_pattern_info
            
        Returns:
            Dict with metabolic breakdown (anabolic, metabolic, neural)
        """
        # Default profile
        profile = {
            'anabolic': 0.33,
            'metabolic': 0.67,
            'neural': 0.0
        }
        
        # Adjust based on circuit type
        if circuit.circuit_type == CircuitType.ROUNDS_FOR_TIME:
            profile['metabolic'] = 0.8
            profile['anabolic'] = 0.2
        elif circuit.circuit_type == CircuitType.AMRAP:
            profile['metabolic'] = 0.75
            profile['anabolic'] = 0.25
        elif circuit.circuit_type == CircuitType.EMOM:
            profile['metabolic'] = 0.6
            profile['anabolic'] = 0.4
        elif circuit.circuit_type == CircuitType.LADDER:
            profile['neural'] = 0.1
            profile['metabolic'] = 0.6
            profile['anabolic'] = 0.3
        
        # Adjust based on dominant pattern
        dominant_pattern = pattern_info.get('dominant_pattern', '')
        if dominant_pattern in ['squat', 'hinge', 'lunge']:
            profile['anabolic'] += 0.1
            profile['metabolic'] -= 0.1
        elif dominant_pattern in ['horizontal_push', 'vertical_push']:
            profile['anabolic'] += 0.05
        
        # Normalize to sum to 1.0
        total = sum(profile.values())
        if total > 0:
            profile = {k: v / total for k, v in profile.items()}
        
        return profile
    
    def _estimate_calories_per_hour(self, circuit: CircuitTemplate) -> int:
        """Estimate calories burned per hour for circuit.
        
        Args:
            circuit: CircuitTemplate object
            
        Returns:
            Estimated calories per hour
        """
        # Base estimate based on circuit type and intensity
        base_cals = 400  # Moderate intensity
        
        if circuit.fatigue_factor:
            multiplier = circuit.fatigue_factor / 1.0
        else:
            multiplier = 1.0
        
        return int(base_cals * multiplier)
    
    def _estimate_space_requirement(self, melted_exercises: List[CircuitMelted]) -> float:
        """Estimate space requirement for circuit.
        
        Args:
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Estimated space in square meters
        """
        # Default to 2x2 meter area (4 sqm) for typical circuit
        return 4.0
    
    def _get_circuit_type_intensity(self, circuit_type: CircuitType) -> float:
        """Get intensity multiplier for circuit type.
        
        Args:
            circuit_type: CircuitType enum value
            
        Returns:
            Intensity multiplier (0.8-1.2 range)
        """
        intensity_map = {
            CircuitType.ROUNDS_FOR_TIME: 1.1,  # Time pressure
            CircuitType.AMRAP: 1.15,            # Continuous work
            CircuitType.LADDER: 1.05,           # Progressive
            CircuitType.EMOM: 0.95,             # Structured
            CircuitType.TABATA: 1.2,             # High intensity
            CircuitType.CHIPPER: 0.9,            # Endurance
            CircuitType.STATION: 0.85,           # Structured
        }
        return intensity_map.get(circuit_type, 1.0)
    
    def _calculate_data_completeness(self, circuit: CircuitTemplate, melted_exercises: List[CircuitMelted]) -> float:
        """Calculate data completeness score (0-1).
        
        Args:
            circuit: CircuitTemplate object
            melted_exercises: List of CircuitMelted objects
            
        Returns:
            Completeness score (0-1)
        """
        required_fields = [
            'fatigue_factor',
            'stimulus_factor',
            'difficulty_tier',
            'min_recovery_hours'
        ]
        
        score = 0.0
        for field in required_fields:
            value = getattr(circuit, field, None)
            if value is not None:
                score += 0.25
        
        # Check melted exercises
        if melted_exercises:
            score += 0.25
        else:
            score += 0.0
        
        return min(score, 1.0)
    
    def _parse_metric_type(self, metric_type_str: Optional[str]) -> MetricType:
        """Parse metric type string to enum.
        
        Args:
            metric_type_str: String representation of metric type
            
        Returns:
            MetricType enum value
        """
        if not metric_type_str:
            return MetricType.REPS
        
        metric_map = {
            'reps': MetricType.REPS,
            'time': MetricType.TIME,
            'distance': MetricType.DISTANCE,
            'calories': MetricType.CALORIES,
            'time_under_tension': MetricType.TIME_UNDER_TENSION
        }
        
        return metric_map.get(metric_type_str.lower(), MetricType.REPS)
    
    async def run(self) -> Dict:
        """Run complete population process.
        
        Returns:
            Dict with statistics
        """
        self.log("=" * 60, force=True)
        self.log("Starting circuit table population", force=True)
        self.log(f"Dry run: {self.dry_run}", force=True)
        self.log(f"Verbose: {self.verbose}", force=True)
        self.log("=" * 60, force=True)
        
        try:
            # Populate circuits_melted
            melted_count = await self.populate_circuits_melted()
            self.log(f"Created {melted_count} melted records", force=True)
            
            # Populate circuits_macro
            macro_count = await self.populate_circuits_macro()
            self.log(f"Created {macro_count} macro records", force=True)
            
            # Print summary
            self.log("=" * 60, force=True)
            self.log("Population complete!", force=True)
            self.log(f"  Circuits processed: {self.stats['circuits_processed']}", force=True)
            self.log(f"  Melted records created: {self.stats['melted_created']}", force=True)
            self.log(f"  Macro records created: {self.stats['macro_created']}", force=True)
            self.log(f"  Errors: {self.stats['errors']}", force=True)
            self.log("=" * 60, force=True)
            
            return self.stats
            
        except Exception as e:
            self.log(f"Fatal error during population: {e}", force=True)
            await self.db.rollback()
            raise


async def main():
    """Main entry point for population script."""
    parser = argparse.ArgumentParser(description='Populate circuit tables with normalized metrics')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without executing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable detailed logging')
    
    args = parser.parse_args()
    
    async for db in get_db():
        populator = CircuitTablePopulator(
            db=db,
            verbose=args.verbose,
            dry_run=args.dry_run
        )
        
        stats = await populator.run()
        
        if stats['errors'] > 0:
            print(f"\nWarning: {stats['errors']} errors occurred during population")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
