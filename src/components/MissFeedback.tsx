import React from 'react';
import { HelpCircle } from 'lucide-react';
import { RecognitionResult } from '../services/islRecognizer';

export type MissKind = 'close' | 'wrong' | 'unsure' | 'no_hands' | 'error';

export interface Miss {
  id: number; // new id per miss, so the animations replay
  kind: MissKind;
  guess: string; // what the model thought it saw (only shown for 'wrong')
}

// Why a take did not count, so each case can say something useful.
export function missKind(result: RecognitionResult, target: string): MissKind {
  if (result.status !== 'ok') return result.status;
  if (result.topLabel === target) return 'close';
  if (result.topConfidence >= 0.5) return 'wrong';
  if (result.predictions.slice(0, 3).some((p) => p.label === target)) return 'close';
  return 'unsure';
}

const LOOK: Record<MissKind, { icon: string; hue: number; title: string; tip: string }> = {
  close: { icon: '🤏', hue: 38, title: 'So close!', tip: 'Make the sign a little clearer and hold it a moment longer.' },
  wrong: { icon: '🙈', hue: 14, title: 'Not quite!', tip: '' },
  unsure: { icon: '🤔', hue: 262, title: "Couldn't read that one", tip: 'Try a bit slower, with your hands in good light.' },
  no_hands: { icon: '👀', hue: 199, title: "Can't see your hands", tip: 'Move back a little and keep your hands in the frame.' },
  error: { icon: '🔌', hue: 220, title: 'Something went wrong', tip: "That wasn't your signing. Give it another go." },
};

interface MissFeedbackProps {
  miss: Miss;
  signName: string;
  onShowHowTo?: () => void;
}

/** The "try again" counterpart of the confetti, drawn over the camera picture. */
export const MissFeedback: React.FC<MissFeedbackProps> = ({ miss, signName, onShowHowTo }) => {
  const look = LOOK[miss.kind];
  return (
    <div key={miss.id} role="status" className="miss-overlay" style={{ '--h': look.hue } as React.CSSProperties}>
      {Array.from({ length: 14 }, (_, i) => (
        <span
          key={i}
          className="miss-drop"
          style={{
            left: `${(i * 29 + 6) % 100}%`,
            width: 7 + ((i * 5) % 11),
            height: 7 + ((i * 5) % 11),
            animationDelay: `${(i % 7) * 0.09}s`,
          }}
        />
      ))}
      <div className="miss-card">
        <span className="miss-icon">{look.icon}</span>
        <div className="miss-title">{look.title}</div>
        <p className="miss-tip">
          {miss.kind === 'wrong' ? (
            <>
              That looked like <strong>{miss.guess}</strong>. Try <strong>{signName}</strong> again.
            </>
          ) : (
            look.tip
          )}
        </p>
        {onShowHowTo && (
          <button type="button" className="miss-howto" onClick={onShowHowTo}>
            <HelpCircle className="w-3.5 h-3.5" />
            See how to sign it
          </button>
        )}
      </div>
    </div>
  );
};
