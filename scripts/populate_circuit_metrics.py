"""One-time script to populate circuit metrics for all existing circuits.

This script calculates and updates normalized metrics (fatigue_factor, stimulus_factor,
min_recovery_hours, muscle_volume, muscle_fatigue, etc.) for all circuits
in the database.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.models.circuit import CircuitTemplate
from app.services.circuit_metrics import circuit_metrics_calculator


async def populate_all_circuit_metrics():
    """
    Calculate and update metrics for all circuits in the database.
    
    This is a one-time migration script that should be run after the
    database schema has been updated to include the new metric columns.
    """
    print("Starting circuit metrics population...")
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    total_processed = 0
    success_count = 0
    error_count = 0
    missing_rounds_count = 0
    
    async with async_session() as session:
        # Load all circuits
        stmt = select(CircuitTemplate)
        result = await session.execute(stmt)
        circuits = result.scalars().all()
        
        print(f"Found {len(circuits)} circuits to process")
        
        # Process in batches
        batch_size = 100
        for i in range(0, len(circuits), batch_size):
            batch = circuits[i:i + batch_size]
            
            for circuit in batch:
                total_processed += 1
                
                try:
                    # Check if circuit has exercises
                    if not circuit.exercises_json or len(circuit.exercises_json) == 0:
                        print(f"  WARNING: Circuit '{circuit.name}' (ID: {circuit.id}) has no exercises - skipping")
                        error_count += 1
                        continue
                    
                    # Check if circuit has default_rounds
                    if not circuit.default_rounds:
                        print(f"  WARNING: Circuit '{circuit.name}' (ID: {circuit.id}) missing default_rounds - setting to 1")
                        missing_rounds_count += 1
                        rounds = 1
                    else:
                        rounds = circuit.default_rounds
                    
                    # Calculate metrics
                    metrics = await circuit_metrics_calculator.calculate_circuit_metrics(
                        db=session,
                        circuit=circuit,
                        rounds=rounds,
                        duration_seconds=circuit.default_duration_seconds
                    )
                    
                    # Update circuit with calculated metrics
                    circuit.fatigue_factor = metrics["fatigue_factor"]
                    circuit.stimulus_factor = metrics["stimulus_factor"]
                    circuit.min_recovery_hours = metrics["min_recovery_hours"]
                    circuit.muscle_volume = metrics["muscle_volume"]
                    circuit.muscle_fatigue = metrics["muscle_fatigue"]
                    circuit.total_reps = metrics["total_reps"]
                    circuit.estimated_work_seconds = metrics["estimated_work_seconds"]
                    circuit.effective_work_volume = metrics["effective_work_volume"]
                    
                    success_count += 1
                    
                    if total_processed % 50 == 0:
                        print(f"  Processed {total_processed}/{len(circuits)} circuits...")
                
                except Exception as e:
                    print(f"  ERROR: Circuit '{circuit.name}' (ID: {circuit.id}): {str(e)}")
                    error_count += 1
                    continue
            
            # Commit batch
            await session.commit()
            print(f"  Committed batch {i // batch_size + 1}")
    
    # Summary
    print("\n" + "=" * 50)
    print("Circuit Metrics Population Complete")
    print("=" * 50)
    print(f"Total circuits processed: {total_processed}")
    print(f"Successfully updated: {success_count}")
    print(f"Errors encountered: {error_count}")
    print(f"Missing default_rounds: {missing_rounds_count}")
    
    if missing_rounds_count > 0:
        print("\nNOTE: Some circuits are missing default_rounds.")
        print("Please manually review and update these circuits with appropriate round counts.")
        print("Circuits missing rounds were set to 1 for calculation purposes.")
    
    if error_count > 0:
        print("\nWARNING: Some circuits encountered errors during calculation.")
        print("Please review the error messages above and fix any data issues.")


if __name__ == "__main__":
    asyncio.run(populate_all_circuit_metrics())
