from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, JSON, Enum as SQLEnum, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base
from app.models.enums import CircuitType, MetricType, MovementTier, PrimaryRegion


class CircuitMelted(Base):
    """
    Circuit-movement junction table with exercise-specific details.
    
    This table normalizes the circuit_templates structure by exploding
    the exercises_json array into individual rows, enabling:
    - Efficient querying of circuits by movement
    - Exercise-level metrics and scaling
    - Better data integrity and relationships
    """
    __tablename__ = "circuits_melted"
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Keys (CRITICAL: Maintain referential integrity)
    circuit_id = Column(
        Integer, 
        ForeignKey("circuit_templates.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="References parent circuit_template"
    )
    movement_id = Column(
        Integer, 
        ForeignKey("movements.id", ondelete="RESTRICT"), 
        nullable=True,
        index=True,
        comment="References the movement/exercise (nullable for custom exercises)"
    )
    
    # Exercise Sequence & Positioning
    exercise_sequence = Column(
        Integer, 
        nullable=False,
        index=True,
        comment="Position of this exercise within the circuit (1-based)"
    )
    
    # Exercise Identification (Denormalized for performance)
    movement_name = Column(
        String(200), 
        nullable=False,
        comment="Denormalized movement name for fast reads"
    )
    
    # Exercise Metrics (Matches CircuitTemplate structure)
    metric_type = Column(
        SQLEnum(MetricType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        comment="How this exercise is measured (reps, time, distance, etc.)"
    )
    
    # Metric Values (Mutually exclusive based on metric_type)
    reps = Column(
        Integer, 
        nullable=True,
        comment="Number of repetitions (when metric_type=REPS)"
    )
    distance_meters = Column(
        Float, 
        nullable=True,
        comment="Distance in meters (when metric_type=DISTANCE)"
    )
    duration_seconds = Column(
        Integer, 
        nullable=True,
        comment="Duration in seconds (when metric_type=TIME)"
    )
    calories = Column(
        Integer, 
        nullable=True,
        comment="Calories (when metric_type=TIME_UNDER_TENSION or cardio)"
    )
    
    # Rest & Notes
    rest_seconds = Column(
        Integer, 
        nullable=True,
        comment="Rest time after this exercise in seconds"
    )
    notes = Column(
        Text, 
        nullable=True,
        comment="Exercise-specific notes or scaling instructions"
    )
    
    # RX Weights (Prescribed weights for different sexes)
    rx_weight_male = Column(
        Float, 
        nullable=True,
        comment="Prescribed weight for male athletes (lbs or kg)"
    )
    rx_weight_female = Column(
        Float, 
        nullable=True,
        comment="Prescribed weight for female athletes (lbs or kg)"
    )
    
    # Timestamps for data lineage
    created_at = Column(
        Float, 
        default=datetime.utcnow().timestamp,
        comment="When this melted record was created (Unix timestamp)"
    )
    updated_at = Column(
        Float, 
        default=datetime.utcnow().timestamp, 
        onupdate=datetime.utcnow().timestamp,
        comment="When this melted record was last updated (Unix timestamp)"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "exercise_sequence > 0",
            name="valid_exercise_sequence"
        ),
        # At least one metric value must be set
        CheckConstraint(
            "(reps IS NOT NULL) OR (distance_meters IS NOT NULL) OR "
            "(duration_seconds IS NOT NULL) OR (calories IS NOT NULL)",
            name="at_least_one_metric"
        ),
        # Unique constraint for circuit+sequence to prevent duplicates
        UniqueConstraint(
            'circuit_id', 'exercise_sequence',
            name='uq_circuit_exercise_sequence'
        ),
    )
    
    # Relationships
    circuit = relationship("CircuitTemplate", back_populates="melted_exercises")
    movement = relationship("Movement")
    
    def __repr__(self):
        return f"<CircuitMelted(id={self.id}, circuit_id={self.circuit_id}, " \
               f"movement_id={self.movement_id}, sequence={self.exercise_sequence})>"


class CircuitMacro(Base):
    """
    Circuit-level aggregated metrics.
    
    This table stores pre-computed aggregate metrics for each circuit,
    enabling fast circuit comparison and filtering without querying
    all melted exercises. Updated when circuits_melted changes.
    """
    __tablename__ = "circuits_macro"
    
    # Primary Key (1:1 with circuit_templates)
    circuit_id = Column(
        Integer, 
        ForeignKey("circuit_templates.id", ondelete="CASCADE"), 
        primary_key=True,
        comment="References parent circuit_template"
    )
    
    # Exercise Count & Structure
    total_exercises = Column(
        Integer, 
        nullable=False,
        index=True,
        comment="Total number of exercises in this circuit"
    )
    unique_movements = Column(
        Integer, 
        nullable=False,
        comment="Number of unique movements (some may repeat)"
    )
    
    # Primary Metrics (Aggregated from melted data)
    total_reps = Column(
        Integer, 
        nullable=True,
        comment="Total repetitions across all exercises (if applicable)"
    )
    total_distance_meters = Column(
        Float, 
        nullable=True,
        comment="Total distance in meters across all exercises"
    )
    total_work_seconds = Column(
        Integer, 
        nullable=True,
        comment="Total estimated work time in seconds"
    )
    total_rest_seconds = Column(
        Integer, 
        nullable=True,
        comment="Total rest time in seconds across all exercises"
    )
    
    # Intensity & Difficulty Metrics
    estimated_duration_seconds = Column(
        Integer, 
        nullable=True,
        index=True,
        comment="Estimated total duration including work + rest"
    )
    difficulty_tier = Column(
        SQLEnum(MovementTier, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MovementTier.BRONZE,
        index=True,
        comment="Overall difficulty classification"
    )
    min_recovery_hours = Column(
        Integer, 
        nullable=False,
        default=24,
        comment="Recommended minimum recovery time after this circuit"
    )
    
    # RX Weight Ranges (Aggregate of all exercises)
    max_rx_weight_male = Column(
        Float, 
        nullable=True,
        comment="Maximum RX weight across all exercises (male)"
    )
    max_rx_weight_female = Column(
        Float, 
        nullable=True,
        comment="Maximum RX weight across all exercises (female)"
    )
    
    # Muscle Engagement (Aggregated from movement data)
    primary_muscles = Column(
        JSONB, 
        nullable=False,
        default=list,
        comment="List of primary muscle groups targeted"
    )
    muscle_engagement_score = Column(
        Float, 
        nullable=False,
        default=0.0,
        comment="Normalized score (0-1) indicating muscle engagement intensity"
    )
    
    # Region Classification (for comparability with movements)
    primary_region = Column(
        SQLEnum(PrimaryRegion, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
        default="full_body",
        comment="Dominant body region: upper, lower, full_body"
    )
    region_diversity_score = Column(
        Float, 
        nullable=False,
        default=0.0,
        comment="Simpson's diversity index for body regions (0-1)"
    )
    
    # Equipment Requirements (Aggregate of all movements)
    required_equipment = Column(
        JSONB, 
        nullable=False,
        default=list,
        comment="List of equipment IDs required for this circuit"
    )
    equipment_complexity = Column(
        Integer, 
        nullable=False,
        default=0,
        comment="Count of unique equipment items needed"
    )
    
    # Movement Pattern Distribution
    movement_pattern_counts = Column(
        JSONB, 
        nullable=False,
        default=dict,
        comment="Count of exercises by pattern: {'squat': 2, 'hinge': 1, ...}"
    )
    pattern_diversity_score = Column(
        Float, 
        nullable=False,
        default=0.0,
        comment="Simpson's diversity index for movement patterns (0-1)"
    )
    
    # Metabolic Profile
    metabolic_profile = Column(
        JSONB, 
        nullable=False,
        default=dict,
        comment="Breakdown: {'anabolic': 0.4, 'metabolic': 0.6, 'neural': 0.0}"
    )
    estimated_calories_per_hour = Column(
        Integer, 
        nullable=True,
        comment="Estimated calories burned per hour"
    )
    
    # Space & Logistics Requirements
    space_requirement_meters = Column(
        Float, 
        nullable=True,
        comment="Minimum space required in square meters"
    )
    station_count = Column(
        Integer, 
        nullable=False,
        default=1,
        comment="Number of simultaneous stations needed"
    )
    
    # Circuit-Specific Metrics
    default_rounds = Column(
        Integer, 
        nullable=True,
        comment="Default number of rounds for circuit completion"
    )
    circuit_type_intensity = Column(
        Float, 
        nullable=False,
        default=1.0,
        comment="Intensity multiplier based on circuit type (AMRAP > RFT)"
    )
    
    # Quality Metrics
    data_completeness_score = Column(
        Float, 
        nullable=False,
        default=1.0,
        comment="Percentage of required fields populated (0-1)"
    )
    validation_errors = Column(
        JSONB, 
        nullable=False,
        default=list,
        comment="List of validation errors or warnings"
    )
    
    # Timestamps for data lineage
    created_at = Column(
        Float, 
        default=datetime.utcnow().timestamp,
        comment="When this macro record was created (Unix timestamp)"
    )
    updated_at = Column(
        Float, 
        default=datetime.utcnow().timestamp, 
        onupdate=datetime.utcnow().timestamp,
        comment="When this macro record was last recalculated (Unix timestamp)"
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint("total_exercises >= 1", name="valid_exercise_count"),
        CheckConstraint("unique_movements >= 1", name="valid_unique_movements"),
        CheckConstraint("min_recovery_hours >= 0", name="valid_recovery"),
    )
    
    # Relationships
    circuit = relationship("CircuitTemplate", back_populates="macro_metrics")
    
    def __repr__(self):
        return f"<CircuitMacro(circuit_id={self.circuit_id}, " \
               f"total_exercises={self.total_exercises}, tier={self.difficulty_tier})>"
