export type Difficulty = 'beginner' | 'intermediate' | 'advanced';

export type SignCategory =
  | 'greetings'
  | 'pronouns'
  | 'family'
  | 'people'
  | 'time_basics'
  | 'days'
  | 'time_units'
  | 'animals'
  | 'colours'
  | 'objects';

export interface ISLSign {
  id: string;
  name: string;
  hindiName: string;
  category: SignCategory;
  description: string;
  handsCount: 1 | 2;
  handshapeDescription: string;
  facialExpressionNote?: string;
  movementDescription: string;
  culturalNote?: string;
  difficulty: Difficulty;
  iconEmoji: string;
  badgeColor: string;
  /** Label from model config.json — used for ONNX recognition */
  gestureTarget: string;
  /** Whether a guide video exists in public/guides/ */
  hasGuideVideo: boolean;
}

export interface LevelLesson {
  id: string;
  title: string;
  hindiTitle: string;
  description: string;
  signIds: string[];
  xpReward: number;
  unlocked: boolean;
  completed: boolean;
  accuracyBest?: number;
}

export interface GameBubble {
  id: string;
  signId: string;
  signName: string;
  hindiName: string;
  emoji: string;
  x: number;
  y: number;
  speed: number;
  size: number;
  color: string;
  isTarget: boolean;
  popped: boolean;
  popAnimationProgress?: number;
}
