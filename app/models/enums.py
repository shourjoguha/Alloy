"""Enum definitions for database models."""
from enum import Enum


class MovementPattern(str, Enum):
    """Movement pattern categories."""
    SQUAT = "squat"
    HINGE = "hinge"
    HORIZONTAL_PUSH = "horizontal_push"
    VERTICAL_PUSH = "vertical_push"
    HORIZONTAL_PULL = "horizontal_pull"
    VERTICAL_PULL = "vertical_pull"
    CARRY = "carry"
    CORE = "core"
    LUNGE = "lunge"
    ROTATION = "rotation"
    PLYOMETRIC = "plyometric"
    OLYMPIC = "olympic"
    ISOLATION = "isolation"
    MOBILITY = "mobility"
    ISOMETRIC = "isometric"
    CONDITIONING = "conditioning"
    CARDIO = "cardio"

class PrimaryRegion(str, Enum):
    ANTERIOR_LOWER = "anterior lower"
    POSTERIOR_LOWER = "posterior lower"
    SHOULDER = "shoulder"
    ANTERIOR_UPPER = "anterior upper"
    POSTERIOR_UPPER = "posterior upper"
    FULL_BODY = "full body"
    LOWER_BODY = "lower body"
    UPPER_BODY = "upper body"
    CORE = "core"

class PrimaryMuscle(str, Enum):
    """Primary muscle groups."""
    QUADRICEPS = "quadriceps"    
    HAMSTRINGS = "hamstrings"
    GLUTES = "glutes"
    CALVES = "calves"
    CHEST = "chest"
    LATS = "lats"
    UPPER_BACK = "upper_back"
    REAR_DELTS = "rear_delts"
    FRONT_DELTS = "front_delts"
    SIDE_DELTS = "side_delts"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    FOREARMS = "forearms"
    CORE = "core"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower_back"
    HIP_FLEXORS = "hip_flexors"
    ADDUCTORS = "adductors"
    FULL_BODY = "full_body"


class MetricType(str, Enum):
    """How the movement is measured."""
    REPS = "reps"
    TIME = "time"
    TIME_UNDER_TENSION = "time_under_tension"
    DISTANCE = "distance"


class SkillLevel(str, Enum):
    """Movement skill/complexity level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    ELITE = "elite"


class CNSLoad(str, Enum):
    """Central nervous system load category."""
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Goal(str, Enum):
    """Training goals."""
    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"
    ENDURANCE = "endurance"
    FAT_LOSS = "fat_loss"
    MOBILITY = "mobility"
    EXPLOSIVENESS = "explosiveness"
    SPEED = "speed"


class SplitTemplate(str, Enum):
    """Program split templates."""
    UPPER_LOWER = "upper_lower"
    PPL = "ppl"  # Push/Pull/Legs
    FULL_BODY = "full_body"
    HYBRID = "hybrid"  # User-customizable


class ProgressionStyle(str, Enum):
    """Progression methodologies."""
    SINGLE_PROGRESSION = "single_progression"  # Increase weight when hitting rep target
    DOUBLE_PROGRESSION = "double_progression"  # Increase reps then weight
    PAUSED_VARIATIONS = "paused_variations"  # Add pauses for progression
    BUILD_TO_DROP = "build_to_drop"  # Build to rep range, drop reps + increase load
    WAVE_LOADING = "wave_loading"  # Vary load/reps in waves (e.g. 7-5-3)


class MovementRuleType(str, Enum):
    """User movement preference rules."""
    HARD_NO = "hard_no"  # Never include
    HARD_YES = "hard_yes"  # Must appear at least once per microcycle
    PREFERRED = "preferred"  # Must appear at least once every 2 weeks
    INCLUDE = "include"
    EXCLUDE = "exclude"
    BIAS = "bias"


class RuleOperator(str, Enum):
    """Operator for movement rules."""
    EQ = "eq"
    GT = "gt"
    LT = "lt"
    LTE = "lte"
    GTE = "gte"


class SpinalCompression(str, Enum):
    """Level of spinal loading."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class DisciplineType(str, Enum):
    """Standardized disciplines."""
    POWERLIFTING = "powerlifting"
    OLYMPIC_WEIGHTLIFTING = "olympic_weightlifting"
    BODYBUILDING = "bodybuilding"
    CROSSFIT = "crossfit"
    STRONGMAN = "strongman"
    CALISTHENICS = "calisthenics"
    YOGA = "yoga"
    RUNNING = "running"
    OTHER = "other"


class SessionSection(str, Enum):
    """Section of a training session. Deprecated: Use ExerciseRole instead."""
    WARMUP = "warmup"
    MAIN = "main"
    ACCESSORY = "accessory"
    SKILL = "skill"
    FINISHER = "finisher"
    COOLDOWN = "cooldown"
    CARDIO = "cardio"
    CONDITIONING = "conditioning"


class RuleCadence(str, Enum):
    """Cadence for movement rules."""
    PER_MICROCYCLE = "per_microcycle"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"


class EnjoyableActivity(str, Enum):
    """Enjoyable activities for recommendations."""
    TENNIS = "tennis"
    BOULDERING = "bouldering"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    HIKING = "hiking"
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    YOGA = "yoga"
    MARTIAL_ARTS = "martial_arts"
    DANCE = "dance"
    OTHER = "other"


class SessionType(str, Enum):
    """Types of training sessions."""
    UPPER = "upper"
    LOWER = "lower"
    PUSH = "push"
    PULL = "pull"
    LEGS = "legs"
    FULL_BODY = "full_body"
    CARDIO = "cardio"
    MOBILITY = "mobility"
    RECOVERY = "recovery"
    SKILL = "skill"
    CUSTOM = "custom"


class ExerciseRole(str, Enum):
    """Role of exercise within a session."""
    WARMUP = "warmup"
    MAIN = "main"
    ACCESSORY = "accessory"
    SKILL = "skill"
    FINISHER = "finisher"
    COOLDOWN = "cooldown"
    CARDIO = "cardio"
    CONDITIONING = "conditioning"


class MicrocycleStatus(str, Enum):
    """Status of a microcycle."""
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETE = "complete"


class E1RMFormula(str, Enum):
    """Estimated 1RM calculation formulas."""
    EPLEY = "epley"
    BRZYCKI = "brzycki"
    LOMBARDI = "lombardi"
    OCONNER = "oconner"


class RecoverySource(str, Enum):
    """Source of recovery signals."""
    DUMMY = "dummy"
    MANUAL = "manual"
    GARMIN = "garmin"
    APPLE = "apple"
    AURA_RING = "aura ring"
    WHOOP_BAND = "whoop band"

class PersonaTone(str, Enum):
    """Coach communication tone presets."""
    DRILL_SERGEANT = "drill_sergeant"
    SUPPORTIVE = "supportive"
    ANALYTICAL = "analytical"
    MOTIVATIONAL = "motivational"
    MINIMALIST = "minimalist"


class RelationshipType(str, Enum):
    """Types of relationships between movements."""
    PROGRESSION = "progression"   # Target is harder/more complex
    REGRESSION = "regression"     # Target is easier/less complex
    VARIATION = "variation"       # Similar pattern, different emphasis
    ANTAGONIST = "antagonist"     # Opposing muscle group
    PREP = "prep"                # Warmup/activation for target


class CircuitType(str, Enum):
    """Types of circuit structures."""
    ROUNDS_FOR_TIME = "rounds_for_time"  # e.g., 3 rounds of X, Y, Z
    AMRAP = "amrap"                      # As many rounds as possible in time T
    EMOM = "emom"                        # Every minute on the minute
    LADDER = "ladder"                    # 21-15-9 or 1-2-3-4...
    TABATA = "tabata"                    # 20s work / 10s rest intervals
    CHIPPER = "chipper"                  # One big list to complete once
    STATION = "station"                  # Hyrox/race station (Run 1km + 100 Wall balls)


class StressBucket(str, Enum):
    """Buckets for normalizing training stress."""
    STRENGTH = "strength"         # Neuromuscular/mechanical load
    CONDITIONING = "conditioning" # Metabolic/cardiovascular load
    IMPACT_UPPER = "impact_upper" # Joint/tissue stress upper body
    IMPACT_LOWER = "impact_lower" # Joint/tissue stress lower body
    CNS = "cns"                   # Central nervous system fatigue


class PersonaAggression(str, Enum):
    """Programming aggressiveness level."""
    CONSERVATIVE = "CONSERVATIVE"
    MODERATE_CONSERVATIVE = "MODERATE_CONSERVATIVE"
    BALANCED = "BALANCED"
    MODERATE_AGGRESSIVE = "MODERATE_AGGRESSIVE"
    AGGRESSIVE = "AGGRESSIVE"


class ExperienceLevel(str, Enum):
    """User experience level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class Visibility(str, Enum):
    """Content visibility level."""
    PRIVATE = "private"  # Only creator
    FRIENDS = "friends"  # Creator + friends/team
    PUBLIC = "public"    # Everyone


class Sex(str, Enum):
    """User sex for biometric and health calculations."""
    FEMALE = "female"
    MALE = "male"
    INTERSEX = "intersex"
    UNSPECIFIED = "unspecified"


class DataSource(str, Enum):
    """Source of time-series or ingested records."""
    MANUAL = "manual"
    PROVIDER = "provider"
    ESTIMATED = "estimated"


class BiometricMetricType(str, Enum):
    """Types of biometric measurements tracked over time."""
    WEIGHT_KG = "weight_kg"
    BODY_FAT_PERCENT = "body_fat_percent"
    RESTING_HR = "resting_hr"
    HRV = "hrv"
    SLEEP_HOURS = "sleep_hours"
    VO2_MAX = "vo2_max"


class GoalType(str, Enum):
    """High-level goal category; detailed targets live in target_json."""
    PERFORMANCE = "performance"
    BODY_COMPOSITION = "body_composition"
    SKILL = "skill"
    HEALTH = "health"
    HABIT = "habit"
    OTHER = "other"


class GoalStatus(str, Enum):
    """Lifecycle status of a goal."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ExternalProvider(str, Enum):
    """External health/fitness provider."""
    STRAVA = "strava"
    GARMIN = "garmin"
    APPLE_HEALTH = "apple_health"
    WHOOP = "whoop"
    OURA = "oura"
    OTHER = "other"


class IngestionRunStatus(str, Enum):
    """Status for an ingestion run."""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DisciplineCategory(str, Enum):
    """High-level grouping for disciplines."""
    TRAINING = "training"
    SPORT = "sport"
    RECOVERY = "recovery"
    OTHER = "other"


class ActivityCategory(str, Enum):
    """High-level grouping for activity definitions."""
    STRENGTH = "strength"
    CARDIO = "cardio"
    MOBILITY = "mobility"
    SPORT = "sport"
    RECOVERY = "recovery"
    OTHER = "other"


class ActivitySource(str, Enum):
    """How an activity instance was created."""
    PLANNED = "planned"
    MANUAL = "manual"
    PROVIDER = "provider"


class MuscleRole(str, Enum):
    """Role of a muscle in an activity or movement."""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    STABILIZER = "stabilizer"


class MovementTier(str, Enum):
    """Movement ROI tier - indicates exercise value and priority."""
    DIAMOND = "diamond"
    GOLD = "gold"
    SILVER = "silver"
    BRONZE = "bronze"


class MetabolicDemand(str, Enum):
    """Primary metabolic system used by the movement."""
    ANABOLIC = "anabolic"
    METABOLIC = "metabolic"
    NEURAL = "neural"
