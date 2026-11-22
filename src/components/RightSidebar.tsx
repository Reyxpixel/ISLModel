import React from 'react';
import { Flame, Trophy, Volume2, ArrowRight, Check, Sparkles, BookOpen, Lightbulb } from 'lucide-react';
import { ISL_SIGNS } from '../data/islCurriculum';
import { ISLSign } from '../types/isl';
import { HandDiagram } from './HandDiagram';
import { sounds } from '../services/audio';
import { speechService } from '../services/speech';

interface RightSidebarProps {
  streak: number;
  xp: number;
  onSelectSign: (sign: ISLSign) => void;
  recordedSamplesCount: number;
  isDemoMode?: boolean;
}

export const RightSidebar: React.FC<RightSidebarProps> = ({
  streak,
  xp,
  onSelectSign,
  recordedSamplesCount,
  isDemoMode = false,
}) => {
  // Sign of the Day
  const featuredSign = ISL_SIGNS.hello || Object.values(ISL_SIGNS)[0];

  // 7-day activity days
  const daysOfWeek = [
    { day: 'M', completed: isDemoMode },
    { day: 'T', completed: isDemoMode },
    { day: 'W', completed: isDemoMode },
    { day: 'T', completed: false },
    { day: 'F', completed: false },
    { day: 'S', completed: false },
    { day: 'S', completed: false },
  ];

  // Demo Leaderboard (populated only when Demo Mode is ON)
  const demoLeaderboard = [
    { rank: 1, name: 'Priya Sharma', xp: 780, avatar: '👩', medal: '🥇' },
    { rank: 2, name: 'Aarav Patel', xp: 620, avatar: '👨', medal: '🥈' },
    { rank: 3, name: 'You (Learner)', xp: xp || 250, avatar: '🤟', medal: '🥉', isCurrentUser: true },
    { rank: 4, name: 'Sneha Reddy', xp: 390, avatar: '🧕', medal: '4' },
    { rank: 5, name: 'Vikram Singh', xp: 310, avatar: '👳', medal: '5' },
  ];

  const handlePronounce = (e: React.MouseEvent) => {
    e.stopPropagation();
    sounds.playTap();
    speechService.speak(featuredSign.name, 'en-IN');
    setTimeout(() => {
      speechService.speak(featuredSign.hindiName, 'hi-IN');
    }, 900);
  };

  const displayStreak = isDemoMode ? streak : 0;

  return (
    <aside className="hidden xl:flex flex-col w-84 2xl:w-92 h-full gap-4 pl-2 shrink-0 overflow-y-auto pb-4 select-none scrollbar-none">
      {/* 1. Daily Streak Card */}
      <div className="bg-white rounded-3xl p-4.5 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`w-10 h-10 rounded-2xl border flex items-center justify-center ${
              displayStreak > 0
                ? 'bg-amber-50 border-amber-200 text-amber-500'
                : 'bg-slate-50 border-slate-200 text-slate-400'
            }`}>
              <Flame className={`w-5 h-5 ${displayStreak > 0 ? 'fill-amber-500 text-amber-500' : 'text-slate-400'}`} />
            </div>
            <div>
              <div className="font-black text-sm text-slate-800">
                {displayStreak > 0 ? `${displayStreak} Day Streak!` : '0 Day Streak'}
              </div>
              <div className="text-[11px] font-bold text-slate-400">
                {displayStreak > 0 ? 'Keep practicing daily' : 'Complete a lesson today to ignite!'}
              </div>
            </div>
          </div>
          <span className={`text-[10px] font-black px-2.5 py-0.5 rounded-full border ${
            displayStreak > 0
              ? 'text-amber-600 bg-amber-50 border-amber-200'
              : 'text-slate-500 bg-slate-100 border-slate-200'
          }`}>
            {displayStreak > 0 ? 'Active' : 'Start Today'}
          </span>
        </div>

        {/* 7-Day Dots */}
        <div className="grid grid-cols-7 gap-1.5 pt-1">
          {daysOfWeek.map((d, idx) => (
            <div key={idx} className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center text-xs font-black transition-all ${
                  d.completed
                    ? 'bg-amber-500 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-400 border border-slate-200'
                }`}
              >
                {d.completed ? <Check className="w-4 h-4 stroke-[3]" /> : d.day}
              </div>
              <span className="text-[10px] font-bold text-slate-400">{d.day}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 2. ISL Sign of the Day Showcase (Mudra of the Day) */}
      <div className="bg-gradient-to-br from-sky-50/70 via-white to-blue-50/60 rounded-3xl p-4.5 border-2 border-sky-200 shadow-2xs flex flex-col gap-3 relative overflow-hidden">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-sky-600 bg-sky-100/90 px-2.5 py-0.5 rounded-md border border-sky-300">
            Mudra of the Day
          </span>
          <button
            onClick={handlePronounce}
            title="Hear pronunciation in Hindi & English"
            className="p-1.5 rounded-xl bg-white hover:bg-sky-50 border border-sky-200 text-sky-600 transition-colors flex items-center gap-1 text-[11px] font-bold shadow-2xs"
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span>Audio</span>
          </button>
        </div>

        {/* Vector SVG Diagram & Description */}
        <div className="flex items-center gap-3">
          <div className="w-22 h-22 bg-white rounded-2xl border-2 border-sky-100 flex items-center justify-center p-1 shadow-inner shrink-0 relative">
            <HandDiagram signId={featuredSign.id} className="w-full h-full" />
            {featuredSign.hasGuideVideo && (
              <span className="absolute -top-1 -right-1 bg-amber-400 text-amber-950 text-[9px] font-black px-1.5 py-0.2 rounded-full border border-white shadow-xs" title="Video Guide Available">
                HD
              </span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h4 className="font-black text-sm text-slate-800 leading-tight">
              {featuredSign.name}
            </h4>
            <p className="text-xs font-bold text-sky-600 mb-1">{featuredSign.hindiName}</p>
            <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
              {featuredSign.handshapeDescription}
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            sounds.playTap();
            onSelectSign(featuredSign);
          }}
          className="w-full btn-duo-primary py-2.5 rounded-xl text-xs font-black flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
        >
          <span>Practice Mudra Now</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 3. Community Weekly League */}
      <div className="bg-white rounded-3xl p-5 border-2 border-slate-200/90 shadow-2xs flex flex-col gap-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Trophy className="w-4 h-4 text-amber-500" />
            <h4 className="font-black text-sm text-slate-800">Silver League</h4>
          </div>
          <span className="text-[10px] font-black text-slate-400 bg-slate-100 px-2 py-0.5 rounded-md">
            Reset: 2d
          </span>
        </div>

        {isDemoMode ? (
          <div className="flex flex-col gap-2">
            {demoLeaderboard.map((user) => (
              <div
                key={user.rank}
                className={`flex items-center justify-between p-2.5 rounded-xl text-xs transition-all ${
                  user.isCurrentUser
                    ? 'bg-sky-50 border-2 border-sky-300 font-black text-sky-900 shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-50 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <span className="w-4 text-center text-xs font-black">{user.medal}</span>
                  <span className="text-base">{user.avatar}</span>
                  <span className="truncate font-extrabold">{user.name}</span>
                </div>
                <span className="font-mono font-black text-xs text-slate-600 shrink-0">
                  {user.xp} XP
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-7 px-4 text-center flex flex-col items-center justify-center bg-slate-50/80 rounded-2xl border border-slate-100">
            <Trophy className="w-8 h-8 text-slate-300 mb-2 opacity-60" />
            <p className="font-black text-xs text-slate-700 mb-1">No players ranked yet</p>
            <p className="text-[11px] text-slate-400 max-w-[210px] leading-relaxed">
              Complete lessons or play Arcade mode to claim the #1 rank in this week's league!
            </p>
          </div>
        )}
      </div>

      {/* 4. ISL Grammar & Signing Tip Widget */}
      <div className="bg-sky-50/50 rounded-3xl p-4.5 border-2 border-sky-100/90 shadow-2xs flex flex-col gap-2">
        <div className="flex items-center gap-1.5 text-xs font-black text-sky-800">
          <Lightbulb className="w-4 h-4 text-sky-500" />
          <span>ISL Signing Pro-Tip</span>
        </div>
        <p className="text-[11px] text-slate-600 font-semibold leading-relaxed">
          In Indian Sign Language, non-manual cues like eyebrow movement, eye gaze, and subtle head tilts carry vital grammatical meaning for questions and emphasis!
        </p>
      </div>
    </aside>
  );
};
