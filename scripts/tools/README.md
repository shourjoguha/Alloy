# Movement Management Tools

Reusable tools for dynamically adding movements and relationships to the Gainsly database.

## Features

- **Dynamic Movement Creation**: Add movements with full biomechanical data
- **Relationship Management**: Create progressions, regressions, and variations
- **Batch Import**: Import movements from JSON files
- **CLI Interface**: Easy-to-use command-line interface
- **Validation**: Automatic validation of enum values and data integrity

## Installation

No additional installation required. The tools use existing project dependencies.

## Quick Start

### 1. Add a Single Movement (Interactive)

```bash
python -m scripts.tools.movement_cli add-movement
```

Follow the prompts to enter movement details.

### 2. Add a Movement from JSON

```bash
python -m scripts.tools.movement_cli add-movement --file path/to/movement.json
```

### 3. Add a Relationship

```bash
python -m scripts.tools.movement_cli add-relationship \
    --source "Barbell Squat" \
    --target "Goblet Squat" \
    --type regression \
    --notes "Easier variation for beginners"
```

### 4. Import Movements and Relationships from JSON

```bash
python -m scripts.tools.movement_cli import --file path/to/movements.json
```

### 5. View Movement Details

```bash
python -m scripts.tools.movement_cli show "Barbell Squat"
```

### 6. List All Movements

```bash
python -m scripts.tools.movement_cli list
```

## JSON File Format

### Movement JSON Structure

```json
{
  "name": "Barbell Squat",
  "pattern": "squat",
  "primary_muscle": "quadriceps",
  "primary_region": "anterior lower",
  "skill_level": "beginner",
  "compound": true,
  "equipment": ["barbell", "squat_rack"],
  "tags": ["compound", "lower_body"],
  "disciplines": ["powerlifting", "bodybuilding"],
  "tier": "gold",
  "metabolic_demand": "neural",
  "biomechanics_profile": {
    "force_vector": "vertical",
    "joint_dominance": "knee",
    "tempo_preference": "controlled",
    "lumbar_shear": "moderate",
    "eccentric_load": "high",
    "concentric_drive": "glute_dominant",
    "stability_demand": "high",
    "unilateral_benefit": "none"
  }
}
```

### Bulk Import JSON Structure

```json
{
  "movements": [
    {
      "name": "Zercher Squat",
      "pattern": "squat",
      "primary_muscle": "quadriceps",
      ...
    }
  ],
  "relationships": [
    {
      "source": "Back Squat",
      "target": "Zercher Squat",
      "type": "variation",
      "notes": "Barbell position changes center of mass"
    }
  ]
}
```

## Valid Enum Values

### Movement Patterns
`squat`, `hinge`, `horizontal_push`, `vertical_push`, `horizontal_pull`, `vertical_pull`, `carry`, `core`, `lunge`, `rotation`, `plyometric`, `olympic`, `isolation`, `mobility`, `isometric`, `conditioning`, `cardio`

### Primary Muscles
`quadriceps`, `hamstrings`, `glutes`, `calves`, `chest`, `lats`, `upper_back`, `rear_delts`, `front_delts`, `side_delts`, `biceps`, `triceps`, `forearms`, `core`, `obliques`, `lower_back`, `hip_flexors`, `adductors`, `full_body`

### Primary Regions
`anterior lower`, `posterior lower`, `shoulder`, `anterior upper`, `posterior upper`, `full_body`, `lower body`, `upper body`, `core`

### Skill Levels
`beginner`, `intermediate`, `advanced`, `expert`, `elite`

### CNS Load
`very_low`, `low`, `moderate`, `high`, `very_high`

### Spinal Compression
`none`, `low`, `moderate`, `high`

### Metric Types
`reps`, `time`, `time_under_tension`, `distance`

### Movement Tiers
`bronze`, `silver`, `gold`, `diamond`

### Metabolic Demand
`neural`, `metabolic`

### Relationship Types
`progression`, `regression`, `variation`, `antagonist`

### Discipline Types
`powerlifting`, `olympic_weightlifting`, `bodybuilding`, `crossfit`, `strongman`, `calisthenics`, `yoga`, `running`, `cycling`, `swimming`, `functional_training`

## Python API Usage

### Core Library

```python
import asyncio
from scripts.tools.movement_manager import MovementManager

async def add_movement():
    movement_data = {
        "name": "Barbell Squat",
        "pattern": "squat",
        "primary_muscle": "quadriceps",
        "compound": True,
        "tier": "gold"
    }
    
    async with MovementManager() as manager:
        movement = await manager.add_movement(movement_data)
        print(f"Created movement: {movement.name}")

asyncio.run(add_movement())
```

### Add Relationship

```python
import asyncio
from scripts.tools.movement_manager import add_single_relationship

async def add_relationship():
    success = await add_single_relationship(
        source="Barbell Squat",
        target="Goblet Squat",
        rel_type="regression",
        notes="Easier variation"
    )
    print(f"Relationship created: {success}")

asyncio.run(add_relationship())
```

### Import from JSON

```python
import asyncio
from scripts.tools.movement_manager import import_movements_from_json

async def import_data():
    results = await import_movements_from_json("movements.json")
    print(f"Imported {results['movements_created']} movements")
    print(f"Created {results['relationships_created']} relationships")

asyncio.run(import_data())
```

## Examples

See `scripts/tools/examples/sample_movements.json` for a complete example.

## Error Handling

The tools include comprehensive error handling:

- **Duplicate Detection**: Prevents creating movements with identical names
- **Enum Validation**: Validates all enum values against allowed values
- **Relationship Validation**: Checks that both movements exist before creating relationships
- **Database Integrity**: Uses transactions to ensure data consistency

## Best Practices

1. **Use JSON for Batch Imports**: JSON files are easier to maintain and version control
2. **Validate Data Before Import**: Check your JSON structure against the format examples
3. **Test with Small Batches**: Start with a few movements to validate your data format
4. **Use Meaningful Notes**: Add descriptive notes to relationships for future reference
5. **Follow Naming Conventions**: Use consistent capitalization and naming patterns

## Troubleshooting

### Movement Already Exists
If you see "Movement already exists", the tool will skip creating duplicates.

### Invalid Enum Value
Check your enum values against the valid values listed above.

### Movement Not Found
When creating relationships, ensure both movements exist in the database first.

### Import Failures
Check the import results output for details on failed items.

## Architecture

- `movement_manager.py`: Core library with MovementManager class
- `movement_cli.py`: Command-line interface
- `examples/`: Sample JSON files for reference

## Future Enhancements

Potential improvements:
- CSV import support
- Bulk relationship import from spreadsheet
- Movement update/editing functionality
- Relationship visualization
- Validation rules and constraints
- Bulk deletion/archiving
