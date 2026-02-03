import { create } from 'zustand';
import {
  Goal,
  GoalWeight,
  SplitTemplate,
  ProgressionStyle,
  MovementRuleCreate,
  EnjoyableActivityCreate,
  MovementRuleType,
} from '@/types';

export interface MovementPreference {
  id: number;
  movement_id: number;
  rule_type: string;
  cadence: string | null;
  notes: string | null;
}

export interface OnboardingData {
  gym_comfort_level?: string;
  equipment_familiarity?: Record<string, number>;
  goal_category?: string;
  goal_description?: string;
  enjoyable_activities?: string[];
}

// Discipline types for step 3
export interface DisciplineWeight {
  discipline: string;
  weight: number;
}

export const DISCIPLINES = [
  { id: 'bodybuilding', name: 'Bodybuilding', description: 'Hypertrophy-focused training for muscle size and aesthetics', icon: '💪' },
  { id: 'powerlifting', name: 'Powerlifting', description: 'Strength training focused on squat, bench, and deadlift', icon: '🏋️' },
  { id: 'olympic_weightlifting', name: 'Olympic Weightlifting', description: 'Explosive movements like cleans, snatches, and jerks', icon: '⚡' },
  { id: 'strongman', name: 'Strongman', description: 'Functional strength with heavy carries and implements', icon: '🏋️' },
  { id: 'calisthenics', name: 'Calisthenics', description: 'Bodyweight training for strength and control', icon: '🤸' },
  { id: 'crossfit', name: 'CrossFit', description: 'High-intensity functional movements', icon: '🔥' },
  { id: 'yoga', name: 'Yoga', description: 'Flexibility, balance, and mindfulness practices', icon: '🧘' },
  { id: 'running', name: 'Running', description: 'Cardiovascular endurance and leg conditioning', icon: '🏃' },
  { id: 'other', name: 'Other', description: 'Any other training discipline', icon: '🎯' },
] as const;

// Communication style options for step 7
export const COMMUNICATION_STYLES = [
  { id: 'encouraging', name: 'Encouraging', description: 'Supportive and motivating', icon: '❤️' },
  { id: 'drill_sergeant', name: 'Drill Sergeant', description: 'Tough love, no excuses', icon: '💪' },
  { id: 'scientific', name: 'Scientific', description: 'Data-driven and analytical', icon: '⚡' },
  { id: 'casual', name: 'Casual Buddy', description: 'Relaxed and friendly', icon: '😎' },
] as const;

interface ProgramWizardState {
  // Step 1: Goals
  goals: GoalWeight[];
  setGoals: (goals: GoalWeight[]) => void;
  updateGoalWeight: (goal: Goal, weight: number) => void;
  
  // Step 2: Split
  daysPerWeek: number;
  setDaysPerWeek: (days: number) => void;
  maxDuration: number;
  setMaxDuration: (minutes: number) => void;
  splitPreference: SplitTemplate | null;
  setSplitPreference: (split: SplitTemplate | null) => void;
  
  // Step 3: Disciplines
  disciplines: DisciplineWeight[];
  setDisciplines: (disciplines: DisciplineWeight[]) => void;
  updateDisciplineWeight: (discipline: string, weight: number) => void;
  
  // Step 4: Progression
  progressionStyle: ProgressionStyle | null;
  setProgressionStyle: (style: ProgressionStyle | null) => void;
  
  // Step 5: Movements
  movementRules: MovementRuleCreate[];
  setMovementRules: (rules: MovementRuleCreate[]) => void;
  addMovementRule: (rule: MovementRuleCreate) => void;
  removeMovementRule: (movementId: number) => void;
  
  // Step 6: Activities
  enjoyableActivities: EnjoyableActivityCreate[];
  setEnjoyableActivities: (activities: EnjoyableActivityCreate[]) => void;
  addEnjoyableActivity: (activity: EnjoyableActivityCreate) => void;
  removeEnjoyableActivity: (activityType: string) => void;
  
  // Step 7: Coach persona
  communicationStyle: string;
  setCommunicationStyle: (style: string) => void;
  pushIntensity: number; // 1-5 scale
  setPushIntensity: (intensity: number) => void;
  
  // Program duration
  durationWeeks: number;
  setDurationWeeks: (weeks: number) => void;
  
  // Utilities
  reset: () => void;
  getTotalGoalWeight: () => number;
  getTotalDisciplineWeight: () => number;
  isGoalsValid: () => boolean;
  isDisciplinesValid: () => boolean;

  // User Preferences Sync
  initializeFromUserPreferences: (userPreferences: MovementPreference[]) => void;
  exportToUserPreferences: () => MovementPreference[];
  
  // Onboarding Data Integration
  initializeFromOnboardingData: (onboardingData: OnboardingData) => void;
}

const initialState = {
  goals: [],
  daysPerWeek: 4,
  maxDuration: 60,
  splitPreference: null,
  disciplines: [],
  progressionStyle: ProgressionStyle.DOUBLE_PROGRESSION,
  movementRules: [],
  enjoyableActivities: [],
  communicationStyle: 'encouraging',
  pushIntensity: 3,
  durationWeeks: 12,
};

export const useProgramWizardStore = create<ProgramWizardState>()((set, get) => ({
  ...initialState,
  
  // Step 1: Goals
  setGoals: (goals) => set({ goals }),
  updateGoalWeight: (goal, weight) => {
    const { goals } = get();
    const existingIndex = goals.findIndex((g) => g.goal === goal);
    
    if (weight === 0 && existingIndex !== -1) {
      // Remove goal if weight is 0
      set({ goals: goals.filter((g) => g.goal !== goal) });
    } else if (existingIndex !== -1) {
      // Update existing goal
      const updated = [...goals];
      updated[existingIndex] = { goal, weight };
      set({ goals: updated });
    } else if (weight > 0) {
      // Add new goal
      set({ goals: [...goals, { goal, weight }] });
    }
  },
  
  // Step 2: Split
  setDaysPerWeek: (days) => set({ daysPerWeek: days }),
  setMaxDuration: (minutes) => set({ maxDuration: minutes }),
  setSplitPreference: (split) => set({ splitPreference: split }),
  
  // Step 3: Disciplines
  setDisciplines: (disciplines) => set({ disciplines }),
  updateDisciplineWeight: (discipline, weight) => {
    const { disciplines } = get();
    const existingIndex = disciplines.findIndex((d) => d.discipline === discipline);
    
    if (weight === 0 && existingIndex !== -1) {
      set({ disciplines: disciplines.filter((d) => d.discipline !== discipline) });
    } else if (existingIndex !== -1) {
      const updated = [...disciplines];
      updated[existingIndex] = { discipline, weight };
      set({ disciplines: updated });
    } else if (weight > 0) {
      set({ disciplines: [...disciplines, { discipline, weight }] });
    }
  },
  
  // Step 4: Progression
  setProgressionStyle: (style) => set({ progressionStyle: style }),
  
  // Step 5: Movements
  setMovementRules: (rules) => set({ movementRules: rules }),
  addMovementRule: (rule) => {
    const { movementRules } = get();
    const existingIndex = movementRules.findIndex((r) => r.movement_id === rule.movement_id);
    
    if (existingIndex !== -1) {
      const updated = [...movementRules];
      updated[existingIndex] = rule;
      set({ movementRules: updated });
    } else {
      set({ movementRules: [...movementRules, rule] });
    }
  },
  removeMovementRule: (movementId) => {
    const { movementRules } = get();
    set({ movementRules: movementRules.filter((r) => r.movement_id !== movementId) });
  },
  
  // Step 6: Activities
  setEnjoyableActivities: (activities) => set({ enjoyableActivities: activities }),
  addEnjoyableActivity: (activity) => {
    const { enjoyableActivities } = get();
    set({ enjoyableActivities: [...enjoyableActivities, activity] });
  },
  removeEnjoyableActivity: (activityType) => {
    const { enjoyableActivities } = get();
    set({ enjoyableActivities: enjoyableActivities.filter((a) => a.activity_type !== activityType) });
  },
  
  // Step 7: Coach
  setCommunicationStyle: (style) => set({ communicationStyle: style }),
  setPushIntensity: (intensity) => set({ pushIntensity: intensity }),
  
  // Duration
  setDurationWeeks: (weeks) => set({ durationWeeks: weeks }),
  
  // Utilities
  reset: () => set(initialState),
  getTotalGoalWeight: () => get().goals.reduce((sum, g) => sum + g.weight, 0),
  getTotalDisciplineWeight: () => get().disciplines.reduce((sum, d) => sum + d.weight, 0),
  isGoalsValid: () => {
    const { goals } = get();
    const total = goals.reduce((sum, g) => sum + g.weight, 0);
    const goalNames = goals.map((g) => g.goal);
    const unique = new Set(goalNames).size === goalNames.length;
    return goals.length >= 1 && goals.length <= 3 && total === 10 && unique;
  },
  isDisciplinesValid: () => {
    const total = get().getTotalDisciplineWeight();
    return total === 10;
  },

  // User Preferences Sync
  initializeFromUserPreferences: (userPreferences) => {
    const movementRules: MovementRuleCreate[] = userPreferences.map((pref) => ({
      movement_id: pref.movement_id,
      rule_type: pref.rule_type as MovementRuleType,
      cadence: pref.cadence || undefined,
      notes: pref.notes || undefined,
    }));
    set({ movementRules });
  },
  exportToUserPreferences: () => {
    const { movementRules } = get();
    return movementRules.map((rule, index) => ({
      id: index,
      movement_id: rule.movement_id,
      rule_type: rule.rule_type,
      cadence: rule.cadence || null,
      notes: rule.notes || null,
    }));
  },
  
  // Onboarding Data Integration
  initializeFromOnboardingData: (onboardingData) => {
    const { gym_comfort_level, goal_category, enjoyable_activities } = onboardingData;
    
    // 1. Map gym_comfort_level to split template
    let splitTemplate: SplitTemplate | null = null;
    if (gym_comfort_level === 'beginner') {
      splitTemplate = SplitTemplate.UPPER_LOWER;
    } else if (gym_comfort_level === 'active') {
      splitTemplate = SplitTemplate.UPPER_LOWER;
    } else if (gym_comfort_level === 'experienced') {
      splitTemplate = SplitTemplate.PUSH_PULL_LEGS;
    }
    
    // 2. Map goal_category to default goals
    let defaultGoals: GoalWeight[] = [];
    if (goal_category) {
      const goalMap: Record<string, Goal> = {
        'muscle_gain': Goal.HYPERTROPHY,
        'strength': Goal.STRENGTH,
        'fat_loss': Goal.FAT_LOSS,
        'endurance': Goal.ENDURANCE,
        'mobility': Goal.MOBILITY,
      };
      const mappedGoal = goalMap[goal_category];
      if (mappedGoal) {
        defaultGoals = [{ goal: mappedGoal, weight: 10 }];
      }
    }
    
    // 3. Map enjoyable_activities to EnjoyableActivityCreate
    let activities: EnjoyableActivityCreate[] = [];
    if (enjoyable_activities && enjoyable_activities.length > 0) {
      activities = enjoyable_activities.map((activity) => ({
        activity_type: activity,
        recommend_every_days: 28,
        enabled: true,
      }));
    }
    
    // Set the state with mapped values
    set({
      splitPreference: splitTemplate,
      goals: defaultGoals,
      enjoyableActivities: activities,
    });
  },
}));
