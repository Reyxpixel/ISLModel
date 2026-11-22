import JSZip from 'jszip';
import { HandLandmarkData, LandmarkPoint, RecordedFrame, RecordedSample } from '../types/dataset';
import { RawFrame } from './preprocess';

const DB_NAME = 'SignIt_ISL_Dataset_DB';
const STORE_NAME = 'recorded_samples';
const DB_VERSION = 2;

class DataRecorderService {
  private mediaRecorder: MediaRecorder | null = null;
  private recordedChunks: Blob[] = [];
  private currentFrameBuffer: RecordedFrame[] = [];
  private currentRawFrames: RawFrame[] = [];
  private isRecordingActive: boolean = false;
  private recordingStartTime: number = 0;
  private currentSignId: string = '';
  private currentSignName: string = '';
  private currentHindiName: string = '';
  private frameCounter: number = 0;
  private contributorId: string = '';

  constructor() {
    this.initContributorId();
  }

  private initContributorId() {
    if (typeof window !== 'undefined') {
      let id = localStorage.getItem('isl_contributor_id');
      if (!id) {
        id = 'contrib_' + Math.random().toString(36).substring(2, 9);
        localStorage.setItem('isl_contributor_id', id);
      }
      this.contributorId = id;
    }
  }

  public getContributorId(): string {
    return this.contributorId;
  }

  // Open IndexedDB database
  private openDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
      request.onupgradeneeded = (e) => {
        const db = (e.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        }
      };
    });
  }

  public isRecording(): boolean {
    return this.isRecordingActive;
  }

  /**
   * Start recording session for a specific sign take
   */
  public startRecording(stream: MediaStream, signId: string, signName: string, hindiName: string) {
    this.currentSignId = signId;
    this.currentSignName = signName;
    this.currentHindiName = hindiName;
    this.recordedChunks = [];
    this.currentFrameBuffer = [];
    this.currentRawFrames = [];
    this.frameCounter = 0;
    this.recordingStartTime = performance.now();

    try {
      let mimeType = 'video/webm;codecs=vp9';
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm;codecs=vp8';
      }
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm';
      }

      this.mediaRecorder = new MediaRecorder(stream, { mimeType });
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          this.recordedChunks.push(e.data);
        }
      };

      this.mediaRecorder.start(100);
      this.isRecordingActive = true;
    } catch {
      this.isRecordingActive = true;
    }
  }

  /**
   * Capture synchronized landmark frame and raw frame during take
   */
  public captureFrame(hands: HandLandmarkData[], face?: LandmarkPoint[], rawFrame?: RawFrame) {
    if (!this.isRecordingActive) return;

    const timestampMs = Math.round(performance.now() - this.recordingStartTime);
    this.currentFrameBuffer.push({
      frameIndex: this.frameCounter++,
      timestampMs,
      hands: JSON.parse(JSON.stringify(hands)),
      face: face ? JSON.parse(JSON.stringify(face)) : undefined,
    });

    if (rawFrame) {
      this.currentRawFrames.push(JSON.parse(JSON.stringify(rawFrame)));
    }
  }

  /**
   * Stop recording take and save cleanly to IndexedDB with model predictions & verification labeling
   */
  public async stopRecording(
    confidenceScore: number = 0.9,
    predictedLabel?: string,
    isCorrect?: boolean,
    mode: 'learning' | 'arcade_model' | 'arcade_practice' = 'learning'
  ): Promise<RecordedSample | null> {
    if (!this.isRecordingActive && this.currentFrameBuffer.length === 0) return null;
    this.isRecordingActive = false;

    return new Promise((resolve) => {
      const finalizeSave = async (videoBlob?: Blob) => {
        const durationMs = Math.max(100, Math.round(performance.now() - this.recordingStartTime));
        const fps = this.currentFrameBuffer.length > 0
          ? Math.round((this.currentFrameBuffer.length / (durationMs / 1000)) * 10) / 10
          : 30;

        const sampleId = `take_${this.currentSignId}_${Date.now()}`;
        const sample: RecordedSample = {
          id: sampleId,
          signId: this.currentSignId,
          signName: this.currentSignName,
          hindiName: this.currentHindiName,
          contributorId: this.contributorId,
          recordedAt: new Date().toISOString(),
          durationMs,
          fps,
          totalFrames: this.currentFrameBuffer.length,
          landmarkSequence: this.currentFrameBuffer,
          rawFrames: this.currentRawFrames.length > 0 ? this.currentRawFrames : undefined,
          predictedLabel,
          isCorrect: isCorrect !== undefined ? isCorrect : (predictedLabel === this.currentSignId),
          confidenceScore,
          status: isCorrect ? 'verified' : 'pending',
          gameMode: mode,
          videoBlob,
          videoBlobUrl: videoBlob ? URL.createObjectURL(videoBlob) : undefined,
        };

        // Save to IndexedDB
        try {
          const db = await this.openDB();
          const tx = db.transaction(STORE_NAME, 'readwrite');
          const store = tx.objectStore(STORE_NAME);
          store.put(sample);
          await new Promise((res) => {
            tx.oncomplete = () => res(true);
          });
        } catch (dbErr) {
          console.error('Error saving take to IndexedDB:', dbErr);
        }

        resolve(sample);
      };

      if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.onstop = () => {
          const videoBlob = new Blob(this.recordedChunks, { type: this.mediaRecorder?.mimeType || 'video/webm' });
          finalizeSave(videoBlob);
        };
        try {
          this.mediaRecorder.stop();
        } catch {
          finalizeSave();
        }
      } else {
        finalizeSave();
      }
    });
  }

  /**
   * Directly save a completed take with rawFrames and prediction outcome
   */
  public async saveTakeDirect(
    signId: string,
    signName: string,
    hindiName: string,
    rawFrames: RawFrame[],
    videoBlob?: Blob,
    predictedLabel?: string,
    confidenceScore: number = 0,
    isCorrect: boolean = false,
    mode: 'learning' | 'arcade_model' | 'arcade_practice' = 'learning'
  ): Promise<RecordedSample> {
    const durationMs = Math.round((rawFrames.length / 30) * 1000);
    const sampleId = `take_${signId}_${Date.now()}`;

    const sample: RecordedSample = {
      id: sampleId,
      signId,
      signName,
      hindiName,
      contributorId: this.contributorId,
      recordedAt: new Date().toISOString(),
      durationMs,
      fps: 30,
      totalFrames: rawFrames.length,
      landmarkSequence: [],
      rawFrames,
      predictedLabel,
      isCorrect,
      confidenceScore,
      status: isCorrect ? 'verified' : 'pending',
      gameMode: mode,
      videoBlob,
      videoBlobUrl: videoBlob ? URL.createObjectURL(videoBlob) : undefined,
    };

    try {
      const db = await this.openDB();
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      store.put(sample);
      await new Promise((res) => {
        tx.oncomplete = () => res(true);
      });
    } catch (dbErr) {
      console.error('Error saving direct take to IndexedDB:', dbErr);
    }

    return sample;
  }

  /**
   * Fetch all recorded samples from IndexedDB
   */
  public async getAllSamples(): Promise<RecordedSample[]> {
    try {
      const db = await this.openDB();
      return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const store = tx.objectStore(STORE_NAME);
        const req = store.getAll();
        req.onsuccess = () => {
          const samples = req.result as RecordedSample[];
          samples.forEach((s) => {
            if (s.videoBlob && !s.videoBlobUrl) {
              s.videoBlobUrl = URL.createObjectURL(s.videoBlob);
            }
          });
          resolve(samples.reverse());
        };
        req.onerror = () => resolve([]);
      });
    } catch {
      return [];
    }
  }

  /**
   * Delete a sample by ID
   */
  public async deleteSample(id: string): Promise<boolean> {
    try {
      const db = await this.openDB();
      return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const req = store.delete(id);
        req.onsuccess = () => resolve(true);
        req.onerror = () => resolve(false);
      });
    } catch {
      return false;
    }
  }

  /**
   * Clear all recorded samples from the database
   */
  public async clearAllSamples(): Promise<boolean> {
    try {
      const db = await this.openDB();
      return new Promise((resolve) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        const store = tx.objectStore(STORE_NAME);
        const req = store.clear();
        req.onsuccess = () => resolve(true);
        req.onerror = () => resolve(false);
      });
    } catch {
      return false;
    }
  }

  /**
   * Export the entire dataset as a clean ZIP package ready for ISL model training
   * (formatted like mpipe.py and mudra_bubbles output)
   */
  public async exportDatasetZip(): Promise<Blob> {
    const samples = await this.getAllSamples();
    const zip = new JSZip();

    // Summary Manifest
    const manifest = {
      dataset_name: 'SignIt_Indian_Sign_Language_Dataset',
      version: '2.0.0',
      total_samples: samples.length,
      exported_at: new Date().toISOString(),
      annotation_format: 'google_mediapipe_landmarks_v1_bilstm',
      samples: samples.map((s) => ({
        id: s.id,
        sign_id: s.signId,
        sign_name: s.signName,
        hindi_name: s.hindiName,
        contributor_id: s.contributorId,
        recorded_at: s.recordedAt,
        duration_ms: s.durationMs,
        fps: s.fps,
        total_frames: s.totalFrames,
        confidence_score: s.confidenceScore,
        predicted_label: s.predictedLabel,
        is_verified: s.isCorrect,
        game_mode: s.gameMode,
        video_filename: s.videoBlob ? `takes/${s.signId}/${s.id}/video.webm` : null,
        landmarks_folder: `takes/${s.signId}/${s.id}/landmarks/`,
      })),
    };

    zip.file('manifest.json', JSON.stringify(manifest, null, 2));

    // CSV Manifest
    const csvRows = [
      'sample_id,sign_id,sign_name,hindi_name,duration_ms,fps,frames_count,confidence,predicted_label,is_correct,contributor_id,recorded_at',
    ];
    samples.forEach((s) => {
      csvRows.push(
        `"${s.id}","${s.signId}","${s.signName}","${s.hindiName}",${s.durationMs},${s.fps},${s.totalFrames},${s.confidenceScore},"${s.predictedLabel || ''}",${s.isCorrect || false},"${s.contributorId}","${s.recordedAt}"`
      );
    });
    zip.file('dataset_manifest.csv', csvRows.join('\n'));

    // README with ISL training guidance
    const readmeContent = `# SignIt - Indian Sign Language (ISL) Training Dataset

Collected using the SignIt platform with real-time MediaPipe Hand & Face landmark tracking.
Format matches ISLModel/mpipe.py and mudra_bubbles so it can be passed into train.py.

## Directory Structure
- \`manifest.json\`: Full dataset index with metadata and model predictions.
- \`dataset_manifest.csv\`: CSV format for Pandas dataframes.
- \`takes/<sign_id>/<take_id>/\`:
    - \`meta.json\`: Target label, verification status, confidence.
    - \`landmarks/hands.json\`: [N][2][21][3] metric 3D hand coordinates (MediaPipe world landmarks).
    - \`landmarks/hands_screen.json\`: [N][2][21][3] normalized 2D/3D screen coordinates.
    - \`landmarks/face_coords.json\`: [N][478][3] face landmarks for position scale features.
    - \`video.webm\`: Raw synchronized camera video.

## Training with ISLModel/train.py
\`\`\`python
import json, glob
# Load hands from all takes for a sign
take_files = glob.glob('takes/*/*/landmarks/hands.json')
print(f"Total takes ready for retraining: {len(take_files)}")
\`\`\`
`;
    zip.file('README.md', readmeContent);

    // Save individual takes
    samples.forEach((sample) => {
      const takeFolder = zip.folder(`takes/${sample.signId}/${sample.id}`);
      if (!takeFolder) return;

      const meta = {
        id: sample.id,
        word: sample.signId,
        sign_name: sample.signName,
        hindi_name: sample.hindiName,
        contributor: sample.contributorId,
        recorded_at: sample.recordedAt,
        duration_ms: sample.durationMs,
        fps: sample.fps,
        frames_count: sample.totalFrames,
        confidence: sample.confidenceScore,
        predicted_label: sample.predictedLabel,
        is_verified: sample.isCorrect,
        game_mode: sample.gameMode,
      };
      takeFolder.file('meta.json', JSON.stringify(meta, null, 2));

      if (sample.rawFrames && sample.rawFrames.length > 0) {
        const lmFolder = takeFolder.folder('landmarks');
        if (lmFolder) {
          const hands = sample.rawFrames.map((f) => f.hands);
          const handsScreen = sample.rawFrames.map((f) => f.handsScreen);
          const face = sample.rawFrames.map((f) => f.face);
          lmFolder.file('hands.json', JSON.stringify(hands));
          lmFolder.file('hands_screen.json', JSON.stringify(handsScreen));
          lmFolder.file('face_coords.json', JSON.stringify(face));
        }
      } else if (sample.landmarkSequence && sample.landmarkSequence.length > 0) {
        const lmFolder = takeFolder.folder('landmarks');
        if (lmFolder) {
          lmFolder.file('landmarkSequence.json', JSON.stringify(sample.landmarkSequence, null, 2));
        }
      }

      if (sample.videoBlob) {
        takeFolder.file('video.webm', sample.videoBlob);
      }
    });

    return await zip.generateAsync({ type: 'blob' });
  }
}

export const dataRecorder = new DataRecorderService();
