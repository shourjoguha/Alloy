export interface QuestionOption {
  id: string;
  label: string;
  icon?: string;
  description?: string;
}

// Icon mapping for lucide-react icons
export const ICON_MAPPINGS: Record<string, string> = {
  // Athletic activities
  'tennis': 'Trophy',
  'bouldering': 'Mountain',
  'cycling': 'Bike',
  'swimming': 'Droplets',
  'hiking': 'Mountain',
  'basketball': 'CircleDot',
  'football': 'Flag',
  'yoga': 'Flower2',
  'martial_arts': 'Target',
  'dance': 'Music',
  'other': 'Sparkles',
  
  // Equipment
  'barbell': 'Dumbbell',
  'dumbbell': 'Dumbbell',
  'kettlebell': 'Dumbbell',
  'machines': 'Building',
  'cables': 'Zap',
  
  // Movements
  'squat': 'Dumbbell',
  'deadlift': 'Zap',
  'bench': 'Target',
  'overhead_press': 'Target',
  'pull_ups': 'Target',
  'olympic': 'Trophy',
  'lunges': 'Footprints',
  
  // Goals
  'muscle_gain': 'Dumbbell',
  'fat_loss': 'Flame',
  'strength': 'Zap',
  'performance': 'Target',
  'general_fitness': 'Heart',
  'health_longevity': 'Leaf',
};

export interface Question {
  id: string;
  type: 'basic' | 'cards' | 'slider' | 'yes_no' | 'text' | 'date' | 'sex_toggle';
  category: 'basics' | 'workout_philosophy' | 'goals';
  text: string;
  subtext?: string;
  options?: QuestionOption[];
  min?: number;
  max?: number;
  required: boolean;
  multiSelect?: boolean;
  validation?: (value: unknown) => string | null;
  mapping: {
    field: string;
    transform?: (value: unknown) => unknown;
  };
}

export const ONBOARDING_QUESTIONS: Question[] = [
  {
    id: 'date_of_birth',
    type: 'date',
    category: 'basics',
    text: "When's your birthday? Don't worry, I won't sing. 🎂",
    subtext: "I just want to make sure I design appropriate workouts for your age.",
    required: true,
    mapping: { field: 'date_of_birth' },
  },
  {
    id: 'sex',
    type: 'sex_toggle',
    category: 'basics',
    text: "What's your sex preference?",
    subtext: "I want to make sure I address you correctly.",
    required: true,
    mapping: { field: 'sex' },
  },
  {
    id: 'gym_comfort_level',
    type: 'cards',
    category: 'workout_philosophy',
    text: "So, how would you describe your fitness journey so far?",
    subtext: "Be honest - this helps me design the perfect starting point for you.",
    required: true,
    options: [
      {
        id: 'beginner',
        label: "Just getting started",
        description: "I'm new to working out or haven't been consistent",
      },
      {
        id: 'active',
        label: "I'm pretty active, but new to the gym",
        description: "I do sports, running, yoga, or other activities regularly",
      },
      {
        id: 'experienced',
        label: "I've been training for a while",
        description: "I've been going to the gym consistently for 6+ months",
      },
    ],
    mapping: { field: 'gym_comfort_level' },
  },
  {
    id: 'athletic_activities',
    type: 'cards',
    category: 'workout_philosophy',
    text: "What do you love doing outside the gym?",
    subtext: "This helps me understand what movements you enjoy and might want more of.",
    required: false,
    multiSelect: true,
    options: [
      { id: 'tennis', label: 'Tennis', description: 'Agility, hand-eye coordination' },
      { id: 'bouldering', label: 'Bouldering', description: 'Strength, problem-solving' },
      { id: 'cycling', label: 'Cycling', description: 'Endurance, leg strength' },
      { id: 'swimming', label: 'Swimming', description: 'Low impact, full body' },
      { id: 'hiking', label: 'Hiking', description: 'Outdoors, endurance, nature' },
      { id: 'basketball', label: 'Basketball', description: 'Agility, explosiveness' },
      { id: 'football', label: 'Football', description: 'Speed, strength, teamwork' },
      { id: 'yoga', label: 'Yoga', description: 'Flexibility, mindfulness, recovery' },
      { id: 'martial_arts', label: 'Martial Arts', description: 'Boxing, BJJ, karate...' },
      { id: 'dance', label: 'Dance', description: 'Rhythm, coordination, cardio' },
      { id: 'other', label: 'Other', description: 'Something else you love' },
    ],
    mapping: {
      field: 'enjoyable_activities',
      transform: (value) => value,
    },
  },
  {
    id: 'equipment_familiarity',
    type: 'slider',
    category: 'workout_philosophy',
    text: "How familiar are you with gym equipment?",
    subtext: "1 = Never touched it, 5 = We're best friends",
    required: true,
    options: [
      { id: 'barbell', label: 'Barbells' },
      { id: 'dumbbell', label: 'Dumbbells' },
      { id: 'kettlebell', label: 'Kettlebells' },
      { id: 'machines', label: 'Gym Machines' },
      { id: 'cables', label: 'Cable Machines' },
    ],
    min: 1,
    max: 5,
    mapping: { field: 'equipment_familiarity' },
  },
  {
    id: 'movement_experience',
    type: 'yes_no',
    category: 'workout_philosophy',
    text: "Which of these movements have you tried before?",
    subtext: "No worries if you haven't - we'll start from where you are!",
    required: false,
    options: [
      { id: 'squat', label: 'Squats', description: 'Barbell, goblet, bodyweight' },
      { id: 'deadlift', label: 'Deadlifts', description: 'Conventional, sumo, RDL' },
      { id: 'bench', label: 'Bench Press', description: 'Flat, incline, dumbbell' },
      { id: 'overhead_press', label: 'Overhead Press', description: 'Military, dumbbell, push press' },
      { id: 'pull_ups', label: 'Pull-ups/Rows', description: 'Lat pulldowns, rows, chin-ups' },
      { id: 'olympic', label: 'Olympic Lifts', description: 'Snatch, clean & jerk' },
      { id: 'lunges', label: 'Lunges', description: 'Walking, reverse, lateral' },
    ],
    mapping: { field: 'movement_experience' },
  },
  {
    id: 'goal_category',
    type: 'cards',
    category: 'goals',
    text: "Alright, the million-dollar question: What's your big goal for the next 1-3 years?",
    subtext: "Dream big - what's driving you to show up today?",
    required: true,
    options: [
      { 
        id: 'muscle_gain', 
        label: 'Build Muscle', 
        description: 'Add size, get jacked, aesthetic physique' 
      },
      { 
        id: 'fat_loss', 
        label: 'Lose Fat', 
        description: 'Get lean, improve body composition' 
      },
      { 
        id: 'strength', 
        label: 'Get Stronger', 
        description: 'Lift heavier, increase power' 
      },
      { 
        id: 'performance', 
        label: 'Athletic Performance', 
        description: 'Run faster, jump higher, move better' 
      },
      { 
        id: 'general_fitness', 
        label: 'General Fitness', 
        description: 'Feel better, move better, stay healthy' 
      },
      { 
        id: 'health_longevity', 
        label: 'Health & Longevity', 
        description: 'Build healthy habits, sustainable fitness' 
      },
    ],
    mapping: { field: 'goal_category' },
  },
  {
    id: 'goal_description',
    type: 'text',
    category: 'goals',
    text: "Tell me more about that goal...",
    subtext: "The more specific you are, the better I can help you achieve it. What would make you feel like you succeeded?",
    required: false,
    mapping: { field: 'goal_description' },
  },
];

export const getQuestionById = (id: string): Question | undefined => {
  return ONBOARDING_QUESTIONS.find(q => q.id === id);
};

export const getQuestionsByCategory = (category: Question['category']): Question[] => {
  return ONBOARDING_QUESTIONS.filter(q => q.category === category);
};