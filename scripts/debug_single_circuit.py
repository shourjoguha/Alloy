"""Debug a single circuit to find the error."""

import asyncio
import sys
from pathlib import Path
import traceback
from sqlalchemy import select

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import get_db
from app.models.circuit import CircuitTemplate, CircuitMacro, CircuitMelted
from app.models import Movement
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer


async def main():
    """Debug a specific circuit."""
    circuit_id = 134
    
    async for db in get_db():
        try:
            # Get the circuit
            stmt = select(CircuitTemplate).where(CircuitTemplate.id == circuit_id)
            result = await db.execute(stmt)
            circuit = result.scalar_one_or_none()
            
            if not circuit:
                print(f"Circuit {circuit_id} not found")
                return
            
            print(f"Debugging circuit {circuit_id}: {circuit.name}")
            print(f"  Circuit type: {circuit.circuit_type}")
            print(f"  Fatigue factor: {circuit.fatigue_factor}")
            print(f"  Stimulus factor: {circuit.stimulus_factor}")
            print(f"  Work volume: {circuit.effective_work_volume}")
            print()
            
            # Get melted exercises
            stmt = select(CircuitMelted).where(CircuitMelted.circuit_id == circuit_id)
            result = await db.execute(stmt)
            melted_exercises = result.scalars().all()
            
            print(f"Melted exercises: {len(melted_exercises)}")
            for ex in melted_exercises:
                print(f"  - {ex.movement_id or 'None'}: reps={ex.reps}, distance={ex.distance_meters}, duration={ex.duration_seconds}")
                if ex.movement_id:
                    stmt = select(Movement).where(Movement.id == ex.movement_id)
                    result = await db.execute(stmt)
                    movement = result.scalar_one_or_none()
                    if movement:
                        print(f"    Movement: {movement.name}")
                        print(f"    Fatigue: {movement.fatigue_factor}, Stimulus: {movement.stimulus_factor}")
            print()
            
            # Try to normalize
            try:
                normalizer = CircuitMetricsNormalizer(db)
                baseline = await normalizer.calculate_main_lift_baseline()
                print(f"Baseline calculated: {baseline.avg_fatigue_factor:.2f}, {baseline.avg_stimulus_factor:.2f}")
                print()
                
                normalized = await normalizer.normalize_circuit_metrics(circuit, baseline)
                print(f"Normalization succeeded!")
                print(f"  Fatigue: {normalized.fatigue_factor:.3f}")
                print(f"  Stimulus: {normalized.stimulus_factor:.3f}")
                
            except Exception as e:
                print(f"Normalization failed: {e}")
                traceback.print_exc()
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
