// ISL ONNX model recognizer — replaces the old heuristic gestureRecognizer.
// Uses the real BiLSTM model for 91-sign recognition via onnxruntime-web.

import * as ort from 'onnxruntime-web';
import { preprocess, topK, ModelConfig, RawFrame, Prediction } from './preprocess';

export type RecognizerState = 'unloaded' | 'loading' | 'ready' | 'countdown' | 'recording' | 'classifying' | 'error';

export interface RecognitionResult {
  predictions: Prediction[];
  topLabel: string;
  topConfidence: number;
  feedbackMessage: string;
}

const EMPTY_RESULT: RecognitionResult = {
  predictions: [],
  topLabel: '',
  topConfidence: 0,
  feedbackMessage: 'Position your hands in the camera frame',
};

class ISLRecognizer {
  private session: ort.InferenceSession | null = null;
  private config: ModelConfig | null = null;
  private state: RecognizerState = 'unloaded';
  private stateListeners = new Set<(s: RecognizerState) => void>();

  // Recording state
  private take: RawFrame[] = [];
  private recordStart = 0;
  private countdownStart = 0;

  // Timing (matches ISLModel/web/index.html)
  public readonly COUNTDOWN_SECONDS = 2.0;
  public readonly RECORD_SECONDS = 2.5;

  public getState(): RecognizerState { return this.state; }

  public getConfig(): ModelConfig | null { return this.config; }

  public onStateChange(cb: (s: RecognizerState) => void): () => void {
    this.stateListeners.add(cb);
    return () => this.stateListeners.delete(cb);
  }

  private setState(s: RecognizerState) {
    this.state = s;
    this.stateListeners.forEach((cb) => cb(s));
  }

  /**
   * Load ONNX model and config from /model/ directory
   */
  public async load(): Promise<boolean> {
    if (this.session) return true;
    this.setState('loading');

    try {
      // Set WASM paths for onnxruntime-web
      ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/';

      const [configRes, session] = await Promise.all([
        fetch('/model/config.json').then((r) => r.json()),
        ort.InferenceSession.create('/model/model.onnx'),
      ]);

      this.config = configRes as ModelConfig;
      this.session = session;
      this.setState('ready');
      return true;
    } catch (err) {
      console.error('Failed to load ISL ONNX model:', err);
      this.setState('error');
      return false;
    }
  }

  /**
   * Start the countdown → recording sequence
   */
  public startRecording(): void {
    if (this.state !== 'ready') return;
    this.take = [];
    this.countdownStart = performance.now() / 1000;
    this.setState('countdown');
  }

  /**
   * Cancel an in-progress recording
   */
  public cancelRecording(): void {
    this.take = [];
    this.setState('ready');
  }

  /**
   * Feed a frame during the recording/countdown phase.
   * Returns time remaining info and triggers classification when done.
   */
  public feedFrame(frame: RawFrame): { phase: 'countdown' | 'recording' | 'done'; timeLeft: number } | null {
    const now = performance.now() / 1000;

    if (this.state === 'countdown') {
      const left = this.COUNTDOWN_SECONDS - (now - this.countdownStart);
      if (left <= 0) {
        // Transition to recording
        this.recordStart = now;
        this.take = [];
        this.setState('recording');
        return { phase: 'recording', timeLeft: this.RECORD_SECONDS };
      }
      return { phase: 'countdown', timeLeft: left };
    }

    if (this.state === 'recording') {
      this.take.push(frame);
      const left = this.RECORD_SECONDS - (now - this.recordStart);
      if (left <= 0 && this.take.length >= 2) {
        this.setState('classifying');
        return { phase: 'done', timeLeft: 0 };
      }
      return { phase: 'recording', timeLeft: Math.max(0, left) };
    }

    return null;
  }

  /**
   * Run ONNX inference on the recorded take
   */
  public async classify(targetLabel?: string): Promise<RecognitionResult> {
    if (!this.session || !this.config || this.take.length < 2) {
      this.setState('ready');
      return {
        ...EMPTY_RESULT,
        feedbackMessage: 'No hand data captured. Keep hands visible and try again.',
      };
    }

    try {
      // Check if any hands were detected
      const hasHands = this.take.some((f) =>
        f.hands.some((h) => h.some((p) => p[0] !== 0 || p[1] !== 0 || p[2] !== 0)),
      );
      if (!hasHands) {
        this.setState('ready');
        return {
          ...EMPTY_RESULT,
          feedbackMessage: 'No hands detected. Keep your hands visible in the camera.',
        };
      }

      const x = preprocess(this.take, this.config);
      const tensor = new ort.Tensor('float32', x, [1, this.config.seq_len, this.config.n_features]);
      const output = await this.session.run({ features: tensor });
      const logits = output.logits.data as Float32Array;
      const predictions = topK(logits, this.config.labels, 5);

      const top = predictions[0];
      const isMatch = targetLabel ? top.label === targetLabel : true;
      const isConfident = top.p >= 0.5;

      let feedbackMessage: string;
      if (isConfident && isMatch) {
        feedbackMessage = `✅ Correct! "${pretty(top.label)}" recognized at ${pct(top.p)}`;
      } else if (isConfident && !isMatch) {
        feedbackMessage = `Detected "${pretty(top.label)}" (${pct(top.p)}) — try "${pretty(targetLabel || '')}" again`;
      } else {
        feedbackMessage = `Not sure (${pct(top.p)}) — try holding the sign more clearly`;
      }

      this.setState('ready');
      return {
        predictions,
        topLabel: top.label,
        topConfidence: top.p,
        feedbackMessage,
      };
    } catch (err) {
      console.error('ONNX inference error:', err);
      this.setState('ready');
      return {
        ...EMPTY_RESULT,
        feedbackMessage: 'Model inference failed. Please try again.',
      };
    }
  }

  /**
   * Reset to ready state
   */
  public reset(): void {
    this.take = [];
    if (this.state !== 'unloaded' && this.state !== 'loading' && this.state !== 'error') {
      this.setState('ready');
    }
  }
}

function pretty(label: string): string {
  return label.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export const islRecognizer = new ISLRecognizer();

