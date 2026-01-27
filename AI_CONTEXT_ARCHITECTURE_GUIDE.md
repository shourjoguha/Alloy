# AI Context & Architecture Guide

## 1. Architectural Philosophy

### The `movements` Table as Source of Truth

The **`movements`** table serves as the central "source of truth" for the entire Gainsly fitness platform's biomechanical knowledge graph. All exercise selection, session generation, and adaptation logic ultimately derives from this table and its constellation of related tables (`movement_muscle_map`, `movement_relationships`, `pattern_exposure`).

Think of a movement not as a simple row, but as a rich, multi-dimensional entity defined by:

| Dimension | Key Attributes |
|-----------|----------------|
| **Pattern** | squat, hinge, horizontal_push, vertical_push, horizontal_pull, vertical_pull, carry, core, lunge, rotation, plyometric, olympic, isolation, mobility, isometric, conditioning, cardio |
| **Region** | anterior_lower, posterior_lower, shoulder, anterior_upper, posterior_upper, full_body, lower_body, upper_body |
| **Primary Muscle** | quadriceps, hamstrings, glutes, calves, chest, lats, upper_back, rear_delts, front_delts, side_delts, biceps, triceps, forearms, core, obliques, lower_back, hip_flexors, adductors, full_body |
| **Mechanics** | cns_load, skill_level, compound, is_complex_lift, is_unilateral |
| **Metrics** | metric_type (reps, time, time_under_tension, distance), fatigue_factor, stimulus_factor, injury_risk_factor |

### The "Soft Enum" Convention

Gainsly employs a **"Soft Enum" Convention** that is critical to understand:

1. **Database Storage**: Many categorical fields store values as **Strings** (e.g., `movements.pattern` = `"horizontal_push"`). This provides flexibility for future schema evolution without requiring DDL changes.

2. **Application Enforcement**: The Python application code (specifically `app/models/enums.py`) defines strict `Enum` types that validate values at the application layer. This creates a dual-layer validation system.

3. **SQL Enum Columns**: Some tables use PostgreSQL ENUM types (e.g., `top_set_logs.pattern`, `pattern_exposures.pattern`) where the values are stored as UPPERCASE strings like `HORIZONTAL_PUSH`.

> **Instruction to Future Agent**: "Always assume valid values are defined in code (e.g., `enums.py`). Use provided lists as *examples* of the vocabulary, not exhaustive laws. If a better value exists conceptually, propose it."

The canonical enum values are:
- **MovementPattern**: squat, hinge, horizontal_push, vertical_push, horizontal_pull, vertical_pull, carry, core, lunge, rotation, plyometric, olympic, isolation, mobility, isometric, conditioning, cardio
- **PrimaryMuscle**: quadriceps, hamstrings, glutes, calves, chest, lats, upper_back, rear_delts, front_delts, side_delts, biceps, triceps, forearms, core, obliques, lower_back, hip_flexors, adductors, full_body
- **PrimaryRegion**: anterior_lower, posterior_lower, shoulder, anterior_upper, posterior_upper, full_body, lower_body, upper_body
- **CNSLoad**: very_low, low, moderate, high, very_high
- **SkillLevel**: beginner, intermediate, advanced, expert, elite
- **RelationshipType**: progression, regression, variation, antagonist, prep

---

## 2. The Biomechanical Data Model

### Movements: The Constellation of Attributes

A movement is defined not just by its name, but by a multidimensional constellation of biomechanical attributes that enable intelligent exercise selection and adaptation.

```
Movement
├── Pattern (Fundamental Movement Classification)
│   ├── Squat Pattern → Primary: quads, glutes; Region: anterior_lower/posterior_lower
│   ├── Hinge Pattern → Primary: hamstrings, glutes; Region: posterior_lower
│   ├── Push Patterns → Primary: chest, delts, triceps; Region: anterior_upper
│   ├── Pull Patterns → Primary: lats, upper_back, rear_delts; Region: posterior_upper
│   └── Carry/Core → Primary: core, forearms; Region: shoulder
│
├── Primary Region (Body Area Emphasis)
│   ├── Anterior Lower (quads-focused)
│   ├── Posterior Lower (hamstrings/glutes-focused)
│   ├── Anterior Upper (chest/delts-focused)
│   └── Posterior Upper (lats/upper_back-focused)
│
├── Primary Muscle + Secondary Muscles
│   └── Mapped via movement_muscle_map with roles
│
├── Mechanics (CNS Load & Complexity)
│   ├── cns_load: very_low → very_high (affects fatigue calculations)
│   ├── skill_level: beginner → elite (affects exercise selection)
│   ├── compound: Boolean (affects fatigue_factor)
│   └── is_complex_lift: Boolean (flags high-skill barbell lifts)
│
└── Fitness Function Metrics
    ├── fatigue_factor: Systemic fatigue cost multiplier
    ├── stimulus_factor: Hypertrophy stimulus multiplier
    └── injury_risk_factor: Base injury risk score
```

### Muscle Mapping Logic: Beyond "What Muscles"

The `movement_muscle_map` junction table does not merely track "what muscles are used" but captures **how** muscles are engaged:

| Role | Meaning | Example |
|------|---------|---------|
| **Prime Mover** | Primary agonist muscle generating force | Quads in Back Squat |
| **Synergist** | Assists the prime mover | Glutes in Back Squat |
| **Stabilizer** | Provides joint stability | Core in Overhead Press |
| **Antagonist** | Opposes the prime mover (eccentric loading) | Hamstrings in Leg Extensions |

The `magnitude` field (Float, default 1.0) provides nuanced muscle involvement scaling, enabling:
- Precise muscle-level fatigue tracking
- Targeted volume distribution calculations
- Intelligent exercise substitution based on muscle emphasis

### Movement Relationships: The Knowledge Graph

The `movement_relationships` table encodes the biomechanical knowledge graph, enabling intelligent exercise selection based on difficulty, equipment, and movement patterns:

| Relationship Type | Purpose | Example |
|-------------------|---------|---------|
| **progression** | Harder variant of same pattern | Barbell Squat → Overhead Squat |
| **regression** | Easier variant of same pattern | Dumbbell Press → Push-up |
| **variation** | Same pattern, different emphasis | Conventional Deadlift → Sumo Deadlift |
| **antagonist** | Opposing movement pattern | Bench Press ↔ Bent-over Row |
| **prep** | Prepares muscles for main movement | Band Pull-apart → Overhead Press |

The `severity` field (Float, default 0.5) quantifies interference between movements, enabling:
- Detection of pattern overlap in same session
- Optimization of exercise ordering
- Prevention of overuse injuries

### Directional Logic: Rules of Thumb

When reasoning about movements, use these biomechanical heuristics:

#### Pattern → Muscle Inference Rules
- **If movement is "horizontal_push"**: Likely involves **front_delts**, **side_delts**, **triceps**, **chest**
- **If movement is "vertical_push"**: Likely involves **side_delts**, **triceps**, **front_delts** (shoulder focus)
- **If movement is "horizontal_pull"**: Likely involves **lats**, **upper_back**, **rear_delts**, **biceps**
- **If movement is "vertical_pull"**: Likely involves **lats**, **biceps**, **lower_back**
- **If movement is "squat"**: Likely involves **quadriceps**, **glutes**, **adductors**, **core**
- **If movement is "hinge"**: Likely involves **hamstrings**, **glutes**, **lower_back**
- **If movement is "lunge"**: Likely involves **quadriceps**, **glutes**, **hip_flexors**, **adductors**
- **If movement is "core"**: Likely involves **core**, **obliques**, **lower_back**

#### CNS Load Inference Rules
- **If movement is "olympic"** or "plyometric": High CNS load (very_high, high)
- **If movement is "isometric"**: Variable CNS load (moderate, low)
- **If movement is "conditioning"** or "cardio": Low to moderate CNS load
- **If movement is "isolation"**: Very low CNS load

#### Equipment-Based Reasoning
- **If movement uses barbell and is compound**: High fatigue_factor, high CNS load
- **If movement is bodyweight**: Lower fatigue_factor, scalable via progression/regression
- **If movement is unilateral**: May require higher skill_level, lower absolute load

---

## 3. Inference Guidelines: Rules of Engagement for Autonomous Agents

When encountering gaps in data or needing to make biomechanical inferences, follow these guiding principles:

### 1. Infer from Physics

Use fundamental biomechanics to reason about muscle involvement when undefined:

| Pattern | Primary Muscles (Inference) | Secondary Muscles (Inference) |
|---------|---------------------------|------------------------------|
| horizontal_push | chest, front_delts, triceps | side_delts, core |
| vertical_push | side_delts, triceps | front_delts, upper_back, core |
| horizontal_pull | lats, upper_back, rear_delts | biceps, lower_back |
| vertical_pull | lats, biceps | rear_delts, lower_back, core |
| squat | quadriceps, glutes | hamstrings, adductors, core |
| hinge | hamstrings, glutes | lower_back, adductors |
| lunge | quadriceps, glutes | hamstrings, hip_flexors, core |
| carry | forearms, core | traps, rear_delts |
| core | core, obliques | lower_back |

**Example**: If a new movement has `pattern = "horizontal_push"` but undefined `primary_muscle`, infer `primary_muscle = "chest"` and add `front_delts`, `triceps` as secondary muscles.

### 2. Standardize Over Inventing

Prefer existing categorical tags and conventions:

- **Use existing pattern values** (`horizontal_push`, not `chest_press`)
- **Use existing muscle values** (`front_delts`, not `anterior_deltoid`)
- **Follow naming conventions** (snake_case for semantic values, UPPERCASE for DB enum values)

However, **stay open to new values** if the physics demand it:

- If a movement genuinely represents a new biomechanical pattern (e.g., `kettlebell_swing` has elements of hinge, ballistic, and conditioning), propose new patterns rather than force-fitting into existing categories.
- If a muscle is commonly referenced but not in the enum (e.g., `traps` vs `upper_back`), evaluate whether the distinction is biomechanically significant.

### 3. Consult the Application: Truth Hierarchy

When resolving conflicts or determining authoritative values, follow this hierarchy:

```
┌─────────────────────────────────────────┐
│  1. Codebase (app/models/enums.py)      │  ← Highest Authority
│     - Defines canonical enum values      │
│     - Application-level validation       │
│     - Semantic values (.value)           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  2. Database Schema (DDL)                │
│     - SQL enum types (UPPERCASE)         │
│     - Column definitions                 │
│     - Foreign key relationships          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  3. Current Data (actual values)         │
│     - What's actually stored in rows     │
│     - May contain legacy/outdated values │
│     - May reflect user-defined movements │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  4. General Knowledge                   │  ← Last Resort
│     - Biomechanics principles            │
│     - Exercise science                  │
│     - Coaching best practices            │
└─────────────────────────────────────────┘
```

**Example**: If the database contains `pattern = "dumbbell_press"` but `enums.py` only defines `horizontal_push`, trust the enum and map the data accordingly rather than inventing a new pattern.

### 4. Contextual Reasoning

When selecting exercises for a session, consider the full context:

- **User experience level**: Beginners get regressions; experts get progressions
- **User movement rules**: Respect `HARD_NO`, `HARD_YES`, `PREFERRED` constraints
- **Pattern exposure**: Avoid overexposure to same pattern (check `pattern_exposure`)
- **Movement relationships**: Avoid pairing antagonists in supersets
- **Fatigue state**: Respect `user_fatigue_state` and `recovery_signals`
- **Goals**: Align movement selection with program goals (`strength`, `hypertrophy`, etc.)

---

## 4. Key Table Hierarchy

The Gainsly database is organized around a core biomechanical knowledge graph with peripheral tables for user data, program planning, and analytics.

### Core Knowledge Graph (Biomechanics)

```
┌─────────────────────────────────────────────────────────────────┐
│                        movements                                │
│  Central reference table for all exercise movements           │
│  Contains: pattern, region, muscle, mechanics, fitness metrics │
└─────────────────────────────────────────────────────────────────┘
         │
         ├── many_to_many ────┬───┐
         │                    │   │
         ▼                    ▼   ▼
┌──────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│ movement_muscle  │  │ movement_equipment│  │ movement_tags    │
│       _map       │  │                   │  │                  │
│                  │  │ Junction table    │  │ Flexible tagging │
│ - movement_id    │  │ - movement_id     │  │ - movement_id    │
│ - muscle_id      │  │ - equipment_tag   │  │ - tag            │
│ - role (enum)    │  │                   │  │                  │
│ - magnitude      │  │                   │  │                  │
└──────────────────┘  └───────────────────┘  └──────────────────┘
         │
         │
         ▼
┌────────────────────┐
│     muscles        │
│  Reference table   │
│  for muscle groups │
│                    │
│ - name             │
│ - body_region      │
│ - description      │
└────────────────────┘
         │
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    movement_relationships                       │
│  Encodes biomechanical knowledge: progressions, regressions,    │
│  variations, antagonists, prep movements                        │
│                                                                 │
│  - movement_1_id (FK → movements)                               │
│  - movement_2_id (FK → movements)                               │
│  - relationship_type (enum: progression, regression, etc.)      │
│  - severity (Float)                                             │
└─────────────────────────────────────────────────────────────────┘
```

### User & Personalization Layer

```
┌───────────────────────────────────────────────────────────────────┐
│                         users                                     │
│  Core user account with authentication and preferences            │
│  - email, name, experience_level, persona_tone, persona_aggression│
│  - hashed_password (String 255, nullable) - Bcrypt hash     │
│  - is_active (Boolean, default True) - Account status       │
│  - created_at (DateTime, default now) - Account timestamp   │
└───────────────────────────────────────────────────────────────────┘
         │
         ├── 1:1 ────┬──────────────────┬──────────────────┬──────┐
         │           │                  │                  │      │
         ▼           ▼                  ▼                  ▼      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   user_settings  │  │ user_profiles    │  │ user_movement_   │
│                  │  │                  │  │      rules       │
│ - user_id        │  │ - user_id        │  │ - user_id        │
│ - e1rm_formula   │  │ - date_of_birth  │  │ - movement_id    │
│ - use_metric     │  │ - sex            │  │ - rule_type      │
│                  │  │ - height_cm      │  │ - cadence        │
└──────────────────┘  │ - JSON prefs     │  └──────────────────┘
                      └──────────────────┘
         │
         ├── 1:N ────┬──────────────────┬──────────────────┬──────┐
         │           │                  │                  │      │
         ▼           ▼                  ▼                  ▼      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  user_enjoyable_ │  │ user_injuries    │  │ user_skills      │
│   activities     │  │                  │  │                  │
│                  │  │ - user_id        │  │ - user_id        │
│ - user_id        │  │ - body_part      │  │ - discipline_id  │
│ - activity_type  │  │ - severity       │  │ - skill_level    │
│ - enjoyment_score│  │ - description    │  │ - interest_level │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### Program Planning & Session Generation

```
┌──────────────────┐      ┌──────────────────┐
│   macro_cycles   │◄─────│      users       │
│                  │      │                  │
│ - user_id        │      └──────────────────┘
│ - start_date     │              │
│ - end_date       │              ▼
└──────────────────┘      ┌──────────────────┐
         │                │     programs     │
         │                │                  │
         │                │ - user_id        │
         │                │ - macro_cycle_id │
         │                │ - goal_1/2/3     │
         │                │ - goal_weight_*  │
         │                │ - split_template │
         │                │ - progression_   │
         │                │   style          │
         │                └──────────────────┘
         │                        │
         │                        ▼
         │                ┌──────────────────┐
         │                │   microcycles    │
         │                │                  │
         │                │ - program_id     │
         │                │ - week_number    │
         │                │ - is_deload      │
         │                │ - intensity_%    │
         │                │ - volume_%       │
         │                └──────────────────┘
         │                        │
         │                        ▼
         │                ┌────────────────────────┐
         │                │     sessions           │
         │                │                        │
         │                │ - microcycle_id        │
         │                │ - date                 │
         │                │ - session_type         │
         │                │ - main_circuit_id      │
         │                │ - finisher_circuit_id  │
         │                └────────────────────────┘
         │                        │
         │                        ▼
         │                ┌───────────────────┐
         │                │session_exercises  │
         │                │                   │
         │                │ - session_id      │
         │                │ - movement_id     │
         │                │ - role (warmup,   │
         │                │   main, etc.)     │
         │                │ - order_in_session│
         │                │ - superset_group  │
         │                │ - target_sets     │
         │                │ - target_rep_*    │
         │                │ - target_rpe      │
         │                │ - target_rir      │
         │                └───────────────────┘
         │                        │
         │                        ▼
         │                ┌──────────────────┐
         │                │     movements    │
         │                │  (from Knowledge │
         │                │      Graph)      │
         │                └──────────────────┘
```

### Fatigue, Recovery & Analytics

```
┌────────────────────┐      ┌──────────────────────┐
│ workout_logs       │◄─────│     sessions         │
│                    │      │                      │
│ - session_id       │      │ - user_id            │
│ - workout_date     │      │ - date               │
│ - duration_sec     │      │ - total_stimulus     │
│ - perceived_effort │      │ - total_fatigue      │
│ - mood_before/after│      │ - cns_fatigue        │
└────────────────────┘      │ - muscle_volume_json │
         │                  └──────────────────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐      ┌──────────────────┐
│  top_set_logs    │      │ pattern_exposure │
│                  │      │                  │
│ - session_id     │      │ - user_id        │
│ - movement_id    │      │ - pattern_type   │
│ - set_number     │      │ - exposure_count │
│ - reps           │      │ - last_exposure  │
│ - load_kg        │      │ - consecutive_*  │
│ - rpe            │      └──────────────────┘
│ - velocity       │               │
└──────────────────┘               ▼
         │                ┌───────────────────┐
         ▼                │ user_fatigue_     │
┌──────────────────┐      │      state        │
│ soreness_logs    │      │                   │
│                  │      │ - user_id         │
│ - user_id        │      │ - date            │
│ - log_date       │      │ - muscle_fatigue_ │
│ - body_part      │      │   json            │
│ - severity       │      │ - systemic_fatigue│
└──────────────────┘      │ - cns_fatigue     │
         │                │ - recovery_score  │
         ▼                └───────────────────┘
┌───────────────────┐               │
│recovery_signals   │               ▼
│                   │      ┌──────────────────┐
│ - user_id         │      │ recovery_signals │
│ - signal_date     │      │                  │
│ - overall_recovery│      │ - overall_score  │
│   _score          │      │ - muscle_recovery│
│ - muscle_recovery │      │   _json          │
│   _json           │      │ - sleep_quality  │
│ - hrv_score       │      │ - soreness_score │
│ - resting_hr      │      │ - readiness_score│
└───────────────────┘      └──────────────────┘
```

### Circuit Templates (CrossFit/Hyrox)

```
┌──────────────────────────────────────────────────────────────────┐
│                     circuit_templates                            │
│  Pre-defined CrossFit/Hyrox style circuit structures             │
│                                                                  │
│  - name, description                                             │
│  - circuit_type (enum: rounds_for_time, amrap, emom, ladder,     │
│    tabata, chipper, station)                                     │
│  - exercises_json (flexible structure)                           │
│  - default_rounds, time_cap_seconds                              │
│  - bucket_stress (JSON: stress by movement bucket)               │
│  - fatigue_factor, stimulus_factor (fitness function metrics)    │
└──────────────────────────────────────────────────────────────────┘
         │
         ├── referenced by ────┐
         │                     │
         ▼                     ▼
┌──────────────────┐  ┌──────────────────┐
│   sessions       │  │   sessions       │
│                  │  │                  │
│ - main_circuit_id│  │ - finisher_      │
│                  │  │   circuit_id     │
└──────────────────┘  └──────────────────┘
```

### External Data Integration

```
┌──────────────────┐      ┌──────────────────┐
│external_provider_│◄─────│      users       │
│    accounts      │      │                  │
│                  │      └──────────────────┘
│ - user_id        │               │
│ - provider_type  │               ▼
│   (enum)         │      ┌──────────────────┐
│ - access_token   │      │external_ingestion│
│ - refresh_token  │      │     _runs        │
└──────────────────┘      │                  │
         │                │ - user_id        │
         │                │ - provider_account_id│
         ▼                │ - run_type       │
┌──────────────────┐      │ - status         │
│external_activity_│      └──────────────────┘
│    records       │               │
│                  │               ├── produces ───┐
│ - user_id        │               │               │
│ - provider_      │               ▼               ▼
│   activity_id    │      ┌──────────────────┐ ┌──────────────────┐
│ - activity_type  │      │external_activity_│ │external_metric_  │
│ - raw_data_json  │      │    records       │ │    streams       │
│                  │      └──────────────────┘ └──────────────────┘
│ processed_to_    │               │                  │
│   instance_id    │               ▼                  ▼
└──────────────────┘      ┌──────────────────┐ ┌──────────────────┐
                          │activity_instances│ │recovery_signals │
                          │                  │ │                  │
                          │ - user_id        │ │ - hrv_score      │
                          │ - activity_      │ │ - sleep_quality  │
                          │   definition_id  │ │ - resting_hr     │
                          └──────────────────┘ └──────────────────┘
```

---

## 5. Authentication System Architecture

### JWT-Based Authentication

Gainsly implements production-ready authentication using JSON Web Tokens (JWT) with bcrypt password hashing for secure user identity management.

**Authentication Flow**:
```
User Registration/Login
    ↓
Validate credentials
    ↓
Generate JWT token (HS256 algorithm)
    ↓
Return access_token + user_id
    ↓
Client includes token in Authorization header
    ↓
Token verified on protected routes
```

**Security Architecture**:
- **Password Storage**: Bcrypt with per-password salt generation
- **Token Algorithm**: HS256 (HMAC SHA-256)
- **Token Payload**: `{"sub": user_id, "exp": expiration_timestamp}`
- **Token Expiration**: Configurable (default: 30 minutes)
- **Token Validation**: Decode with secret key, verify signature and expiration

**Authentication Models**:
- [User](file:///Users/shourjosmac/Documents/alloy/app/models/user.py#L26-78): Core user model with auth fields
  - `hashed_password`: Bcrypt password hash (String 255, nullable)
  - `is_active`: Account activation status (Boolean, default True)
  - `created_at`: Account creation timestamp (DateTime, default now)
- [UserRegister](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L18-22): Registration request model
- [UserLogin](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L25-28): Login request model
- [TokenResponse](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L31-35): Token response model
- [UserResponse](file:///Users/shourjosmac/Documents/alloy/app/api/routes/auth.py#L38-44): User info response model

**Authentication Endpoints**:
- `POST /auth/register`: User registration with email validation and JWT token issuance
- `POST /auth/login`: User authentication with credential verification and JWT token issuance
- `GET /auth/verify-token`: Token verification and user info retrieval

**Security Utilities** ([jwt_utils.py](file:///Users/shourjosmac/Documents/alloy/app/security/jwt_utils.py)):
- `get_password_hash()`: Generate bcrypt hash with salt
- `verify_password()`: Verify password against bcrypt hash (constant-time comparison)
- `create_access_token()`: Generate JWT token with user_id and expiration
- `verify_token()`: Decode and validate JWT token, extract user_id

**Integration Points**:
- Frontend: Token storage in `auth-store.ts` with persistence
- API: Bearer token authentication in Authorization header
- Database: User account activation status checked on login
- Configuration: JWT settings in environment variables (secret_key, access_token_expire_minutes)

**Authentication Flow for AI Agents**:
When implementing features that require user authentication:
1. Check if endpoint requires authentication (protected routes)
2. Verify JWT token from Authorization header
3. Extract user_id from token "sub" claim
4. Validate user.is_active status
5. Use user_id for all user-scoped operations

**Security Considerations**:
- Email uniqueness enforced at registration
- Password never stored in plain text
- Token expiration prevents indefinite access
- Account activation status checked on login
- Bearer token pattern for API requests
- Secret key must be kept secure (environment variable)

---

## Summary

This architecture guide provides foundational understanding for autonomous AI agents to interact effectively with Gainsly database:

1. **The `movements` table is central source of truth** for all biomechanical reasoning
2. **Soft Enums provide flexibility** while maintaining application-level validation
3. **Biomechanical inference** follows physics-based rules (pattern → muscle → mechanics)
4. **Truth hierarchy**: Codebase > Database Schema > Current Data > General Knowledge
5. **Context matters**: User preferences, fatigue state, and goals all influence exercise selection
6. **Authentication is JWT-based** with bcrypt password hashing for secure user identity management

Use this guide as a reference when implementing session generation, adaptation logic, or any feature that requires understanding of biomechanical relationships encoded in Gainsly knowledge graph.
