# Circuit Comparison and Recommendation System

## Overview

The Circuit Comparison and Recommendation System provides intelligent circuit analysis, similarity scoring, and recommendation capabilities for the Alloy training platform. This system enables smart circuit selection based on movement patterns, body regions, muscle engagement, equipment requirements, and intensity metrics.

## Architecture

### Core Components

1. **Database Models** ([app/models/circuit_extended.py](file:///Users/shourjosmac/Documents/alloy/app/models/circuit_extended.py))
   - `CircuitMelted`: Exercise-level circuit data
   - `CircuitMacro`: Aggregated circuit metrics

2. **Comparison Service** ([app/services/circuit_comparison.py](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_comparison.py))
   - `CircuitComparisonService`: Core comparison logic
   - Similarity scoring algorithms
   - Complementary circuit identification
   - Recommendation engine

3. **API Routes** ([app/api/routes/circuits.py](file:///Users/shourjosmac/Documents/alloy/app/api/routes/circuits.py))
   - Circuit macro data endpoints
   - Similarity endpoints
   - Complementary circuit endpoints
   - Recommendation endpoints

4. **Integration Services**
   - OptimizationService: Circuit diversity constraints
   - SessionGenerator: Circuit loading with macro data

## Features

### 1. Circuit Similarity Scoring

Similarity between circuits is calculated based on five weighted dimensions:

#### Similarity Dimensions

1. **Pattern Similarity (25%)**
   - Uses Jaccard similarity on movement patterns
   - Patterns: squat, hinge, push, pull, carry, lunge, rotation, gait, core
   - Higher overlap = higher similarity

2. **Region Similarity (20%)**
   - Binary match on primary region
   - Regions: upper, lower, full_body, core
   - Exact match = 1.0, different = 0.0

3. **Muscle Similarity (25%)**
   - Uses Jaccard similarity on primary muscles
   - Higher overlap = higher similarity

4. **Equipment Similarity (15%)**
   - Uses Jaccard similarity on required equipment
   - Higher overlap = higher similarity

5. **Intensity Similarity (15%)**
   - Based on difficulty tier difference
   - Based on duration difference
   - Average of normalized differences

#### Similarity Score Calculation

```
overall_similarity = (
    pattern_similarity * 0.25 +
    region_similarity * 0.20 +
    muscle_similarity * 0.25 +
    equipment_similarity * 0.15 +
    intensity_similarity * 0.15
)
```

#### Usage Example

```python
from app.services.circuit_comparison import CircuitComparisonService

service = CircuitComparisonService(db)
result = await service.calculate_circuit_similarity_score(
    circuit_a_id=1,
    circuit_b_id=2
)

print(f"Overall similarity: {result.similarity_score:.2%}")
print(f"Pattern similarity: {result.pattern_similarity:.2%}")
print(f"Region similarity: {result.region_similarity:.2%}")
print(f"Muscle similarity: {result.muscle_similarity:.2%}")
print(f"Equipment similarity: {result.equipment_similarity:.2%}")
print(f"Intensity similarity: {result.intensity_similarity:.2%}")
```

### 2. Finding Similar Circuits

Find circuits similar to a reference circuit, sorted by similarity score.

#### API Endpoint

```
GET /api/circuits/{circuit_id}/similar
```

#### Query Parameters

- `limit` (optional): Maximum number of results (default: 10)
- `min_similarity` (optional): Minimum similarity threshold (default: 0.5)

#### Response

```json
[
  {
    "circuit_id": 2,
    "similarity_score": 0.85,
    "pattern_similarity": 1.0,
    "region_similarity": 1.0,
    "muscle_similarity": 0.9,
    "equipment_similarity": 0.8,
    "intensity_similarity": 0.7
  }
]
```

#### Usage Example

```python
service = CircuitComparisonService(db)
similar = await service.find_similar_circuits(
    circuit_id=1,
    limit=5,
    min_similarity=0.6
)

for result in similar:
    print(f"Circuit {result.circuit_id}: {result.similarity_score:.2%}")
```

### 3. Finding Complementary Circuits

Find circuits that complement a reference circuit by targeting different muscles, regions, and patterns.

#### Complementarity Dimensions

1. **Pattern Diversity (30%)**
   - Different patterns are preferred
   - No overlap = highest complementarity

2. **Region Diversity (30%)**
   - Different regions are preferred
   - Upper ↔ Lower = highest complementarity

3. **Muscle Diversity (30%)**
   - Different muscles are preferred
   - No overlap = highest complementarity

4. **Equipment Overlap (10%)**
   - Some shared equipment is beneficial
   - Reduces setup time between circuits

#### API Endpoint

```
GET /api/circuits/{circuit_id}/complementary
```

#### Query Parameters

- `limit` (optional): Maximum number of results (default: 10)
- `min_complementarity` (optional): Minimum complementarity threshold (default: 0.3)

#### Response

```json
[
  {
    "circuit_id": 3,
    "reason": "targets lower body region; uses different movement patterns",
    "similarity_score": 0.25,
    "complementary_score": 0.85,
    "metadata": {
      "primary_region": "lower",
      "difficulty_tier": 2
    }
  }
]
```

#### Usage Example

```python
service = CircuitComparisonService(db)
complementary = await service.find_complementary_circuits(
    circuit_id=1,
    limit=5,
    min_complementarity=0.5
)

for rec in complementary:
    print(f"Circuit {rec.circuit_id}: {rec.reason}")
    print(f"  Complementarity: {rec.complementary_score:.2%}")
```

### 4. Circuit Recommendations

Get circuit recommendations based on session constraints and preferences.

#### API Endpoint

```
POST /api/circuits/recommendations
```

#### Request Body

```json
{
  "circuit_ids": [1, 2],        // Current circuits (optional)
  "target_regions": ["lower"],     // Preferred regions (optional)
  "target_patterns": ["squat"],    // Preferred patterns (optional)
  "difficulty_tier": "silver",     // Max difficulty (optional)
  "max_equipment": 2,             // Max equipment items (optional)
  "limit": 5                      // Max results (optional)
}
```

#### Response

```json
[
  {
    "circuit_id": 3,
    "reason": "matches session criteria",
    "similarity_score": 0.3,
    "complementary_score": 0.7,
    "metadata": {
      "primary_region": "lower",
      "difficulty_tier": 2,
      "total_exercises": 4
    }
  }
]
```

#### Usage Example

```python
service = CircuitComparisonService(db)
recommendations = await service.recommend_circuits_for_session(
    circuit_ids=[1],              # Complement to current session
    target_regions=["lower"],       # Focus on lower body
    difficulty_tier="silver",      # Moderate difficulty
    max_equipment=2,              # Limited equipment
    limit=5
)

for rec in recommendations:
    print(f"Circuit {rec.circuit_id}: {rec.reason}")
```

### 5. Circuit Macro Data

Access comprehensive macro data for any circuit.

#### API Endpoint

```
GET /api/circuits/{circuit_id}/macro
```

#### Response

```json
{
  "total_exercises": 4,
  "unique_movements": 3,
  "total_reps": 32,
  "total_distance_meters": null,
  "total_work_seconds": 480,
  "estimated_duration_seconds": 480,
  "difficulty_tier": "silver",
  "min_recovery_hours": 24,
  "max_rx_weight_male": 60.0,
  "max_rx_weight_female": 40.0,
  "primary_muscles": ["chest", "shoulders", "triceps"],
  "muscle_engagement_score": 0.85,
  "primary_region": "upper",
  "region_diversity_score": 0.3,
  "required_equipment": [1, 2],
  "equipment_complexity": 2,
  "movement_pattern_counts": {"push": 2, "pull": 2},
  "pattern_diversity_score": 0.5,
  "metabolic_profile": {
    "anabolic": 0.4,
    "metabolic": 0.4,
    "neural": 0.2
  },
  "estimated_calories_per_hour": 350.0,
  "space_requirement_meters": 2.5,
  "station_count": 2,
  "circuit_type_intensity": "medium",
  "data_completeness_score": 1.0
}
```

#### Combined Endpoint

```
GET /api/circuits/{circuit_id}/with-macro
```

Returns circuit template with macro data included.

## Optimization Integration

### Circuit Diversity Constraints

The optimization service now includes circuit diversity constraints:

1. **Max 1 Circuit per Body Region**
   - Prevents overtraining specific body parts
   - Ensures balanced muscle engagement

2. **Pattern Diversity Constraint**
   - Limits low-diversity circuits in a session
   - Promotes varied movement patterns

### SolverCircuit Model

```python
@dataclass
class SolverCircuit:
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
```

## Session Generator Integration

The session generator now loads circuits with macro data:

```python
async def _load_all_circuits(self, db: AsyncSession) -> list[SolverCircuit]:
    """Load all circuits and convert to SolverCircuit format."""
    stmt = select(CircuitTemplate, CircuitMacro).join(
        CircuitMacro, CircuitTemplate.id == CircuitMacro.circuit_id
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    return [
        SolverCircuit(
            id=c.id,
            name=c.name,
            # ... other fields ...
            primary_region=m.primary_region.value if m else None,
            pattern_diversity_score=m.pattern_diversity_score if m else 0.0,
            equipment_complexity=m.equipment_complexity if m else 0
        )
        for c, m in rows
    ]
```

## Data Population

### Population Script

Run the population script to populate melted and macro tables:

```bash
python scripts/populate_circuit_tables.py
```

#### Options

- `--force`: Re-populate all circuits (skip existing data)
- `--verbose`: Detailed logging
- `--dry-run`: Preview changes without executing

### Current Status

- Total circuits: 27
- Circuits with melted data: 26
- Circuits with macro data: 26
- Melted records: 139
- Macro records: 26

Note: Circuit 138 lacks data because it has no measurable metrics (no reps, distance, duration, or calories).

## Testing

### Test Coverage

Comprehensive tests are available in [tests/test_circuit_comparison.py](file:///Users/shourjosmac/Documents/alloy/tests/test_circuit_comparison.py):

- Similarity scoring tests
- Similar circuit finding tests
- Complementary circuit finding tests
- Recommendation tests
- Error handling tests
- Individual similarity calculation method tests

### Running Tests

```bash
# Run all circuit comparison tests
pytest tests/test_circuit_comparison.py -v

# Run specific test class
pytest tests/test_circuit_comparison.py::TestCircuitSimilarityScoring -v

# Run specific test
pytest tests/test_circuit_comparison.py::TestCircuitSimilarityScoring::test_similar_circuits_high_similarity -v
```

Note: Tests require PostgreSQL (JSONB support) and will fail with SQLite.

## API Documentation

### Endpoints

| Endpoint | Method | Description |
|----------|---------|-------------|
| `/api/circuits/{id}/macro` | GET | Get circuit macro data |
| `/api/circuits/{id}/with-macro` | GET | Get circuit with macro data |
| `/api/circuits/{id}/similar` | GET | Find similar circuits |
| `/api/circuits/{id}/complementary` | GET | Find complementary circuits |
| `/api/circuits/recommendations` | POST | Get circuit recommendations |

### Response Models

- `CircuitMacroData`: Circuit macro data schema
- `CircuitSimilarityResult`: Similarity scoring result
- `CircuitRecommendation`: Recommendation result with metadata

## Best Practices

### For Similar Circuits

- Use when building progressive overload programs
- Use for injury recovery (similar patterns, different intensity)
- Use for skill reinforcement (same patterns, same intensity)

### For Complementary Circuits

- Use for balanced training programs
- Use for muscle recovery (different regions)
- Use for variety in training (different patterns)

### For Recommendations

- Use for session planning with constraints
- Use for equipment-limited environments
- Use for goal-specific circuit selection

## Performance Considerations

### Database Indexes

- B-tree indexes on circuit_id, movement_id, exercise_sequence
- GIN indexes on JSONB columns (primary_muscles, movement_pattern_counts, required_equipment)

### Query Optimization

- Use joins to avoid N+1 queries
- Filter by macro data to skip non-populated circuits
- Use limit to reduce result set size

### Caching

Consider caching:
- Baseline similarity scores for frequently compared circuits
- Complementarity scores for popular circuits
- Recommendation results for common session configurations

## Future Enhancements

### Potential Improvements

1. **Machine Learning Integration**
   - Learn optimal similarity weights from user feedback
   - Personalize recommendations based on training history

2. **Temporal Similarity**
   - Consider session timing (morning vs evening)
   - Account for recovery status

3. **Equipment Substitution**
   - Suggest alternative circuits with available equipment
   - Calculate equipment compatibility scores

4. **Progressive Overload Support**
   - Track circuit progression over time
   - Suggest similar circuits with increased difficulty

5. **Social Features**
   - "Most similar to your recent circuits"
   - "Popular circuits like this one"
   - "Friends who did this circuit also did..."

## Troubleshooting

### Common Issues

**Issue: Circuits without macro data**
- Cause: Circuit has no measurable metrics
- Solution: Add exercises with reps, distance, duration, or calories

**Issue: Low similarity scores**
- Cause: Circuits are genuinely different
- Solution: Lower min_similarity threshold or check circuit composition

**Issue: No complementary circuits found**
- Cause: Too few circuits or too high threshold
- Solution: Lower min_complementarity threshold or add more circuits

**Issue: Performance issues with large circuit sets**
- Cause: N^2 similarity calculations
- Solution: Use indexes, limit result sets, implement caching

## Contributing

When adding new features:

1. Update similarity weights based on empirical evidence
2. Add comprehensive tests for new algorithms
3. Document API changes in this README
4. Update migration scripts if schema changes
5. Re-run population script after schema changes

## References

- [Circuit Normalization Readme](file:///Users/shourjosmac/Documents/alloy/docs/circuit_normalization_readme.md)
- [Circuit Models](file:///Users/shourjosmac/Documents/alloy/app/models/circuit_extended.py)
- [Comparison Service](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_comparison.py)
- [API Routes](file:///Users/shourjosmac/Documents/alloy/app/api/routes/circuits.py)
- [Tests](file:///Users/shourjosmac/Documents/alloy/tests/test_circuit_comparison.py)
