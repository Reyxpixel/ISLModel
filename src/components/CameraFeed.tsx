import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Camera, CameraOff, RefreshCw, Eye, Sparkles, Wand2, Play, CheckCircle2, AlertCircle } from 'lucide-react';
import { visionService, FrameDetectionOutput } from '../services/vision';
import { islRecognizer, SUCCESS_CONFIDENCE, RecognizerState, RecognitionResult } from '../services/islRecognizer';
import { Miss, MissFeedback, missKind } from './MissFeedback';
import { sounds } from '../services/audio';
import { dataRecorder } from '../services/dataRecorder';

interface CameraFeedProps {
  targetGesture: string; // Model label, e.g. "hello", "thank_you"
  signName: string;
  hindiName: string;
  signId: string;
  onSignRecognized?: (result: RecognitionResult) => void;
  /** The take was wrong or could not be recognised */
  onSignMissed?: (result: RecognitionResult) => void;
  /** Adds a "See how to sign it" button to the miss feedback */
  onShowHowTo?: () => void;
  /** Shown beside the camera, with the results under it, instead of one tall column */
  aside?: React.ReactNode;
  isRecordingDataset?: boolean;
  isDemoMode?: boolean;
}

export const CameraFeed: React.FC<CameraFeedProps> = ({
  targetGesture,
  signName,
  hindiName,
  signId,
  onSignRecognized,
  onSignMissed,
  onShowHowTo,
  aside,
  isRecordingDataset = true,
  isDemoMode,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const [hasCamera, setHasCamera] = useState<boolean>(false);
  const [isInitializing, setIsInitializing] = useState<boolean>(true);
  const [modelStatus, setModelStatus] = useState<string>('Initializing BiLSTM AI Model...');
  const [showSkeleton, setShowSkeleton] = useState<boolean>(true);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  // Recognizer state machine
  // The recognizer is shared by every camera view, so start from its current state:
  // once the model is loaded it never re-announces 'ready' to a newly opened view.
  const [recogState, setRecogState] = useState<RecognizerState>(() => islRecognizer.getState());
  const [timerText, setTimerText] = useState<string>('');
  const [lastResult, setLastResult] = useState<RecognitionResult | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraError, setCameraError] = useState<string>('');
  const [miss, setMiss] = useState<Miss | null>(null);
  const missCountRef = useRef(0);

  // Initialize ONNX model & MediaPipe vision
  useEffect(() => {
    let isMounted = true;

    async function init() {
      setIsInitializing(true);
      setModelStatus('Loading 91-Sign BiLSTM Neural Network...');

      // 1. Load ONNX model (already loaded if another view used it; then just clear
      // any take a previous view left half-finished)
      await islRecognizer.load();
      islRecognizer.reset();
      if (isMounted) setRecogState(islRecognizer.getState());

      // 2. Load MediaPipe vision models
      setModelStatus('Loading MediaPipe Hand & Face Models...');
      await visionService.initMediaPipe();

      setModelStatus('AI Models Active (91 Signs)');

      // A view that closed while the models loaded must not take the webcam from the
      // view that is open now.
      if (!isMounted) return;

      // 3. Start Camera
      if (videoRef.current && canvasRef.current) {
        const stream = await visionService.startCamera(videoRef.current, canvasRef.current);
        if (isMounted) {
          if (stream) {
            streamRef.current = stream;
            setHasCamera(true);
            setIsSimulating(false);
            visionService.setSimulation(false);
          } else {
            setHasCamera(false);
            setIsSimulating(false);
            visionService.setSimulation(false);
            setCameraError(visionService.getCameraError());
          }
          setIsInitializing(false);
        }
      }
    }

    init();

    const unsubRecog = islRecognizer.onStateChange((s) => {
      setRecogState(s);
    });

    return () => {
      isMounted = false;
      unsubRecog();
      visionService.stopCamera();
    };
  }, []);

  // Sync demo mode if prop provided
  useEffect(() => {
    if (isDemoMode !== undefined) {
      setIsSimulating(isDemoMode);
      visionService.setSimulation(isDemoMode, signId);
    }
  }, [isDemoMode, signId]);

  // Update simulator sign when in demo mode
  useEffect(() => {
    if (isSimulating) {
      visionService.setSimulation(true, signId);
    } else {
      visionService.setSimulation(false);
    }
  }, [signId, isSimulating]);

  // Miss feedback goes away by itself, and never carries over to another sign
  useEffect(() => setMiss(null), [signId]);
  useEffect(() => {
    if (!miss) return;
    const t = setTimeout(() => setMiss(null), 4500);
    return () => clearTimeout(t);
  }, [miss]);

  // Trigger classification when take finishes and save take to dataset
  const handleClassify = useCallback(async () => {
    const res = await islRecognizer.classify(targetGesture);
    setLastResult(res);

    const isSuccess =
      isSimulating ||
      (res.topLabel === targetGesture && res.topConfidence >= SUCCESS_CONFIDENCE);

    if (!isSuccess) {
      sounds.playMiss();
      setMiss({
        id: ++missCountRef.current,
        kind: missKind(res, targetGesture),
        guess: res.topLabel.replace(/_/g, ' '),
      });
      onSignMissed?.(res);
    }

    // Save take with labels, model prediction, and verification status for model retraining
    if (dataRecorder.isRecording()) {
      await dataRecorder.stopRecording(
        res.topConfidence,
        res.topLabel,
        res.topLabel === targetGesture,
        'learning'
      );
    }

    if (isSuccess && onSignRecognized) {
      onSignRecognized(res);
    }
  }, [targetGesture, isSimulating, onSignRecognized, onSignMissed]);

  // Frame processing loop
  useEffect(() => {
    const unsubscribe = visionService.subscribe((output: FrameDetectionOutput) => {
      // Record frame if dataset collection active
      if (dataRecorder.isRecording() && hasCamera) {
        dataRecorder.captureFrame(output.hands, output.face, output.rawFrame);
      }

      // Feed frame to ISL Recognizer
      const feed = islRecognizer.feedFrame(output.rawFrame);
      if (feed) {
        if (feed.phase === 'countdown') {
          setTimerText(`Get Ready: ${feed.timeLeft.toFixed(1)}s`);
        } else if (feed.phase === 'recording') {
          setTimerText(`Signing: ${feed.timeLeft.toFixed(1)}s`);
        } else if (feed.phase === 'done') {
          setTimerText('Classifying...');
          handleClassify();
        }
      }
    });

    return () => {
      unsubscribe();
    };
  }, [handleClassify, hasCamera]);

  // Spacebar to trigger recording
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && (hasCamera || isSimulating) && recogState === 'ready') {
        e.preventDefault();
        handleStartRecord();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [hasCamera, isSimulating, recogState]);

  const handleStartRecord = () => {
    setLastResult(null);
    setMiss(null);
    setTimerText('Get ready...');
    if (streamRef.current && hasCamera) {
      dataRecorder.startRecording(streamRef.current, signId, signName, hindiName);
    }
    islRecognizer.startRecording();
  };

  const handleToggleSimulation = () => {
    const nextState = !isSimulating;
    setIsSimulating(nextState);
    visionService.setSimulation(nextState, signId);
    islRecognizer.reset();
    setLastResult(null);
    setMiss(null);
  };

  const handleRetryCamera = async () => {
    if (videoRef.current && canvasRef.current) {
      setIsInitializing(true);
      setCameraError('');
      const stream = await visionService.startCamera(videoRef.current, canvasRef.current);
      if (stream) {
        streamRef.current = stream;
        setHasCamera(true);
        setIsSimulating(false);
        visionService.setSimulation(false);
      } else {
        setCameraError(visionService.getCameraError());
      }
      setIsInitializing(false);
    }
  };

  return (
    <div className={aside ? 'learn-split' : 'flex flex-col gap-2.5 w-full'}>
      <div className={aside ? 'learn-media learn-media-camera flex flex-col gap-2.5' : 'contents'}>
      {/* Top Status & Controls Bar */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-slate-100/90 rounded-2xl border border-slate-200/90 text-xs shadow-2xs gap-3">
        {/* Camera Live/Off status */}
        <div className="flex items-center gap-2 shrink-0">
          {hasCamera ? (
            <span className="flex items-center gap-1.5 font-black text-emerald-700 bg-emerald-100/90 px-3 py-1 rounded-xl border border-emerald-300 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live Camera
            </span>
          ) : (
            <button
              onClick={handleRetryCamera}
              className="flex items-center gap-1.5 font-extrabold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 px-3 py-1 rounded-xl transition-all shadow-2xs active:scale-95 whitespace-nowrap"
            >
              <CameraOff className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>Camera Off · Retry</span>
            </button>
          )}
        </div>

        {/* Demo Mode Toggle Switch */}
        <div
          onClick={handleToggleSimulation}
          className={`flex items-center gap-2 px-3 py-1 rounded-xl border transition-all cursor-pointer select-none shadow-2xs shrink-0 ${
            isSimulating ? 'bg-amber-50 border-amber-300' : 'bg-white border-slate-200 hover:border-slate-300'
          }`}
          title="Toggle authentic dataset simulation"
        >
          <Wand2 className={`w-3.5 h-3.5 shrink-0 ${isSimulating ? 'text-amber-500' : 'text-slate-400'}`} />
          <span className="text-xs font-black text-slate-700 hidden sm:inline">
            Demo Mode
          </span>
          <div
            className={`relative inline-flex h-4.5 w-8 shrink-0 items-center rounded-full transition-colors duration-200 ease-in-out ${
              isSimulating ? 'bg-amber-500' : 'bg-slate-300'
            }`}
          >
            <span
              className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-xs transition-transform duration-200 ease-in-out ${
                isSimulating ? 'translate-x-4' : 'translate-x-0.5'
              }`}
            />
          </div>
          <span
            className={`text-[9px] font-black px-1.5 py-0.2 rounded ${
              isSimulating ? 'bg-amber-200 text-amber-900' : 'bg-slate-200 text-slate-600'
            }`}
          >
            {isSimulating ? 'ON' : 'OFF'}
          </span>
        </div>
      </div>

      {/* Camera Video / Canvas Arena */}
      <div
        className={`relative w-full rounded-3xl bg-slate-100 overflow-hidden shadow-inner border-2 border-slate-200 aspect-4/3 max-h-[440px] flex items-center justify-center ${
          miss && recogState === 'ready' ? 'miss-shake' : ''
        }`}
      >
        {/* Hidden Video Source for MediaPipe */}
        <video
          ref={videoRef}
          playsInline
          muted
          className="hidden"
        />

        {/* Mirrored Canvas — draws webcam video + glowing landmark skeleton */}
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          className={`w-full h-full object-cover ${
            hasCamera || isSimulating ? 'opacity-100' : 'opacity-0'
          }`}
        />

        {/* Clean Duolingo-styled Camera Inactive Screen */}
        {!hasCamera && !isSimulating && !isInitializing && (
          <div className="absolute inset-0 bg-gradient-to-b from-sky-50/70 via-slate-50 to-white flex flex-col items-center justify-center p-6 text-center z-10 border-2 border-dashed border-sky-200/90 m-2 rounded-2xl">
            <div className="w-14 h-14 rounded-2xl bg-sky-100 border-2 border-sky-200 flex items-center justify-center mb-3 shadow-2xs text-sky-600">
              <Camera className="w-7 h-7" />
            </div>
            <h4 className="text-slate-900 font-black text-sm mb-1">Camera Waiting to Connect</h4>
            <p className="text-xs text-slate-500 max-w-xs mb-4 font-semibold leading-relaxed">
              Enable webcam access to test your signing live, or switch on <strong>Demo Mode</strong> above to test with authentic recordings!
            </p>
            {cameraError && (
              <p className="text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2 max-w-sm mb-4">
                {cameraError}
              </p>
            )}
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button
                onClick={handleRetryCamera}
                className="btn-duo-primary px-4 py-2.5 rounded-xl text-xs font-black flex items-center gap-1.5 shadow-sm active:translate-y-0.5"
              >
                <Camera className="w-3.5 h-3.5" />
                <span>Turn On Camera</span>
              </button>
              <button
                onClick={handleToggleSimulation}
                className="px-4 py-2.5 rounded-xl text-xs font-black bg-amber-500 hover:bg-amber-400 text-white border-b-4 border-amber-600 active:translate-y-0.5 shadow-sm flex items-center gap-1.5 transition-all"
              >
                <Wand2 className="w-3.5 h-3.5" />
                <span>Switch on Demo Mode</span>
              </button>
            </div>
          </div>
        )}

        {/* Active Simulation Badge (Only displayed when actively simulating) */}
        {isSimulating && (
          <div className="absolute top-3 left-3 pointer-events-none z-10">
            <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500 text-white text-xs font-black shadow-md">
              <Wand2 className="w-3 h-3" />
              <span>SIMULATING "{signName.toUpperCase()}"</span>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {isInitializing && (
          <div className="absolute inset-0 bg-slate-900/90 flex flex-col items-center justify-center gap-3 z-20">
            <RefreshCw className="w-8 h-8 text-sky-400 animate-spin" />
            <p className="text-white text-sm font-semibold tracking-wide">Starting AI Models & Camera...</p>
          </div>
        )}

        {/* Countdown / Recording Overlay Banner */}
        {(recogState === 'countdown' || recogState === 'recording' || recogState === 'classifying') && (
          <div className="absolute inset-0 bg-black/40 backdrop-blur-xs flex flex-col items-center justify-center pointer-events-none z-20">
            <div className={`px-6 py-3 rounded-2xl text-white font-black text-xl shadow-2xl flex items-center gap-3 animate-pulse ${
              recogState === 'countdown'
                ? 'bg-amber-500'
                : recogState === 'recording'
                ? 'bg-red-500'
                : 'bg-sky-500'
            }`}>
              <span className="w-3.5 h-3.5 rounded-full bg-white animate-ping" />
              {timerText}
            </div>
            <p className="text-white text-xs font-bold mt-2 drop-shadow">
              {recogState === 'countdown' ? 'Prepare hands in frame' : 'Perform sign now!'}
            </p>
          </div>
        )}

        {/* Wrong / not recognised (the counterpart of the success confetti) */}
        {miss && recogState === 'ready' && (
          <MissFeedback miss={miss} signName={signName} onShowHowTo={onShowHowTo} />
        )}

        {/* Action Button: Start Recording Take */}
        {(hasCamera || isSimulating) && recogState === 'ready' && (
          <div className="absolute bottom-3 left-3 right-3 z-30 flex flex-col gap-2">
            <button
              onClick={handleStartRecord}
              className="w-full btn-duo-primary py-3 rounded-2xl font-black text-sm flex items-center justify-center gap-2 shadow-xl hover:scale-[1.01] active:scale-95 transition-all"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>{miss ? 'Try again (Space or Click)' : 'Record Sign (Space or Click)'}</span>
            </button>
          </div>
        )}
      </div>

      </div>

      <div className={aside ? 'learn-side' : 'contents'}>
      {aside}
      {/* Recognition Results & Confidence Cards */}
      {lastResult && (
        <div className="learn-result bg-white rounded-2xl p-3 border-2 border-slate-200/90 shadow-sm flex flex-col gap-2 animate-in fade-in duration-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {lastResult.topLabel === targetGesture ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-500" />
              ) : (
                <AlertCircle className="w-5 h-5 text-amber-500" />
              )}
              <span className="font-extrabold text-sm text-slate-800">
                {lastResult.feedbackMessage}
              </span>
            </div>
            <span className="font-mono text-xs font-black px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
              Top: {Math.round(lastResult.topConfidence * 100)}%
            </span>
          </div>

          {/* Top 3 Predictions Bar */}
          <div className="flex flex-col gap-1.5">
            {lastResult.predictions.slice(0, 3).map((p, i) => (
              <div key={p.label} className="flex items-center gap-2 text-xs">
                <span className="w-4 text-slate-400 font-bold">{i + 1}.</span>
                <span className={`w-32 truncate font-semibold ${
                  p.label === targetGesture ? 'text-sky-600 font-bold' : 'text-slate-700'
                }`}>
                  {p.label.replace(/_/g, ' ')}
                </span>
                <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      p.label === targetGesture ? 'bg-emerald-500' : 'bg-sky-400'
                    }`}
                    style={{ width: `${Math.round(p.p * 100)}%` }}
                  />
                </div>
                <span className="font-mono text-[11px] text-slate-500 w-10 text-right">
                  {Math.round(p.p * 100)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      </div>
    </div>
  );
};
