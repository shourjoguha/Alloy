"""Example usage of Circuit Metrics Normalization Service.

This script demonstrates how to use the circuit metrics normalization
service to calculate baselines and normalize circuit metrics.
"""

import asyncio
import sys
sys.path.insert(0, '.')

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import get_settings
from app.models.circuit import CircuitTemplate
from app.services.circuit_metrics_normalization import (
    CircuitMetricsNormalizer,
    MainLiftBaseline,
    NormalizedCircuitMetrics,
    normalize_single_circuit
)


async def example_1_calculate_baseline():
    """Example 1: Calculate main lift baseline from database.
    
    This demonstrates how to query all main lift movements and calculate
    average fatigue_factor, stimulus_factor, and work_volume.
    """
    print("=" * 60)
    print("Example 1: Calculate Main Lift Baseline")
    print("=" * 60)
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        normalizer = CircuitMetricsNormalizer(db)
        
        try:
            baseline = await normalizer.calculate_main_lift_baseline(limit=500)
            
            print(f"\nMain Lift Baseline (n={baseline.sample_size}):")
            print(f"  Avg Fatigue Factor:    {baseline.avg_fatigue_factor:.4f}")
            print(f"  Avg Stimulus Factor:   {baseline.avg_stimulus_factor:.4f}")
            print(f"  Avg Work Volume:       {baseline.avg_work_volume:.4f}")
            
            return baseline
            
        except ValueError as e:
            print(f"\nError calculating baseline: {e}")
            return None


async def example_2_normalize_single_circuit(baseline: MainLiftBaseline):
    """Example 2: Normalize a single circuit with given baseline.
    
    This demonstrates how to normalize circuit metrics to 40-60% of
    the main lift baseline, applying circuit-specific modifiers.
    """
    print("\n" + "=" * 60)
    print("Example 2: Normalize Single Circuit")
    print("=" * 60)
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        normalizer = CircuitMetricsNormalizer(db)
        
        # Get first circuit from database
        stmt = select(CircuitTemplate).limit(1)
        result = await db.execute(stmt)
        circuit = result.scalar_one_or_none()
        
        if not circuit:
            print("\nNo circuits found in database")
            return None
        
        print(f"\nCircuit: {circuit.name}")
        print(f"Type: {circuit.circuit_type.value}")
        print(f"Original Fatigue Factor:    {circuit.fatigue_factor:.4f}")
        print(f"Original Stimulus Factor:   {circuit.stimulus_factor:.4f}")
        print(f"Original Work Volume:       {circuit.effective_work_volume or 0:.4f}")
        
        # Normalize with force_normalization=False to see original result
        print("\n--- Normalization (Force=False) ---")
        normalized = await normalizer.normalize_circuit_metrics(
            circuit=circuit,
            baseline=baseline,
            force_normalization=False
        )
        
        print(f"Normalized Fatigue Factor:    {normalized.fatigue_factor:.4f}")
        print(f"Normalized Stimulus Factor:   {normalized.stimulus_factor:.4f}")
        print(f"Normalized Work Volume:       {normalized.effective_work_volume:.4f}")
        print(f"Validation Passed: {normalized.validation_passed}")
        print(f"Modifiers Applied: {', '.join(normalized.modifiers_applied)}")
        
        # Calculate quality score
        score = normalizer.calculate_normalization_score(normalized, baseline)
        print(f"\nQuality Score: {score['score']:.1f}/100")
        print(f"Fatigue Ratio: {score['fatigue_ratio']:.2%}")
        print(f"Stimulus Ratio: {score['stimulus_ratio']:.2%}")
        print(f"Within 40-60% Range: {score['within_range']}")
        
        # Normalize with force_normalization=True to clamp values
        print("\n--- Normalization (Force=True) ---")
        normalized_clamped = await normalizer.normalize_circuit_metrics(
            circuit=circuit,
            baseline=baseline,
            force_normalization=True
        )
        
        print(f"Clamped Fatigue Factor:    {normalized_clamped.fatigue_factor:.4f}")
        print(f"Clamped Stimulus Factor:   {normalized_clamped.stimulus_factor:.4f}")
        print(f"Clamped Work Volume:       {normalized_clamped.effective_work_volume:.4f}")
        print(f"Validation Passed: {normalized_clamped.validation_passed}")
        print(f"Modifiers Applied: {', '.join(normalized_clamped.modifiers_applied)}")
        
        return normalized


async def example_3_batch_normalize_circuits(baseline: MainLiftBaseline):
    """Example 3: Normalize multiple circuits in batches.
    
    This demonstrates batch processing for normalizing multiple circuits
    efficiently with commits per batch.
    """
    print("\n" + "=" * 60)
    print("Example 3: Batch Normalize Circuits")
    print("=" * 60)
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        normalizer = CircuitMetricsNormalizer(db)
        
        # Get first 10 circuit IDs
        stmt = select(CircuitTemplate.id).limit(10)
        result = await db.execute(stmt)
        circuit_ids = result.scalars().all()
        
        if not circuit_ids:
            print("\nNo circuits found in database")
            return
        
        print(f"\nNormalizing {len(circuit_ids)} circuits...")
        
        # Batch normalize
        results = await normalizer.batch_normalize_circuits(
            circuit_ids=circuit_ids,
            baseline=baseline,
            force_normalization=True,
            commit_batch_size=5
        )
        
        print(f"\nBatch Results:")
        print(f"  Total Processed: {results['total_processed']}")
        print(f"  Success: {results['success_count']}")
        print(f"  Errors: {results['error_count']}")
        
        if results['errors']:
            print(f"\nErrors:")
            for error in results['errors'][:5]:  # Show first 5 errors
                print(f"  - {error}")


async def example_4_circuit_type_modifiers():
    """Example 4: Demonstrate circuit type modifiers.
    
    This shows how different circuit types receive different modifiers.
    """
    print("\n" + "=" * 60)
    print("Example 4: Circuit Type Modifiers")
    print("=" * 60)
    
    from app.models.enums import CircuitType
    
    modifiers = CircuitMetricsNormalizer.CIRCUIT_TYPE_MODIFIERS
    
    print("\nCircuit Type Modifiers (higher = closer to baseline):")
    for circuit_type, modifier in sorted(modifiers.items(), key=lambda x: x[1], reverse=True):
        print(f"  {circuit_type.value:20s}: {modifier:.2f}")
    
    print("\nInterpretation:")
    print("  - STATION (0.95): Structured stations, closest to main lifts")
    print("  - EMOM (0.92): Structured intervals, moderate reduction")
    print("  - RFT (0.90): Time pressure, slight reduction")
    print("  - LADDER (0.88): Progressive intensity, moderate reduction")
    print("  - CHIPPER (0.87): Long format, endurance-focused")
    print("  - AMRAP (0.85): Continuous work, significant reduction")
    print("  - TABATA (0.82): High intensity intervals, largest reduction")


async def example_5_convenience_function():
    """Example 5: Use convenience function for single circuit.
    
    This demonstrates the simplified normalize_single_circuit function.
    """
    print("\n" + "=" * 60)
    print("Example 5: Convenience Function")
    print("=" * 60)
    
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get first circuit ID
        stmt = select(CircuitTemplate.id).limit(1)
        result = await db.execute(stmt)
        circuit_id = result.scalar_one_or_none()
        
        if not circuit_id:
            print("\nNo circuits found in database")
            return
        
        print(f"\nNormalizing circuit ID {circuit_id}...")
        
        # Use convenience function
        normalized = await normalize_single_circuit(
            db=db,
            circuit_id=circuit_id,
            force_normalization=True
        )
        
        print(f"\nResult:")
        print(f"  Fatigue Factor:  {normalized.fatigue_factor:.4f}")
        print(f"  Stimulus Factor: {normalized.stimulus_factor:.4f}")
        print(f"  Work Volume:     {normalized.effective_work_volume:.4f}")
        print(f"  Validation:      {normalized.validation_passed}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("CIRCUIT METRICS NORMALIZATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Calculate baseline
    baseline = await example_1_calculate_baseline()
    
    if not baseline:
        print("\nCannot proceed with remaining examples without baseline")
        return
    
    # Example 2: Normalize single circuit
    await example_2_normalize_single_circuit(baseline)
    
    # Example 3: Batch normalize
    await example_3_batch_normalize_circuits(baseline)
    
    # Example 4: Show modifiers
    await example_4_circuit_type_modifiers()
    
    # Example 5: Convenience function
    await example_5_convenience_function()
    
    print("\n" + "=" * 60)
    print("EXAMPLES COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
