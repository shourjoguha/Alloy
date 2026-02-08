# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Environment

### Starting the Full Stack
```bash
# Single command to start all services (PostgreSQL, Ollama, backend, frontend)
./start-dev.sh

# Services will be available at:
# - Backend: http://0.0.0.0:8000
# - Frontend: http://localhost:5173
# - Ollama: http://localhost:11434
# - PostgreSQL: localhost:5433 (Docker container named "alloy")
```

### Backend (FastAPI)
```bash
# Activate virtual environment
source .venv/bin/activate

# Run backend only
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head                    # Apply all migrations
alembic revision --autogenerate -m ""   # Generate new migration

# Testing
pytest                                  # Run all tests
pytest --cov=app                        # Run with coverage
pytest -k test_name                     # Run specific test
pytest -v                               # Verbose output

# Code quality
ruff check .                            # Lint
ruff format .                           # Format
black .                                 # Alternative formatter
```

### Frontend (React + Vite)
```bash
cd frontend

# Start development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint
```

### Prerequisites
- **Ollama**: Must be running with `llama3.2:3b` model
  - Start: `ollama serve`
  - Pull model: `ollama pull llama3.2:3b`
- **PostgreSQL**: Runs via Docker (handled by start-dev.sh)
- **Python 3.11+** with virtual environment at `.venv`

## High-Level Architecture

### Core Philosophy: The Movements Table as Source of Truth

The `movements` table is the central "source of truth" for all exercise selection, session generation, and adaptation logic. Think of a movement as a rich, multi-dimensional entity defined by:

- **Pattern** (squat, hinge, horizontal_push, vertical_push, horizontal_pull, vertical_pull, carry, core, lunge, rotation, plyometric, olympic, isolation, mobility, isometric, conditioning, cardio)
- **Region** (anterior_lower, posterior_lower, shoulder, anterior_upper, posterior_upper, full_body, lower_body, upper_body)
- **Primary Muscle** (quadriceps, hamstrings, glutes, calves, chest, lats, upper_back, rear_delts, front_delts, side_delts, biceps, triceps, forearms, core, obliques, lower_back, hip_flexors, adductors, full_body)
- **Mechanics** (CNS load, skill level, compound vs isolation)
- **Fitness Metrics** (fatigue_factor, stimulus_factor, injury_risk_factor)

Think of a circuit as a dedicated finisher. a session will can have either a finisher (a finisher is always a circuit) or accessories but never both.
Circuits may have their own metrics ('default_rounds' or a max time cap), the movements within a circuit will have their owne metrics('reps', 'distance_meters','calories,' , 'time_seconds')

Then there are 2 'circuit' related table 'circuit_macro' and 'circuit_melted'
- business logic : a circuit is a predefined ordered list of movements with differnt metrics performed in order 1 to any number of times on repeat. There are many types of circuits.
- business logic : circuit_macro contains information on the circuit type and rounds (number of times the movement list in that circuit is to be repeated)
- business logic : circuit_melted contains melted information on the contents of the circuits ( the individual movements, their sequence, there metric - distance,calories, reps, time, and the correposponding measurement of that metric)
    - circuits_melted has columns for each metric ('reps', 'distance_meters','calories,' , 'time_seconds'). but only the column relevant for the movement (as shows on 'metric_type') will be populated

A session will build in finishers with a main lift proportionate to program goals - if endurance and fatloss weighting determine frequency. 

There is a 'user_profiles' table. movement selection (based on 'movement_discipline') should be *lightly* influenced/biased by user 'interest' level. 

### Soft Enum Convention (Critical)

Gainsly employs a "Soft Enum" pattern with dual-layer validation:

1. **Database Storage**: Categorical fields store values as **UPPERCASE strings** in PostgreSQL ENUMs (e.g., `HORIZONTAL_PUSH`, `SQUAT`)
2. **Application Layer**: Python enums in `app/models/enums.py` define **semantic lowercase values** (e.g., `"horizontal_push"`, `"squat"`)
3. **API Responses**: Use semantic lowercase values for readability

**Important**: When querying or filtering, the application accepts both formats. When writing new code, prefer semantic values from the enum `.value` attribute.

### Database Hierarchy

```
User -> Programs -> Microcycles -> Sessions -> SessionExercises
     -> UserSettings
     -> UserMovementRules
     -> WorkoutLogs -> TopSetLogs
     -> SorenessLogs
     -> RecoverySignals
     -> PatternExposure

Movement <- Movement Relationships (progression/regression/variation/antagonist/prep)
         <- MovementMuscleMap (with roles: prime_mover/synergist/stabilizer/antagonist)
         <- MovementEquipment
         <- MovementTags
         <- MovementDiscipline

Circuits <- Circuits_macro 
         <- Circuits_melted 
```

### Core Services

The application services are organized hierarchically. **ProgramService** acts as the main orchestrator, delegating planning to the **Logic & Planning Layer**, which then instructs the **Execution Layer** to generate content using **Core Engines**.

```mermaid
graph TD
    subgraph "Orchestration Layer"
        PS[ProgramService]
    end

    subgraph "Logic & Planning Layer"
        IS[InterferenceService]
        AIS[AllocationIntegrationService]
        AS[AdaptationService]
    end

    subgraph "Execution Layer"
        SGS[SessionGeneratorService]
    end

    subgraph "Core Engines"
        OS[OptimizationService]
        TES[TimeEstimationService]
        CCS[CircuitComparisonService]
        MS[MovementService]
    end

    %% Relationships
    PS --> IS
    PS --> AIS
    PS --> SGS
    
    SGS --> OS
    SGS --> TES
    SGS --> CCS
    SGS --> MS
    
    AS --> CCS
    AS --> MS
```

#### 1. Orchestration Layer
*   **ProgramService** (`app/services/program.py`)
    *   **Role**: Entry point for program creation. Orchestrates microcycles, split templates, and goal distribution.
    *   **Dependencies**:
        *   `InterferenceService`: To validate goal conflicts.
        *   `AllocationIntegrationService`: To plan session types.
        *   `SessionGeneratorService`: To generate session content.

#### 2. Logic & Planning Layer
*   **InterferenceService** (`app/services/interference.py`)
    *   **Role**: Validates user goals and detects logical conflicts (e.g., incompatibility between "Powerlifting" focus and "Marathon" training).
    *   **Dependencies**: None.

*   **AllocationIntegrationService** (`app/services/allocation_integration.py`)
    *   **Role**: Coordinates session type allocation (Finisher vs Accessory). Merges wizard goals with user settings and uses distribution logic to assign types across a microcycle.
    *   **Dependencies**: Internal helpers (`SessionTypeCalculator`, `SessionTypeDistributor`).

*   **AdaptationService** (`app/services/adaptation.py`)
    *   **Role**: Real-time session adjustments based on user constraints (time, equipment, recovery).
    *   **Dependencies**: `CircuitComparisonService` (for circuit swaps), `MovementService` (for exercise swaps).

#### 3. Execution Layer
*   **SessionGeneratorService** (`app/services/session_generator.py`)
    *   **Role**: Generates actual workout content (warmup, main, accessory, finisher).
    *   **Mechanism**: Uses **OR-Tools** (Constraint Solver) exclusively. Legacy LLM generation has been removed.
    *   **Dependencies**:
        *   `OptimizationService`: The solver engine.
        *   `TimeEstimationService`: To ensure sessions fit duration constraints.
        *   `CircuitComparisonService`: To select appropriate finishers.

#### 4. Core Engines (Foundational Services)
*   **OptimizationService** (`app/services/optimization.py`)
    *   **Role**: Wrapper around Google OR-Tools. Solves the complex constraint satisfaction problem of selecting exercises that meet all biomechanical, equipment, and time rules.

*   **MovementService** (`app/services/movement.py`)
    *   **Role**: Manages movement data, pattern interference detection, and variety rules.
    *   **Key Feature**: Prevents same movement patterns on consecutive days.

*   **TimeEstimationService** (`app/services/time_estimation.py`)
    *   **Role**: Predicts session duration based on exercise count, sets, reps, and rest periods.

*   **CircuitComparisonService** (`app/services/circuit_assignment.py` / `circuit_comparison.py`)
    *   **Role**: Assigns and compares CrossFit/Hyrox-style circuits. Handles mutual exclusivity enforcement.

*   **MetricsService** (`app/services/metrics.py`)
    *   **Role**: Calculates e1RM (Epley, Brzycki, etc.) and Pattern Strength Index (PSI).

*   **DeloadService** (`app/services/deload.py`)
    *   **Role**: Manages deload scheduling logic.

### The Coaching Logic

The "brain" of the application lies in how the **OptimizationService** (OR-Tools) selects exercises. It doesn't just pick random movements; it solves a mathematical optimization problem to find the "best" workout.

#### 1. The Selection Formula (How Movements are Compared)
The optimizer compares movements by calculating a **Score** for each candidate and trying to maximize the total session score.

*   **Primary Driver**: `Stimulus` vs. `Goal Priority`
    *   Logic: `Score = (Movement Stimulus × Goal Pressure) + Duration Incentive`
    *   *Goal Pressure* comes from user goals (e.g., Strength goals prioritize high-stimulus compounds).
    *   *Duration Incentive* ensures the session fills the time (rather than picking the fewest exercises).

*   **The "Cost" (Constraints)**
    *   **Fatigue Budget**: Every movement has a `fatigue_factor`. The session cannot exceed the global `max_fatigue` (default 8.0, relaxes if solving fails).
    *   **Time Budget**: Calculated via `TimeEstimationService`. Rest periods + work time must fit within `target_duration ± tolerance`.

*   **Tie-Breakers**:
    *   **User Preference**: Preferred movements get a **15% score bonus**.
    *   **Compound Requirement**: Solvers are forced to pick at least 2 compound movements first.

#### 2. Global Configuration (Where the Rules Live)
The rules are not hardcoded in the service but stored globally in `app/config/`. This allows for tuning the "Coach's Personality" without changing code.

*   **`app/config/heuristics.py` (The Biomechanics & Physics)**
    *   **`GOAL_DOSE_HEURISTICS`**: Defines the "dose" for each goal (e.g., Strength = Low Reps, High Rest, High CNS Cost).
    *   **`TIME_ESTIMATION`**: Defines the physics of time (e.g., 1-5 reps takes 15s execution + 180s rest).
    *   **`SECTION_PATTERN_FILTERS`**: Hard rules on what goes where (e.g., "No Isolation movements in Main Lift section").

*   **`app/config/activity_distribution.py` (The Strategy)**
    *   **`goal_bucket_weights`**: Determines the mix of session types (e.g., how many Finishers vs. Accessories based on Fat Loss vs. Strength goals).
    *   **Solver Constraints**: Sets the global limits (e.g., `or_tools_max_fatigue = 8.0`).

#### 3. Technical Illustration (Data Models)

The following tables illustrate the data that drives the optimizer's decision-making process.

**A. Goal Pressure (Heuristics)**
This table defines the "dose" the optimizer attempts to construct for each goal type. Sourced from `GOAL_DOSE_HEURISTICS`.

| Goal | Rep Range | Rest (Seconds) | CNS Budget | Volume (Sets/Muscle) |
| :--- | :--- | :--- | :--- | :--- |
| **Strength** | 1 - 6 | 180 - 300 | High | 10 - 15 |
| **Hypertrophy** | 6 - 15 | 60 - 120 | Moderate | 15 - 25 |
| **Endurance** | 15 - 30 | 30 - 60 | Low | 12 - 20 |
| **Fat Loss** | 10 - 20 | 30 - 60 | Moderate | 12 - 18 |
| **Explosiveness** | 1 - 6 | 120 - 240 | High | 8 - 15 |

**B. Scoring Influence (The "Why")**
Factors that increase an exercise's score in the objective function.

| Factor | Influence Multiplier | Description |
| :--- | :--- | :--- |
| **Stimulus** | `Goal Pressure × 100` | The primary driver. Heavily weighted by user's main goal (e.g., Squats score higher for Strength goals). |
| **Duration** | `100` | Strong incentive to fill the session time budget completely. |
| **User Preference** | `+15%` | Explicit bonus for exercises in the user's "Preferred" list. |
| **Circuit Duration** | `10 × Cardio Pressure` | For endurance goals, longer circuits score higher. |

**C. Solver Thresholds (Constraints)**
Hard limits the solver must respect (defined in `activity_distribution.py`).

| Threshold | Value | Description |
| :--- | :--- | :--- |
| **Max Fatigue** | `8.0` | Global limit for session fatigue score. Relaxes (+50%) if solving fails. |
| **Duration Window** | `±12%` | A 60min session is valid between 53–67 minutes. |
| **Sets per Move** | `2 - 5` | Exercises must have at least 2 sets, max 5. |
| **Volume Reduction** | `20%` | Target volume is reduced by 20% to ensure solvable solutions. |

### LLM Integration (Legacy/Deprecated)

The application previously used LLMs for session generation. This has been replaced by deterministic solvers (OR-Tools) for reliability and speed.

*   **Current Status**: largely deprecated.
*   **Remaining Usage**: `ProgramService` contains logic to generate "Coach Notes" (Jerome Persona) via LLM, but this path is currently under refactoring.
*   **Infrastructure**: `app/llm/` contains the provider-agnostic interface (`base.py`) and `ollama_provider.py`, which remain available for future features (e.g., chat, motivation).

### Session Structure

Sessions have flexible, optional JSON sections:
- `warmup_json` - Always included
- `main_json` - Main lifts or cardio block
- `accessory_json` - Optional accessory work
- `finisher_json` - Optional finisher (conditioning, cardio, metabolic)
- `cooldown_json` - Always included

Session types determine structure:
- **Strength/Hypertrophy**: Main lifts + (Accessory XOR Finisher)
- **Cardio-only**: Dedicated cardio block
- **Conditioning-only**: Circuit-based (≥5 movements, ≥30 minutes)
- **Mobility**: Extended warmup/cooldown

### Movement Variety System

Critical for preventing overuse and maintaining training quality:

1. **Pattern Interference Rules**
   - No same main pattern on consecutive training days
   - Maximum 2 uses per pattern per week
   - Intelligent pattern substitution (squat → hinge → lunge rotation)

2. **Variety Enforcement**
   - Intra-session deduplication (no exercise appears twice in same session)
   - Inter-session variety tracking across the week
   - Muscle group fatigue tracking
   - Movement history context passed to the Optimizer

3. **Pattern Exposure Tracking** (`pattern_exposures` table)
   - Tracks consecutive uses of same pattern
   - Last exposure date for each pattern
   - Total exposure count

### Authentication

JWT-based authentication with bcrypt password hashing:

**Endpoints**:
- `POST /auth/register` - User registration with JWT issuance
- `POST /auth/login` - Credential verification with JWT issuance
- `GET /auth/verify-token` - Token validation and user info

**Security**:
- Passwords hashed with bcrypt (never stored plain-text)
- JWT tokens use HS256 algorithm
- Token payload: `{"sub": user_id, "exp": expiration_timestamp}`
- Default expiration: 30 minutes (configurable)
- Secret key stored in environment variable

**Integration**:
- Frontend stores token in `auth-store.ts` with persistence
- Protected routes require Bearer token in Authorization header
- All user-scoped operations use `user_id` from token's "sub" claim

### Frontend Architecture

- **React 19** with TypeScript
- **TanStack Router** for type-safe routing
- **React Query** for server state management with automatic caching
- **Tailwind CSS** with dark neon theme
- **Zustand** for client-side state management
- **React Hook Form** + Zod for form validation

**Key Stores**:
- `auth-store.ts` - Authentication state and token management
- `program-wizard-store.ts` - Multi-step program creation wizard state

**Design System**:
- Primary: Vibrant teal (#06B6D4)
- Secondary: Deep slate (#1E293B)
- Accent: Amber (#F59E0B) for warnings/deload
- Success: Emerald (#10B981) for completed sessions/PRs

## Key Implementation Patterns

### Program Creation Flow

1. User completes program wizard in frontend
2. POST /programs with `ProgramCreate` schema
3. `InterferenceService.validate_goals()` checks goal conflicts
4. `ProgramService.create_program()` creates Program, Microcycles, Session shells
5. Transaction committed
6. Background task queued: `generate_active_microcycle_sessions()`
7. `AllocationIntegrationService` determines session types (finisher/accessory), then `SessionGeneratorService` generates exercise content via OR-Tools
8. `ConstraintSolver` (OR-Tools) validates and optimizes selections
9. Exercises saved to database with pattern exposure tracking

### Daily Session Adaptation

1. GET `/days/{date}/plan` - Fetch planned session
2. User provides constraints (time, equipment, recovery)
3. POST `/days/{date}/adapt` or `/days/{date}/adapt/stream` (SSE)
4. `AdaptationService` adjusts session based on constraints
5. Alternative exercises are generated using database logic (substitution groups) and optimization rules.
6. Updated session returned (streaming or complete)

### Testing Strategy

- Tests use **in-memory SQLite** with async sessions (`conftest.py`)
- Fixtures provide sample data: users, movements, programs, logs
- Service tests focus on business logic isolation
- Integration tests cover full API flows
- Performance testing available with Locust (`tests/performance_test_locust.py`)

**Running Tests**:
- Single test file: `pytest tests/test_program_service.py`
- Specific test: `pytest -k test_create_program_with_goals`
- With output: `pytest -v -s`

### Database Migrations

- Alembic manages schema changes
- Migration files in `alembic/versions/`
- **Before creating migrations**: Ensure local database matches current head
- **After creating migrations**: Review autogenerated SQL for correctness
- Soft enum pattern: Database uses UPPERCASE, code uses `.value` for lowercase

### Scripts Directory

The `scripts/` directory contains utility scripts for data analysis and maintenance:
- `check_*.py` - Database consistency checks
- `analyze_*.py` - Data analysis and reporting
- `create_*.py` - Data generation and imports
- Many scripts are one-off utilities for specific investigations

**Note**: Scripts are not part of the main application flow. They're tools for debugging and analysis.

## Important Conventions

### Biomechanical Inference Rules

When selecting exercises or analyzing movements:

- **If pattern = "horizontal_push"** → Likely involves front_delts, side_delts, triceps, chest
- **If pattern = "vertical_push"** → Likely involves side_delts, triceps, front_delts
- **If pattern = "horizontal_pull"** → Likely involves lats, upper_back, rear_delts, biceps
- **If pattern = "vertical_pull"** → Likely involves lats, biceps, lower_back
- **If pattern = "squat"** → Likely involves quadriceps, glutes, adductors, core
- **If pattern = "hinge"** → Likely involves hamstrings, glutes, lower_back
- **If pattern = "lunge"** → Likely involves quadriceps, glutes, hip_flexors, adductors

### CNS Load Inference

- **olympic/plyometric** → High to very high CNS load
- **isometric** → Variable CNS load (moderate to low)
- **conditioning/cardio** → Low to moderate CNS load
- **isolation** → Very low CNS load
- **compound barbell movements** → High CNS load, high fatigue_factor

### Code Organization

- `app/models/` - SQLAlchemy ORM models and enums
- `app/schemas/` - Pydantic request/response schemas
- `app/api/routes/` - FastAPI endpoint definitions
- `app/services/` - Business logic (keep fat)
- `app/llm/` - LLM provider abstractions
- `app/security/` - Authentication utilities
- `app/config/` - Application configuration
- `app/db/` - Database connection and seeding

### Environment Variables

Required in `.env` file:
```
DATABASE_URL=postgresql+asyncpg://gainsly:gainslypass@localhost:5433/gainslydb
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=1100.0
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
DEBUG=true
```

## Documentation References

For deeper understanding of specific areas:

- **AI_CONTEXT_ARCHITECTURE_GUIDE.md** - Detailed biomechanical data model, inference rules, soft enum convention, truth hierarchy
- **DATABASE_OVERVIEW.md** - Complete schema documentation with all enums and their values
- **PROGRAM_CREATION_ARCHITECTURE.md** - Program creation flow, wizard state management, background task execution
- **API_REFERENCE.md** - Complete API endpoint documentation
- **README.md** - Project overview, features, and quick start
- **docs/PERFORMANCE_TESTING.md** - Locust performance testing guide
- **docs/NOTES.md** - Architecture decisions and design patterns

## Common Pitfalls

1. **Enum Case Sensitivity**: Database stores UPPERCASE, code uses lowercase `.value`. Both work in queries but be consistent in new code.

2. **Session Generation is Async**: After program creation, sessions are generated in a background task. Don't expect immediate session content.

3. **Movement Pattern Interference**: Respect the pattern interference rules when manually creating or modifying sessions. The Optimizer enforces these, but manual database changes bypass them.

4. **JSON Fields**: Session content sections (warmup_json, main_json, etc.) are flexible schemas. Don't assume rigid structure—validate before accessing nested fields.

5. **Test Database**: Tests use SQLite in-memory, production uses PostgreSQL. Some features (like JSONB operators) aren't available in tests.

6. **Migrations**: Always review autogenerated migrations. Alembic can't detect everything (like enum value changes or complex column modifications).

7. **Authentication Required**: Most endpoints require valid JWT token. Test endpoints with proper Authorization header or use the test fixtures.

8. **Ollama Must Be Running**: Backend will fail health checks if Ollama isn't available. Always start it before backend.
