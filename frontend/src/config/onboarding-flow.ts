export type AnswerValue = string | string[] | number | boolean | Record<string, number> | Record<string, boolean> | null;

export interface Answers {
  [questionId: string]: AnswerValue;
}

export interface FlowNode {
  questionId: string;
  showCondition?: (answers: Answers) => boolean;
  nextQuestionIds?: string[];
}

export const ONBOARDING_FLOW: FlowNode[] = [
  {
    questionId: 'date_of_birth',
  },
  {
    questionId: 'sex',
  },
  {
    questionId: 'gym_comfort_level',
  },
  {
    questionId: 'athletic_activities',
    showCondition: (answers) => {
      const gymComfort = answers.gym_comfort_level;
      return gymComfort !== 'beginner';
    },
  },
  {
    questionId: 'equipment_familiarity',
    showCondition: (answers) => {
      const gymComfort = answers.gym_comfort_level;
      return gymComfort !== 'beginner';
    },
  },
  {
    questionId: 'movement_experience',
    showCondition: (answers) => {
      const gymComfort = answers.gym_comfort_level;
      return gymComfort === 'experienced';
    },
  },
  {
    questionId: 'goal_category',
  },
  {
    questionId: 'goal_description',
    showCondition: (answers) => {
      return answers.goal_category !== undefined && answers.goal_category !== null;
    },
  },
];

export const getVisibleQuestions = (answers: Answers): string[] => {
  return ONBOARDING_FLOW
    .filter(node => !node.showCondition || node.showCondition(answers))
    .map(node => node.questionId);
};

export const getNextQuestionId = (currentQuestionId: string, answers: Answers): string | null => {
  const currentIndex = ONBOARDING_FLOW.findIndex(node => node.questionId === currentQuestionId);
  
  for (let i = currentIndex + 1; i < ONBOARDING_FLOW.length; i++) {
    const node = ONBOARDING_FLOW[i];
    if (!node.showCondition || node.showCondition(answers)) {
      return node.questionId;
    }
  }
  
  return null;
};

export const getPreviousQuestionId = (currentQuestionId: string, answers: Answers): string | null => {
  const currentIndex = ONBOARDING_FLOW.findIndex(node => node.questionId === currentQuestionId);
  
  for (let i = currentIndex - 1; i >= 0; i--) {
    const node = ONBOARDING_FLOW[i];
    if (!node.showCondition || node.showCondition(answers)) {
      return node.questionId;
    }
  }
  
  return null;
};

export const getVisibleQuestionCount = (answers: Answers): number => {
  return getVisibleQuestions(answers).length;
};

export const getCurrentQuestionIndex = (currentQuestionId: string, answers: Answers): number => {
  const visibleQuestions = getVisibleQuestions(answers);
  return visibleQuestions.indexOf(currentQuestionId);
};

export const isFirstQuestion = (questionId: string, answers: Answers): boolean => {
  return getPreviousQuestionId(questionId, answers) === null;
};

export const isLastQuestion = (questionId: string, answers: Answers): boolean => {
  return getNextQuestionId(questionId, answers) === null;
};