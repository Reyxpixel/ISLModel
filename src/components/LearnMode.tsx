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

const StepCard: React.FC<{ n: number; title: string; text: string; amber?: boolean }> = ({ n, title, text, amber }) => (
  <div
    className={`border-2 rounded-2xl p-3 flex items-start gap-3 ${
      amber ? 'bg-amber-50/70 border-amber-200' : 'bg-white border-slate-200'
    }`}
  >
    <div
      className={`w-7 h-7 rounded-full font-black text-xs flex items-center justify-center shrink-0 ${
        amber ? 'bg-amber-100 text-amber-700' : 'bg-sky-100 text-sky-700'
      }`}
    >
      {n}
    </div>
    <div>
      <h4 className={`font-bold text-xs ${amber ? 'text-amber-900' : 'text-slate-800'}`}>{title}</h4>
      <p className={`text-xs mt-0.5 ${amber ? 'text-amber-800' : 'text-slate-600'}`}>{text}</p>
    </div>
  </div>
);

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

  const signSteps = (
    <div className="flex flex-col gap-2">
      <StepCard n={1} title="Hand Formation" text={sign.handshapeDescription} />
      <StepCard n={2} title="Movement & Timing" text={sign.movementDescription} />
      {sign.facialExpressionNote && (
        <StepCard n={3} title="Facial Expression (Grammar)" text={sign.facialExpressionNote} amber />
      )}
      {sign.culturalNote && (
        <div className="bg-sky-50/60 border border-sky-200 rounded-2xl p-3 text-xs text-sky-800">
          <span className="font-bold">Cultural Note:</span> {sign.culturalNote}
        </div>
      )}
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 overflow-y-auto">
      <div className={`bg-white rounded-3xl ${step === 'complete' ? 'max-w-2xl' : 'max-w-5xl'} w-full border-4 border-sky-300 shadow-2xl overflow-hidden flex flex-col my-auto animate-in zoom-in-95 duration-200`}>
        {/* Top Header */}
        <div className="bg-slate-50 px-5 py-2.5 border-b border-slate-200 flex items-center justify-between">
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

        {/* Modal Content: everything fits on one screen from tablet width up */}
        <div className="p-4 sm:p-5 flex-1 overflow-y-auto max-h-[calc(100dvh-110px)]">
          {step === 'study' && (
            <div className="learn-split">
              {/* Reference Video or 3D Landmark Signer */}
              <div className="learn-media learn-media-study">
                <SignVisualizer sign={sign} />
              </div>

              <div className="learn-side">
                {signSteps}
                <button
                  onClick={handleStartPractice}
                  className="learn-cta btn-duo-primary py-3.5 rounded-2xl font-black text-base flex items-center justify-center gap-2 shadow-lg active:scale-95"
                >
                  <span>Practice with Camera</span>
                  <ArrowRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          )}

          {step === 'practice' && (
            /* Camera Feed with BiLSTM model; steps and results sit beside the camera */
            <CameraFeed
              targetGesture={sign.gestureTarget}
              signName={sign.name}
              hindiName={sign.hindiName}
              signId={sign.id}
              onSignRecognized={handleSignRecognized}
              onShowHowTo={() => setStep('study')}
              isRecordingDataset={true}
              isDemoMode={isDemoMode}
              aside={
                <>
                  <div className="learn-hint bg-sky-50 border border-sky-200 rounded-2xl p-3 text-xs font-bold text-sky-800 flex items-start gap-1.5">
                    <Sparkles className="w-4 h-4 text-sky-500 shrink-0" />
                    <span>
                      Perform "{sign.name}" in front of the camera ({sign.handsCount === 1 ? '1 hand' : '2 hands'}).
                      Press record, then sign for 2.5 seconds.
                    </span>
                  </div>
                  {signSteps}
                  <button
                    onClick={() => setStep('study')}
                    className="btn-duo-secondary px-4 py-2 rounded-xl text-xs font-bold self-start"
                  >
                    Back to Tutorial
                  </button>
                </>
              }
            />
          )}

          {step === 'complete' && (
            <div className="flex flex-col items-center text-center py-2 gap-3">
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
