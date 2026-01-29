# Circuit Metrics Normalization Service

## Overview

The Circuit Metrics Normalization Service implements a **50% normalization strategy** for circuit training metrics. This ensures that circuits are appropriately scaled relative to main lift baselines, enabling fair comparison and intelligent selection by the optimization engine.

## Problem Statement

Circuit training and main lifting produce fundamentally different fatigue and stimulus patterns:

- **Main Lifts**: Heavy compound movements (squats, deadlifts, bench press) with high fatigue and stimulus per rep
- **Circuits**: High-rep, time-based work with lower per-movement intensity but cumulative fatigue

Without normalization, circuits would be unfairly penalized or overvalued in the optimization engine.

## Solution: 50% Normalization

The normalization approach scales circuit metrics to represent approximately **50% of the stimulus and fatigue** of main lifts, with circuit-specific modifiers applied.

### Normalization Formula

```
Normalized Metric = Baseline Metric × 0.50 × Circuit_Type_Modifier × Volume_Factor × Rep_Efficiency_Factor
```

#### Components:

1. **Baseline Metric** (50%): Average across all main lifts
2. **Circuit Type Modifier**: Adjusts for circuit structure
3. **Volume Factor**: Scales based on circuit volume vs. average main lift volume
4. **Rep Efficiency Factor**: Reduces high-rep, low-weight circuits

## Circuit Type Modifiers

| Circuit Type | Modifier | Interpretation |
|-------------|----------|----------------|
| STATION | 0.95 | Structured stations, closest to baseline |
| EMOM | 0.92 | Structured intervals, moderate reduction |
| RFT (Rounds for Time) | 0.90 | Time pressure, slight reduction |
| LADDER | 0.88 | Progressive intensity, moderate reduction |
| CHIPPER | 0.87 | Long format, endurance-focused |
| AMRAP | 0.85 | Continuous work, significant reduction |
| TABATA | 0.82 | High intensity intervals, largest reduction |

## Target Range

Normalized metrics are validated to be within **40-60% of main lift baseline**:

- **Minimum**: 40% of baseline
- **Target**: 50% of baseline
- **Maximum**: 60% of baseline

## Installation

The service is located at:
```
app/services/circuit_metrics_normalization.py
```

## Usage Examples

### Example 1: Calculate Main Lift Baseline

```python
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer
from app.models import Session, SessionExercise
from app.models.enums import ExerciseRole

async def calculate_baseline(db):
    """Calculate baseline from all main lift movements."""
    normalizer = CircuitMetricsNormalizer(db)
    
    baseline = await normalizer.calculate_main_lift_baseline(limit=500)
    
    print(f"Baseline Fatigue: {baseline.avg_fatigue_factor:.4f}")
    print(f"Baseline Stimulus: {baseline.avg_stimulus_factor:.4f}")
    print(f"Baseline Volume: {baseline.avg_work_volume:.4f}")
    print(f"Sample Size: {baseline.sample_size}")
    
    return baseline
```

**Output:**
```
Baseline Fatigue: 1.5234
Baseline Stimulus: 1.1876
Baseline Volume: 123.45
Sample Size: 247
```

### Example 2: Normalize Single Circuit

```python
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer

async def normalize_circuit(db, circuit_id, baseline):
    """Normalize circuit metrics to 50% of baseline."""
    normalizer = CircuitMetricsNormalizer(db)
    
    circuit = await db.get(CircuitTemplate, circuit_id)
    
    normalized = await normalizer.normalize_circuit_metrics(
        circuit=circuit,
        baseline=baseline,
        force_normalization=False  # Don't clamp to range
    )
    
    print(f"Original Fatigue: {normalized.original_values['fatigue_factor']:.4f}")
    print(f"Normalized Fatigue: {normalized.fatigue_factor:.4f}")
    print(f"Validation Passed: {normalized.validation_passed}")
    print(f"Modifiers: {', '.join(normalized.modifiers_applied)}")
    
    return normalized
```

**Output:**
```
Original Fatigue: 2.5000
Normalized Fatigue: 0.6856
Validation Passed: True
Modifiers: circ_type_amrap_mod_0.85, vol_factor_0.75
```

### Example 3: Apply Normalization to Circuit (Update DB)

```python
async def apply_normalization(db, circuit_id, baseline):
    """Normalize and update circuit in database."""
    normalizer = CircuitMetricsNormalizer(db)
    
    circuit = await db.get(CircuitTemplate, circuit_id)
    
    normalized = await normalizer.apply_normalization_to_circuit(
        circuit=circuit,  # Updates in place
        baseline=baseline,
        force_normalization=True  # Clamp to 40-60% range
    )
    
    await db.commit()
    
    return normalized
```

### Example 4: Batch Normalize Circuits

```python
async def batch_normalize(db, circuit_ids):
    """Normalize multiple circuits in batches."""
    normalizer = CircuitMetricsNormalizer(db)
    
    results = await normalizer.batch_normalize_circuits(
        circuit_ids=circuit_ids,
        baseline=None,  # Auto-calculate
        force_normalization=True,
        commit_batch_size=100
    )
    
    print(f"Processed: {results['total_processed']}")
    print(f"Success: {results['success_count']}")
    print(f"Errors: {results['error_count']}")
    
    return results
```

**Output:**
```
Processed: 250
Success: 245
Errors: 5
```

### Example 5: Convenience Function

```python
from app.services.circuit_metrics_normalization import normalize_single_circuit

async def quick_normalize(db, circuit_id):
    """Quick normalization with auto-calculated baseline."""
    normalized = await normalize_single_circuit(
        db=db,
        circuit_id=circuit_id,
        force_normalization=True
    )
    
    return normalized
```

### Example 6: Calculate Quality Score

```python
async def evaluate_normalization(db, circuit_id, baseline):
    """Evaluate normalization quality score."""
    normalizer = CircuitMetricsNormalizer(db)
    
    circuit = await db.get(CircuitTemplate, circuit_id)
    normalized = await normalizer.normalize_circuit_metrics(
        circuit=circuit,
        baseline=baseline
    )
    
    score = normalizer.calculate_normalization_score(
        normalized=normalized,
        baseline=baseline
    )
    
    print(f"Quality Score: {score['score']:.1f}/100")
    print(f"Fatigue Ratio: {score['fatigue_ratio']:.2%}")
    print(f"Stimulus Ratio: {score['stimulus_ratio']:.2%}")
    print(f"Within Range: {score['within_range']}")
    
    return score
```

**Output:**
```
Quality Score: 92.5/100
Fatigue Ratio: 52.3%
Stimulus Ratio: 48.7%
Within Range: True
```

## Data Structures

### MainLiftBaseline

```python
@dataclass
class MainLiftBaseline:
    avg_fatigue_factor: float      # Average fatigue across main lifts
    avg_stimulus_factor: float     # Average stimulus across main lifts
    avg_work_volume: float          # Average work volume across main lifts
    sample_size: int                # Number of main lifts used
```

### NormalizedCircuitMetrics

```python
@dataclass
class NormalizedCircuitMetrics:
    fatigue_factor: float                    # Normalized fatigue value
    stimulus_factor: float                   # Normalized stimulus value
    effective_work_volume: float             # Normalized work volume
    normalization_applied: bool             # Whether normalization was applied
    original_values: Dict[str, float]       # Original unnormalized values
    modifiers_applied: List[str]            # List of modifiers used
    validation_passed: bool                 # Whether values pass 40-60% validation
```

## Main Lift Identification Criteria

A movement is considered a "main lift" if it meets **all** of the following criteria:

1. **Exercise Role**: `ExerciseRole.MAIN` in a session
2. **Compound Movement**: `movement.compound == True`
3. **High Fatigue OR Complex Lift**:
   - `movement.fatigue_factor > 0.6` **OR**
   - `movement.is_complex_lift == True`

## Error Handling

### Common Errors and Solutions

#### Error: "No main exercises found in database"
**Cause**: No SessionExercise records with `exercise_role == MAIN`
**Solution**: Ensure sessions have main exercises populated

#### Error: "Insufficient main lifts for baseline calculation"
**Cause**: Fewer than 10 main lifts meet criteria
**Solution**: 
- Increase the number of sessions
- Adjust `min_sample_size` parameter
- Use default baseline with `DEFAULT_BASELINE`

#### Error: "Circuit not found"
**Cause**: Invalid circuit ID
**Solution**: Verify circuit exists in database

#### Error: "Validation failed"
**Cause**: Normalized values outside 40-60% range
**Solution**: Use `force_normalization=True` to clamp values

## Advanced Configuration

### Custom Circuit Type Modifiers

```python
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer
from app.models.enums import CircuitType

# Create custom normalizer with modified values
normalizer = CircuitMetricsNormalizer(db)

# Override default modifier for a specific type
normalizer.CIRCUIT_TYPE_MODIFIERS[CircuitType.AMRAP] = 0.80  # More aggressive reduction
```

### Custom Normalization Range

```python
# Modify normalization target range
normalizer.NORMALIZATION_TARGET_MIN = 0.30  # 30% minimum
normalizer.NORMALIZATION_TARGET_MAX = 0.70  # 70% maximum
normalizer.NORMALIZATION_TARGET_CENTER = 0.50  # 50% target
```

### Custom High-Rep Threshold

```python
# Change threshold for rep efficiency factor
normalizer.HIGH_REP_THRESHOLD = 20  # 20+ reps = high rep
normalizer.REP_EFFICIENCY_FACTOR = 0.6  # 60% reduction for high-rep circuits
```

## Integration with Population Script

The normalization service integrates with the existing circuit metrics population script:

```python
from app.services.circuit_metrics_normalization import CircuitMetricsNormalizer

async def populate_with_normalization(db):
    """Populate circuit metrics with normalization applied."""
    normalizer = CircuitMetricsNormalizer(db)
    
    # Calculate baseline once
    baseline = await normalizer.calculate_main_lift_baseline()
    
    # Get all circuits
    stmt = select(CircuitTemplate)
    result = await db.execute(stmt)
    circuits = result.scalars().all()
    
    # Normalize each circuit
    for circuit in circuits:
        normalized = await normalizer.apply_normalization_to_circuit(
            circuit=circuit,
            baseline=baseline,
            force_normalization=True
        )
        
        # Additional logic...
    
    await db.commit()
```

## Testing

Run the example script to see the service in action:

```bash
python examples/circuit_normalization_example.py
```

## Performance Considerations

### Baseline Calculation

- **Time**: O(n) where n = number of SessionExercise records
- **Memory**: Loads all main lift movements into memory
- **Optimization**: Calculate baseline once and reuse for multiple circuits

### Batch Normalization

- **Commit Batching**: Use `commit_batch_size` to control memory usage
- **Recommended**: 100-500 circuits per batch
- **Transaction Safety**: Each batch is committed independently

### Caching

For production use, consider caching the baseline:

```python
import asyncio
from functools import lru_cache

@lru_cache(maxsize=1)
async def get_cached_baseline(db) -> MainLiftBaseline:
    """Cache baseline calculation."""
    normalizer = CircuitMetricsNormalizer(db)
    return await normalizer.calculate_main_lift_baseline()
```

## Validation

The normalization service includes built-in validation:

### Validation Checks

1. **Range Validation**: Values must be within 40-60% of baseline
2. **Non-Negative**: All metrics must be >= 0
3. **Finite Values**: No NaN or infinity values
4. **Reasonable Bounds**: Sanity checks for extreme values

### Quality Scoring

Calculate a quality score (0-100) for normalized metrics:

- **100**: Perfect normalization (exactly 50% of baseline)
- **80-99**: Good normalization (40-60% range)
- **60-79**: Acceptable (slightly outside range)
- **< 60**: Poor normalization (significant deviation)

## Troubleshooting

### Issue: Normalized values are too low

**Symptoms**: Circuits have very low fatigue/stimulus compared to baseline

**Possible Causes**:
1. Circuit type modifier too aggressive
2. Volume factor reducing values excessively
3. High-rep efficiency factor applied incorrectly

**Solutions**:
1. Check `CIRCUIT_TYPE_MODIFIERS` values
2. Review `effective_work_volume` calculation
3. Verify `HIGH_REP_THRESHOLD` and `REP_EFFICIENCY_FACTOR`

### Issue: Normalized values are too high

**Symptoms**: Circuits have fatigue/stimulus exceeding 60% of baseline

**Possible Causes**:
1. Circuit type modifier too lenient
2. Volume factor > 1.0 (circuit volume exceeds average)
3. `force_normalization=False` allowing out-of-range values

**Solutions**:
1. Use `force_normalization=True` to clamp values
2. Review circuit volume calculation
3. Adjust `NORMALIZATION_TARGET_MAX`

### Issue: High error rate in batch normalization

**Symptoms**: Many circuits failing normalization

**Possible Causes**:
1. Missing or invalid circuit data
2. Database connection issues
3. Circuits without exercises_json

**Solutions**:
1. Check error messages in `results['errors']`
2. Validate circuit data before normalization
3. Handle missing data gracefully

## API Reference

### CircuitMetricsNormalizer

Main class for circuit metrics normalization.

#### Methods

##### `calculate_main_lift_baseline(limit=None, min_sample_size=10)`

Calculate baseline metrics from main lift movements.

**Parameters:**
- `limit` (Optional[int]): Maximum sessions to query
- `min_sample_size` (int): Minimum main lifts required

**Returns:** `MainLiftBaseline`

**Raises:** `ValueError` if insufficient data

##### `normalize_circuit_metrics(circuit, baseline=None, force_normalization=True)`

Normalize circuit metrics to 40-60% of baseline.

**Parameters:**
- `circuit` (CircuitTemplate): Circuit to normalize
- `baseline` (Optional[MainLiftBaseline]): Baseline for normalization
- `force_normalization` (bool): Force values into target range

**Returns:** `NormalizedCircuitMetrics`

**Raises:** `ValueError` if invalid circuit data

##### `apply_normalization_to_circuit(circuit, baseline=None, force_normalization=True)`

Normalize and update circuit in place.

**Parameters:**
- `circuit` (CircuitTemplate): Circuit to normalize and update
- `baseline` (Optional[MainLiftBaseline]): Baseline for normalization
- `force_normalization` (bool): Force values into target range

**Returns:** `NormalizedCircuitMetrics`

##### `batch_normalize_circuits(circuit_ids, baseline=None, force_normalization=True, commit_batch_size=100)`

Normalize multiple circuits in batches.

**Parameters:**
- `circuit_ids` (List[int]): Circuit IDs to normalize
- `baseline` (Optional[MainLiftBaseline]): Baseline for normalization
- `force_normalization` (bool): Force values into target range
- `commit_batch_size` (int): Circuits per commit batch

**Returns:** `Dict[str, Any]` with results

##### `calculate_normalization_score(normalized, baseline)`

Calculate quality score for normalized metrics.

**Parameters:**
- `normalized` (NormalizedCircuitMetrics): Normalized metrics
- `baseline` (MainLiftBaseline): Baseline used for normalization

**Returns:** `Dict[str, Any]` with quality metrics

## Contributing

When extending the normalization service:

1. Maintain backward compatibility
2. Add type hints to all functions
3. Include docstrings with examples
4. Add tests for new functionality
5. Update this documentation

## License

This service is part of the Alloy training platform.
