// ========================================
// ENUMS (matching backend)
// ========================================

export enum Goal {
  STRENGTH = 'strength',
  HYPERTROPHY = 'hypertrophy',
  ENDURANCE = 'endurance',
  FAT_LOSS = 'fat_loss',
  MOBILITY = 'mobility',
  EXPLOSIVENESS = 'explosiveness',
  SPEED = 'speed',
}

export enum SplitTemplate {
  UPPER_LOWER = 'upper_lower',
  PPL = 'ppl',
  FULL_BODY = 'full_body',
  HYBRID = 'hybrid',
}

export enum ProgressionStyle {
  SINGLE_PROGRESSION = 'single_progression',
  DOUBLE_PROGRESSION = 'double_progression',
  PAUSED_VARIATIONS = 'paused_variations',
  BUILD_TO_DROP = 'build_to_drop',
  WAVE_LOADING = 'wave_loading',
}

export enum SessionType {
  UPPER = 'upper',
  LOWER = 'lower',
  PUSH = 'push',
  PULL = 'pull',
  LEGS = 'legs',
  FULL_BODY = 'full_body',
  CARDIO = 'cardio',
  MOBILITY = 'mobility',
  RECOVERY = 'recovery',
  SKILL = 'skill',
  CUSTOM = 'custom',
}

export enum MicrocycleStatus {
  PLANNED = 'planned',
  ACTIVE = 'active',
  COMPLETE = 'complete',
}

export enum MovementPattern {
  SQUAT = 'squat',
  HINGE = 'hinge',
  HORIZONTAL_PUSH = 'horizontal_push',
  VERTICAL_PUSH = 'vertical_push',
  HORIZONTAL_PULL = 'horizontal_pull',
  VERTICAL_PULL = 'vertical_pull',
  CARRY = 'carry',
  CORE = 'core',
  LUNGE = 'lunge',
  ROTATION = 'rotation',
  PLYOMETRIC = 'plyometric',
  OLYMPIC = 'olympic',
  ISOLATION = 'isolation',
  MOBILITY = 'mobility',
  ISOMETRIC = 'isometric',
  CONDITIONING = 'conditioning',
  CARDIO = 'cardio',
}

export enum PrimaryRegion {
  ANTERIOR_LOWER = "anterior lower",
  POSTERIOR_LOWER = "posterior lower",
  SHOULDER = "shoulder",
  ANTERIOR_UPPER = "anterior upper",
  POSTERIOR_UPPER = "posterior upper",
  FULL_BODY = "full body",
}

export enum PrimaryMuscle {
  QUADRICEPS = "quadriceps",
  HAMSTRINGS = "hamstrings",
  GLUTES = "glutes",
  CALVES = "calves",
  CHEST = "chest",
  LATS = "lats",
  UPPER_BACK = "upper_back",
  REAR_DELTS = "rear_delts",
  FRONT_DELTS = "front_delts",
  SIDE_DELTS = "side_delts",
  BICEPS = "biceps",
  TRICEPS = "triceps",
  FOREARMS = "forearms",
  CORE = "core",
  OBLIQUES = "obliques",
  LOWER_BACK = "lower_back",
  HIP_FLEXORS = "hip_flexors",
  ADDUCTORS = "adductors",
  ABDUCTORS = "abductors",
  FULL_BODY = "full_body",
}

export enum SkillLevel {
  BEGINNER = "beginner",
  INTERMEDIATE = "intermediate",
  ADVANCED = "advanced",
  EXPERT = "expert",
  ELITE = "elite",
}

export enum CNSLoad {
  VERY_LOW = "very_low",
  LOW = "low",
  MODERATE = "moderate",
  HIGH = "high",
  VERY_HIGH = "very_high",
}

export enum MetricType {
  REPS = "reps",
  TIME = "time",
  TIME_UNDER_TENSION = "time_under_tension",
  DISTANCE = "distance",
}

export enum ExperienceLevel {
  BEGINNER = 'beginner',
  INTERMEDIATE = 'intermediate',
  ADVANCED = 'advanced',
  ELITE = 'elite',
}

export enum Sex {
  MALE = 'male',
  FEMALE = 'female',
  INTERSEX = 'intersex',
  UNSPECIFIED = 'unspecified',
}

export enum MovementRuleType {
  HARD_NO = 'hard_no',
  HARD_YES = 'hard_yes',
  PREFERRED = 'preferred',
}

export enum CircuitType {
  ROUNDS_FOR_TIME = 'rounds_for_time',
  AMRAP = 'amrap',
  EMOM = 'emom',
  LADDER = 'ladder',
  TABATA = 'tabata',
  CHIPPER = 'chipper',
  STATION = 'station',
}

export enum PersonaTone {
  DRILL_SERGEANT = 'drill_sergeant',
  SUPPORTIVE = 'supportive',
  ANALYTICAL = 'analytical',
  MOTIVATIONAL = 'motivational',
  MINIMALIST = 'minimalist',
}

export enum PersonaAggression {
  CONSERVATIVE = 'CONSERVATIVE',
  MODERATE_CONSERVATIVE = 'MODERATE_CONSERVATIVE',
  BALANCED = 'BALANCED',
  MODERATE_AGGRESSIVE = 'MODERATE_AGGRESSIVE',
  AGGRESSIVE = 'AGGRESSIVE',
}

export enum RecoverySource {
  DUMMY = 'dummy',
  MANUAL = 'manual',
  GARMIN = 'garmin',
  APPLE = 'apple',
  AURA_RING = 'aura_ring',
  WHOOP_BAND = 'whoop_band',
}

// ========================================
// PROGRAM TYPES
// ========================================

export interface GoalWeight {
  goal: Goal;
  weight: number;
}

export interface DisciplineWeight {
  discipline: string;
  weight: number;
}

export interface ProgramCreate {
  name?: string;
  goals: GoalWeight[];
  duration_weeks: number;
  program_start_date?: string;
  split_template?: SplitTemplate;
  days_per_week: number;
  max_session_duration?: number;
  progression_style?: ProgressionStyle;
  hybrid_definition?: HybridDefinition;
  deload_every_n_microcycles?: number;
  persona_tone?: PersonaTone;
  persona_aggression?: PersonaAggression;
  disciplines?: DisciplineWeight[];
  movement_rules?: MovementRuleCreate[];
  enjoyable_activities?: EnjoyableActivityCreate[];
}

export interface HybridDefinition {
  mode: 'day_by_day' | 'block_composition';
  days?: HybridDayDefinition[];
  composition?: HybridBlockComposition;
}

export interface HybridDayDefinition {
  day: number;
  session_type: SessionType;
  focus?: string[];
  notes?: string;
}

export interface HybridBlockComposition {
  blocks: string[];
}

export interface Program {
  id: number;
  user_id: number;
  name?: string;
  program_start_date?: string;
  duration_weeks: number;
  goal_1: Goal;
  goal_2: Goal;
  goal_3: Goal;
  goal_weight_1: number;
  goal_weight_2: number;
  goal_weight_3: number;
  split_template: SplitTemplate;
  days_per_week: number;
  progression_style: ProgressionStyle;
  hybrid_definition?: Record<string, unknown>;
  deload_every_n_microcycles: number;
  persona_tone?: PersonaTone;
  persona_aggression?: PersonaAggression;
  is_active: boolean;
  created_at?: string;
}

export interface ProgramUpdate {
  name?: string | null;
  is_active?: boolean;
}

export interface MicrocycleWithSessions extends Microcycle {
  sessions: Session[];
}

export interface ProgramWithMicrocycle {
  program: Program;
  active_microcycle?: Microcycle;
  upcoming_sessions: Session[];
  microcycles?: MicrocycleWithSessions[];
}

// ========================================
// MICROCYCLE & SESSION TYPES
// ========================================

export interface Microcycle {
  id: number;
  program_id: number;
  micro_start_date?: string;
  length_days: number;
  sequence_number: number;
  status: MicrocycleStatus;
  is_deload: boolean;
}

export interface Session {
  id: number;
  microcycle_id: number;
  session_date?: string;
  day_number: number;
  session_type: SessionType;
  intent_tags: string[];
  warmup?: ExerciseBlock[];
  main?: ExerciseBlock[];
  accessory?: ExerciseBlock[];
  finisher?: FinisherBlock;
  cooldown?: ExerciseBlock[];
  estimated_duration_minutes?: number;
  warmup_duration_minutes?: number;
  main_duration_minutes?: number;
  accessory_duration_minutes?: number;
  finisher_duration_minutes?: number;
  cooldown_duration_minutes?: number;
  coach_notes?: string;
}

export interface ExerciseBlock {
  movement: string;
  movement_id?: number;
  sets?: number;  // Optional for cooldown/stretches that only have duration
  reps?: number; // Fixed rep count (e.g. for circuit exercises)
  rep_range_min?: number;
  rep_range_max?: number;
  target_rpe?: number;
  target_rir?: number;
  duration_seconds?: number;
  rest_seconds?: number;
  superset_with?: string;
  notes?: string;
}

export interface FinisherBlock {
  type: string;
  circuit_type?: string; // e.g. AMRAP, EMOM, RFT
  duration_minutes?: number;
  rounds?: string | number; // Support text like "Max Rounds"
  exercises?: ExerciseBlock[];
  notes?: string;
}

// ========================================
// CIRCUIT TYPES
// ========================================

export interface CircuitTemplate {
  id: number;
  name: string;
  description?: string;
  circuit_type: CircuitType;
  exercises_json: Record<string, unknown>[];
  default_rounds?: number;
  default_duration_seconds?: number;
  tags: string[];
  difficulty_tier: number;
}

export interface CircuitTemplateAdminDetail extends CircuitTemplate {
  raw_workout?: string | null;
}

// ========================================
// DAILY PLANNING TYPES
// ========================================

export interface DailyPlan {
  plan_date?: string;
  session?: Session;
  is_rest_day: boolean;
  recommended_activities?: string[];
  coach_message?: string;
}

export interface AdaptationRequest {
  program_id: number;
  focus_for_today?: string;
  preference?: 'lift' | 'calisthenics' | 'cardio' | 'sport' | 'any';
  excluded_movements?: string[];
  excluded_patterns?: string[];
  time_available_minutes?: number;
  soreness?: SorenessInput[];
  recovery?: RecoveryInput;
  activity_yesterday?: string;
  adherence_vs_optimality?: 'adherence' | 'optimality' | 'balanced';
  persona_tone_override?: PersonaTone;
  persona_aggression_override?: PersonaAggression;
  thread_id?: number;
  user_message?: string;
}

export interface SorenessInput {
  body_part: string;
  level: number;
}

export interface RecoveryInput {
  sleep_quality?: 'poor' | 'fair' | 'good' | 'excellent';
  sleep_hours?: number;
  energy_level?: number;
  stress_level?: number;
  notes?: string;
}

export interface AdaptationResponse {
  plan_date?: string;
  original_session_type?: SessionType;
  adapted_plan?: AdaptedSessionPlan;
  changes_made: string[];
  reasoning: string;
  trade_offs?: string;
  alternative_suggestion?: string;
  follow_up_question?: string;
  thread_id?: number;
}

export interface AdaptedSessionPlan {
  warmup?: ExerciseBlock[];
  main?: ExerciseBlock[];
  accessory?: ExerciseBlock[];
  finisher?: FinisherBlock;
  cooldown?: ExerciseBlock[];
  estimated_duration_minutes: number;
  reasoning: string;
  trade_offs?: string;
}

// ========================================
// LOGGING TYPES
// ========================================

export interface WorkoutLogCreate {
  session_id?: number;
  log_date?: string;
  started_at?: string;
  ended_at?: string;
  completed?: boolean;
  top_sets?: TopSetCreate[];
  exercises_completed?: Record<string, unknown>[];
  notes?: string;
  perceived_exertion?: number;
  energy_level?: number;
  adherence_percentage?: number;
  coach_feedback_request?: string;
}

export interface TopSetCreate {
  movement_id: number;
  weight: number;
  reps: number;
  rpe?: number;
  rir?: number;
}

export interface WorkoutLog {
  id: number;
  user_id?: number;
  session_id?: number;
  log_date?: string;
  started_at?: string;
  ended_at?: string;
  completed: boolean;
  notes?: string;
  perceived_exertion?: number;
  energy_level?: number;
  adherence_percentage?: number;
  coach_feedback_request?: string;
  exercises_completed?: Record<string, unknown>[];
  top_sets: TopSetLog[];
  created_at?: string;
}

export interface TopSetLog {
  id: number;
  movement_id: number;
  movement_name?: string;
  weight: number;
  reps: number;
  rpe?: number;
  e1rm?: number;
  is_pr: boolean;
}

export interface SorenessLogCreate {
  log_date?: string;
  body_part: string;
  soreness_1_5: number;
  notes?: string;
}

export interface SorenessLog {
  id: number;
  log_date?: string;
  body_part: string;
  soreness_1_5: number;
  notes?: string;
}

export interface RecoverySignalCreate {
  log_date?: string;
  source?: RecoverySource;
  hrv?: number;
  resting_hr?: number;
  sleep_score?: number;
  sleep_hours?: number;
  readiness?: number;
  raw_payload?: Record<string, unknown>;
  notes?: string;
}

export interface RecoverySignal {
  id: number;
  log_date?: string;
  source: RecoverySource;
  hrv?: number;
  resting_hr?: number;
  sleep_score?: number;
  sleep_hours?: number;
  readiness?: number;
  notes?: string;
}

// ========================================
// ACTIVITY & CUSTOM WORKOUT TYPES
// ========================================

export enum ExerciseRole {
  WARMUP = 'warmup',
  MAIN = 'main',
  ACCESSORY = 'accessory',
  SKILL = 'skill',
  FINISHER = 'finisher',
  COOLDOWN = 'cooldown',
  CARDIO = 'cardio',
  CONDITIONING = 'conditioning',
}

export interface ActivityDefinition {
  id: number;
  name: string;
  category: string;
  is_custom: boolean;
}

export interface ActivityInstanceCreate {
  activity_definition_id: number;
  activity_name?: string;
  log_date?: string;
  duration_minutes: number;
  distance_km?: number;
  notes?: string;
  perceived_difficulty?: number;
  enjoyment_rating?: number;
}

export interface CustomExerciseCreate {
  movement_id: number;
  sets: number;
  reps?: number;
  weight?: number;
  distance_meters?: number;
  duration_seconds?: number;
  notes?: string;
}

export interface CustomWorkoutCreate {
  log_date: string;
  workout_name?: string;
  duration_minutes?: number;
  notes?: string;
  perceived_difficulty?: number;
  enjoyment_rating?: number;
  
  warmup?: CustomExerciseCreate[];
  main?: CustomExerciseCreate[];
  accessory?: CustomExerciseCreate[];
  finisher?: CustomExerciseCreate[];
  cooldown?: CustomExerciseCreate[];
  
  main_circuit_id?: number;
  finisher_circuit_id?: number;
}

// ========================================
// SETTINGS TYPES
// ========================================

export interface UserSettings {
  id: number;
  persona_coaching_style?: string;
  persona_strictness?: number;
  persona_humor?: number;
  persona_explanation_level?: number;
  notification_preference?: string;
  preferred_units?: string;
  default_session_duration_minutes?: number;
  e1rm_formula?: string;
}

export interface Movement {
  id: number;
  name: string;
  primary_pattern?: MovementPattern;
  primary_region?: PrimaryRegion;
  primary_muscles?: PrimaryMuscle[];
  secondary_muscles?: PrimaryMuscle[];
  default_equipment?: string;
  equipment_tags?: string[];
  complexity?: string | number;
  skill_level?: SkillLevel;
  is_compound: boolean;
  cns_load?: CNSLoad;
  metric_type?: MetricType;
  description?: string;
  user_id?: number;
  created_at?: string;
}

export interface MovementCreate {
  name: string;
  primary_pattern: MovementPattern;
  primary_region: PrimaryRegion;
  primary_muscles: PrimaryMuscle[];
  secondary_muscles: PrimaryMuscle[];
  default_equipment?: string;
  equipment_tags: string[];
  complexity: number;
  skill_level: SkillLevel;
  is_compound: boolean;
  cns_load: CNSLoad;
  metric_type: MetricType;
  description?: string;
}

export interface MovementRuleCreate {
  movement_id: number;
  rule_type: MovementRuleType | string;
  cadence?: string;
  notes?: string;
}

export interface MovementRule {
  id: number;
  movement_id: number;
  movement_name?: string;
  rule_type: string;
  substitute_movement_id?: number;
  substitute_movement_name?: string;
  cadence?: string;
  reason?: string;
  notes?: string;
}

export interface EnjoyableActivityCreate {
  activity_type: string;
  custom_name?: string;
  recommend_every_days?: number;
}

export interface EnjoyableActivity {
  id: number;
  activity_name?: string;
  activity_type?: string;
  category?: string;
  typical_duration_minutes?: number;
  recommend_every_days?: number;
  enabled?: boolean;
}

// ========================================
// API RESPONSE TYPES
// ========================================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthCheck {
  status: 'healthy' | 'unhealthy';
  app?: string;
  provider?: string;
  model?: string;
}

export interface DisciplinePreferences {
  mobility: number;
  calisthenics: number;
  olympic_lifts: number;
  crossfit: number;
  strength: number;
}

export interface DisciplineExperience {
  mobility?: ExperienceLevel;
  calisthenics?: ExperienceLevel;
  olympic_lifts?: ExperienceLevel;
  crossfit?: ExperienceLevel;
  strength?: ExperienceLevel;
}

export interface SchedulingPreferences {
  mix_disciplines: boolean;
  cardio_preference: 'dedicated_day' | 'finisher' | 'mixed' | 'none';
  endurance_dedicated_cardio_day_policy?: 'default' | 'always' | 'never';
  microcycle_length_days?: 'auto' | number;
  split_template_preference?: 'none' | 'full_body' | 'upper_lower' | 'ppl' | 'hybrid';
}

export interface UserProfile {
  id: number;
  name?: string;
  email?: string;
  experience_level: ExperienceLevel;
  persona_tone: PersonaTone;
  persona_aggression: PersonaAggression;
  date_of_birth?: string;
  sex?: Sex;
  height_cm?: number;
  discipline_preferences?: DisciplinePreferences;
  discipline_experience?: DisciplineExperience;
  scheduling_preferences?: SchedulingPreferences;
  long_term_goal_category?: string;
  long_term_goal_description?: string;
}

export interface UserProfileUpdate {
  name?: string;
  experience_level?: ExperienceLevel;
  persona_tone?: PersonaTone;
  persona_aggression?: PersonaAggression;
  date_of_birth?: string;
  sex?: Sex;
  height_cm?: number;
  discipline_preferences?: DisciplinePreferences;
  discipline_experience?: DisciplineExperience;
  scheduling_preferences?: SchedulingPreferences;
  long_term_goal_category?: string;
  long_term_goal_description?: string;
}
