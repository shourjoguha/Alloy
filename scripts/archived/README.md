# Archived Scripts

This directory contains scripts that are no longer actively used but are preserved for reference.

## Phase 3 Scripts

These scripts were used for the initial data population of movements and relationships during Phase 3 of the Gainsly platform development.

### `phase3_create_archetypes.py`
- Created foundational movement archetypes with full biomechanical profiles
- Included equipment, tags, disciplines, and coaching cues
- Populated the initial movement knowledge graph

### `phase3_map_relationships.py`
- Mapped complex movement relationships (progressions, variations, regressions)
- Created substitution groups for workout flexibility
- Established movement hierarchies

## Migration to Movement Management Tool

These scripts have been replaced by the dynamic movement management tool located in `scripts/tools/`:
- `movement_manager.py` - Core library for movement/relationship operations
- `movement_cli.py` - CLI interface for adding movements and relationships
- `examples/sample_movements.json` - Sample data for batch import

## Usage

The movement management tool provides:
- Interactive movement creation
- JSON batch import
- Relationship validation
- Duplicate detection
- Enum validation for data integrity

See `scripts/tools/README.md` for detailed usage instructions.
