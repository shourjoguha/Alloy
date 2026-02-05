I will create `PROGRAM_CREATION_ARCHITECTURE.md` documenting:

## Document Structure

1. **High-Level Overview** - Architecture diagram and component responsibilities
2. **Data Schema References** - Tables/models and what they store (with file references)
3. **Frontend Program Wizard** - User data collection through wizard steps
4. **API Layer** - POST /programs endpoint flow (file: `app/api/routes/programs.py`)
5. **ProgramService** - Core business logic (file: `app/services/program.py`)
6. **Session Generator** - Exercise population via LLM (file: `app/services/session_generator.py`)
7. **Constraint Solver** - OR-Tools optimization (file: `app/services/optimization.py`)
8. **Circuit Assignment** - Atomic circuit operations (file: `app/services/circuit_assignment.py`)
9. **Deload Service** - Deload scheduling (file: `app/services/deload.py`)
10. **Interference Service** - Goal conflict detection (file: `app/services/interference.py`)
11. **Data Flow Diagrams** - Sequence diagrams for key flows
12. **Deviations from Intended Behavior** - Where implementation differs from design
13. **Areas for Improvement** - Compactness, efficiency, elegance recommendations

## Key Focus Areas
- Constraint collection (movement rules, marked movements, user preferences) → point to `UserMovementRule`, `UserProfile` models
- Goal validation through interference service → point to `InterferenceService.validate_goals()`
- Split template configuration and microcycle generation → point to `ProgramService._build_freeform_split_config()`
- Session population with LLM → point to `SessionGeneratorService.populate_session_by_id()`
- Progressive constraint relaxation → point to `ConstraintSolver.solve_session_with_progressive_relaxation()`
- Deload scheduling logic → point to `DeloadService` and microcycle `is_deload` flag
- Cross-session tracking (used movements, fatigued muscles, pattern interference) → point to tracking variables in program generation loop