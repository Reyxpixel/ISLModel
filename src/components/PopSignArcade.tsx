import React, { useState, useEffect, useCallback, useRef } from 'react';
import confetti from 'canvas-confetti';
import { Play, RotateCcw, Trophy, Zap, CheckCircle2, HelpCircle, SkipForward, Sparkles, X } from 'lucide-react';
import { CameraFeed } from './CameraFeed';
import { SignVisualizer } from './SignVisualizer';
import { ISL_SIGNS } from '../data/islCurriculum';
import { ISLSign } from '../types/isl';
import { sounds } from '../services/audio';
import { RecognitionResult } from '../services/islRecognizer';

interface PopSignArcadeProps {
  onScoreEarned: (xp: number, gems: number) => void;
  onSampleRecorded: () => void;
  isDemoMode?: boolean;
}

interface BubbleTarget {
  id: string;
  sign: ISLSign;
  slotIndex: number;
  hue: number;
  bursting: boolean;
}

interface Burst {
  id: string;
  x: number;
  y: number;
  hue: number;
  points: number;
}

const ROUND_WORDS = [
  'hello', 'thank_you', 'how_are_you', 'we', 'i', 'you', 'they', 'she',
  'good_morning', 'good_night', 'hammer', 'handkerchief', 'hen', 'hole',
  'horse', 'in', 'individual', 'introduction', 'iron', 'it', 'mother',
  'father', 'friend', 'time', 'cat', 'dog', 'red', 'blue',
].filter((id) => ISL_SIGNS[id]);

const TOTAL_TARGETS_PER_ROUND = 10;
const BUBBLE_COUNT = 6;
const POP_MS = 520;

// Loose, staggered spots on the stage (percent of width / height), so the
// bubbles never sit in a stiff grid and never overlap.
const SLOTS = [
  { x: 17, y: 31 }, { x: 50, y: 25 }, { x: 83, y: 33 },
  { x: 24, y: 72 }, { x: 54, y: 70 }, { x: 83, y: 74 },
];
const HUES = [199, 158, 36, 258, 336, 186];

// Small decorative bubbles that drift up behind the game bubbles.
const AMBIENT = Array.from({ length: 14 }, (_, i) => ({
  left: (i * 37 + 7) % 100,
  size: 6 + ((i * 13) % 16),
  duration: 9 + ((i * 7) % 8),
  delay: -((i * 1.9) % 12),
}));

const shuffle = <T,>(arr: T[]) => [...arr].sort(() => Math.random() - 0.5);

const makeBubble = (signId: string, slotIndex: number): BubbleTarget => ({
  id: `b_${signId}_${Math.random().toString(36).slice(2, 8)}`,
  sign: ISL_SIGNS[signId],
  slotIndex,
  hue: HUES[slotIndex % HUES.length],
  bursting: false,
});

const freshBoard = () => shuffle(ROUND_WORDS).slice(0, BUBBLE_COUNT).map((id, i) => makeBubble(id, i));

const pickTarget = (board: BubbleTarget[], ...avoidIds: string[]) => {
  const live = board.filter((b) => !b.bursting);
  const choices = live.filter((b) => !avoidIds.includes(b.sign.id));
  const from = choices.length ? choices : live;
  return from[Math.floor(Math.random() * from.length)]?.sign;
};

export const PopSignArcade: React.FC<PopSignArcadeProps> = ({
  onScoreEarned,
  onSampleRecorded,
  isDemoMode = false,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isGameOver, setIsGameOver] = useState<boolean>(false);
  const [score, setScore] = useState<number>(0);
  const [combo, setCombo] = useState<number>(0);
  const [maxCombo, setMaxCombo] = useState<number>(0);
  const [roundTargetsCount, setRoundTargetsCount] = useState<number>(0);
  const [poppedCount, setPoppedCount] = useState<number>(0);

  const [bubbles, setBubbles] = useState<BubbleTarget[]>(freshBoard);
  const [targetSign, setTargetSign] = useState<ISLSign>(() => ISL_SIGNS.hello);
  const [bursts, setBursts] = useState<Burst[]>([]);
  const [showHowToModal, setShowHowToModal] = useState<boolean>(false);
  const [lastFeedback, setLastFeedback] = useState<{ text: string; good: boolean } | null>(null);

  const bubblesRef = useRef(bubbles);
  bubblesRef.current = bubbles;
  const busyRef = useRef(false); // true while a pop animation is running

  const startNewRound = useCallback(() => {
    const board = freshBoard();
    setBubbles(board);
    setTargetSign(board[0].sign);
    setRoundTargetsCount(0);
    setPoppedCount(0);
    setScore(0);
    setCombo(0);
    setMaxCombo(0);
    setBursts([]);
    setIsGameOver(false);
    setIsPlaying(true);
    setLastFeedback(null);
    busyRef.current = false;
    sounds.playTap();
  }, []);

  const countTarget = useCallback(() => {
    setRoundTargetsCount((prev) => {
      const next = prev + 1;
      if (next >= TOTAL_TARGETS_PER_ROUND) {
        setTimeout(() => {
          setIsGameOver(true);
          setIsPlaying(false);
          sounds.playFanfare();
        }, POP_MS + 150);
      }
      return next;
    });
  }, []);

  // Pop the bubble showing `signId`, then blow a new one in its place.
  const popBubble = useCallback((signId: string, points: number) => {
    const bubble = bubblesRef.current.find((b) => b.sign.id === signId && !b.bursting);
    if (!bubble) return;
    busyRef.current = true;
    const slot = SLOTS[bubble.slotIndex];
    const burst: Burst = { id: bubble.id, x: slot.x, y: slot.y, hue: bubble.hue, points };
    setBursts((prev) => [...prev, burst]);
    setBubbles((prev) => prev.map((b) => (b.id === bubble.id ? { ...b, bursting: true } : b)));

    setTimeout(() => {
      const onBoard = new Set(bubblesRef.current.map((b) => b.sign.id));
      const pool = ROUND_WORDS.filter((id) => !onBoard.has(id));
      const newId = pool[Math.floor(Math.random() * pool.length)] ?? signId;
      const next = bubblesRef.current.map((b) => (b.id === bubble.id ? makeBubble(newId, b.slotIndex) : b));
      setBubbles(next);
      const t = pickTarget(next, signId, newId);
      if (t) setTargetSign(t);
      busyRef.current = false;
    }, POP_MS);
    setTimeout(() => setBursts((prev) => prev.filter((x) => x.id !== burst.id)), 1100);
  }, []);

  const handleSignRecognized = (result: RecognitionResult) => {
    if (isGameOver || !isPlaying || busyRef.current) return;

    const topLabel = result.topLabel;
    const isTop1 = topLabel === targetSign.id;
    const isTop3 = result.predictions.slice(0, 3).some((p) => p.label === targetSign.id);
    const success = isDemoMode || isTop1 || isTop3;

    if (success) {
      sounds.playPop();
      const nextCombo = combo + 1;
      setCombo(nextCombo);
      if (nextCombo > maxCombo) setMaxCombo(nextCombo);
      sounds.playCombo(nextCombo);

      const earned = (isTop1 ? 100 : 50) * Math.max(1, nextCombo);
      setScore((s) => s + earned);
      setPoppedCount((n) => n + 1);
      setLastFeedback({ text: `Popped "${targetSign.name}"! +${earned}`, good: true });

      confetti({
        particleCount: 30,
        spread: 70,
        origin: { y: 0.45 },
        colors: ['#0ea5e9', '#38bdf8', '#10b981', '#f59e0b', '#8b5cf6'],
      });

      popBubble(targetSign.id, earned);
      onSampleRecorded();
      countTarget();
    } else {
      setCombo(0);
      setLastFeedback({
        text: `Looked like "${topLabel.replace(/_/g, ' ')}" (${Math.round(result.topConfidence * 100)}%). Try again or skip.`,
        good: false,
      });
    }
  };

  const handleSkipTarget = useCallback(() => {
    if (!isPlaying || busyRef.current) return;
    sounds.playTap();
    setCombo(0);
    setLastFeedback({ text: `Skipped "${targetSign.name}"`, good: false });
    const t = pickTarget(bubblesRef.current, targetSign.id);
    if (t) setTargetSign(t);
    countTarget();
  }, [isPlaying, targetSign, countTarget]);

  // Keyboard shortcuts (space = sign, h = how-to, n = skip, r = restart)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isGameOver) return;
      const k = e.key.toLowerCase();
      if (k === 'h') setShowHowToModal((prev) => !prev);
      else if (k === 'n') handleSkipTarget();
      else if (k === 'r') startNewRound();
      else if (k === 'escape') setShowHowToModal(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isGameOver, startNewRound, handleSkipTarget]);

  const handleClaimReward = () => {
    onScoreEarned(Math.round(score / 4) + 60, poppedCount * 2 + 8);
    sounds.playFanfare();
    setIsGameOver(false);
  };

  const progress = Math.min(roundTargetsCount, TOTAL_TARGETS_PER_ROUND);

  return (
    <div className="@container w-full flex flex-col gap-4">
      {/* ── HUD ── */}
      <div className="bg-white rounded-3xl px-4 py-3 border-2 border-slate-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="arcade-logo w-11 h-11 rounded-2xl flex items-center justify-center shrink-0">
            <span className="arcade-logo-bubble" />
          </div>
          <div className="min-w-0">
            <h1 className="font-black text-lg text-slate-800 tracking-tight leading-tight">PopSign Arcade</h1>
            <div className="flex items-center gap-1 mt-1" title={`${progress} of ${TOTAL_TARGETS_PER_ROUND} bubbles`}>
              {Array.from({ length: TOTAL_TARGETS_PER_ROUND }, (_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    i < progress ? 'w-4 bg-sky-500' : i === progress && isPlaying ? 'w-4 bg-sky-200' : 'w-2.5 bg-slate-200'
                  }`}
                />
              ))}
              <span className="ml-1.5 text-[10px] font-black text-slate-400">
                {progress}/{TOTAL_TARGETS_PER_ROUND}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-slate-900 text-white font-black text-xs tabular-nums">
            <Trophy className="w-3.5 h-3.5 text-amber-300" />
            {score}
          </div>
          <div
            className={`flex items-center gap-1 px-3 py-1.5 rounded-2xl font-black text-xs transition-all ${
              combo > 1 ? 'bg-amber-400 text-amber-950 scale-105' : 'bg-slate-100 text-slate-400'
            }`}
          >
            <Zap className={`w-3.5 h-3.5 ${combo > 1 ? 'fill-amber-950' : ''}`} />
            {combo > 1 ? `${combo}x combo` : 'combo'}
          </div>
          <button
            onClick={startNewRound}
            className="p-2 rounded-2xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 transition-colors"
            title="Restart round (R)"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── Stage + camera ── */}
      <div className="flex flex-col @4xl:flex-row gap-4 items-stretch">
        {/* Bubble stage */}
        <div className="arcade-stage @container relative rounded-3xl overflow-hidden h-[360px] @4xl:h-auto @4xl:min-h-[560px] @4xl:flex-1 select-none">
          {AMBIENT.map((a, i) => (
            <span
              key={i}
              className="arcade-ambient"
              style={{
                left: `${a.left}%`,
                width: a.size,
                height: a.size,
                animationDuration: `${a.duration}s`,
                animationDelay: `${a.delay}s`,
              }}
            />
          ))}

          {bubbles.map((b) => {
            const slot = SLOTS[b.slotIndex];
            const isTarget = isPlaying && b.sign.id === targetSign.id && !b.bursting;
            return (
              <div
                key={b.id}
                className="absolute -translate-x-1/2 -translate-y-1/2"
                style={{ left: `${slot.x}%`, top: `${slot.y}%`, zIndex: isTarget ? 5 : 2 }}
              >
                <div
                  className="arcade-drift"
                  style={{
                    animationDuration: `${6 + (b.slotIndex % 3) * 1.3}s`,
                    animationDelay: `${-b.slotIndex * 1.1}s`,
                    animationDirection: b.slotIndex % 2 ? 'reverse' : 'normal',
                  }}
                >
                  <button
                    type="button"
                    disabled={!isPlaying}
                    onClick={() => {
                      if (busyRef.current) return;
                      sounds.playTap();
                      setTargetSign(b.sign);
                    }}
                    className={`arcade-bubble ${b.bursting ? 'is-popping' : 'is-new'} ${
                      isTarget ? 'is-target' : isPlaying ? 'is-idle' : ''
                    }`}
                    style={{ '--h': b.hue } as React.CSSProperties}
                    title={isPlaying ? `Make "${b.sign.name}" the target` : undefined}
                  >
                    {isTarget && <span className="arcade-target-tag">Sign this</span>}
                    <span className="arcade-bubble-emoji">{b.sign.iconEmoji}</span>
                    <span className="arcade-bubble-word">{b.sign.name}</span>
                    <span className="arcade-bubble-hindi">{b.sign.hindiName}</span>
                  </button>
                </div>
              </div>
            );
          })}

          {bursts.map((p) => (
            <div
              key={p.id}
              className="absolute pointer-events-none"
              style={{ left: `${p.x}%`, top: `${p.y}%`, zIndex: 6, '--h': p.hue } as React.CSSProperties}
            >
              {Array.from({ length: 10 }, (_, i) => {
                const a = (i / 10) * Math.PI * 2;
                return (
                  <span
                    key={i}
                    className="arcade-droplet"
                    style={{ '--dx': `${Math.cos(a) * 70}px`, '--dy': `${Math.sin(a) * 70}px` } as React.CSSProperties}
                  />
                );
              })}
              <span className="arcade-points">+{p.points}</span>
            </div>
          ))}

          {/* Start screen */}
          {!isPlaying && !isGameOver && (
            <div className="absolute inset-0 z-20 flex items-center justify-center p-6 bg-white/35 backdrop-blur-[3px]">
              <div className="bg-white/90 rounded-3xl px-7 py-6 shadow-xl border border-white text-center max-w-sm">
                <h3 className="font-black text-2xl text-slate-800 mb-1">Ready to pop?</h3>
                <p className="text-sm text-slate-500 mb-5 leading-relaxed">
                  A bubble glows with the word to sign. Sign it to the camera and it bursts. Ten bubbles a round.
                </p>
                <button
                  onClick={startNewRound}
                  className="btn-duo-primary px-7 py-3 rounded-2xl font-black text-sm active:scale-95 inline-flex items-center gap-2"
                >
                  <Play className="w-4 h-4 fill-white" />
                  Start round
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Camera + target panel */}
        <div className="grid grid-cols-1 @xl:grid-cols-[1.25fr_1fr] @4xl:flex @4xl:flex-col @4xl:w-[400px] @4xl:shrink-0 gap-4">
          <div className="bg-white rounded-3xl p-3 border-2 border-slate-200/90 shadow-2xs">
            <CameraFeed
              targetGesture={targetSign.gestureTarget}
              signName={targetSign.name}
              hindiName={targetSign.hindiName}
              signId={targetSign.id}
              onSignRecognized={handleSignRecognized}
              isRecordingDataset={true}
              isDemoMode={isDemoMode}
            />
          </div>

          <div className="bg-white rounded-3xl p-4 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div
                className="arcade-bubble arcade-bubble-mini shrink-0"
                style={{ '--h': bubbles.find((b) => b.sign.id === targetSign.id)?.hue ?? 199 } as React.CSSProperties}
              >
                <span className="text-2xl">{targetSign.iconEmoji}</span>
              </div>
              <div className="min-w-0">
                <span className="text-[10px] uppercase font-black tracking-wider text-sky-600">Sign this word</span>
                <div className="font-black text-2xl text-slate-800 leading-tight truncate">{targetSign.name}</div>
                <div className="text-sm font-bold text-slate-400">{targetSign.hindiName}</div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setShowHowToModal(true)}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-2xl bg-sky-50 hover:bg-sky-100 text-sky-700 border-2 border-sky-200 text-xs font-black transition-all"
              >
                <HelpCircle className="w-4 h-4" />
                How to sign
              </button>
              <button
                onClick={handleSkipTarget}
                disabled={!isPlaying}
                className="flex items-center justify-center gap-1.5 py-2.5 rounded-2xl bg-white hover:bg-slate-50 text-slate-600 border-2 border-slate-200 text-xs font-black transition-all disabled:opacity-40"
              >
                Skip
                <SkipForward className="w-4 h-4" />
              </button>
            </div>

            {lastFeedback && (
              <div
                className={`rounded-2xl px-3 py-2.5 text-xs font-bold flex items-center gap-2 border-2 ${
                  lastFeedback.good
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-amber-50 border-amber-200 text-amber-900'
                }`}
              >
                <Sparkles className="w-4 h-4 shrink-0" />
                <span>{lastFeedback.text}</span>
              </div>
            )}

            <div className="flex items-center gap-x-3 gap-y-1 flex-wrap text-[11px] font-bold text-slate-400 mt-auto">
              <span><kbd className="arcade-kbd">Space</kbd> record</span>
              <span><kbd className="arcade-kbd">H</kbd> how to</span>
              <span><kbd className="arcade-kbd">N</kbd> skip</span>
              <span><kbd className="arcade-kbd">R</kbd> restart</span>
            </div>
          </div>
        </div>
      </div>

      {/* How-to modal: guide clip where we have one, otherwise the 3D signer */}
      {showHowToModal && (
        <div
          className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowHowToModal(false)}
        >
          <div
            className="bg-white rounded-3xl max-w-xl w-full p-5 shadow-2xl flex flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="text-3xl">{targetSign.iconEmoji}</span>
                <div>
                  <h3 className="font-black text-lg text-slate-800">How to sign "{targetSign.name}"</h3>
                  <p className="text-xs font-bold text-sky-600">{targetSign.hindiName}</p>
                </div>
              </div>
              <button
                onClick={() => setShowHowToModal(false)}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <SignVisualizer sign={targetSign} />

            <button
              onClick={() => setShowHowToModal(false)}
              className="w-full btn-duo-primary py-3 rounded-2xl font-black text-sm"
            >
              Got it, back to the game
            </button>
          </div>
        </div>
      )}

      {/* Round finished */}
      {isGameOver && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl flex flex-col items-center text-center">
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-tr from-amber-400 to-yellow-500 flex items-center justify-center text-4xl shadow-lg shadow-amber-500/30 mb-3">
              🏆
            </div>
            <h2 className="text-2xl font-black text-slate-800 mb-1">Round complete!</h2>
            <p className="text-xs text-slate-500 mb-5">Shabash! Every take was saved with its label for training.</p>

            <div className="w-full grid grid-cols-3 gap-2.5 mb-5">
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Score</div>
                <div className="text-xl font-black text-slate-800">{score}</div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Popped</div>
                <div className="text-xl font-black text-sky-600">{poppedCount}/{TOTAL_TARGETS_PER_ROUND}</div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Best combo</div>
                <div className="text-xl font-black text-amber-600">{maxCombo}x</div>
              </div>
            </div>

            <div className="w-full bg-emerald-50 border border-emerald-200 rounded-2xl p-3.5 mb-5 flex items-center gap-2.5 text-left text-xs text-emerald-800">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <span>All takes saved with verified labels to your research dataset.</span>
            </div>

            <div className="w-full flex gap-3">
              <button
                onClick={startNewRound}
                className="flex-1 btn-duo-secondary py-3 rounded-2xl font-bold text-xs flex items-center justify-center gap-1.5"
              >
                <RotateCcw className="w-4 h-4" />
                Play again
              </button>
              <button
                onClick={handleClaimReward}
                className="flex-1 btn-duo-success py-3 rounded-2xl font-black text-xs flex items-center justify-center gap-1.5 shadow-md"
              >
                Claim rewards
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
