"""Program planning models."""
from datetime import date, datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, Date, DateTime, 
    ForeignKey, Text, JSON, Enum as SQLEnum, Float,
    CheckConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    Goal,
    SplitTemplate,
    ProgressionStyle,
    PersonaTone,
    PersonaAggression,
    MicrocycleStatus,
    SessionType,
    ExerciseRole,
    Visibility,
    GoalType,
    GoalStatus,
    DisciplineCategory,
    ActivityCategory,
    ActivitySource,
    MetricType,
)


class Program(Base):
    """Training program (8-12 weeks)."""
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    macro_cycle_id = Column(Integer, ForeignKey("macro_cycles.id"), nullable=True, index=True)
    name = Column(String(100), nullable=True)  # Added for historic programs
    
    # Program duration
    start_date = Column(Date, nullable=False)
    duration_weeks = Column(Integer, nullable=False)  # 8-12
    
    # Goals with ten-dollar method weights (must sum to 10)
    goal_1 = Column(SQLEnum(Goal), nullable=False)
    goal_2 = Column(SQLEnum(Goal), nullable=False)
    goal_3 = Column(SQLEnum(Goal), nullable=False)
    goal_weight_1 = Column(Integer, nullable=False)
    goal_weight_2 = Column(Integer, nullable=False)
    goal_weight_3 = Column(Integer, nullable=False)
    
    # Program structure
    split_template = Column(SQLEnum(SplitTemplate), nullable=False)
    days_per_week = Column(Integer, nullable=False)  # User's training frequency (2-7)
    max_session_duration = Column(Integer, nullable=False, default=60)  # Max minutes per session
    progression_style = Column(SQLEnum(ProgressionStyle), nullable=False)
    
    # Hybrid split definition (for SplitTemplate.HYBRID)
    # Stores the custom day-by-day structure or block composition
    hybrid_definition = Column(JSON, nullable=True)
    
    # Deload configuration
    deload_every_n_microcycles = Column(Integer, nullable=False, default=4)
    
    # Persona snapshot (copied from user at program creation)
    persona_tone = Column(SQLEnum(PersonaTone, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default='supportive')
    persona_aggression = Column(SQLEnum(PersonaAggression, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default='BALANCED')
    
    # Status
    is_active = Column(Boolean, default=True)
    is_template = Column(Boolean, default=False)  # Reusable template
    visibility = Column(SQLEnum(Visibility), default=Visibility.PRIVATE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('duration_weeks >= 8 AND duration_weeks <= 12', name='valid_duration'),
        CheckConstraint('goal_weight_1 + goal_weight_2 + goal_weight_3 = 10', name='goals_sum_to_ten'),
        CheckConstraint('goal_weight_1 >= 0 AND goal_weight_2 >= 0 AND goal_weight_3 >= 0', name='positive_weights'),
    )
    
    # Relationships
    user = relationship("User", back_populates="programs")
    macro_cycle = relationship("MacroCycle", back_populates="programs")
    microcycles = relationship("Microcycle", back_populates="program", cascade="all, delete-orphan")
    goals = relationship("UserGoal", back_populates="program", cascade="all, delete-orphan")
    program_disciplines = relationship("ProgramDiscipline", back_populates="program", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="program", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Program(id={self.id}, user_id={self.user_id}, split={self.split_template})>"


class ProgramDiscipline(Base):
    """Junction table for Program <-> DisciplineType with weights."""
    __tablename__ = "program_disciplines"

    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, primary_key=True)
    discipline_type = Column(String(50), nullable=False, primary_key=True)
    weight = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    program = relationship("Program", back_populates="program_disciplines")

    @property
    def discipline(self):
        return self.discipline_type

    def __repr__(self):
        return f"<ProgramDiscipline(program_id={self.program_id}, discipline_type='{self.discipline_type}', weight={self.weight})>"


class Microcycle(Base):
    """Training microcycle (7-14 days)."""
    __tablename__ = "microcycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=False, index=True)
    
    # Timing
    start_date = Column(Date, nullable=False)
    length_days = Column(Integer, nullable=False)  # 7-14
    sequence_number = Column(Integer, nullable=False)  # 1, 2, 3, etc.
    
    # Status
    status = Column(SQLEnum(MicrocycleStatus), nullable=False, default=MicrocycleStatus.PLANNED)
    is_deload = Column(Boolean, default=False)
    
    # Constraints
    __table_args__ = (
        CheckConstraint('length_days >= 7 AND length_days <= 14', name='valid_length'),
    )
    
    # Relationships
    program = relationship("Program", back_populates="microcycles")
    sessions = relationship("Session", back_populates="microcycle", cascade="all, delete-orphan")
    pattern_exposures = relationship("PatternExposure", back_populates="microcycle", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Microcycle(id={self.id}, program_id={self.program_id}, seq={self.sequence_number})>"


class Session(Base):
    """
    Training session within a microcycle.
    
    Sessions are flexible and may not include all sections. For example:
    - A cardio session might only have: warmup, main, cooldown
    - A strength day would have: warmup, main, accessory, cooldown
    - A mobility session might only have: warmup, main
    
    Each section (warmup, main, accessory, finisher, cooldown) is optional.
    Sections are stored as JSON arrays of exercise objects.
    """
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    microcycle_id = Column(Integer, ForeignKey("microcycles.id"), nullable=True, index=True)
    
    # Scheduling
    date = Column(Date, nullable=False, index=True)
    day_number = Column(Integer, nullable=False)  # Day within microcycle (1-14)
    
    # Session type and intent
    session_type = Column(SQLEnum(SessionType), nullable=False)
    intent_tags = Column(JSON, default=list)  # e.g., ["strength", "hypertrophy"]
    
    # Session content (JSON blocks) - ALL OPTIONAL
    # Each section can be None if not needed for this session type
    # DEPRECATED: Moving to session_exercises table
    # warmup_json = Column(JSON, nullable=True)  # Optional: general preparation
    # main_json = Column(JSON, nullable=True)  # Optional: primary work
    # accessory_json = Column(JSON, nullable=True)  # Optional: supporting work
    # finisher_json = Column(JSON, nullable=True)  # Optional: brief high-effort completion
    # cooldown_json = Column(JSON, nullable=True)  # Optional: active recovery
    
    # Circuit Integration
    # If this session IS a circuit (Hyrox/Crossfit day), these fields are used
    main_circuit_id = Column(Integer, ForeignKey("circuit_templates.id"), nullable=True)
    finisher_circuit_id = Column(Integer, ForeignKey("circuit_templates.id"), nullable=True)
    
    # Time estimation
    estimated_duration_minutes = Column(Integer, nullable=True)
    warmup_duration_minutes = Column(Integer, nullable=True)
    main_duration_minutes = Column(Integer, nullable=True)
    accessory_duration_minutes = Column(Integer, nullable=True)
    finisher_duration_minutes = Column(Integer, nullable=True)
    cooldown_duration_minutes = Column(Integer, nullable=True)
    
    # Coach reasoning
    coach_notes = Column(Text, nullable=True)
    
    # Session Metrics (Actuals)
    total_stimulus = Column(Float, default=0.0)
    total_fatigue = Column(Float, default=0.0)
    cns_fatigue = Column(Float, default=0.0)
    muscle_volume_json = Column(JSON, default=dict)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    microcycle = relationship("Microcycle", back_populates="sessions")
    exercises = relationship("SessionExercise", back_populates="session", cascade="all, delete-orphan")
    workout_logs = relationship("WorkoutLog", back_populates="session")
    
    # Circuit Relationships
    main_circuit = relationship("CircuitTemplate", foreign_keys=[main_circuit_id])
    finisher_circuit = relationship("CircuitTemplate", foreign_keys=[finisher_circuit_id])

    def __repr__(self):
        return f"<Session(id={self.id}, date={self.date}, type={self.session_type})>"


class SessionExercise(Base):
    """Individual exercise within a session."""
    __tablename__ = "session_exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    
    # Section & Organization (unified ExerciseRole enum)
    exercise_role = Column(SQLEnum(ExerciseRole, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    circuit_id = Column(Integer, ForeignKey("circuit_templates.id"), nullable=True, index=True)
    order_in_session = Column(Integer, nullable=False)
    superset_group = Column(Integer, nullable=True)
    
    # Prescription
    target_sets = Column(Integer, nullable=False)
    target_rep_range_min = Column(Integer, nullable=True)
    target_rep_range_max = Column(Integer, nullable=True)
    target_rpe = Column(Float, nullable=True)
    target_rir = Column(Integer, nullable=True)
    target_duration_seconds = Column(Integer, nullable=True)
    
    # Rest
    default_rest_seconds = Column(Integer, nullable=True)
    
    # Substitution info
    is_complex_lift = Column(Boolean, default=False)
    substitution_allowed = Column(Boolean, default=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Custom Metrics
    stimulus = Column(Float, nullable=True)
    fatigue = Column(Float, nullable=True)

    # Relationships
    session = relationship("Session", back_populates="exercises")
    user = relationship("User", foreign_keys=[user_id])
    movement = relationship("Movement", back_populates="session_exercises")
    circuit = relationship("CircuitTemplate", foreign_keys=[circuit_id])

    def __repr__(self):
        return f"<SessionExercise(id={self.id}, session_id={self.session_id}, movement_id={self.movement_id})>"


class MacroCycle(Base):
    __tablename__ = "macro_cycles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(200), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="macro_cycles")
    programs = relationship("Program", back_populates="macro_cycle", cascade="all, delete-orphan")
    goals = relationship("UserGoal", back_populates="macro_cycle", cascade="all, delete-orphan")


class UserGoal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    macro_cycle_id = Column(Integer, ForeignKey("macro_cycles.id"), nullable=True, index=True)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True, index=True)

    goal_type = Column(SQLEnum(GoalType), nullable=False)
    target_json = Column(JSON, nullable=True)
    priority = Column(Integer, nullable=False, default=3)
    status = Column(SQLEnum(GoalStatus), nullable=False, default=GoalStatus.ACTIVE)

    effective_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    effective_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")
    macro_cycle = relationship("MacroCycle", back_populates="goals")
    program = relationship("Program", back_populates="goals")
    checkins = relationship("GoalCheckin", back_populates="goal", cascade="all, delete-orphan")


class GoalCheckin(Base):
    __tablename__ = "goal_checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)
    value_json = Column(JSON, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    goal = relationship("UserGoal", back_populates="checkins")


class Discipline(Base):
    __tablename__ = "disciplines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    category = Column(SQLEnum(DisciplineCategory), nullable=False, default=DisciplineCategory.TRAINING)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityDefinition(Base):
    __tablename__ = "activity_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    category = Column(SQLEnum(ActivityCategory), nullable=False, index=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=True, index=True)
    default_metric_type = Column(SQLEnum(MetricType), nullable=True)
    default_equipment_tags = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    discipline = relationship("Discipline")
    activity_instances = relationship("ActivityInstance", back_populates="activity_definition")


class ActivityInstance(Base):
    __tablename__ = "activity_instances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    planned_session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    source = Column(SQLEnum(ActivitySource), nullable=False, index=True)

    activity_definition_id = Column(Integer, ForeignKey("activity_definitions.id"), nullable=True, index=True)
    name = Column(String(50), nullable=True)
    performed_start = Column(DateTime, nullable=True, index=True)
    performed_end = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    distance_km = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)
    perceived_difficulty = Column(Integer, nullable=True)
    enjoyment_rating = Column(Integer, nullable=True)
    visibility = Column(SQLEnum(Visibility), default=Visibility.PRIVATE, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    activity_definition = relationship("ActivityDefinition", back_populates="activity_instances")
    user = relationship("User", back_populates="activity_instances")


class ActivityMuscleMap(Base):
    __tablename__ = "activity_muscle_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_definition_id = Column(Integer, ForeignKey("activity_definitions.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    magnitude = Column(Float, nullable=False, default=1.0)
    cns_impact = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserFatigueState(Base):
    __tablename__ = "user_fatigue_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    fatigue_score = Column(Float, nullable=False)
    computed_from = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityInstanceLink(Base):
    __tablename__ = "activity_instance_links"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_instance_id = Column(Integer, ForeignKey("activity_instances.id"), nullable=False, index=True)
    external_activity_record_id = Column(Integer, ForeignKey("external_activity_records.id"), nullable=True, index=True)
    workout_log_id = Column(Integer, ForeignKey("workout_logs.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
