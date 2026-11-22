import { FilesetResolver, HandLandmarker, FaceLandmarker } from '@mediapipe/tasks-vision';
import { HandLandmarkData, LandmarkPoint } from '../types/dataset';
import { RawFrame } from './preprocess';

// Standard 21 Hand Landmark Connections in MediaPipe
export const HAND_CONNECTIONS: [number, number][] = [
  // Thumb
  [0, 1], [1, 2], [2, 3], [3, 4],
  // Index
  [0, 5], [5, 6], [6, 7], [7, 8],
  // Middle
  [0, 9], [9, 10], [10, 11], [11, 12],
  // Ring
  [0, 13], [13, 14], [14, 15], [15, 16],
  // Pinky
  [0, 17], [17, 18], [18, 19], [19, 20],
  // Palm Base
  [5, 9], [9, 13], [13, 17]
];

export type VisionStatus = 'idle' | 'loading' | 'ready' | 'fallback' | 'error';

export interface FrameDetectionOutput {
  hands: HandLandmarkData[];
  face?: LandmarkPoint[];
  rawFrame: RawFrame;
  timestamp: number;
}

export type DetectionCallback = (output: FrameDetectionOutput) => void;

const zeros = (n: number): number[][] => Array.from({ length: n }, () => [0, 0, 0]);

class VisionService {
  private handLandmarker: HandLandmarker | null = null;
  private faceLandmarker: FaceLandmarker | null = null;
  private status: VisionStatus = 'idle';
  private statusMessage: string = 'Initializing computer vision models...';
  private videoElement: HTMLVideoElement | null = null;
  private canvasElement: HTMLCanvasElement | null = null;
  private animFrameId: number | null = null;
  private stream: MediaStream | null = null;
  private subscribers: Set<DetectionCallback> = new Set();
  private simulationActive: boolean = false;
  private simulatedSignId: string = 'hello';
  private simFrames: number[][][][] | null = null; // [N][2][21][3]
  private simFrameIndex: number = 0;
  private lastSimFetch: string = '';
  private lastTs: number = 0;

  public getStatus(): VisionStatus {
    return this.status;
  }

  public getStatusMessage(): string {
    return this.statusMessage;
  }

  public isSimulating(): boolean {
    return this.simulationActive;
  }

  public setSimulation(active: boolean, signId: string = 'hello') {
    this.simulationActive = active;
    this.simulatedSignId = signId;
    if (active && this.lastSimFetch !== signId) {
      this.loadSimulationData(signId);
    }
  }

  private async loadSimulationData(signId: string) {
    this.lastSimFetch = signId;
    try {
      const res = await fetch(`/animations/${signId.toLowerCase()}.json`);
      if (res.ok) {
        const data = await res.json();
        this.simFrames = data.frames;
        this.simFrameIndex = 0;
      }
    } catch {
      this.simFrames = null;
    }
  }

  public subscribe(cb: DetectionCallback): () => void {
    this.subscribers.add(cb);
    return () => this.subscribers.delete(cb);
  }

  /**
   * Initializes Google's MediaPipe Hand Landmarker & Face Landmarker models
   * exactly matching the ISL model training parameters.
   */
  public async initMediaPipe(): Promise<boolean> {
    if (this.handLandmarker) return true;
    this.status = 'loading';
    this.statusMessage = 'Loading MediaPipe Hand & Face models...';

    try {
      let vision;
      try {
        vision = await FilesetResolver.forVisionTasks('/wasm');
      } catch {
        vision = await FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
        );
      }

      // Initialize Hand Landmarker (same settings as mpipe.py / ISL model training)
      try {
        this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: '/hand_landmarker.task',
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          numHands: 2,
          minHandDetectionConfidence: 0.6,
          minHandPresenceConfidence: 0.6,
          minTrackingConfidence: 0.5,
        });
      } catch {
        // Fallback to CPU or remote URL
        this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
            delegate: 'CPU',
          },
          runningMode: 'VIDEO',
          numHands: 2,
          minHandDetectionConfidence: 0.6,
          minHandPresenceConfidence: 0.6,
          minTrackingConfidence: 0.5,
        });
      }

      // Initialize Face Landmarker (for ISL position features & head/face tracking)
      try {
        this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath: '/face_landmarker.task',
            delegate: 'GPU',
          },
          runningMode: 'VIDEO',
          numFaces: 1,
          minFaceDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
      } catch {
        try {
          this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
            baseOptions: {
              modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
              delegate: 'CPU',
            },
            runningMode: 'VIDEO',
            numFaces: 1,
            minFaceDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
          });
        } catch (faceErr) {
          console.warn('Face landmarker init note:', faceErr);
        }
      }

      this.status = 'ready';
      this.statusMessage = 'MediaPipe Hand & Face Models Active';
      return true;
    } catch (err) {
      console.warn('MediaPipe initialization warning:', err);
      this.status = 'fallback';
      this.statusMessage = 'Vision Running (Fallback Mode)';
      return false;
    }
  }

  /**
   * Start webcam video stream
   */
  public async startCamera(videoEl: HTMLVideoElement, canvasEl: HTMLCanvasElement): Promise<MediaStream | null> {
    this.videoElement = videoEl;
    this.canvasElement = canvasEl;

    try {
      const constraints: MediaStreamConstraints = {
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
        audio: false,
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;
      await this.videoElement.play();

      this.startDetectionLoop();
      return this.stream;
    } catch (cameraErr) {
      console.warn('Camera access denied or unavailable:', cameraErr);
      this.simulationActive = false;
      this.startDetectionLoop();
      return null;
    }
  }

  /**
   * Stop camera and processing loops
   */
  public stopCamera() {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
  }

  /**
   * Main detection loop matching ISLModel/web/index.html
   */
  private startDetectionLoop() {
    let lastVideoTime = -1;

    const loop = () => {
      const now = performance.now();
      const ts = Math.max(now, this.lastTs + 1);
      this.lastTs = ts;

      let detectionOutput: FrameDetectionOutput = {
        hands: [],
        rawFrame: {
          hands: [zeros(21), zeros(21)],
          handsScreen: [zeros(21), zeros(21)],
          face: null,
        },
        timestamp: ts,
      };

      // 1. Simulation Mode (uses real animation data from dataset)
      if (this.simulationActive) {
        detectionOutput = this.generateSimulatedPose(this.simulatedSignId, ts);
      }
      // 2. Real Camera Mode
      else if (this.videoElement && this.canvasElement && this.stream && this.videoElement.readyState >= 2) {
        const canvas = this.canvasElement;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });

        if (ctx && this.videoElement.currentTime !== lastVideoTime) {
          lastVideoTime = this.videoElement.currentTime;

          // Mirror frame onto canvas BEFORE detection (CRITICAL: model was trained on mirrored frames)
          ctx.save();
          ctx.translate(canvas.width, 0);
          ctx.scale(-1, 1);
          ctx.drawImage(this.videoElement, 0, 0, canvas.width, canvas.height);
          ctx.restore();

          const rawFrame: RawFrame = {
            hands: [zeros(21), zeros(21)],
            handsScreen: [zeros(21), zeros(21)],
            face: null,
          };
          const displayHands: HandLandmarkData[] = [];

          // Detect Hands on mirrored canvas
          if (this.handLandmarker) {
            try {
              const h = this.handLandmarker.detectForVideo(canvas, ts);
              if (h && h.worldLandmarks && h.landmarks) {
                h.worldLandmarks.forEach((world, i) => {
                  const handednessStr = h.handednesses[i]?.[0]?.categoryName || 'Right';
                  // Slot 0 is Right, Slot 1 is Left
                  const slot = handednessStr === 'Right' ? 0 : 1;
                  rawFrame.hands[slot] = world.map((p) => [p.x, p.y, p.z]);
                  rawFrame.handsScreen[slot] = h.landmarks[i].map((p) => [p.x, p.y, p.z]);

                  displayHands.push({
                    handedness: handednessStr as 'Left' | 'Right',
                    score: h.handednesses[i]?.[0]?.score || 0.9,
                    landmarks: h.landmarks[i].map((p) => ({ x: p.x, y: p.y, z: p.z || 0 })),
                  });
                });
              }
            } catch (detErr) {
              console.error('Hand detect error:', detErr);
            }
          }

          // Detect Face on mirrored canvas
          if (this.faceLandmarker) {
            try {
              const f = this.faceLandmarker.detectForVideo(canvas, ts);
              if (f && f.faceLandmarks && f.faceLandmarks.length > 0) {
                rawFrame.face = f.faceLandmarks[0].map((p) => [p.x, p.y, p.z]);
                const keyIndices = [1, 152, 33, 133, 362, 263, 61, 291, 10, 70, 300];
                detectionOutput.face = keyIndices.map((idx) => {
                  const pt = f.faceLandmarks[0][idx] || f.faceLandmarks[0][0];
                  return { x: pt.x, y: pt.y, z: pt.z || 0 };
                });
              }
            } catch {
              // Ignore single face frame error
            }
          }

          detectionOutput.hands = displayHands;
          detectionOutput.rawFrame = rawFrame;
        }
      }

      // Render Skeleton on canvas if canvas exists
      this.renderLandmarks(detectionOutput);

      // Notify subscribers
      this.subscribers.forEach((cb) => cb(detectionOutput));

      this.animFrameId = requestAnimationFrame(loop);
    };

    this.animFrameId = requestAnimationFrame(loop);
  }

  /**
   * Render glowing skeleton overlay onto Canvas
   */
  private renderLandmarks(output: FrameDetectionOutput) {
    if (!this.canvasElement) return;
    const canvas = this.canvasElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // In simulation mode, clear the canvas first (since no video frame was drawn)
    if (this.simulationActive) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw subtle grid
      ctx.strokeStyle = '#1e293b';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 30) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 30) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
      }
    }

    // Render Hands
    output.hands.forEach((hand) => {
      const isRight = hand.handedness === 'Right';
      const strokeColor = isRight ? '#0284c7' : '#0ea5e9';
      const jointGlowColor = isRight ? '#38bdf8' : '#7dd3fc';

      // Draw bones
      ctx.lineWidth = 3.5;
      ctx.lineCap = 'round';
      ctx.strokeStyle = strokeColor;
      ctx.shadowColor = jointGlowColor;
      ctx.shadowBlur = 8;

      HAND_CONNECTIONS.forEach(([i, j]) => {
        const p1 = hand.landmarks[i];
        const p2 = hand.landmarks[j];
        if (p1 && p2) {
          ctx.beginPath();
          ctx.moveTo(p1.x * canvas.width, p1.y * canvas.height);
          ctx.lineTo(p2.x * canvas.width, p2.y * canvas.height);
          ctx.stroke();
        }
      });

      // Draw joints
      hand.landmarks.forEach((pt, ptIdx) => {
        const x = pt.x * canvas.width;
        const y = pt.y * canvas.height;
        const isTip = [4, 8, 12, 16, 20].includes(ptIdx);
        const radius = isTip ? 5.5 : 3.5;

        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = isTip ? '#ffffff' : jointGlowColor;
        ctx.shadowColor = '#0284c7';
        ctx.shadowBlur = isTip ? 12 : 6;
        ctx.fill();
        ctx.strokeStyle = '#0369a1';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      });

      // Draw hand badge
      const wrist = hand.landmarks[0];
      if (wrist) {
        ctx.font = '600 12px Plus Jakarta Sans, sans-serif';
        ctx.fillStyle = '#38bdf8';
        ctx.shadowBlur = 0;
        ctx.fillText(
          `${hand.handedness} (${Math.round(hand.score * 100)}%)`,
          wrist.x * canvas.width - 24,
          wrist.y * canvas.height + 22
        );
      }
    });

    // Render Face hint
    if (output.face && output.face.length > 0) {
      ctx.fillStyle = '#38bdf8';
      ctx.shadowBlur = 4;
      output.face.forEach((pt) => {
        ctx.beginPath();
        ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 2.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }
  }

  /**
   * Generates simulation output using authentic dataset animations from /animations/{signId}.json
   */
  private generateSimulatedPose(signId: string, timestamp: number): FrameDetectionOutput {
    const rawFrame: RawFrame = {
      hands: [zeros(21), zeros(21)],
      handsScreen: [zeros(21), zeros(21)],
      face: null,
    };
    const displayHands: HandLandmarkData[] = [];

    if (this.simFrames && this.simFrames.length > 0) {
      const frameData = this.simFrames[this.simFrameIndex % this.simFrames.length];
      this.simFrameIndex = (this.simFrameIndex + 1) % this.simFrames.length;

      // Slot 0 = Right, Slot 1 = Left
      for (let s = 0; s < 2; s++) {
        const handPts = frameData[s];
        const isPresent = handPts && handPts.some((p) => p[0] !== 0 || p[1] !== 0 || p[2] !== 0);

        if (isPresent) {
          rawFrame.hands[s] = handPts;
          // Approximate screen coords by mapping (-0.2..0.2) to (0.3..0.7)
          rawFrame.handsScreen[s] = handPts.map((p) => [
            Math.max(0.05, Math.min(0.95, 0.5 + p[0] * 1.5)),
            Math.max(0.05, Math.min(0.95, 0.5 + p[1] * 1.5)),
            p[2],
          ]);

          displayHands.push({
            handedness: s === 0 ? 'Right' : 'Left',
            score: 0.98,
            landmarks: rawFrame.handsScreen[s].map((p) => ({ x: p[0], y: p[1], z: p[2] })),
          });
        }
      }
    }

    return {
      hands: displayHands,
      rawFrame,
      timestamp,
    };
  }
}

export const visionService = new VisionService();
