# Gainsly - AI Workout Coach

An AI-enabled workout coach that creates adaptive 8-12 week strength/fitness programs and adapts daily sessions based on your preferences, constraints, and recovery signals.

## Features

- **JWT Authentication**: Production-ready authentication with bcrypt password hashing and secure token management
- **User Registration & Login**: Email-based user accounts with secure password storage
- **Token Verification**: JWT token validation with expiration and signature checking
- **Program Generation**: Create personalized 8-12 week programs based on 3 weighted goals
- **Multiple Split Templates**: Upper/Lower, PPL, Full Body, or custom Hybrid splits
- **Daily Adaptation**: Real-time session adjustments based on constraints and recovery
- **Progress Tracking**: e1RM calculation with multiple formulas (Epley, Brzycki, Lombardi, O'Conner)
- **Pattern Strength Index (PSI)**: Track strength across movement patterns
- **Intelligent Deloading**: Time-based and performance-triggered deload scheduling
- **Interference Management**: Account for recreational activities affecting training
- **Coach Personas**: Customizable tone and programming aggressiveness
- **Movement Variety System**: Prevents exercise duplication and enforces pattern diversity
- **Real-time Streaming**: SSE-powered session adaptation with live LLM feedback
- **Advanced Preferences**: Discipline priorities, cardio finishers, and scheduling options
- **Circuit Support**: CrossFit-style circuits with AMRAP, EMOM, and other formats
- **Goals System**: Long-term macro cycles with versioned goals and check-ins
- **External Integrations**: Data lake architecture for Strava, Garmin, Apple Health, WHOOP, Oura
- **Custom Workout Logging**: Log ad-hoc activities and custom workouts with detailed metrics
- **Historic Tracking**: View and manage past programs and sessions


## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (via SQLAlchemy async engine)
- **LLM**: Ollama (local) with provider-agnostic interface (llama3.2:3b)
- **HTTP Client**: httpx (async)
- **Frontend**: React 19 + TypeScript + Vite + TanStack Router + Tailwind CSS
- **Optimization**: OR-Tools constraint solver for session planning

## Quick Start

### Prerequisites

1. Python 3.11+
2. Ollama installed and running (`ollama serve`)
3. llama3.2:3b model pulled (`ollama pull llama3.2:3b`)
4. PostgreSQL installed and running

### Installation

```bash
# Navigate to project directory
cd Gainsly

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run the application
uvicorn app.main:app --reload
```

### Frontend Development

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Check LLM connection
curl http://localhost:8000/health/llm
```

## Project Structure

```
Gainsly/
├── app/
│   ├── api/
│   │   └── routes/          # API endpoint routers
│   ├── config/
│   │   └── settings.py      # Application configuration
│   ├── db/
│   │   └── database.py      # Database connection
│   ├── llm/
│   │   ├── base.py          # LLM provider interface
│   │   ├── ollama_provider.py  # Ollama implementation
│   │   └── prompts.py       # System prompts for session generation
│   ├── models/
│   │   ├── enums.py         # Enum definitions
│   │   ├── movement.py      # Movement repository
│   │   ├── user.py          # User configuration
│   │   ├── program.py       # Program/session planning
│   │   ├── logging.py       # Workout logging
│   │   ├── config.py        # Heuristic configs
│   │   └── circuit.py      # Circuit templates
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/
│   │   ├── metrics.py       # e1RM and PSI calculations
│   │   ├── time_estimation.py  # Session duration estimation
│   │   ├── program.py       # Program generation with pattern interference
│   │   ├── session_generator.py  # LLM-powered session creation
│   │   ├── adaptation.py    # Session adaptation logic
│   │   ├── deload.py       # Deload scheduling
│   │   ├── interference.py  # Goal validation and conflict detection
│   │   └── optimization.py # OR-Tools constraint solver
│   └── main.py              # FastAPI app entry point
├── frontend/
│   ├── src/
│   │   ├── components/      # React components with design system
│   │   ├── hooks/           # Custom React hooks
│   │   ├── api/             # API client layer
│   │   ├── types/           # TypeScript definitions
│   │   └── pages/           # Route components
│   └── package.json
├── seed_data/
│   ├── movements.json       # Pre-populated movement library
│   └── heuristic_configs.json  # Default configurations
├── scripts/                # Data ingestion and utility scripts
├── tests/
├── docs/                   # Additional documentation
│   ├── WARP.md             # WARP (warp.dev) development guide
│   ├── PERFORMANCE_TESTING.md # Performance testing with Locust
│   └── NOTES.md            # Development notes and architecture decisions
├── requirements.txt
└── README.md
```

## API Endpoints

### Authentication
- `POST /auth/register` - User registration with JWT token issuance
- `POST /auth/login` - User authentication with JWT token issuance
- `GET /auth/verify-token` - Token verification and user info retrieval

### Program Lifecycle
- `POST /programs` - Create new program with LLM-generated sessions
- `GET /programs/{id}` - Get program details with sessions
- `GET /programs?active_only=true` - List active programs

### Daily Planning
- `GET /days/{date}/plan` - Get daily session plan
- `POST /days/{date}/adapt` - Adapt session with constraints
- `POST /days/{date}/adapt/stream` - Real-time adaptation with SSE streaming

### Logging
- `POST /logs/workouts` - Log workout completion with feedback
- `POST /logs/custom` - Log custom workout or activity
- `POST /logs/soreness` - Log muscle soreness
- `POST /logs/recovery` - Log recovery signals

### Settings & Configuration
- `GET /settings` - Get user settings
- `PUT /settings` - Update settings
- `GET /settings/profile` - Get user profile with advanced preferences
- `PUT /settings/profile` - Update user profile
- `GET /configs` - List heuristic configurations
- `PUT /configs/{name}/active` - Activate config version

## Configuration

Environment variables (or `.env` file):

```env
# LLM Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT=1100.0

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# App
DEBUG=true

# Authentication
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
```

## Goals (Ten-Dollar Method)

Select 3 goals and assign weights that sum to 10:
- `strength` - Max force production
- `hypertrophy` - Muscle growth
- `endurance` - Work capacity
- `fat_loss` - Body composition
- `mobility` - Range of motion
- `explosiveness` - Power output
- `speed` - Movement velocity

## Split Templates

- **Upper/Lower**: 4 days/week, alternating upper and lower body
- **PPL**: 6 days/week, Push/Pull/Legs rotation
- **Full Body**: 3 days/week, whole body each session
- **Hybrid**: Custom day-by-day or block composition

## Progression Styles

1. **Single Progression**: Increase weight when hitting rep target
2. **Double Progression**: Increase reps, then weight
3. **Paused Variations**: Add pauses for difficulty
4. **Build to Drop**: Build reps, drop and add weight
5. **Wave Loading**: Undulating intensity across sets

## Movement Variety System

### Pattern Interference Rules
- No same main pattern on consecutive training days
- Maximum 2 uses per pattern per week
- Intelligent pattern substitution (squat → hinge → lunge rotation)
- Prevents back-to-back loading of same movement patterns

### Variety Enforcement
- Intra-session deduplication prevents exercise repetition
- Inter-session variety tracking across the week
- Muscle group fatigue tracking to prevent overload
- Movement history context passed to LLM

## Session Structure

Sessions have flexible, optional sections stored as JSON:
- **warmup_json** - Always included
- **main_json** - Main lifts or cardio block
- **accessory_json** - Optional accessory work
- **finisher_json** - Optional finisher (conditioning, cardio, or metabolic)
- **cooldown_json** - Always included

Session types determine middle piece structure:
- **Strength/Hypertrophy**: Main lifts + (Accessory XOR Finisher)
- **Cardio-only**: Dedicated cardio block only
- **Conditioning-only**: Circuit-based conditioning (≥5 movements, ≥30 minutes)
- **Mobility**: Extended warmup/cooldown with mobility work

## Frontend Design System

### Color Palette
- **Primary**: Vibrant teal (#06B6D4) for CTAs and progress
- **Secondary**: Deep slate (#1E293B) for backgrounds
- **Accent**: Amber (#F59E0B) for warnings and deload indicators
- **Success**: Emerald (#10B981) for completed sessions and PRs

### Component Library
- Unified button system with hover effects and accessibility
- Card components with type-specific styling
- Form components with real-time validation
- Modal system with smooth animations
- Loading states and skeleton components

## Database Schema

The database uses PostgreSQL with SQLAlchemy ORM. Key tables include:

- **users** - User profiles, settings, and personas
- **programs** - 8-12 week programs with goals and splits
- **microcycles** - 7-10 day blocks within programs
- **sessions** - Daily workout plans with JSON content sections
- **movements** - Exercise library with patterns and muscle groups
- **circuit_templates** - CrossFit-style circuits (AMRAP, EMOM, etc.)
- **movement_relationships** - Progression, regression, variation edges
- **workout_logs** - Completed workouts with performance data
- **recovery_signals** - Recovery data from various sources
- **macro_cycles** - Long-term (12-month) planning
- **goals** - Versioned goals with check-ins
- **external_provider_accounts** - Integration credentials
- **external_activity_records** - Imported activity data

For complete schema documentation, see [DATABASE_OVERVIEW.md](DATABASE_OVERVIEW.md).

For detailed implementation plans and roadmap items, see [docs/plans/](docs/plans/).

## e1RM Calculation

**Supported formulas** (configurable per user):
- `epley`: weight × (1 + reps/30)
- `brzycki`: weight × 36 / (37 - reps)
- `lombardi`: weight × reps^0.10
- `oconner`: weight × (1 + reps/40)

## Testing

```bash
# Run backend tests
pytest

# Run tests with coverage
pytest --cov=app

# Run frontend tests
cd frontend && npm test

# Performance testing with Locust
pip install locust
locust -f tests/performance_test_locust.py
```

See [docs/PERFORMANCE_TESTING.md](docs/PERFORMANCE_TESTING.md) for detailed performance testing guidance.

## Development Notes

For detailed architecture decisions, development patterns, and implementation notes, see:
- [docs/NOTES.md](docs/NOTES.md) - Architecture decisions and design patterns
- [docs/WARP.md](docs/WARP.md) - WARP (warp.dev) development guide
- [SESSION_LOG.md](SESSION_LOG.md) - Development session history

## Roadmap & Future Enhancements

### Current Development
- Ensemble coach architecture with multiple LLM providers
- Circuit metrics normalization for optimizer integration
- Goal-based weekly time distribution
- External activity ingestion (Strava, Garmin, Apple Health)
- Biometrics tracking and user profiles

### Planned Features
- [ ] Cloud LLM providers (OpenAI, Anthropic)
- [ ] Mobile native app (React Native)
- [ ] Advanced analytics and progress visualization
- [ ] Social features (share programs, compete with friends)
- [ ] Workout video analysis with computer vision

## License

MIT
