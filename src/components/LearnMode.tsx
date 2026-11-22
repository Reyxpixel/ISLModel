import React, { useRef, useState } from 'react';
import confetti from 'canvas-confetti';
import { X, ArrowRight, CheckCircle2, Sparkles, BookOpen, RotateCcw, Eye } from 'lucide-react';
import { CameraFeed } from './CameraFeed';
import { SignVisualizer } from './SignVisualizer';
import { ISLSign } from '../types/isl';
import { sounds } from '../services/audio';
import { RecognitionResult } from '../services/islRecognizer';

interface LearnModeProps {
  sign: ISLSign;
  onClose: () => void;
  onComplete: (xp: number, gems: number) => void;
  onSampleRecorded: () => void;
  isDemoMode?: boolean;
}

export const LearnMode: React.FC<LearnModeProps> = ({
  sign,
  onClose,
  onComplete,
  onSampleRecorded,
  isDemoMode,
}) => {
  const [step, setStep] = useState<'study' | 'practice' | 'complete'>('study');
  const [hasSucceeded, setHasSucceeded] = useState<boolean>(false);
  const rewardedRef = useRef(false);

  const handleStartPractice = () => {
    sounds.playTap();
    setStep('practice');
  };

  const handleSignRecognized = (result: RecognitionResult) => {
    if (hasSucceeded) return;
    setHasSucceeded(true);
    sounds.playSuccess();
    confetti({
      particleCount: 60,
      spread: 75,
      origin: { y: 0.5 },
      colors: ['#0ea5e9', '#38bdf8', '#10b981', '#f59e0b', '#6366f1'],
    });
    onSampleRecorded();

    // Count the sign as done as soon as it is recognised, so leaving through
    // "Review Sign" or the close button still saves the progress.
    if (!rewardedRef.current) {
      rewardedRef.current = true;
      onComplete(50, 10);
    }

    setTimeout(() => {
      setStep('complete');
      sounds.playFanfare();
    }, 1200);
  };

  const handleFinish = () => {
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
      <div className="bg-white rounded-3xl max-w-2xl w-full border-4 border-sky-300 shadow-2xl overflow-hidden flex flex-col my-auto animate-in zoom-in-95 duration-200">
        {/* Top Header */}
        <div className="bg-slate-50 px-5 sm:px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{sign.iconEmoji}</span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-black text-xl text-slate-800">{sign.name}</h2>
                <span className="text-sm font-semibold text-sky-600 bg-sky-50 px-2 py-0.5 rounded-md border border-sky-200">
                  {sign.hindiName}
                </span>
              </div>
              <p className="text-xs text-slate-400 capitalize">
                Category: {sign.category.replace('_', ' ')} • {sign.handsCount} Hand{sign.handsCount > 1 ? 's' : ''} • {sign.difficulty}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-2xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-5 sm:p-6 flex-1 overflow-y-auto max-h-[calc(90vh-120px)]">
          {step === 'study' && (
            <div className="flex flex-col gap-5">
              {/* Reference Video or 3D Landmark Signer */}
              <SignVisualizer sign={sign} />

              {/* Instructions List */}
              <div className="space-y-3">
                <div className="bg-white border-2 border-slate-200 rounded-2xl p-4 flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-sky-100 text-sky-700 font-black text-xs flex items-center justify-center shrink-0">
                    1
                  </div>
                  <div>
                    <h4 className="font-bold text-xs text-slate-800">Hand Formation</h4>
                    <p className="text-xs text-slate-600 mt-0.5">{sign.handshapeDescription}</p>
                  </div>
                </div>

                <div className="bg-white border-2 border-slate-200 rounded-2xl p-4 flex items-start gap-3">
                  <div className="w-7 h-7 rounded-full bg-sky-100 text-sky-700 font-black text-xs flex items-center justify-center shrink-0">
                    2
                  </div>
                  <div>
                    <h4 className="font-bold text-xs text-slate-800">Movement & Timing</h4>
                    <p className="text-xs text-slate-600 mt-0.5">{sign.movementDescription}</p>
                  </div>
                </div>

                {sign.facialExpressionNote && (
                  <div className="bg-amber-50/70 border-2 border-amber-200 rounded-2xl p-4 flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-amber-100 text-amber-700 font-black text-xs flex items-center justify-center shrink-0">
                      3
                    </div>
                    <div>
                      <h4 className="font-bold text-xs text-amber-900">Facial Expression (Grammar)</h4>
                      <p className="text-xs text-amber-800 mt-0.5">{sign.facialExpressionNote}</p>
                    </div>
                  </div>
                )}

                {sign.culturalNote && (
                  <div className="bg-sky-50/60 border border-sky-200 rounded-2xl p-3 text-xs text-sky-800">
                    <span className="font-bold">Cultural Note:</span> {sign.culturalNote}
                  </div>
                )}
              </div>

              {/* Action Button */}
              <button
                onClick={handleStartPractice}
                className="btn-duo-primary py-3.5 rounded-2xl font-black text-base flex items-center justify-center gap-2 shadow-lg active:scale-95"
              >
                <span>Practice with Camera</span>
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          )}

          {step === 'practice' && (
            <div className="flex flex-col gap-4">
              <div className="bg-sky-50 border border-sky-200 rounded-2xl p-3 flex items-center justify-between text-xs">
                <span className="font-bold text-sky-800 flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-sky-500" />
                  Perform the "{sign.name}" sign in front of the camera
                </span>
                <span className="text-slate-500 font-semibold">{sign.handsCount === 1 ? '1 Hand' : '2 Hands'}</span>
              </div>

              {/* Camera Feed with BiLSTM model */}
              <CameraFeed
                targetGesture={sign.gestureTarget}
                signName={sign.name}
                hindiName={sign.hindiName}
                signId={sign.id}
                onSignRecognized={handleSignRecognized}
                isRecordingDataset={true}
                isDemoMode={isDemoMode}
              />

              <div className="flex items-center justify-between pt-1">
                <button
                  onClick={() => setStep('study')}
                  className="btn-duo-secondary px-4 py-2 rounded-xl text-xs font-bold"
                >
                  Back to Tutorial
                </button>
                <div className="text-xs text-slate-400 font-medium">
                  Record 2.5s clip to test your sign
                </div>
              </div>
            </div>
          )}

          {step === 'complete' && (
            <div className="flex flex-col items-center text-center py-6 gap-4">
              <div className="w-20 h-20 rounded-3xl bg-emerald-100 text-emerald-600 flex items-center justify-center text-4xl shadow-md border-2 border-emerald-200 animate-bounce">
                ✨
              </div>
              <div>
                <h3 className="font-black text-2xl text-slate-800">Sign Mastered!</h3>
                <p className="text-sm text-slate-500 mt-1">
                  You successfully performed "{sign.name}" ({sign.hindiName})!
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 w-full max-w-xs my-2">
                <div className="bg-purple-50 border border-purple-200 rounded-2xl p-3 text-center">
                  <div className="text-xs font-bold text-purple-400">XP Earned</div>
                  <div className="text-xl font-black text-purple-700">+50 XP</div>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-2xl p-3 text-center">
                  <div className="text-xs font-bold text-blue-400">Gems</div>
                  <div className="text-xl font-black text-blue-700">+10 💎</div>
                </div>
              </div>

              <div className="w-full bg-sky-50 border border-sky-200 rounded-2xl p-3 flex items-center gap-2.5 text-xs text-sky-800 text-left">
                <CheckCircle2 className="w-5 h-5 text-sky-600 shrink-0" />
                <span>
                  Video & MediaPipe landmarks captured to further train Indian Sign Language research models!
                </span>
              </div>

              <div className="w-full flex gap-3 mt-2">
                <button
                  onClick={() => setStep('study')}
                  className="flex-1 btn-duo-secondary py-3 rounded-2xl font-bold text-sm"
                >
                  Review Sign
                </button>
                <button
                  onClick={handleFinish}
                  className="flex-1 btn-duo-success py-3.5 rounded-2xl font-black text-base shadow-lg"
                >
                  Continue Learning
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
