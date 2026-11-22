import React from 'react';
import { Map, Gamepad2, BookOpen, Database, Sparkles, Volume2, VolumeX, Award, CheckCircle2, Flame, Layers } from 'lucide-react';
import { ActiveTab } from './Navbar';
import { sounds } from '../services/audio';
import { dataRecorder } from '../services/dataRecorder';

interface LeftSidebarProps {
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
  recordedSamplesCount: number;
  completedSignsCount: number;
  questCount: number;
  totalSignsCount: number;
  isMuted: boolean;
  onToggleMute: () => void;
  onOpenDatasetModal: () => void;
  isDemoMode?: boolean;
}

export const LeftSidebar: React.FC<LeftSidebarProps> = ({
  activeTab,
  onTabChange,
  recordedSamplesCount,
  completedSignsCount,
  questCount: realQuestCount,
  totalSignsCount,
  isMuted,
  onToggleMute,
  onOpenDatasetModal,
  isDemoMode = false,
}) => {
  const navItems = [
    {
      id: 'path' as ActiveTab,
      label: 'Journey',
      subtitle: '10 Chapters & Progression',
      icon: Map,
      badge: null,
    },
    {
      id: 'arcade' as ActiveTab,
      label: 'Arcade',
      subtitle: 'Bubble Practice & Data',
      icon: Gamepad2,
      badge: 'LIVE',
    },
    {
      id: 'dictionary' as ActiveTab,
      label: 'Library',
      subtitle: 'All 91 Authentic Signs',
      icon: BookOpen,
      badge: `${totalSignsCount}`,
    },
  ];

  const displayCompletedCount = isDemoMode ? Math.max(12, completedSignsCount) : completedSignsCount;
  const masteryPercent = Math.round((displayCompletedCount / Math.max(1, totalSignsCount)) * 100);
  const questCount = isDemoMode ? 2 : Math.min(3, realQuestCount);

  return (
    <aside className="hidden lg:flex flex-col w-72 xl:w-80 h-full justify-between pr-2 shrink-0 select-none overflow-y-auto pb-4 scrollbar-none">
      <div className="flex flex-col gap-4">
        {/* Navigation Category */}
        <div className="flex flex-col gap-2">
          <div className="px-3 text-[11px] font-black uppercase tracking-wider text-slate-400">
            Main Navigation
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;

            return (
              <button
                key={item.id}
                onClick={() => {
                  sounds.playTap();
                  onTabChange(item.id);
                }}
                className={`flex items-center justify-between w-full p-3.5 rounded-2xl font-black text-sm transition-all duration-150 group ${
                  isActive
                    ? 'bg-sky-500 text-white shadow-md shadow-sky-500/25 translate-x-1'
                    : 'text-slate-600 hover:bg-white hover:text-slate-900 border-2 border-transparent hover:border-slate-200/80 shadow-2xs'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center transition-colors ${
                      isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600 group-hover:bg-sky-100 group-hover:text-sky-600'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="text-left">
                    <div className="leading-tight text-sm">{item.label}</div>
                    <div className={`text-[11px] font-bold ${isActive ? 'text-sky-100' : 'text-slate-400'}`}>
                      {item.subtitle}
                    </div>
                  </div>
                </div>

                {item.badge && (
                  <span
                    className={`text-[10px] font-black px-2 py-0.5 rounded-full ${
                      isActive
                        ? 'bg-white text-sky-600'
                        : 'bg-sky-100 text-sky-700 border border-sky-200'
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}

          {/* Dataset Research Hub Nav Button */}
          <button
            onClick={() => {
              sounds.playTap();
              onOpenDatasetModal();
            }}
            className="flex items-center justify-between w-full p-3.5 rounded-2xl font-black text-sm text-slate-700 bg-white hover:bg-slate-50 border-2 border-slate-200 hover:border-red-300 transition-all shadow-2xs group mt-1"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-red-100 text-red-600 flex items-center justify-center group-hover:scale-105 transition-transform">
                <Database className="w-5 h-5 text-red-500" />
              </div>
              <div className="text-left">
                <div className="leading-tight">Research Hub</div>
                <div className="text-[11px] font-bold text-slate-400">Dataset & Retraining</div>
              </div>
            </div>
            <span className="flex items-center gap-1.5 text-[11px] font-black px-2.5 py-0.5 rounded-full bg-red-100 text-red-700 border border-red-200 font-mono">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              {recordedSamplesCount}
            </span>
          </button>
        </div>

        {/* ISL Mastery Progress Card */}
        <div className="bg-white rounded-3xl p-5 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-black uppercase tracking-wider text-sky-600">
              Curriculum Mastery
            </span>
            <span className="text-xs font-black text-slate-700 font-mono">
              {masteryPercent}%
            </span>
          </div>

          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-sky-50 border border-sky-200 flex items-center justify-center text-xl shrink-0">
              🎓
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-extrabold text-sm text-slate-800">
                {displayCompletedCount} of {totalSignsCount} Signs
              </div>
              <div className="text-[11px] font-bold text-slate-400">
                10 Chapters Loaded
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200">
            <div
              className="bg-gradient-to-r from-sky-500 to-emerald-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${Math.max(5, masteryPercent)}%` }}
            />
          </div>
        </div>

        {/* Daily ISL Quest Card (Affected by Demo Mode) */}
        <div className="bg-gradient-to-br from-amber-50/70 via-white to-orange-50/60 rounded-3xl p-4.5 border-2 border-amber-200/80 shadow-2xs flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-black text-xs text-amber-800">
              <Flame className="w-4 h-4 text-amber-500 fill-amber-500" />
              <span>Daily Practice Quest</span>
            </div>
            <span className="text-[10px] font-black bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full border border-amber-300">
              +50 XP
            </span>
          </div>
          <p className="text-[11px] font-bold text-slate-600 leading-snug">
            {questCount === 0
              ? 'Complete at least 3 signs today to ignite your daily streak!'
              : questCount >= 3
              ? 'Awesome work! Daily quest achieved for today!'
              : `Keep going! Practice ${3 - questCount} more sign${3 - questCount === 1 ? '' : 's'} to complete today's quest.`}
          </p>
          <div className="flex items-center justify-between text-[11px] font-black text-amber-900 pt-1">
            <span>Goal: 3 Signs</span>
            <span className="font-mono">{questCount} / 3</span>
          </div>
          <div className="w-full bg-amber-100 rounded-full h-2 overflow-hidden border border-amber-200/60">
            <div
              className="bg-amber-500 h-full rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, (questCount / 3) * 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Bottom Profile & Audio Card */}
      <div className="flex flex-col gap-3 mt-4">
        <div className="bg-white rounded-3xl p-4 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-sky-400 to-indigo-500 text-white flex items-center justify-center text-lg font-black shadow-md shadow-sky-500/20 shrink-0">
              🤟
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-black text-sm text-slate-800 truncate">
                ISL Researcher
              </div>
              <div className="text-[10px] font-mono text-slate-400 truncate">
                ID: {dataRecorder.getContributorId()}
              </div>
            </div>
          </div>

          {/* Sound Mute Toggle */}
          <button
            onClick={onToggleMute}
            className="flex items-center justify-between px-3.5 py-2 rounded-xl text-xs font-black text-slate-600 bg-slate-50 hover:bg-slate-100 border border-slate-200 transition-colors"
          >
            <span className="flex items-center gap-2">
              {isMuted ? <VolumeX className="w-4 h-4 text-slate-400" /> : <Volume2 className="w-4 h-4 text-sky-500" />}
              Sound Feedback
            </span>
            <span className={`text-[10px] uppercase font-black px-1.5 py-0.5 rounded ${
              isMuted ? 'bg-slate-200 text-slate-500' : 'bg-emerald-100 text-emerald-800'
            }`}>
              {isMuted ? 'Muted' : 'On'}
            </span>
          </button>
        </div>
      </div>
    </aside>
  );
};
