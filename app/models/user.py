"""User and user configuration models."""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, Enum as SQLEnum, Text, CheckConstraint
from sqlalchemy import Date, DateTime, Float, JSON
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import (
    ExperienceLevel,
    SkillLevel,
    PersonaTone,
    PersonaAggression,
    MovementRuleType,
    RuleCadence,
    EnjoyableActivity,
    E1RMFormula,
    Sex,
    DataSource,
    BiometricMetricType,
    RuleOperator,
    DisciplineType,
)


class User(Base):
    """User profile."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True, unique=True)
    
    # Authentication fields
    hashed_password = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Experience and defaults
    experience_level = Column(
        SQLEnum(ExperienceLevel, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default='intermediate'
    )
    
    # Global persona settings
    persona_tone = Column(
        SQLEnum(PersonaTone, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default='supportive'
    )
    persona_aggression = Column(
        SQLEnum(PersonaAggression, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default='BALANCED'
    )
    
    # Relationships
    movement_rules = relationship("UserMovementRule", back_populates="user", cascade="all, delete-orphan")
    enjoyable_activities = relationship("UserEnjoyableActivity", back_populates="user", cascade="all, delete-orphan")
    programs = relationship("Program", back_populates="user", cascade="all, delete-orphan")
    workout_logs = relationship("WorkoutLog", back_populates="user", cascade="all, delete-orphan")
    soreness_logs = relationship("SorenessLog", back_populates="user", cascade="all, delete-orphan")
    recovery_signals = relationship("RecoverySignal", back_populates="user", cascade="all, delete-orphan")
    muscle_recovery_states = relationship("MuscleRecoveryState", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversation_threads = relationship("ConversationThread", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    biometrics_history = relationship("UserBiometricHistory", back_populates="user", cascade="all, delete-orphan")
    macro_cycles = relationship("MacroCycle", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
    activity_instances = relationship("ActivityInstance", back_populates="user", cascade="all, delete-orphan")
    skills = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    injuries = relationship("UserInjury", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}')>"


class UserMovementRule(Base):
    """User preferences for specific movements."""
    __tablename__ = "user_movement_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    
    rule_type = Column(SQLEnum(MovementRuleType), nullable=False)
    rule_operator = Column(SQLEnum(RuleOperator, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=RuleOperator.EQ)
    cadence = Column(SQLEnum(RuleCadence), nullable=False, default=RuleCadence.PER_MICROCYCLE)
    notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="movement_rules")
    movement = relationship("Movement", back_populates="user_rules")

    def __repr__(self):
        return f"<UserMovementRule(user_id={self.user_id}, movement_id={self.movement_id}, rule={self.rule_type})>"


class UserEnjoyableActivity(Base):
    """User's enjoyable activities for recommendations."""
    __tablename__ = "user_enjoyable_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    activity_type = Column(SQLEnum(EnjoyableActivity), nullable=False)
    custom_name = Column(String(100), nullable=True)  # For "other" activities
    recommend_every_days = Column(Integer, nullable=False, default=28)
    enabled = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="enjoyable_activities")

    def __repr__(self):
        return f"<UserEnjoyableActivity(user_id={self.user_id}, activity={self.activity_type})>"


class UserSettings(Base):
    """User-specific settings and preferences."""
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # e1RM calculation preference
    active_e1rm_formula = Column(
        SQLEnum(E1RMFormula),
        nullable=False,
        default=E1RMFormula.EPLEY
    )
    
    # Display preferences
    use_metric = Column(Boolean, default=True)  # True = kg, False = lbs
    
    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id={self.user_id}, formula={self.active_e1rm_formula})>"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    date_of_birth = Column(Date, nullable=True)
    sex = Column(SQLEnum(Sex), nullable=True)
    height_cm = Column(Integer, nullable=True)
    
    # Advanced Preferences
    discipline_preferences = Column(JSON, nullable=True)  # {"mobility": 5, "calisthenics": 3, ...}
    discipline_experience = Column(JSON, nullable=True)  # {"mobility": "intermediate", "crossfit": "beginner"}
    scheduling_preferences = Column(JSON, nullable=True)  # {"mix_disciplines": true, "cardio_preference": "finisher"}

    # Long Term Goals
    long_term_goal_category = Column(String(50), nullable=True)
    long_term_goal_description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="profile")


class UserBiometricHistory(Base):
    __tablename__ = "user_biometrics_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)
    metric_type = Column(SQLEnum(BiometricMetricType), nullable=False, index=True)
    value = Column(Float, nullable=False)
    source = Column(SQLEnum(DataSource), nullable=False, default=DataSource.MANUAL)
    external_reference = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="biometrics_history")


class UserSkill(Base):
    """User's skill level in specific disciplines."""
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id"), nullable=False, index=True)
    
    skill_level = Column(SQLEnum(SkillLevel), nullable=False, default=SkillLevel.BEGINNER)
    interest_level = Column(Integer, CheckConstraint('interest_level >= 0 AND interest_level <= 10'), nullable=False, default=5)
    experience_years = Column(Float, nullable=True)
    
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="skills")
    discipline = relationship("Discipline")


class UserInjury(Base):
    """User-reported injuries/contraindications."""
    __tablename__ = "user_injuries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    body_part = Column(String(50), nullable=False, index=True)  # e.g., "lower_back", "knee_left"
    severity = Column(Float, nullable=False, default=1.0)  # 0.0-1.0 (1.0 = total exclusion)
    description = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="injuries")
