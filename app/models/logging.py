"""Workout logging and metrics models."""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, Date, DateTime,
    ForeignKey, Text, Float, Enum as SQLEnum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    E1RMFormula,
    MovementPattern,
    RecoverySource,
    Visibility,
)


class WorkoutLog(Base):
    """Log of a completed workout session."""
    __tablename__ = "workout_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    
    # Completion
    date = Column(Date, nullable=False, index=True)
    completed = Column(Boolean, nullable=False, default=True)
    
    # User feedback
    notes = Column(Text, nullable=True)
    perceived_difficulty = Column(Integer, nullable=True)  # 1-10
    enjoyment_rating = Column(Integer, nullable=True)  # 1-5
    feedback_tags = Column(JSON, default=list)  # e.g. ["too_hard", "boring"]
    
    # Timing
    actual_duration_minutes = Column(Integer, nullable=True)
    
    # Access Control
    visibility = Column(SQLEnum(Visibility), default=Visibility.PRIVATE, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="workout_logs")
    session = relationship("Session", back_populates="workout_logs")
    top_sets = relationship("TopSetLog", back_populates="workout_log", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkoutLog(id={self.id}, user_id={self.user_id}, date={self.date})>"


class TopSetLog(Base):
    """Log of a top set for progress tracking."""
    __tablename__ = "top_set_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workout_log_id = Column(Integer, ForeignKey("workout_logs.id"), nullable=False, index=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    
    # Performance data
    weight = Column(Float, nullable=False)  # In user's preferred unit
    reps = Column(Integer, nullable=False)
    rpe = Column(Float, nullable=True)  # 6-10 scale
    rir = Column(Integer, nullable=True)  # Reps in reserve
    
    # Optional rest tracking
    avg_rest_seconds = Column(Integer, nullable=True)
    
    # Calculated metrics
    e1rm_value = Column(Float, nullable=True)
    e1rm_formula = Column(SQLEnum(E1RMFormula), nullable=True)
    
    # Denormalized for fast PSI queries
    pattern = Column(SQLEnum(MovementPattern), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    workout_log = relationship("WorkoutLog", back_populates="top_sets")
    movement = relationship("Movement", back_populates="top_set_logs")

    def __repr__(self):
        return f"<TopSetLog(id={self.id}, movement_id={self.movement_id}, weight={self.weight}x{self.reps})>"


class PatternExposure(Base):
    """
    Pattern-level exposure for PSI calculation.
    Each top set becomes a pattern exposure.
    """
    __tablename__ = "pattern_exposures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    microcycle_id = Column(Integer, ForeignKey("microcycles.id"), nullable=False, index=True)
    
    # Pattern and date
    date = Column(Date, nullable=False, index=True)
    pattern = Column(SQLEnum(MovementPattern), nullable=False, index=True)
    
    # e1RM value for this exposure
    e1rm_value = Column(Float, nullable=False)
    
    # Source tracking
    source_top_set_log_id = Column(Integer, ForeignKey("top_set_logs.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    microcycle = relationship("Microcycle", back_populates="pattern_exposures")

    def __repr__(self):
        return f"<PatternExposure(id={self.id}, pattern={self.pattern}, e1rm={self.e1rm_value})>"


class SorenessLog(Base):
    """User-reported muscle soreness."""
    __tablename__ = "soreness_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Soreness data
    date = Column(Date, nullable=False, index=True)
    body_part = Column(String(50), nullable=False)  # Free text for flexibility
    soreness_1_5 = Column(Integer, nullable=False)  # 1 = none, 5 = severe
    
    # DOMS attribution (system-inferred)
    inferred_cause_session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="soreness_logs")

    def __repr__(self):
        return f"<SorenessLog(id={self.id}, body_part='{self.body_part}', level={self.soreness_1_5})>"


class RecoverySignal(Base):
    """Recovery signals (dummy for MVP, Garmin later)."""
    __tablename__ = "recovery_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Timing
    date = Column(Date, nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    
    # Source
    source = Column(SQLEnum(RecoverySource), nullable=False, default=RecoverySource.DUMMY)
    
    # Metrics (nullable - not all sources provide all)
    hrv = Column(Float, nullable=True)  # Heart rate variability
    resting_hr = Column(Integer, nullable=True)  # Resting heart rate
    sleep_score = Column(Float, nullable=True)  # 0-100
    sleep_hours = Column(Float, nullable=True)
    readiness = Column(Float, nullable=True)  # 0-100 overall readiness
    raw_payload_json = Column(JSON, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="recovery_signals")

    def __repr__(self):
        return f"<RecoverySignal(id={self.id}, date={self.date}, source={self.source})>"


class MuscleRecoveryState(Base):
    """Current muscle recovery state for each muscle (not historic)."""
    __tablename__ = "muscle_recovery_states"
    __table_args__ = (
        UniqueConstraint('user_id', 'muscle', name='uq_user_muscle'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Muscle identification
    muscle = Column(String(50), nullable=False, index=True)
    
    # Recovery level (0-5, where 0 = fully recovered, 5 = severe soreness)
    recovery_level = Column(Integer, nullable=False, default=0)
    
    # When this state was last updated
    last_updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="muscle_recovery_states")

    def __repr__(self):
        return f"<MuscleRecoveryState(id={self.id}, muscle='{self.muscle}', level={self.recovery_level})>"
