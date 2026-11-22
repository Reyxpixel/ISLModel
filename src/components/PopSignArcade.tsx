import React, { useState, useEffect, useCallback } from 'react';
import confetti from 'canvas-confetti';
import { Play, RotateCcw, Trophy, Zap, Heart, Sparkles, CheckCircle2, HelpCircle, ArrowRight, Wand2, SkipForward } from 'lucide-react';
import { CameraFeed } from './CameraFeed';
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
  color: string;
  popped: boolean;
  bursting: boolean;
}

const ROUND_WORDS = [
  'hello', 'thank_you', 'how_are_you', 'we', 'i', 'you', 'they', 'she',
  'good_morning', 'good_night', 'hammer', 'handkerchief', 'hen', 'hole',
  'horse', 'in', 'individual', 'introduction', 'iron', 'it', 'mother',
  'father', 'friend', 'time', 'cat', 'dog', 'water', 'red', 'blue'
];

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
  const [lives, setLives] = useState<number>(3);
  const [gameMode, setGameMode] = useState<'model' | 'practice'>('model');

  // Round progression (10 targets per round as in mudra_bubbles.py)
  const [roundTargetsCount, setRoundTargetsCount] = useState<number>(0);
  const TOTAL_TARGETS_PER_ROUND = 10;

  // Active bubbles in the 6 bubble slots
  const [bubbles, setBubbles] = useState<BubbleTarget[]>([]);
  const [targetSign, setTargetSign] = useState<ISLSign>(ISL_SIGNS.hello);
  const [showHowToModal, setShowHowToModal] = useState<boolean>(false);
  const [lastFeedback, setLastFeedback] = useState<string>('');

  const bubbleColorStyles = [
    'from-sky-400 to-blue-500 border-sky-300 text-white shadow-sky-500/20',
    'from-emerald-400 to-teal-500 border-emerald-300 text-white shadow-emerald-500/20',
    'from-amber-400 to-orange-500 border-amber-300 text-white shadow-amber-500/20',
    'from-indigo-400 to-purple-500 border-indigo-300 text-white shadow-indigo-500/20',
    'from-rose-400 to-pink-500 border-rose-300 text-white shadow-rose-500/20',
    'from-cyan-400 to-teal-500 border-cyan-300 text-white shadow-cyan-500/20',
  ];

  // Initialize fresh round with 6 bubble slots
  const startNewRound = useCallback(() => {
    const shuffled = [...ROUND_WORDS].sort(() => 0.5 - Math.random());
    const pickedSigns = shuffled.slice(0, 6).map((id) => ISL_SIGNS[id] || Object.values(ISL_SIGNS)[0]);

    const initialBubbles: BubbleTarget[] = pickedSigns.map((s, idx) => ({
      id: `b_${s.id}_${Math.random()}`,
      sign: s,
      slotIndex: idx,
      color: bubbleColorStyles[idx % bubbleColorStyles.length],
      popped: false,
      bursting: false,
    }));

    setBubbles(initialBubbles);
    setTargetSign(initialBubbles[0].sign);
    setRoundTargetsCount(0);
    setScore(0);
    setCombo(0);
    setMaxCombo(0);
    setLives(3);
    setIsGameOver(false);
    setIsPlaying(true);
    setLastFeedback('');
  }, []);

  // Keyboard shortcuts (space = sign, h = howto, n = skip, m = mode, r = restart)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isGameOver) return;
      if (e.key === 'h' || e.key === 'H') {
        setShowHowToModal((prev) => !prev);
      } else if (e.key === 'n' || e.key === 'N') {
        handleSkipTarget();
      } else if (e.key === 'm' || e.key === 'M') {
        setGameMode((prev) => (prev === 'model' ? 'practice' : 'model'));
      } else if (e.key === 'r' || e.key === 'R') {
        startNewRound();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isGameOver, startNewRound]);

  // Advance to next target bubble
  const advanceTarget = useCallback(() => {
    setBubbles((prev) => {
      const remaining = prev.filter((b) => !b.popped);
      if (remaining.length === 0) {
        // Refill 6 fresh bubble slots
        const shuffled = [...ROUND_WORDS].sort(() => 0.5 - Math.random()).slice(0, 6);
        return shuffled.map((id, idx) => ({
          id: `b_${id}_${Math.random()}`,
          sign: ISL_SIGNS[id] || Object.values(ISL_SIGNS)[0],
          slotIndex: idx,
          color: bubbleColorStyles[idx % bubbleColorStyles.length],
          popped: false,
          bursting: false,
        }));
      }
      return prev;
    });

    setRoundTargetsCount((prev) => {
      const next = prev + 1;
      if (next >= TOTAL_TARGETS_PER_ROUND) {
        setIsGameOver(true);
        setIsPlaying(false);
        sounds.playFanfare();
      }
      return next;
    });

    setTimeout(() => {
      setBubbles((currentBubbles) => {
        const available = currentBubbles.filter((b) => !b.popped);
        if (available.length > 0) {
          const nextTarget = available[Math.floor(Math.random() * available.length)].sign;
          setTargetSign(nextTarget);
        }
        return currentBubbles;
      });
    }, 350);
  }, []);

  // Handle successful sign recognition from camera
  const handleSignRecognized = (result: RecognitionResult) => {
    if (isGameOver) return;

    const topLabel = result.topLabel;
    const isTop1 = topLabel === targetSign.id;
    const isTop3 = result.predictions.slice(0, 3).some((p) => p.label === targetSign.id);

    // In model mode: must match top 3. In practice mode: any active hands
    const success =
      isDemoMode ||
      (gameMode === 'model' ? (isTop1 || isTop3) : result.topConfidence > 0.25);

    if (success) {
      sounds.playPop();
      const nextCombo = combo + 1;
      setCombo(nextCombo);
      if (nextCombo > maxCombo) setMaxCombo(nextCombo);
      sounds.playCombo(nextCombo);

      const baseScore = isTop1 ? 100 : 50;
      const earned = baseScore * Math.max(1, nextCombo);
      setScore((s) => s + earned);

      setLastFeedback(`💥 POP! "${targetSign.name}" Recognized! (+${earned} pts)`);

      confetti({
        particleCount: 35,
        spread: 65,
        origin: { y: 0.55 },
        colors: ['#0ea5e9', '#38bdf8', '#10b981', '#f59e0b', '#8b5cf6'],
      });

      // Mark bubble as popped
      setBubbles((prev) =>
        prev.map((b) =>
          b.sign.id === targetSign.id ? { ...b, bursting: true, popped: true } : b
        )
      );

      onSampleRecorded();
      advanceTarget();
    } else {
      setCombo(0);
      setLastFeedback(
        `Model guessed "${topLabel.replace(/_/g, ' ')}" (${Math.round(result.topConfidence * 100)}%). Try again or press Skip (N)!`
      );
    }
  };

  const handleSkipTarget = () => {
    sounds.playTap();
    setCombo(0);
    setLastFeedback(`Skipped "${targetSign.name}"`);
    advanceTarget();
  };

  const handleClaimReward = () => {
    const earnedXp = Math.round(score / 4) + 60;
    const earnedGems = Math.round(roundTargetsCount * 2) + 8;
    onScoreEarned(earnedXp, earnedGems);
    sounds.playFanfare();
    setIsGameOver(false);
  };

  return (
    <div className="w-full flex flex-col gap-5">
      {/* PopSign Arcade Header HUD Card */}
      <div className="bg-white rounded-3xl p-4.5 border-2 border-slate-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        {/* Title & Round Info */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-sky-400 to-blue-600 flex items-center justify-center text-2xl text-white shadow-md shadow-sky-500/25 shrink-0">
            🫧
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-black text-xl text-slate-800 tracking-tight">
                PopSign Arcade
              </h1>
              <span className="text-[10px] uppercase font-black px-2.5 py-0.5 rounded-full bg-sky-100 text-sky-800 border border-sky-300">
                Bubble {roundTargetsCount + 1} of {TOTAL_TARGETS_PER_ROUND}
              </span>
            </div>
            <p className="text-xs font-semibold text-slate-400">
              Sign the target word bubble with your webcam to pop it!
            </p>
          </div>
        </div>

        {/* Live Game Stats & Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Score Display */}
          <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-2xl bg-gradient-to-r from-purple-500 to-indigo-600 text-white font-black text-xs shadow-xs">
            <Trophy className="w-3.5 h-3.5 text-amber-300" />
            <span>{score} PTS</span>
          </div>

          {/* Combo Multiplier */}
          {combo > 1 && (
            <div className="flex items-center gap-1 px-3 py-1.5 rounded-2xl bg-amber-500 text-white font-black text-xs shadow-xs animate-pulse">
              <Zap className="w-3.5 h-3.5 fill-white" />
              <span>{combo}x COMBO!</span>
            </div>
          )}

          {/* Duolingo Hearts */}
          <div className="flex items-center gap-0.5 bg-rose-50 border border-rose-200 px-2.5 py-1.5 rounded-2xl text-xs">
            <span title="Lives">❤️❤️❤️</span>
          </div>

          {/* How to Sign Helper Button */}
          <button
            onClick={() => setShowHowToModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-sky-50 hover:bg-sky-100 text-sky-700 border border-sky-200 text-xs font-black transition-all"
            title="View video guide on how to perform this sign (H)"
          >
            <HelpCircle className="w-3.5 h-3.5 text-sky-500" />
            <span className="hidden sm:inline">Guide</span>
          </button>

          {/* Reset / New Round Button */}
          <button
            onClick={startNewRound}
            className="p-2 rounded-2xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 transition-colors"
            title="Restart round (R)"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Arcade Stage: 2-Column Balanced Arena */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left Arena: Clean Floating Mudra Bubbles Stage (7 cols) */}
        <div className="lg:col-span-7 bg-gradient-to-b from-sky-50/70 via-white to-blue-50/40 rounded-3xl p-5 border-2 border-sky-100 shadow-2xs relative min-h-[520px] flex flex-col justify-between overflow-hidden">
          {/* Active Bubble Target Banner */}
          <div className="z-10 bg-white/95 backdrop-blur-md border-2 border-sky-200 rounded-2xl p-3.5 shadow-2xs flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-3xl animate-bounce">{targetSign.iconEmoji}</span>
              <div>
                <span className="text-[10px] uppercase font-black tracking-wider text-sky-600 block">
                  Current Target Bubble
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-black text-xl text-slate-800 leading-tight">
                    {targetSign.name}
                  </span>
                  <span className="text-xs font-black text-sky-700 bg-sky-100 px-2 py-0.5 rounded-lg border border-sky-300">
                    {targetSign.hindiName}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowHowToModal(true)}
                className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-sky-100 hover:bg-sky-200 text-sky-800 border border-sky-300 text-xs font-black transition-all"
              >
                <span>How to Sign</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>
          </div>

          {/* Clean 6-Bubble Matrix Grid */}
          <div className="relative flex-1 w-full my-4 min-h-[340px] grid grid-cols-2 sm:grid-cols-3 gap-5 items-center justify-center p-2">
            {bubbles.map((b) => {
              const isTarget = b.sign.id === targetSign.id;
              if (b.popped && !b.bursting) {
                return (
                  <div
                    key={b.id}
                    className="aspect-square rounded-full border-2 border-dashed border-slate-200 bg-slate-50/50 flex flex-col items-center justify-center opacity-40 select-none"
                  >
                    <span className="text-lg">✨</span>
                    <span className="text-[11px] font-bold text-slate-400">Popped</span>
                  </div>
                );
              }

              return (
                <div
                  key={b.id}
                  onClick={() => {
                    sounds.playTap();
                    setTargetSign(b.sign);
                  }}
                  className={`aspect-square rounded-full flex flex-col items-center justify-center p-3 text-center cursor-pointer select-none transition-all duration-300 relative ${
                    b.bursting
                      ? 'scale-125 opacity-0 filter blur-xs'
                      : isTarget
                      ? 'ring-4 ring-amber-400 ring-offset-4 ring-offset-white scale-105 shadow-xl animate-float'
                      : 'hover:scale-102 opacity-85 hover:opacity-100'
                  } bg-gradient-to-br ${b.color} border-3 shadow-md`}
                >
                  {isTarget && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-amber-400 text-amber-950 text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full shadow-md whitespace-nowrap">
                      Pop This! 👇
                    </div>
                  )}

                  <span className="text-3xl filter drop-shadow mb-0.5">{b.sign.iconEmoji}</span>
                  <span className="text-xs font-black tracking-tight leading-tight truncate max-w-full">
                    {b.sign.name}
                  </span>
                  <span className="text-[10px] font-semibold opacity-90 truncate max-w-full">
                    {b.sign.hindiName}
                  </span>
                </div>
              );
            })}

            {/* Waiting prompt when round has not started */}
            {!isPlaying && !isGameOver && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-6 bg-white/95 backdrop-blur-xs rounded-2xl z-20">
                <div className="w-16 h-16 rounded-3xl bg-sky-100 text-sky-600 flex items-center justify-center text-3xl mb-3 shadow-inner">
                  🫧
                </div>
                <h3 className="font-black text-xl text-slate-800 mb-1">
                  Ready to Play PopSign?
                </h3>
                <p className="text-xs text-slate-500 max-w-sm mb-4">
                  Sign the target words with your webcam. Press <strong>Space</strong> or click to record each take!
                </p>
                <button
                  onClick={startNewRound}
                  className="btn-duo-primary px-6 py-3 rounded-2xl font-black text-sm shadow-xl active:scale-95 flex items-center gap-2"
                >
                  <Play className="w-4 h-4 fill-white" />
                  Start PopSign Round
                </button>
              </div>
            )}
          </div>

          {/* Bottom Footer Shortcuts Bar */}
          <div className="z-10 bg-white/90 border border-slate-200/90 rounded-2xl p-2.5 flex items-center justify-between text-xs text-slate-600 flex-wrap gap-2 shadow-2xs">
            <div className="flex items-center gap-2 font-bold text-slate-500">
              <span className="text-sky-600 font-extrabold">Shortcuts:</span>
              <span className="bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200 text-slate-700 font-mono text-[11px]">Space</span> Record
              <span className="bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200 text-slate-700 font-mono text-[11px]">H</span> Guide
              <span className="bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200 text-slate-700 font-mono text-[11px]">N</span> Skip
            </div>

            <button
              onClick={handleSkipTarget}
              className="flex items-center gap-1 text-xs font-black text-slate-500 hover:text-sky-600 transition-colors"
            >
              <span>Skip Word (N)</span>
              <SkipForward className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Right Arena: Camera Vision & Recognition Feed (5 cols) */}
        <div className="lg:col-span-5 flex flex-col gap-3.5">
          <div className="bg-white rounded-3xl p-4.5 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3">
            {/* Clean Header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-sky-100 text-sky-600 flex items-center justify-center font-black text-sm">
                  📷
                </div>
                <div>
                  <h3 className="font-black text-sm text-slate-800 leading-tight">
                    Camera Vision
                  </h3>
                  <p className="text-[10px] font-bold text-slate-400">Position hands clearly in view</p>
                </div>
              </div>
              <span className="text-[10px] font-black text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-xl border border-emerald-200 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                Ready
              </span>
            </div>

            {/* CameraFeed Component */}
            <CameraFeed
              targetGesture={targetSign.gestureTarget}
              signName={targetSign.name}
              hindiName={targetSign.hindiName}
              signId={targetSign.id}
              onSignRecognized={handleSignRecognized}
              isRecordingDataset={true}
              isDemoMode={isDemoMode}
            />

            {/* Recognition Feedback Alert */}
            {lastFeedback && (
              <div className="bg-sky-50/90 border-2 border-sky-200 rounded-2xl p-3 text-xs text-sky-900 font-bold animate-in fade-in flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-sky-500 shrink-0" />
                <span>{lastFeedback}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* How-To Reference Tutorial Modal */}
      {showHowToModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 border-4 border-sky-400 shadow-2xl flex flex-col gap-4 animate-in zoom-in-95">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="text-3xl">{targetSign.iconEmoji}</span>
                <div>
                  <h3 className="font-black text-lg text-slate-800">
                    How to Sign "{targetSign.name}"
                  </h3>
                  <p className="text-xs font-bold text-sky-600">{targetSign.hindiName}</p>
                </div>
              </div>
              <button
                onClick={() => setShowHowToModal(false)}
                className="p-1.5 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100"
              >
                ✕
              </button>
            </div>

            {targetSign.hasGuideVideo ? (
              <video
                src={`/guides/${targetSign.id.toLowerCase()}.mp4`}
                autoPlay
                loop
                muted
                playsInline
                controls
                className="w-full rounded-2xl aspect-4/3 object-contain bg-black shadow-inner"
              />
            ) : (
              <div className="p-6 bg-sky-50/60 rounded-2xl border-2 border-sky-200 text-center text-xs text-slate-700">
                <p className="font-bold text-slate-900 mb-1">{targetSign.handshapeDescription}</p>
                <p>{targetSign.movementDescription}</p>
              </div>
            )}

            <button
              onClick={() => setShowHowToModal(false)}
              className="w-full btn-duo-primary py-3 rounded-2xl font-black text-sm"
            >
              Ready! Back to Arcade
            </button>
          </div>
        </div>
      )}

      {/* Round Finished Modal */}
      {isGameOver && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 border-4 border-sky-400 shadow-2xl flex flex-col items-center text-center animate-in zoom-in-95 duration-200">
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-tr from-amber-400 to-yellow-500 flex items-center justify-center text-4xl shadow-lg shadow-amber-500/30 mb-3 animate-bounce">
              🏆
            </div>

            <h2 className="text-2xl font-black text-slate-800 mb-1">
              Round Complete!
            </h2>
            <p className="text-xs text-slate-500 mb-5">
              Shabash! You popped word bubbles and generated validated takes for ISL research!
            </p>

            <div className="w-full grid grid-cols-3 gap-2.5 mb-5">
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Score</div>
                <div className="text-xl font-black text-purple-600">{score}</div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Popped</div>
                <div className="text-xl font-black text-sky-600">{roundTargetsCount}</div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3">
                <div className="text-[10px] font-bold text-slate-400 uppercase">Max Combo</div>
                <div className="text-xl font-black text-amber-600">{maxCombo}x</div>
              </div>
            </div>

            <div className="w-full bg-emerald-50 border border-emerald-200 rounded-2xl p-3.5 mb-5 flex items-center gap-2.5 text-left text-xs text-emerald-800">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <span>All recorded sign takes saved with verified labels to your research dataset!</span>
            </div>

            <div className="w-full flex gap-3">
              <button
                onClick={startNewRound}
                className="flex-1 btn-duo-secondary py-3 rounded-2xl font-bold text-xs flex items-center justify-center gap-1.5"
              >
                <RotateCcw className="w-4 h-4" />
                Play Again
              </button>
              <button
                onClick={handleClaimReward}
                className="flex-1 btn-duo-success py-3 rounded-2xl font-black text-xs flex items-center justify-center gap-1.5 shadow-md"
              >
                Claim Rewards
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
