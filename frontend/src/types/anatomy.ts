export type MuscleGroup =
  | 'quadriceps'
  | 'hamstrings'
  | 'glutes'
  | 'calves'
  | 'chest'
  | 'lats'
  | 'upper_back'
  | 'rear_delts'
  | 'front_delts'
  | 'side_delts'
  | 'biceps'
  | 'triceps'
  | 'forearms'
  | 'core'
  | 'obliques'
  | 'lower_back'
  | 'hip_flexors'
  | 'adductors'
  | 'full_body';

export type BodyZone =
  | 'posterior upper'
  | 'anterior upper'
  | 'full body'
  | 'shoulder'
  | 'core'
  | 'posterior lower'
  | 'anterior lower'
  | 'upper body'
  | 'lower body'
  | 'front'
  | 'back';

export const ZONE_MAPPING: Record<BodyZone, MuscleGroup[]> = {
  'posterior upper': ['upper_back', 'lats', 'rear_delts'],
  'anterior upper': ['chest', 'front_delts', 'biceps'],
  shoulder: ['front_delts', 'side_delts', 'rear_delts'],
  core: ['core', 'obliques', 'lower_back'],
  'posterior lower': ['hamstrings', 'glutes', 'calves'],
  'anterior lower': ['quadriceps', 'hip_flexors', 'adductors'],
  'full body': [
    'quadriceps',
    'hamstrings',
    'glutes',
    'calves',
    'chest',
    'lats',
    'upper_back',
    'rear_delts',
    'front_delts',
    'side_delts',
    'biceps',
    'triceps',
    'forearms',
    'core',
    'obliques',
    'lower_back',
    'hip_flexors',
    'adductors',
  ],
  'upper body': ['chest', 'lats', 'upper_back', 'rear_delts', 'front_delts', 'side_delts', 'biceps', 'triceps', 'forearms'],
  'lower body': ['quadriceps', 'hamstrings', 'glutes', 'calves', 'hip_flexors', 'adductors'],
  front: [
    'chest',
    'front_delts',
    'biceps',
    'forearms',
    'core',
    'obliques',
    'quadriceps',
    'hip_flexors',
    'adductors',
    'calves',
  ],
  back: [
    'upper_back',
    'lats',
    'rear_delts',
    'side_delts',
    'triceps',
    'forearms',
    'lower_back',
    'hamstrings',
    'glutes',
    'calves',
  ],
};

export const BODY_ZONE_LABELS: Record<BodyZone, string> = {
  'posterior upper': 'Posterior Upper',
  'anterior upper': 'Anterior Upper',
  'full body': 'Full Body',
  shoulder: 'Shoulder',
  core: 'Core',
  'posterior lower': 'Posterior Lower',
  'anterior lower': 'Anterior Lower',
  'upper body': 'Upper Body',
  'lower body': 'Lower Body',
  front: 'Front View',
  back: 'Back View',
};

export const MUSCLE_DISPLAY_NAMES: Record<MuscleGroup, string> = {
  quadriceps: 'Quadriceps',
  hamstrings: 'Hamstrings',
  glutes: 'Glutes',
  calves: 'Calves',
  chest: 'Chest',
  lats: 'Lats',
  upper_back: 'Upper Back',
  rear_delts: 'Rear Delts',
  front_delts: 'Front Delts',
  side_delts: 'Side Delts',
  biceps: 'Biceps',
  triceps: 'Triceps',
  forearms: 'Forearms',
  core: 'Core',
  obliques: 'Obliques',
  lower_back: 'Lower Back',
  hip_flexors: 'Hip Flexors',
  adductors: 'Adductors',
  full_body: 'Full Body',
};
