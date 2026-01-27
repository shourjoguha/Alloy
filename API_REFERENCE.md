# Alloy API Reference

> A comprehensive living document of the Coach ShowMeGains API system architecture, deep execution flows, and interdependencies.

---

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Authentication & Authorization](#authentication--authorization)
3. [Core Services Layer](#core-services-layer)
4. [API Endpoints by Domain](#api-endpoints-by-domain)
5. [Deep Execution Flows](#deep-execution-flows)
6. [Background Jobs & Side Effects](#background-jobs--side-effects)
7. [Data Models & Relationships](#data-models--relationships)
8. [Configuration & Settings](#configuration--settings)
9. [Known Ambiguities & Future Work](#known-ambiguities--future-work)

---

## System Architecture Overview

### Technology Stack

- **Framework**: FastAPI with async/await support
- **Database**: PostgreSQL with SQLAlchemy async ORM
- **LLM Integration**: Ollama (local) with SSE streaming support
- **Authentication**: Production-ready JWT authentication with bcrypt password hashing

### Application Lifecycle

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: Cleanup resources
    from app.llm import cleanup_llm_provider
    await cleanup_llm_provider()
```

**Critical Dependencies**:
- Database must be available at startup
- LLM provider must be accessible for session adaptation
- Admin token required for circuit admin endpoints

---

## Authentication & Authorization

### JWT-Based Authentication System

**Status**: Production-ready authentication implemented with JWT tokens and bcrypt password hashing.

**Authentication Endpoints**:
- `POST /auth/register` - User registration with JWT token issuance
- `POST /auth/login` - User authentication with JWT token issuance
- `GET /auth/verify-token` - Token verification and user info retrieval

**Authentication Flow**:
```python
# Registration
UserRegister(email, password, name)
    ↓
Check email uniqueness
    ↓
Hash password with bcrypt (salt + hash)
    ↓
Create User record
    ↓
Generate JWT token (sub: user_id, exp: expiration)
    ↓
Return TokenResponse(access_token, user_id)

# Login
UserLogin(email, password)
    ↓
Fetch user by email
    ↓
Verify password against bcrypt hash
    ↓
Check user.is_active status
    ↓
Generate JWT token
    ↓
Return TokenResponse(access_token, user_id)

# Token Verification
Bearer token in Authorization header
    ↓
Decode JWT with secret key
    ↓
Extract user_id from "sub" claim
    ↓
Validate expiration (exp claim)
    ↓
Fetch user from database
    ↓
Return UserResponse
```

**Password Security**:
- Hashing algorithm: bcrypt with salt generation
- Salt: Generated per-password using `bcrypt.gensalt()`
- Storage: `hashed_password` column (String 255)
- Verification: `bcrypt.checkpw()` with constant-time comparison

**JWT Token Details**:
- Algorithm: HS256
- Signing key: `settings.secret_key`
- Token payload structure:
  ```json
  {
    "sub": "user_id",  // Subject claim
    "exp": 1234567890  // Expiration timestamp (UTC)
  }
  ```
- Expiration: Configurable via `settings.access_token_expire_minutes` (default: 30 minutes)
- Token type: Bearer

**Authentication Models**:
- [UserRegister](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L18-22): email, password, name
- [UserLogin](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L25-28): email, password
- [TokenResponse](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L31-35): access_token, token_type, user_id
- [UserResponse](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L38-44): id, email, name, is_active

**User Model Authentication Fields**:
- `hashed_password` (String 255, nullable): Bcrypt password hash
- `is_active` (Boolean, default True): Account activation status
- `created_at` (DateTime, default now): Account creation timestamp

**Security Features**:
- Email uniqueness enforced at registration
- Password never stored in plain text
- Token expiration prevents indefinite access
- Account activation status checked on login
- Bearer token pattern for API requests

**Client Usage**:
```python
# Register
POST /auth/register
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "John Doe"
}
Response: {
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": 123
}

# Login
POST /auth/login
{
  "email": "user@example.com",
  "password": "securepassword"
}
Response: {
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": 123
}

# Verify Token
GET /auth/verify-token?token=eyJhbGciOiJIUzI1NiIs...
Response: {
  "id": 123,
  "email": "user@example.com",
  "name": "John Doe",
  "is_active": true
}

# Protected Request
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Authentication Files**:
- [auth.py](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py) - Authentication endpoints
- [jwt_utils.py](file:///Users/shourjosmac/Documents/alloy/app/security/jwt_utils.py) - JWT and password utilities
- [user.py](file:///Users/shourjosmac/Documents/alloy/app/models/user.py#L26-78) - User model with auth fields

### Admin Authorization

**Protected Endpoints**: Circuit admin routes

**Implementation**:
```python
async def require_admin(x_admin_token: str | None = Header(default=None)) -> bool:
    if settings.admin_api_token:
        if x_admin_token != settings.admin_api_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    else:
        if not settings.debug:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin features disabled")
    return True
```

**Header Required**: `X-Admin-Token: gainsly-admin-123`

**Admin Endpoints**:
- `GET /circuits/admin/{circuit_id}` - Get circuit with raw workout data
- `PUT /circuits/admin/{circuit_id}` - Update circuit exercises

---

## Core Services Layer

### Service Registry

Located in [app/services/__init__.py](file:///Users/shourjosmac/Documents/alloy/app/services/__init__.py)

| Service | Purpose | Key Methods |
|---------|---------|-------------|
| **ProgramService** | Generates 8-12 week programs with microcycle structure | `create_program()`, `generate_microcycles()` |
| **AdaptationService** | Real-time session adaptation based on user state | `adapt_session()`, `suggest_exercise_substitution()` |
| **InterferenceService** | Validates goal conflicts and adjusts parameters | `validate_goals()`, `get_conflicts()` |
| **MetricsService** | E1RM calculation and Pattern Strength Index | `calculate_e1rm()`, `get_pattern_exposures()` |
| **TimeEstimationService** | Calculates session durations by component | `estimate_session_time()` |
| **DeloadService** | Manages deload microcycle scheduling | `should_deload()`, `calculate_deload_intensity()` |

### ProgramService Deep Dive

**File**: [app/services/program.py](file:///Users/shourjosmac/Documents/alloy/app/services/program.py)

**Responsibilities**:
1. Validates program creation inputs (8-12 weeks, even numbers only)
2. Validates goal interference via InterferenceService
3. Fetches user profile for advanced preferences
4. Resolves split template from preferences or defaults to HYBRID
5. Determines progression style based on experience level
6. Generates microcycles with appropriate intensity profiles
7. Creates session templates with optional sections

**Validation Rules**:
```python
# Week count validation
if not (8 <= request.duration_weeks <= 12):
    raise ValueError("Program must be 8-12 weeks")
if request.duration_weeks % 2 != 0:
    raise ValueError("Program must be an even number of weeks")

# Goal count validation
if not (1 <= len(goals) <= 3):
    raise ValueError("1-3 goals required")

# Goal weights must sum to 10 (ten-dollar method)
# Enforced by database constraint: CheckConstraint('goal_weight_1 + goal_weight_2 + goal_weight_3 = 10')
```

**Goal Interference Detection**:
```python
# Pads active goals to 3 for validation
while len(validation_goals) < 3:
    validation_goals.append(active_goals[0])

# Validates pairwise conflicts
is_valid, warnings = await interference_service.validate_goals(
    db, validation_goals[0], validation_goals[1], validation_goals[2]
)
```

**Side Effect**: When validation fails with severity > 0.8, raises ValueError with conflict details.

### AdaptationService Deep Dive

**File**: [app/services/adaptation.py](file:///Users/shourjosmac/Documents/alloy/app/services/adaptation.py)

**Responsibilities**:
1. Parses movement rule constraints (forbidden moves, injury restrictions)
2. Adapts sessions based on soreness and recovery signals
3. Suggests exercise substitutions via LLM (MVP: returns empty list)
4. Manages optional session sections (warmup, finisher, conditioning)
5. Enforces user preferences (enjoyable activities weighting)

**Adaptation Logic Flow**:
```python
# For each exercise pattern in session:
for pattern in patterns:
    # 1. Check movement rules (forbidden exercises)
    forbidden = self._is_movement_forbidden(pattern.movement, rules)
    if forbidden:
        removed.append({"movement": pattern.movement, "reason": f"Forbidden: {forbidden}"})
        continue
    
    # 2. Check soreness conflicts
    soreness_dict = {s.body_part: s.level for s in request.soreness or []}
    affected_by_soreness = self._check_soreness_conflict(pattern, soreness_dict)
    if affected_by_soreness:
        removed.append({"movement": pattern.movement, "reason": f"Conflicts with soreness: {affected_by_soreness}"})
        continue
    
    # 3. Adjust sets/reps based on recovery
    adjusted = self._adjust_volume(pattern, recovery)
    adapted.append(adjusted)
```

**Recovery-Based Section Addition**:
```python
# Add optional sections based on recovery score
if recovery.get("recovery_score", 50) > 70:
    added_sections.append("conditioning")
if recovery.get("recovery_score", 50) < 40:
    added_sections.append("extra_warmup")
```

**Ambiguity Flag**: Exercise substitution via LLM is stubbed - returns empty suggestions.

### InterferenceService Deep Dive

**File**: [app/services/interference.py](file:///Users/shourjosmac/Documents/alloy/app/services/interference.py)

**Responsibilities**:
1. Loads heuristic configs from database
2. Validates goal pairs for conflicts
3. Returns conflict details with severity and adjustments

**Validation Logic**:
```python
# Check pairwise conflicts between unique goals
for i in range(n):
    for j in range(i + 1, n):
        g1, g2 = unique_goals[i], unique_goals[j]
        conflict_key = f"{g1.value}_{g2.value}"
        reverse_key = f"{g2.value}_{g1.value}"
        
        conflict_rule = rules.get(conflict_key) or rules.get(reverse_key)
        if conflict_rule:
            if conflict_rule.get("severity", 0) > 0.8:
                # Hard conflict - returns False
                return False, [f"Goals {g1.value} and {g2.value} conflict heavily"]
            else:
                warnings.append(f"Goals {g1.value} and {g2.value} have some conflict")
```

**Side Effect**: Hard conflicts (>0.8 severity) block program creation. Soft conflicts add warnings but allow creation.

### MetricsService Deep Dive

**File**: [app/services/metrics.py](file:///Users/shourjosmac/Documents/alloy/app/services/metrics.py)

**E1RM Calculation Formulas**:

| Formula | Calculation | Use Case |
|---------|-------------|----------|
| **Epley** | `weight × (1 + reps/30)` | Default, good for moderate reps |
| **Brzycki** | `weight × 36 / (37 - reps)` | Becomes undefined as reps → 37 |
| **Lombardi** | `weight × reps^0.10` | Conservative estimate |
| **O'Conner** | `weight × (1 + reps/40)` | Conservative, similar to Epley |

**RPE-Adjusted E1RM**:
```python
# Convert RPE to reps in reserve
rir = 10 - rpe if rpe <= 10 else 0
effective_reps = reps + rir
return MetricsService.calculate_e1rm(weight, effective_reps, formula)
```

**Side Effect**: RPE adjustment increases effective reps, resulting in higher E1RM estimate.

### TimeEstimationService Deep Dive

**File**: [app/services/time_estimation.py](file:///Users/shourjosmac/Documents/alloy/app/services/time_estimation.py)

**Time Breakdown Structure**:
```python
@dataclass
class SessionTimeBreakdown:
    warmup_minutes: int
    main_minutes: int
    accessory_minutes: int
    finisher_minutes: int
    cooldown_minutes: int
    total_minutes: int
```

**Set Execution Time by Rep Range**:
| Rep Range | Seconds per Set |
|-----------|-----------------|
| 1-3 | 15s |
| 4-6 | 25s |
| 7-10 | 35s |
| 11-15 | 45s |
| 16-20 | 55s |
| 21+ | 70s |

**Rest Seconds by Exercise Role**:
| Role | Rest Time |
|------|-----------|
| warmup | 30s |
| main (strength) | 180s |
| main (hypertrophy) | 90s |
| main (endurance) | 45s |
| accessory | 60s |
| skill | 90s |
| finisher | 30s |
| cooldown | 15s |

**Special Adjustments**:
- Superset rest: 50% reduction
- Circuit rounds: 60s between rounds
- Default warmup: 5 min base + 1 min per exercise
- Default cooldown: 5 min base + 1 min per stretch

---

## API Endpoints by Domain

### Programs Domain

**Router**: `/programs`

#### POST /programs

**Purpose**: Create a new 8-12 week training program

**Request Body**: [ProgramCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/program.py)
```python
{
  "goals": [{"goal": "STRENGTH", "weight": 5}, ...],  # 1-3 goals, weights sum to 10
  "duration_weeks": 8,  # 8-12, even numbers only
  "split_template": "HYBRID",
  "progression_style": "DOUBLE_PROGRESSION",
  "persona_tone": "SUPPORTIVE",
  "persona_aggression": "BALANCED"
}
```

**Deep Execution Flow**:
1. Validates week count (8-12, even)
2. Validates goal count (1-3)
3. Pads goals to 3 if needed (with 0-weight dummy)
4. Validates goal interference via InterferenceService
5. Fetches user profile for advanced preferences
6. Resolves split template (from prefs or defaults to HYBRID)
7. Determines progression style (from request or experience level)
8. Calls ProgramService.create_program()
9. **SIDE EFFECT**: Triggers background task `program_service.generate_active_microcycle_sessions`
10. Returns created program with microcycles

**Dependencies**:
- User must exist (id=1 in MVP)
- Split template must be valid enum value
- Goals must not have hard conflicts (>0.8 severity)

**Side Effects**:
- Background session generation (async, non-blocking)
- Database inserts: Program, Microcycles, Sessions, SessionExercises

#### GET /programs

**Purpose**: List all programs for current user

**Response**: List of [ProgramResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/program.py)

**Deep Execution Flow**:
1. Queries programs by user_id
2. For each program, calls TimeEstimationService.estimate_session_time()
3. Returns enriched programs with duration estimates

**Side Effects**: None (read-only)

#### GET /programs/{program_id}

**Purpose**: Get detailed program information

**Response**: [ProgramResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/program.py)

**Deep Execution Flow**:
1. Fetches program by id and user_id
2. Calls TimeEstimationService.estimate_session_time()
3. Returns enriched program

**Side Effects**: None (read-only)

#### DELETE /programs/{program_id}

**Purpose**: Delete a program

**Deep Execution Flow**:
1. Fetches program by id and user_id
2. Cascade deletes: Microcycles, Sessions, SessionExercises
3. Returns deleted program

**Side Effects**:
- Database cascade deletes all related records

#### POST /programs/{program_id}/microcycles/generate-next

**Purpose**: Generate the next microcycle in a program

**Response**: [MicrocycleResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/program.py)

**Deep Execution Flow**:
1. Fetches program by id and user_id
2. Determines if deload needed (based on deload_every_n_microcycles)
3. Creates new microcycle with appropriate status (PLANNED or DELOAD)
4. **AMBIGUITY FLAG**: TODO - Generate sessions using LLM (currently only creates microcycle structure)
5. Returns created microcycle

**Dependencies**:
- Previous microcycle must exist
- Program must be active

**Side Effects**:
- Database insert: Microcycle
- **INCOMPLETE**: Session generation not yet implemented

#### GET /programs/{program_id}/microcycles/{microcycle_id}/sessions/{session_id}

**Purpose**: Get session details with time breakdown

**Response**: [SessionResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/program.py)

**Deep Execution Flow**:
1. Fetches session by id, microcycle_id, program_id, user_id
2. Calls TimeEstimationService.estimate_session_time()
3. Returns enriched session with time breakdown

**Side Effects**: None (read-only)

### Daily Planning Domain

**Router**: `/days`

#### GET /days/{target_date}/plan

**Purpose**: Get the daily workout plan for a specific date

**Response**: [DailyPlanResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/daily.py)

**Deep Execution Flow**:
1. Fetches active program for user
2. Finds session scheduled for target_date
3. **Rest Day Detection**: If no session found, returns rest day
4. Calls TimeEstimationService.estimate_session_time()
5. Returns daily plan or rest day response

**Dependencies**:
- Active program must exist
- Session must be scheduled for target_date

**Side Effects**: None (read-only)

#### POST /days/{target_date}/adapt

**Purpose**: Adapt a session based on user state (non-streaming)

**Request Body**: [AdaptationRequest](file:///Users/shourjosmac/Documents/alloy/app/schemas/daily.py)
```python
{
  "soreness": [{"body_part": "CHEST", "level": 3}],
  "recovery_signal": "POOR",
  "notes": "Feeling fatigued"
}
```

**Deep Execution Flow**:
1. Fetches session by date and user_id
2. Calls AdaptationService.adapt_session()
3. Applies movement rules, soreness constraints, recovery adjustments
4. Returns adaptation results (adapted/removed patterns, added sections)

**Dependencies**:
- Session must exist for target_date
- User movement rules must be loaded

**Side Effects**:
- Creates ConversationThread and ConversationTurn records for LLM context
- Database inserts: ConversationThread, ConversationTurn

#### POST /days/{target_date}/adapt/stream

**Purpose**: Adapt a session with real-time LLM streaming (SSE)

**Request Body**: [AdaptationRequest](file:///Users/shourjosmac/Documents/alloy/app/schemas/daily.py)

**Response**: `text/event-stream` (Server-Sent Events)

**Deep Execution Flow**:
1. Fetches session by date and user_id
2. Builds LLM prompt with:
   - Session context (exercises, sets, reps)
   - User state (soreness, recovery, notes)
   - Movement rules and preferences
3. Initiates SSE stream
4. For each LLM chunk:
   - Accumulates full content
   - Sends SSE event: `data: {"content": "...", "done": false}`
5. On completion:
   - Sends final SSE event: `data: {"content": "...", "done": true}`
   - Updates ConversationThread with final content

**SSE Event Format**:
```json
data: {"content": "Here's your adapted session...", "done": false}

data: {"content": "...", "done": true}
```

**Dependencies**:
- LLM provider must be available (Ollama at localhost:11434)
- Session must exist for target_date
- Ollama model must be running: `gemma3:4b`

**Side Effects**:
- Creates ConversationThread and ConversationTurn records
- Streams response to client (real-time)
- Updates ConversationThread.final_content on completion

**Critical Path**: LLM timeout is set to 1100s (18+ minutes) for local generation.

#### POST /days/{target_date}/accept

**Purpose**: Accept the adapted plan and finalize conversation

**Request Body**: [AcceptPlanRequest](file:///Users/shourjosmac/Documents/alloy/app/schemas/daily.py)
```python
{
  "conversation_id": 123,
  "final_notes": "Looks good!"
}
```

**Deep Execution Flow**:
1. Fetches ConversationThread by id and user_id
2. Marks thread as accepted
3. Updates final notes
4. Returns accepted conversation

**Dependencies**:
- ConversationThread must exist
- Must be in editable state

**Side Effects**:
- Database update: ConversationThread.status = ACCEPTED

### Logging Domain

**Router**: `/logs`

#### POST /logs/workouts

**Purpose**: Log a completed workout with E1RM calculation

**Request Body**: [WorkoutLogCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)
```python
{
  "session_id": 123,
  "performed_at": "2026-01-25T10:00:00",
  "completed_exercises": [
    {
      "session_exercise_id": 456,
      "completed_sets": [
        {"set_number": 1, "weight": 100, "reps": 5, "rpe": 8}
      ]
    }
  ]
}
```

**Deep Execution Flow**:
1. Fetches session by id and user_id
2. For each completed exercise:
   - Fetches SessionExercise details
   - For each set:
     - Calculates E1RM using MetricsService.calculate_e1rm_from_rpe()
     - Formula from UserSettings.active_e1rm_formula (default: EPLEY)
3. Creates WorkoutLog record
4. **SIDE EFFECT**: Updates MuscleRecoveryState for affected body parts
5. Returns logged workout with calculated E1RMs

**Dependencies**:
- Session must exist
- SessionExercise must exist
- UserSettings must have e1rm_formula preference

**Side Effects**:
- Database insert: WorkoutLog
- Database update: MuscleRecoveryState (decrements recovery_level)
- Updates TopSetLog records for pattern tracking

#### POST /logs/custom-workout

**Purpose**: Log an ad-hoc workout (not from a scheduled session)

**Request Body**: [CustomWorkoutLogCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)

**Deep Execution Flow**:
1. Creates WorkoutLog without session_id
2. Creates SessionExercise records for custom exercises
3. **SIDE EFFECT**: Updates MuscleRecoveryState for affected body parts
4. Returns logged workout

**Side Effects**:
- Database insert: WorkoutLog, SessionExercise
- Database update: MuscleRecoveryState

#### POST /logs/soreness

**Purpose**: Log soreness levels for body parts

**Request Body**: [SorenessLogCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)
```python
{
  "logged_at": "2026-01-25T10:00:00",
  "soreness_entries": [
    {"body_part": "CHEST", "level": 3},
    {"body_part": "QUADS", "level": 2}
  ]
}
```

**Deep Execution Flow**:
1. Creates SorenessLog records
2. **SIDE EFFECT**: Updates MuscleRecoveryState for each body part
   - Sets recovery_level to 10 - soreness_level
   - Updates last_updated_at timestamp
3. Returns logged soreness

**Side Effects**:
- Database insert: SorenessLog
- Database update: MuscleRecoveryState

#### GET /logs/muscle-recovery

**Purpose**: Get current muscle recovery states with decay applied

**Response**: List of [MuscleRecoveryStateResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)

**Deep Execution Flow**:
1. Fetches all MuscleRecoveryState records for user
2. For each state:
   - Calculates hours since last update: `(now - last_updated_at).total_seconds() / 3600`
   - Calculates decay points: `int(hours_since_update / 10)`
   - Applies decay: `max(0, recovery_level - decay_points)`
3. Returns decayed recovery states

**Decay Formula**: 1 point of recovery lost per 10 hours

**Example**:
- Recovery level: 7 at 10:00 AM
- Current time: 8:00 PM (10 hours later)
- Decay: 1 point
- Result: 6

**Side Effects**: None (read-only, decay is calculated in memory)

#### POST /logs/recovery-signal

**Purpose**: Log a recovery signal (sleep, stress, nutrition)

**Request Body**: [RecoverySignalCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)

**Deep Execution Flow**:
1. Creates RecoverySignal record
2. Returns logged signal

**Side Effects**:
- Database insert: RecoverySignal

### Settings Domain

**Router**: `/settings`

#### GET /settings

**Purpose**: Get user settings

**Response**: [UserSettingsResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/settings.py)

**Deep Execution Flow**:
1. Fetches UserSettings by user_id
2. Returns settings

**Side Effects**: None (read-only)

#### PUT /settings

**Purpose**: Update user settings

**Request Body**: [UserSettingsUpdate](file:///Users/shourjosmac/Documents/alloy/app/schemas/settings.py)

**Deep Execution Flow**:
1. Fetches UserSettings by user_id
2. Updates fields (e1rm_formula, use_metric, etc.)
3. Commits changes
4. Returns updated settings

**Side Effects**:
- Database update: UserSettings

#### GET /settings/profile

**Purpose**: Get user profile with advanced preferences

**Response**: [UserProfileResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/settings.py)

**Deep Execution Flow**:
1. Fetches UserProfile by user_id
2. Returns profile with:
   - Basic info (name, email, experience_level)
   - Advanced preferences (discipline_preferences, scheduling_preferences)
   - Persona settings

**Side Effects**: None (read-only)

#### PUT /settings/profile

**Purpose**: Update user profile

**Request Body**: [UserProfileUpdate](file:///Users/shourjosmac/Documents/alloy/app/schemas/settings.py)

**Deep Execution Flow**:
1. Fetches UserProfile by user_id
2. Updates fields
3. Commits changes
4. Returns updated profile

**Side Effects**:
- Database update: UserProfile

### Circuits Domain

**Router**: `/circuits`

#### GET /circuits

**Purpose**: List circuit templates with enriched movement names

**Query Params**:
- `circuit_type` (optional): Filter by CircuitType enum

**Response**: List of [CircuitTemplateResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/circuit.py)

**Deep Execution Flow**:
1. Queries CircuitTemplate records
2. Filters by circuit_type if provided
3. **Enrichment**: Fetches Movement names for all movement_ids in exercises_json
4. Mutates exercises_json in-memory to add movement_name fields
5. Returns enriched circuits

**Side Effects**: None (read-only, in-memory enrichment)

**Ambiguity Flag**: exercises_json mutation may mark SQLAlchemy objects as dirty, but changes are not persisted.

#### GET /circuits/{circuit_id}

**Purpose**: Get single circuit template with enriched movement names

**Response**: [CircuitTemplateResponse](file:///Users/shourjosmac/Documents/alloy/app/schemas/circuit.py)

**Deep Execution Flow**:
1. Fetches CircuitTemplate by id
2. Enriches exercises_json with movement names
3. Returns enriched circuit

**Side Effects**: None (read-only)

#### GET /circuits/admin/{circuit_id}

**Purpose**: Get circuit with raw workout data (admin only)

**Headers Required**: `X-Admin-Token: gainsly-admin-123`

**Response**: [CircuitTemplateAdminDetail](file:///Users/shourjosmac/Documents/alloy/app/schemas/circuit.py)

**Deep Execution Flow**:
1. Validates admin token via require_admin()
2. Fetches CircuitTemplate by id
3. Enriches exercises_json with movement names
4. **SIDE EFFECT**: Loads raw_workout from seed_data/scraped_circuits.json
5. Returns circuit with raw_workout field

**Dependencies**:
- Admin token must match settings.admin_api_token
- seed_data/scraped_circuits.json must exist

**Side Effects**:
- File read: seed_data/scraped_circuits.json

#### PUT /circuits/admin/{circuit_id}

**Purpose**: Update circuit exercises (admin only)

**Headers Required**: `X-Admin-Token: gainsly-admin-123`

**Request Body**: [CircuitTemplateUpdate](file:///Users/shourjosmac/Documents/alloy/app/schemas/circuit.py)

**Deep Execution Flow**:
1. Validates admin token
2. Fetches CircuitTemplate by id
3. Updates exercises_json
4. Commits changes
5. Returns updated circuit

**Side Effects**:
- Database update: CircuitTemplate.exercises_json

### Activities Domain

**Router**: `/activities`

#### GET /activities/definitions

**Purpose**: List all activity definitions

**Response**: List of [ActivityDefinition](file:///Users/shourjosmac/Documents/alloy/app/models/program.py)

**Deep Execution Flow**:
1. Queries all ActivityDefinition records
2. Returns list

**Side Effects**: None (read-only)

#### POST /activities/log

**Purpose**: Log an activity instance (running, swimming, etc.)

**Request Body**: [ActivityInstanceCreate](file:///Users/shourjosmac/Documents/alloy/app/schemas/logging.py)
```python
{
  "activity_definition_id": 1,
  "activity_name": "Morning Run",
  "duration_minutes": 30,
  "distance_km": 5.0,
  "notes": "Felt great",
  "perceived_difficulty": 3,
  "enjoyment_rating": 5,
  "performed_start": "2026-01-25T06:00:00"
}
```

**Deep Execution Flow**:
1. Creates ActivityInstance record
2. Converts duration_minutes to duration_seconds
3. Sets source to ActivitySource.MANUAL
4. Commits changes
5. Returns logged activity

**Side Effects**:
- Database insert: ActivityInstance

---

## Deep Execution Flows

### Program Creation Flow

```
Client Request
    ↓
POST /programs
    ↓
Validate: 8-12 weeks, even numbers
    ↓
Validate: 1-3 goals, weights sum to 10
    ↓
Pad goals to 3 (if needed)
    ↓
InterferenceService.validate_goals()
    ├─ Load heuristic configs from DB
    ├─ Check pairwise goal conflicts
    └─ Return (is_valid, warnings)
    ↓
If !is_valid: Raise ValueError
    ↓
Fetch UserProfile (discipline_preferences, scheduling_preferences)
    ↓
Resolve split_template
    ├─ From user preferences (if set)
    └─ Default: HYBRID
    ↓
Resolve progression_style
    ├─ From request (if provided)
    └─ From experience_level:
        ├─ Beginner → SINGLE_PROGRESSION
        ├─ Intermediate → DOUBLE_PROGRESSION
        └─ Advanced/Expert → WAVE_LOADING
    ↓
ProgramService.create_program()
    ├─ Create Program record
    ├─ Generate microcycles (8-12 weeks / preferred length)
    ├─ Generate session templates for each microcycle
    └─ Apply discipline mixing rules
    ↓
SIDE EFFECT: Background task
program_service.generate_active_microcycle_sessions()
    ├─ Fetch first microcycle
    ├─ Generate sessions for microcycle
    └─ Apply movement constraints
    ↓
Return ProgramResponse with duration estimates
```

### Daily Session Adaptation Flow (Streaming)

```
Client Request
    ↓
POST /days/{target_date}/adapt/stream
    ↓
Fetch Session by date and user_id
    ↓
Build LLM Prompt:
    ├─ Session context (exercises, sets, reps)
    ├─ User state (soreness, recovery_signal, notes)
    ├─ Movement rules (forbidden, injury restrictions)
    └─ User preferences (enjoyable activities)
    ↓
Create ConversationThread record
    ↓
Initiate SSE Stream
    ↓
For each LLM chunk:
    ├─ Accumulate full_content
    ├─ Send SSE: {"content": "...", "done": false}
    └─ Continue streaming
    ↓
On LLM completion:
    ├─ Send final SSE: {"content": "...", "done": true}
    ├─ Update ConversationThread.final_content
    └─ Close stream
    ↓
Client receives real-time updates
```

### Muscle Recovery Decay Flow

```
Client Request
    ↓
GET /logs/muscle-recovery
    ↓
Fetch all MuscleRecoveryState for user
    ↓
For each state:
    ├─ Calculate hours_since_update = (now - last_updated_at).total_seconds() / 3600
    ├─ Calculate decay_points = int(hours_since_update / 10)
    ├─ Apply decay: decayed_level = max(0, recovery_level - decay_points)
    └─ Return decayed state
    ↓
Example:
    ├─ Recovery level: 7 at 10:00 AM
    ├─ Current time: 8:00 PM (10 hours later)
    ├─ Decay: 1 point
    └─ Result: 6
```

### E1RM Calculation Flow

```
Client logs workout
    ↓
For each completed set:
    ├─ Fetch UserSettings.active_e1rm_formula (default: EPLEY)
    ├─ If RPE provided:
    │   ├─ Calculate RIR = 10 - RPE
    │   ├─ Calculate effective_reps = reps + RIR
    │   └─ calculate_e1rm(weight, effective_reps, formula)
    └─ Else:
        └─ calculate_e1rm(weight, reps, formula)
    ↓
Formula Examples:
    ├─ Epley: weight × (1 + reps/30)
    ├─ Brzycki: weight × 36 / (37 - reps)
    ├─ Lombardi: weight × reps^0.10
    └─ O'Conner: weight × (1 + reps/40)
    ↓
Store E1RM in WorkoutLog
    ↓
Update TopSetLog for pattern tracking
```

---

## Background Jobs & Side Effects

### Background Task: Program Session Generation

**Trigger**: POST /programs (after program creation)

**Implementation**: `program_service.generate_active_microcycle_sessions()`

**Execution**: Async, non-blocking

**Side Effects**:
- Generates Session records for the first microcycle
- Generates SessionExercise records for each session
- Applies movement constraints and interference rules

**Status**: Implemented and functional

**Ambiguity Flag**: Similar background task for subsequent microcycles may not be fully implemented.

### Side Effect: Muscle Recovery State Updates

**Triggers**:
- POST /logs/workouts
- POST /logs/custom-workout
- POST /logs/soreness

**Effect**:
- Decrements recovery_level based on workout intensity
- Resets recovery_level based on soreness (10 - soreness_level)
- Updates last_updated_at timestamp

**Decay**: Calculated in-memory on GET requests (1 point per 10 hours)

### Side Effect: Conversation Thread Management

**Triggers**:
- POST /days/{target_date}/adapt
- POST /days/{target_date}/adapt/stream
- POST /days/{target_date}/accept

**Effect**:
- Creates ConversationThread for each adaptation session
- Creates ConversationTurn for each LLM interaction
- Updates thread status and final_content

### Side Effect: E1RM Pattern Tracking

**Trigger**: POST /logs/workouts

**Effect**:
- Updates TopSetLog records for each movement pattern
- Tracks personal bests and pattern exposures
- Used for progressive overload calculations

---

## Data Models & Relationships

### Core Model Hierarchy

```
User
├── UserProfile (1:1)
├── UserSettings (1:1)
├── UserMovementRule (1:N)
├── UserEnjoyableActivity (1:N)
├── Program (1:N)
│   ├── Microcycle (1:N)
│   │   ├── Session (1:N)
│   │   │   ├── SessionExercise (1:N)
│   │   │   └── PatternExposure (1:N)
│   │   └── ...
│   ├── ProgramDiscipline (1:N)
│   └── UserGoal (1:N)
├── WorkoutLog (1:N)
│   └── ...
├── SorenessLog (1:N)
├── RecoverySignal (1:N)
├── MuscleRecoveryState (1:N)
├── ConversationThread (1:N)
│   └── ConversationTurn (1:N)
├── ActivityInstance (1:N)
├── UserSkill (1:N)
├── UserInjury (1:N)
├── MacroCycle (1:N)
└── ...
```

### Key Models

**User**: Core user profile with experience level and persona settings
- **id**: Primary key, auto-increment
- **name**: String(100), nullable - User display name
- **email**: String(255), unique, nullable - User email address
- **experience_level**: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT
- **persona_tone**: DRILL_SERGEANT, SUPPORTIVE, ANALYTICAL, MOTIVATIONAL, MINIMALIST
- **persona_aggression**: CONSERVATIVE, MODERATE_CONSERVATIVE, BALANCED, MODERATE_AGGRESSIVE, AGGRESSIVE
- **hashed_password**: String(255), nullable - Bcrypt password hash
- **is_active**: Boolean, default True - Account activation status
- **created_at**: DateTime, default now - Account creation timestamp

**Program**: 8-12 week training program
- **duration_weeks**: 8-12 (even numbers only)
- **split_template**: HYBRID, UPPER_LOWER, PPL, FULL_BODY, etc.
- **progression_style**: SINGLE, DOUBLE, WAVE_LOADING
- **deload_every_n_microcycles**: Default 4
- **goals**: 3 goals with weights summing to 10 (ten-dollar method)

**Microcycle**: 7-14 day training block
- **length_days**: 7-14
- **sequence_number**: 1, 2, 3...
- **status**: PLANNED, ACTIVE, COMPLETED
- **is_deload**: Boolean flag

**Session**: Single workout day
- **session_type**: STRENGTH, HYPERTROPHY, ENDURANCE, MOBILITY, etc.
- **Optional sections**: warmup, main, accessory, finisher, cooldown
- Each section is optional and may be empty

**SessionExercise**: Exercise within a session
- **exercise_role**: WARMUP, MAIN, ACCESSORY, FINISHER, COOLDOWN, SKILL
- **pattern**: Movement pattern (PUSH, PULL, SQUAT, HINGE, etc.)
- **sets**: List of set specifications (reps, rpe, rest_seconds)

**WorkoutLog**: Completed workout record
- **session_id**: Optional (null for custom workouts)
- **performed_at**: Timestamp
- **completed_exercises**: List of completed sets with E1RM calculations

**SorenessLog**: User-reported soreness
- **body_part**: CHEST, BACK, LEGS, SHOULDERS, ARMS, CORE
- **level**: 1-10 scale

**MuscleRecoveryState**: Per-body-part recovery tracking
- **body_part**: Same as soreness
- **recovery_level**: 0-10 scale (10 = fully recovered)
- **last_updated_at**: Timestamp for decay calculation

**ConversationThread**: LLM conversation context
- **session_id**: Related session
- **status**: IN_PROGRESS, ACCEPTED, REJECTED
- **final_content**: Final LLM response

**ConversationTurn**: Individual LLM interaction
- **thread_id**: Parent conversation
- **role**: USER, ASSISTANT
- **content**: Message content

---

## Configuration & Settings

### Application Settings

**File**: [app/config/settings.py](file:///Users/shourjosmac/Documents/alloy/app/config/settings.py)

**Key Settings**:

| Setting | Default | Description |
|---------|---------|-------------|
| `app_name` | "Coach ShowMeGains" | Application name |
| `debug` | `true` | Debug mode |
| `database_url` | PostgreSQL connection string | Database connection |
| `ollama_base_url` | "http://localhost:11434" | LLM endpoint |
| `ollama_model` | "gemma3:4b" | LLM model |
| `ollama_timeout` | 1100.0 | LLM timeout (seconds) |
| `default_e1rm_formula` | "epley" | Default E1RM formula |
| `soreness_decay_hours` | 10 | Hours for 1 point decay |
| `admin_api_token` | "gainsly-admin-123" | Admin auth token |
| `secret_key` | Configured secret | JWT signing key for token generation/validation |
| `access_token_expire_minutes` | 30 | JWT token expiration time in minutes |
| `algorithm` | "HS256" | JWT signing algorithm |

### Database Constraints

**Program**:
```sql
CHECK (duration_weeks >= 8 AND duration_weeks <= 12)
CHECK (goal_weight_1 + goal_weight_2 + goal_weight_3 = 10)
CHECK (goal_weight_1 >= 0 AND goal_weight_2 >= 0 AND goal_weight_3 >= 0)
```

**Microcycle**:
```sql
CHECK (length_days >= 7 AND length_days <= 14)
```

### CORS Configuration

**Allowed Origins**: `*` (configure for production)

**Allowed Methods**: `*`

**Allowed Headers**: `*`

---

## Known Ambiguities & Future Work

### Critical Ambiguities

1. **Session Generation for Microcycles**
   - **Location**: `POST /programs/{program_id}/microcycles/generate-next`
   - **Issue**: TODO comment indicates LLM session generation not implemented
   - **Impact**: Only microcycle structure is created, sessions are empty
   - **Status**: Needs implementation

2. **Exercise Substitution via LLM**
   - **Location**: `AdaptationService.suggest_exercise_substitution()`
   - **Issue**: Returns empty suggestions list
   - **Impact**: No alternative exercises suggested when movements are forbidden
   - **Status**: Stub implementation

3. **Circuit exercises_json Mutation**
   - **Location**: `GET /circuits` and `GET /circuits/{circuit_id}`
   - **Issue**: In-memory mutation may mark SQLAlchemy objects as dirty
   - **Impact**: Changes are not persisted, but may cause unexpected behavior
   - **Status**: Documented, but not critical (read-only endpoints)

### Future Work

1. **Background Task for Subsequent Microcycles**
   - Generate sessions for microcycles 2, 3, 4...
   - Currently only first microcycle gets sessions

2. **LLM Streaming Error Handling**
   - What happens if LLM provider is unavailable?
   - Fallback mechanism needed

3. **Muscle Recovery Persistence**
   - Currently calculated in-memory on GET requests
   - Consider persisting decayed values

4. **Pattern Strength Index Calculation**
   - MetricsService has `get_pattern_exposures()` but usage unclear
   - May need integration with program generation

5. **Circuit Template Validation**
   - No validation of exercises_json structure
   - May cause runtime errors if malformed

6. **Activity Definition Schema**
   - ActivityDefinition model exists but schema not documented
   - May need standardization

---

## Appendix

### Enum Values

**Goal**: STRENGTH, HYPERTROPHY, ENDURANCE, MOBILITY, SKILL, FAT_LOSS

**SplitTemplate**: HYBRID, UPPER_LOWER, PPL, FULL_BODY, BODY_PART_SPLIT, PUSH_PULL

**ProgressionStyle**: SINGLE_PROGRESSION, DOUBLE_PROGRESSION, WAVE_LOADING, BLOCK_PERIODIZATION

**SessionType**: STRENGTH, HYPERTROPHY, ENDURANCE, MOBILITY, SKILL, CONDITIONING, RECOVERY

**MicrocycleStatus**: PLANNED, ACTIVE, COMPLETED, CANCELLED

**ExerciseRole**: WARMUP, MAIN, ACCESSORY, FINISHER, COOLDOWN, SKILL

**E1RMFormula**: EPLEY, BRZYCKI, LOMBARDI, OCONNER

**ExperienceLevel**: BEGINNER, INTERMEDIATE, ADVANCED, EXPERT

**PersonaTone**: SUPPORTIVE, NEUTRAL, DIRECT

**PersonaAggression**: CONSERVATIVE, BALANCED, AGGRESSIVE

**CircuitType**: METCON, EMOM, AMRAP, TABATA, COMPLEX, CIRCUIT

**ActivitySource**: MANUAL, SCHEDULED, GENERATED

### Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request (validation error) |
| 403 | Forbidden (admin access required) |
| 404 | Not Found (resource not found) |
| 422 | Unprocessable Entity (schema validation) |

### Health Check Endpoints

**GET /health**
- Returns: `{"status": "healthy", "app": "Coach ShowMeGains"}`

**GET /health/llm**
- Returns: `{"status": "healthy"|"unhealthy", "provider": "ollama", "model": "gemma3:4b"}`
- Checks LLM provider availability

---

## Strategic Recommendations

Based on comprehensive code audit (Reality Check, Weight Check, Quality Check), prioritize the following improvements:

### Critical Path (LLM Integration)

**Priority 1: LLM-Based Session Generation**
- **Location**: [programs.py:472](file:///Users/shourjosmac/Documents/alloy/app/api/routes/programs.py#L472) - `generate_next_microcycle` endpoint
- **Issue**: TODO comment for LLM session generation currently unimplemented
- **Impact**: Core system functionality depends on this - sessions are created without LLM intelligence
- **Recommendation**: Implement LLM-powered session generation using the existing context collection infrastructure in `session_generator.py`
- **Dependencies**: Requires completion of LLM integration in `session_generator.py:generate_session_exercises_offline`

**Priority 2: LLM-Based Exercise Substitution**
- **Location**: [adaptation.py:78-99](file:///Users/shourjosmac/Documents/alloy/app/services/adaptation.py#L78-99) - `suggest_exercise_substitution` method
- **Issue**: Returns empty list with "not yet implemented" message
- **Impact**: Users cannot get intelligent exercise substitutions for injuries/dislikes
- **Recommendation**: Integrate LLM to suggest alternative exercises based on movement patterns, goals, and constraints

### Performance Optimization

**Priority 3: Bulk SessionExercise Operations**
- **Location**: [session_generator.py:430-584](file:////Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L430-584) - `_save_session_exercises` method
- **Issue**: Exercises added one-by-one with individual `db.add()` calls
- **Impact**: N+1 query problem for sessions with many exercises
- **Recommendation**: Use `bulk_save_objects()` or `execute_many()` for batch inserts
- **Code Reference**: Replace lines 521-531 pattern with batch operation

**Priority 4: PostgreSQL UPSERT for Session Exercises**
- **Location**: Same as above
- **Issue**: Current approach: DELETE all exercises + INSERT all exercises (2 operations)
- **Impact**: Unnecessary I/O overhead, potential foreign key cascading issues
- **Recommendation**: Use `INSERT ... ON CONFLICT (session_id, order_in_session) DO UPDATE` for atomic upserts

**Priority 5: Raw SQL Sequence Reset Race Condition**
- **Location**: [session_generator.py:436-438](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L436-438)
- **Issue**: `setval` sequence reset between delete and insert operations
- **Impact**: Race condition in concurrent session generation scenarios
- **Recommendation**: Remove sequence reset (PostgreSQL handles sequences automatically) or use transaction advisory locks

### Safety & Reliability

**Priority 6: Error Handling in Session Generation**
- **Location**: [session_generator.py:418-423](file:////Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L418-423)
- **Issue**: Swallowed exceptions in draft generation with warning log only
- **Impact**: Silent failures may produce low-quality sessions
- **Recommendation**: Implement retry logic with exponential backoff, fallback to deterministic algorithms after N failures

**Priority 7: Movement Lookup Validation**
- **Location**: [session_generator.py:513-515](file:///Users/shourjosmac/Documents/alloy/app/services/session_generator.py#L513-515)
- **Issue**: Missing movements logged but skipped without user notification
- **Impact**: Sessions may have fewer exercises than intended
- **Recommendation**: Collect missing movements in list, return validation error if critical threshold exceeded

**Priority 8: Soreness Conflict Detection Enhancement**
- **Location**: [adaptation.py:257-269](file:///Users/shourjosmac/Documents/alloy/app/services/adaptation.py#L257-269) - `_check_soreness_conflict` method
- **Issue**: Simple string matching heuristic ("squat" contains "quads")
- **Impact**: False positives (missed conflicts) and false negatives (over-avoidance)
- **Recommendation**: Use `MovementMuscleMap` table for precise muscle-to-exercise mapping instead of name parsing

**Priority 9: Movement Rule Matching Inconsistency**
- **Location**: [adaptation.py:236-253](file:////Users/shourjosmac/Documents/alloy/app/services/adaptation.py#L236-253) - `_is_movement_forbidden` method
- **Issue**: Mixes ID-based and string-based matching
- **Impact**: Inconsistent rule application, potential bypass of hard_no rules
- **Recommendation**: Standardize on ID-based matching only, or add explicit string-to-ID lookup

### Code Cleanup

**Priority 10: Remove Orphaned Components**
- **Locations**:
  - [app/services/circuit_metrics.py](file:///Users/shourjosmac/Documents/alloy/app/services/circuit_metrics.py) - CircuitMetricsService (no imports)
  - [app/llm/embedding_provider.py](file:///Users/shourjosmac/Documents/alloy/app/llm/embedding_provider.py) - EmbeddingProvider (no imports)
  - [app/llm/optimization.py](file:///Users/shourjosmac/Documents/alloy/app/llm/optimization.py) - Optimization functions (no imports)
- **Issue**: Code bloat, maintenance overhead
- **Recommendation**: Delete if truly unused, or add to `__all__` exports if intended for future use

**Priority 11: Remove Unused Models**
- **Location**: [app/models/program.py](file:///Users/shourjosmac/Documents/alloy/app/models/program.py) - MacroCycle model
- **Issue**: No imports found in codebase
- **Recommendation**: Remove model or document intended use case

### Production Readiness

**Priority 12: Replace Hardcoded User ID**
- **Location**: [settings.py](file:///Users/shourjosmac/Documents/alloy/app/core/settings.py) - `default_user_id` setting
- **Issue**: MVP authentication uses hardcoded user ID
- **Impact**: Single-user system, not production-ready
- **Recommendation**: Implement OAuth 2.0 or JWT-based authentication with proper user context
- **Migration Path**: Keep `get_current_user_id()` signature, add `Authorization` header validation

**Priority 13: Implement Adherence Tracking**
- **Location**: [logs.py:871](file:////Users/shourjosmac/Documents/alloy/app/api/routes/logs.py#L871)
- **Issue**: TODO comment for adherence tracking
- **Impact**: No program completion metrics or engagement tracking
- **Recommendation**: Track session completion rates, streaks, and program adherence percentages

### Implementation Priority Matrix

| Priority | Task | Impact | Effort | Dependencies |
|----------|------|--------|--------|--------------|
| P1 | LLM session generation | Critical | High | LLM infrastructure |
| P2 | Exercise substitution | High | Medium | LLM infrastructure |
| P3 | Bulk SessionExercise ops | Medium | Low | None |
| P4 | PostgreSQL UPSERT | Medium | Low | None |
| P5 | Sequence reset removal | Low | Low | None |
| P6 | Error handling retry | High | Medium | Monitoring |
| P7 | Movement validation | Medium | Low | None |
| P8 | Soreness mapping fix | Medium | Medium | MovementMuscleMap |
| P9 | Rule matching fix | Medium | Low | None |
| P10 | Remove orphaned code | Low | Low | None |
| P11 | Remove unused models | Low | Low | Database migration |
| P12 | Auth implementation | Critical | High | User management |
| P13 | Adherence tracking | Medium | Medium | Logging infrastructure |

---

*Document Version: 1.1*  
*Last Updated: 2026-01-25*  
*Maintained by: API Documentation Agent*
