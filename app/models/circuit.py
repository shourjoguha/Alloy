from sqlalchemy import Column, Integer, String, Text, JSON, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.models.enums import CircuitType


class CircuitTemplate(Base):
    __tablename__ = "circuit_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    circuit_type = Column(SQLEnum(CircuitType), nullable=False)
    exercises_json = Column(JSON, nullable=False, default=list)
    default_rounds = Column(Integer, nullable=True)
    default_duration_seconds = Column(Integer, nullable=True)
    bucket_stress = Column(JSON, nullable=False, default=dict)
    tags = Column(JSON, default=list)
    difficulty_tier = Column(Integer, default=1)
    
    # Fitness Function Metrics (parallel to Movement model)
    fatigue_factor = Column(Float, nullable=False, default=1.0)
    stimulus_factor = Column(Float, nullable=False, default=1.0)
    min_recovery_hours = Column(Integer, nullable=False, default=24)
    
    # Muscle-level metrics (normalized)
    muscle_volume = Column(JSON, nullable=False, default=dict)
    muscle_fatigue = Column(JSON, nullable=False, default=dict)
    
    # Circuit-specific metrics
    total_reps = Column(Integer, nullable=True)
    estimated_work_seconds = Column(Integer, nullable=True)
    effective_work_volume = Column(Float, nullable=True)
    
    # Relationships to melted and macro tables
    melted_exercises = relationship(
        "CircuitMelted", 
        back_populates="circuit", 
        cascade="all, delete-orphan",
        order_by="CircuitMelted.exercise_sequence"
    )
    macro_metrics = relationship(
        "CircuitMacro", 
        back_populates="circuit", 
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CircuitTemplate(id={self.id}, name='{self.name}', type={self.circuit_type})>"

