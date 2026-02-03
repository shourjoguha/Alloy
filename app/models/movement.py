"""Movement repository models."""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey
from sqlalchemy import DateTime, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.db.database import Base
from app.models.enums import (
    MovementPattern,
    PrimaryMuscle,
    PrimaryRegion,
    MetricType,
    SkillLevel,
    CNSLoad,
    RelationshipType,
    MuscleRole,
    SpinalCompression,
    DisciplineType,
    MovementTier,
    MetabolicDemand,
)


class Equipment(Base):
    """Equipment reference table."""
    __tablename__ = "equipment"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)


class Tag(Base):
    """General tag reference table."""
    __tablename__ = "tags"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)


class MovementDiscipline(Base):
    """Junction table for Movement <-> Discipline (Enum)."""
    __tablename__ = "movement_disciplines"
    
    movement_id = Column(Integer, ForeignKey("movements.id"), primary_key=True)
    discipline = Column(SQLEnum(DisciplineType, values_callable=lambda obj: [e.value for e in obj]), primary_key=True, index=True)


class MovementEquipment(Base):
    """Junction table for Movement <-> Equipment."""
    __tablename__ = "movement_equipment"
    
    movement_id = Column(Integer, ForeignKey("movements.id"), primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"), primary_key=True)

    equipment = relationship("Equipment")


class MovementTag(Base):
    """Junction table for Movement <-> Tag."""
    __tablename__ = "movement_tags"
    
    movement_id = Column(Integer, ForeignKey("movements.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class MovementCoachingCue(Base):
    """Coaching cues for movements."""
    __tablename__ = "movement_coaching_cues"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    cue_text = Column(Text, nullable=False)
    order = Column(Integer, default=0)
    
    movement = relationship("Movement", back_populates="coaching_cues_list")


class MovementRelationship(Base):
    """Defines relationships between movements (progressions, variations, etc)."""
    __tablename__ = "movement_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    target_movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    relationship_type = Column(SQLEnum(RelationshipType, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    notes = Column(Text, nullable=True)

    # Relationships
    source_movement = relationship("Movement", foreign_keys=[source_movement_id], back_populates="outgoing_relationships")
    target_movement = relationship("Movement", foreign_keys=[target_movement_id], back_populates="incoming_relationships")


class Movement(Base):
    """Movement/exercise definition."""
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # Null for system movements
    name = Column(String(200), nullable=False, unique=True, index=True)
    
    # Movement classification
    pattern = Column(SQLEnum(MovementPattern, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    primary_muscle = Column(SQLEnum(PrimaryMuscle, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    primary_region = Column(SQLEnum(PrimaryRegion, values_callable=lambda obj: [e.value for e in obj]), nullable=False, index=True)
    # secondary_muscles = Column(JSON, default=list)  # REMOVED: Use muscle_maps
    
    # Load and complexity
    cns_load = Column(SQLEnum(CNSLoad, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=CNSLoad.MODERATE)
    skill_level = Column(SQLEnum(SkillLevel, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=SkillLevel.INTERMEDIATE)
    
    # Movement characteristics
    compound = Column(Boolean, default=True)
    is_complex_lift = Column(Boolean, default=False)  # Requires confirmation for safety
    is_unilateral = Column(Boolean, default=False)
    
    # Fitness Function Metrics (RL Reward Signals)
    fatigue_factor = Column(Float, nullable=False, default=1.0)  # Systemic fatigue cost (for SFR)
    stimulus_factor = Column(Float, nullable=False, default=1.0) # Raw hypertrophy/strength stimulus (for SFR)
    injury_risk_factor = Column(Float, nullable=False, default=1.0) # Base injury risk (for Biomechanical Match)
    min_recovery_hours = Column(Integer, nullable=False, default=24) # Estimated recovery time
    spinal_compression = Column(SQLEnum(SpinalCompression, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=SpinalCompression.LOW) # New
    
    # Measurement
    metric_type = Column(SQLEnum(MetricType, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=MetricType.REPS)
    
    # Categorization
    tier = Column(SQLEnum(MovementTier, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=MovementTier.BRONZE, index=True)
    metabolic_demand = Column(SQLEnum(MetabolicDemand, values_callable=lambda obj: [e.value for e in obj]), nullable=False, default=MetabolicDemand.ANABOLIC, index=True)
    
    # Biomechanics Profile (JSONB for granular ratings)
    biomechanics_profile = Column(JSONB, nullable=True, default=dict)
    
    # Embedding for semantic search (LLM-based movement matching)
    embedding_description = Column(Text, nullable=True)
    embedding_vector = Column(Vector(768), nullable=True)
    
    # primary_discipline = Column(String(50), nullable=False, default="All", server_default="All") # REMOVED: Use disciplines
    # discipline_tags = Column(JSON, default=list)  # REMOVED: Use disciplines
    # equipment_tags = Column(JSON, default=list)  # REMOVED: Use equipment
    # tags = Column(JSON, default=list)  # REMOVED: Use movement_tags
    
    # Description and notes
    description = Column(Text, nullable=True)
    # coaching_cues = Column(JSON, default=list)  # REMOVED: Use coaching_cues_list
    
    # Substitution helpers
    substitution_group = Column(String(100), nullable=True, index=True)  # e.g., "single_arm_row"
    
    # Relationships
    user_rules = relationship("UserMovementRule", back_populates="movement")
    session_exercises = relationship("SessionExercise", back_populates="movement")
    top_set_logs = relationship("TopSetLog", back_populates="movement")
    favorites = relationship("Favorite", back_populates="movement", cascade="all, delete-orphan")

    # Movement Relationships
    outgoing_relationships = relationship(
        "MovementRelationship",
        foreign_keys="MovementRelationship.source_movement_id",
        back_populates="source_movement",
        cascade="all, delete-orphan"
    )
    incoming_relationships = relationship(
        "MovementRelationship",
        foreign_keys="MovementRelationship.target_movement_id",
        back_populates="target_movement",
        cascade="all, delete-orphan"
    )

    # Anatomy Bridge
    muscle_maps = relationship("MovementMuscleMap", back_populates="movement", cascade="all, delete-orphan")

    # New Relationships
    disciplines = relationship("MovementDiscipline", backref="movement", cascade="all, delete-orphan")
    equipment = relationship("MovementEquipment", backref="movement", cascade="all, delete-orphan")
    movement_tags = relationship("MovementTag", backref="movement", cascade="all, delete-orphan")
    coaching_cues_list = relationship("MovementCoachingCue", back_populates="movement", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Movement(id={self.id}, name='{self.name}', pattern={self.pattern})>"


class Muscle(Base):
    __tablename__ = "muscles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    region = Column(SQLEnum(PrimaryRegion, values_callable=lambda x: [e.value for e in x]), nullable=True)
    stimulus_coefficient = Column(Float, nullable=False, default=1.0)
    fatigue_coefficient = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class MovementMuscleMap(Base):
    __tablename__ = "movement_muscle_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    movement_id = Column(Integer, ForeignKey("movements.id"), nullable=False, index=True)
    muscle_id = Column(Integer, ForeignKey("muscles.id"), nullable=False, index=True)
    role = Column(SQLEnum(MuscleRole, values_callable=lambda x: [e.name for e in x]), nullable=False, index=True)
    magnitude = Column(Float, nullable=False, default=1.0)
    
    movement = relationship("Movement", back_populates="muscle_maps")
    muscle = relationship("Muscle")
