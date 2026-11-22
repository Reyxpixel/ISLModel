import React, { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Flame, Gem, Zap, Volume2, VolumeX, Database, BookOpen, Gamepad2, Map, Wand2, RotateCcw, AlertTriangle, Loader2 } from 'lucide-react';
import { sounds } from '../services/audio';

export type ActiveTab = 'path' | 'arcade' | 'dictionary' | 'dataset';

interface NavbarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  streak: number;
  xp: number;
  gems: number;
  recordedSamplesCount: number;
  isMuted: boolean;
  onToggleMute: () => void;
  onOpenDatasetModal: () => void;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
  onResetAllData?: () => void | Promise<void>;
  /** What a reset would wipe, shown in the confirmation window */
  resetSummary?: { xp: number; gems: number; streak: number; completedSigns: number; recordedTakes: number };
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onTabChange,
  streak,
  xp,
  gems,
  recordedSamplesCount,
  isMuted,
  onToggleMute,
  onOpenDatasetModal,
  isDemoMode,
  onToggleDemoMode,
  onResetAllData,
  resetSummary,
}) => {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetDone, setResetDone] = useState(false);

  const handleConfirmReset = async () => {
    setIsResetting(true);
    try {
      await onResetAllData?.();
    } finally {
      setIsResetting(false);
      setShowResetConfirm(false);
      setResetDone(true);
      setTimeout(() => setResetDone(false), 2500);
    }
  };

  useEffect(() => {
    if (!showResetConfirm) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isResetting) setShowResetConfirm(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showResetConfirm, isResetting]);

  const wipeList = [
    { label: 'Learning progress', value: `${resetSummary?.completedSigns ?? 0} signs completed, ${resetSummary?.xp ?? 0} XP` },
    { label: 'Gems and streak', value: `${resetSummary?.gems ?? 0} gems, ${resetSummary?.streak ?? 0}-day streak` },
    { label: 'Daily quest', value: "Today's quest starts again at 0 / 3" },
    { label: 'Research Hub', value: `${resetSummary?.recordedTakes ?? 0} recorded takes (video + landmarks)` },
    { label: 'Demo Mode', value: 'Switched off so you see the fresh start' },
  ];

  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b-2 border-slate-200/80 shadow-2xs">
      <div className="max-w-[1780px] w-full mx-auto px-4 sm:px-6 lg:px-8">
        <div className="relative flex items-center justify-between h-18 gap-4">
          {/* Left: Logo & Brand + Demo Mode Toggle */}
          <div className="flex items-center gap-3 sm:gap-4 shrink-0">
            <div
              className="flex items-center gap-3 cursor-pointer select-none group"
              onClick={() => onTabChange('path')}
            >
              <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-sky-500 to-cyan-400 flex items-center justify-center text-white shadow-md shadow-sky-500/25 text-2xl font-black group-hover:scale-105 transition-transform">
                🤟
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-black text-2xl tracking-tight text-slate-900 leading-tight">
                    Sign<span className="text-sky-500">It</span>
                  </span>
                  <span className="px-2 py-0.5 text-[10px] font-black uppercase tracking-wider rounded-md bg-sky-100 text-sky-700 border border-sky-300">
                    ISL AI
                  </span>
                </div>
                <p className="text-[11px] font-bold text-slate-400 hidden sm:block">
                  Indian Sign Language
                </p>
              </div>
            </div>

            {/* Highly Visible Master Demo Mode Switch (Left Side next to Logo) */}
            <div
              onClick={onToggleDemoMode}
              title="Click to toggle Demo Mode: populates or clears mock demo data"
              className={`flex items-center gap-2 px-3 py-1.5 rounded-2xl border-2 transition-all cursor-pointer select-none shadow-2xs ${
                isDemoMode
                  ? 'bg-amber-50 border-amber-300 hover:bg-amber-100/70'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center gap-1.5">
                <Wand2 className={`w-4 h-4 transition-colors ${isDemoMode ? 'text-amber-500 animate-bounce' : 'text-slate-400'}`} />
                <span className="text-xs font-black text-slate-700 hidden md:inline">
                  Demo Mode
                </span>
              </div>

              {/* Polished Toggle Switch */}
              <div
                className={`relative inline-flex h-5.5 w-10 shrink-0 items-center rounded-full transition-colors duration-200 ease-in-out ${
                  isDemoMode ? 'bg-amber-500' : 'bg-slate-300'
                }`}
              >
                <span
                  className={`inline-block h-4.5 w-4.5 transform rounded-full bg-white shadow-md transition-transform duration-200 ease-in-out ${
                    isDemoMode ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </div>

              <span
                className={`text-[10px] font-black px-1.5 py-0.5 rounded-md ${
                  isDemoMode ? 'bg-amber-200 text-amber-900' : 'bg-slate-200 text-slate-600'
                }`}
              >
                {isDemoMode ? 'ON' : 'OFF'}
              </span>
            </div>
          </div>

          {/* Center: Desktop Navigation Tabs (Perfect Centering) */}
          <nav className="hidden lg:flex items-center gap-1.5 bg-slate-100/90 p-1.5 rounded-2xl border border-slate-200/90 shadow-2xs absolute left-1/2 -translate-x-1/2">
            <button
              onClick={() => {
                sounds.playTap();
                onTabChange('path');
              }}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-extrabold transition-all ${
                activeTab === 'path'
                  ? 'bg-white text-sky-600 shadow-sm border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              <Map className="w-4 h-4 text-sky-500" />
              <span>Journey</span>
            </button>

            <button
              onClick={() => {
                sounds.playTap();
                onTabChange('arcade');
              }}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-extrabold transition-all relative ${
                activeTab === 'arcade'
                  ? 'bg-white text-sky-600 shadow-sm border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              <Gamepad2 className="w-4 h-4 text-sky-500" />
              <span>Arcade</span>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
              </span>
            </button>

            <button
              onClick={() => {
                sounds.playTap();
                onTabChange('dictionary');
              }}
              className={`flex items-center gap-2 px-5 py-2 rounded-xl text-sm font-extrabold transition-all ${
                activeTab === 'dictionary'
                  ? 'bg-white text-sky-600 shadow-sm border border-slate-200/60'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
              }`}
            >
              <BookOpen className="w-4 h-4 text-sky-500" />
              <span>Library</span>
            </button>
          </nav>

          {/* Right Top Bar Area: Game Stats, Reset & Sound */}
          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            {/* Research Dataset Counter Button */}
            <button
              onClick={() => {
                sounds.playTap();
                onOpenDatasetModal();
              }}
              title="View & export ISL training dataset takes"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-sky-50 hover:bg-sky-100 border-2 border-sky-200 text-sky-700 font-extrabold text-xs transition-all active:scale-95 shadow-2xs"
            >
              <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
              <Database className="w-3.5 h-3.5 text-sky-600" />
              <span className="hidden md:inline">Dataset:</span>
              <span className="bg-sky-200/90 text-sky-900 px-1.5 py-0.5 rounded-md text-[11px] font-black font-mono">
                {recordedSamplesCount}
              </span>
            </button>

            {/* Streak Counter */}
            <div className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-2xl border-2 font-black text-xs ${
              streak > 0
                ? 'bg-amber-50 border-amber-200 text-amber-600'
                : 'bg-slate-50 border-slate-200 text-slate-400'
            }`}>
              <Flame className={`w-4 h-4 ${streak > 0 ? 'text-amber-500 fill-amber-500' : 'text-slate-400'}`} />
              <span>{streak}</span>
            </div>

            {/* Gems */}
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-blue-50 border-2 border-blue-200 text-blue-600 font-black text-xs">
              <Gem className="w-4 h-4 text-blue-500 fill-blue-500" />
              <span>{gems}</span>
            </div>

            {/* Sound Mute Toggle */}
            <button
              onClick={onToggleMute}
              className="p-2 rounded-2xl text-slate-500 hover:text-slate-800 hover:bg-slate-100 border border-slate-200 transition-colors"
              title={isMuted ? 'Unmute sound effects' : 'Mute sound effects'}
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-slate-400" /> : <Volume2 className="w-4 h-4 text-sky-500" />}
            </button>

            {/* Reset All Progress & Data Button */}
            <button
              onClick={() => {
                sounds.playTap();
                setShowResetConfirm(true);
              }}
              className="p-2 rounded-2xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 hover:border-rose-200 transition-colors"
              title="Reset all current progress & collected dataset takes"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation window for resetting all data. Rendered into <body>: the sticky
          header's backdrop blur would otherwise trap a fixed overlay inside the header. */}
      {showResetConfirm &&
        createPortal(
          <div
            className="fixed inset-0 z-[100] bg-slate-900/55 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => !isResetting && setShowResetConfirm(false)}
          >
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby="reset-title"
              className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl flex flex-col gap-4"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-2xl bg-rose-100 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-6 h-6 text-rose-600" />
                </div>
                <div>
                  <h3 id="reset-title" className="font-black text-lg text-slate-900 leading-tight">Reset everything?</h3>
                  <p className="text-xs font-semibold text-slate-500">This clears the following from this browser and can't be undone.</p>
                </div>
              </div>

              <ul className="flex flex-col gap-1.5">
                {wipeList.map((w) => (
                  <li key={w.label} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 border border-slate-200 px-3 py-2">
                    <span className="text-xs font-black text-slate-700">{w.label}</span>
                    <span className="text-[11px] font-semibold text-slate-500 text-right">{w.value}</span>
                  </li>
                ))}
              </ul>

              {(resetSummary?.recordedTakes ?? 0) > 0 && (
                <p className="text-[11px] font-semibold text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                  Export the dataset from the Research Hub first if you want to keep the recorded takes.
                </p>
              )}

              <div className="flex items-center justify-end gap-2.5 pt-1">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  disabled={isResetting}
                  autoFocus
                  className="px-4 py-2.5 rounded-xl border-2 border-slate-200 text-slate-600 hover:bg-slate-100 font-extrabold text-xs transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmReset}
                  disabled={isResetting}
                  className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-black text-xs shadow-md transition-all active:scale-95 flex items-center gap-1.5 disabled:opacity-70"
                >
                  {isResetting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  <span>{isResetting ? 'Resetting...' : 'Yes, reset everything'}</span>
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}

      {resetDone &&
        createPortal(
          <div className="fixed top-20 left-1/2 -translate-x-1/2 z-[100] bg-slate-900 text-white text-xs font-black px-4 py-2.5 rounded-2xl shadow-xl">
            Everything was reset. Fresh start!
          </div>,
          document.body,
        )}

      {/* Mobile Bottom Navigation Bar */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-md border-t-2 border-slate-200 px-4 py-2 flex justify-around items-center shadow-lg">
        <button
          onClick={() => {
            sounds.playTap();
            onTabChange('path');
          }}
          className={`flex flex-col items-center gap-1 text-xs font-black py-1 px-3 rounded-xl ${
            activeTab === 'path' ? 'text-sky-600' : 'text-slate-400'
          }`}
        >
          <Map className="w-5 h-5" />
          <span>Journey</span>
        </button>

        <button
          onClick={() => {
            sounds.playTap();
            onTabChange('arcade');
          }}
          className={`flex flex-col items-center gap-1 text-xs font-black py-1 px-3 rounded-xl relative ${
            activeTab === 'arcade' ? 'text-sky-600' : 'text-slate-400'
          }`}
        >
          <Gamepad2 className="w-5 h-5" />
          <span>Arcade</span>
          <span className="absolute top-1 right-2.5 w-2 h-2 rounded-full bg-sky-500 animate-ping"></span>
        </button>

        <button
          onClick={() => {
            sounds.playTap();
            onTabChange('dictionary');
          }}
          className={`flex flex-col items-center gap-1 text-xs font-black py-1 px-3 rounded-xl ${
            activeTab === 'dictionary' ? 'text-sky-600' : 'text-slate-400'
          }`}
        >
          <BookOpen className="w-5 h-5" />
          <span>Library</span>
        </button>

        <button
          onClick={() => {
            sounds.playTap();
            onOpenDatasetModal();
          }}
          className="flex flex-col items-center gap-1 text-xs font-black py-1 px-3 rounded-xl text-slate-500"
        >
          <div className="relative">
            <Database className="w-5 h-5 text-red-500" />
            <span className="absolute -top-1 -right-2 bg-red-500 text-white text-[9px] font-black rounded-full px-1">
              {recordedSamplesCount}
            </span>
          </div>
          <span>Dataset</span>
        </button>
      </div>
    </header>
  );
};
