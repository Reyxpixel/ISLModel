import { RawFrame } from '../services/preprocess';

export interface LandmarkPoint {
  x: number;
  y: number;
  z: number;
}

export interface HandLandmarkData {
  handedness: 'Left' | 'Right';
  score: number;
  landmarks: LandmarkPoint[]; // 21 landmarks
}

export interface RecordedFrame {
  frameIndex: number;
  timestampMs: number;
  hands: HandLandmarkData[];
  face?: LandmarkPoint[];
}

export interface RecordedSample {
  id: string;
  signId: string;
  signName: string;
  hindiName: string;
  contributorId: string;
  recordedAt: string; // ISO string
  durationMs: number;
  fps: number;
  totalFrames: number;
  videoBlobUrl?: string;
  videoBlob?: Blob;
  landmarkSequence: RecordedFrame[];
  rawFrames?: RawFrame[];
  predictedLabel?: string;
  isCorrect?: boolean;
  confidenceScore: number;
  status: 'pending' | 'verified' | 'exported';
  gameMode?: 'learning' | 'arcade_model' | 'arcade_practice';
}

export interface DatasetStatistics {
  totalSamples: number;
  uniqueSignsCount: number;
  totalSecondsRecorded: number;
  bySign: Record<string, number>;
}
