import React from 'react';
import { Check, Lock, Play, Star, Sparkles, Trophy, Video } from 'lucide-react';
import { ISL_LEVELS, ISL_SIGNS } from '../data/islCurriculum';
import { ISLSign } from '../types/isl';
import { sounds } from '../services/audio';

interface CurriculumPathProps {
  onSelectSign: (sign: ISLSign) => void;
  onStartArcade: () => void;
  completedSignIds: string[];
  streak: number;
  xp: number;
  isDemoMode?: boolean;
}

// Curving SVG Dotted Path Connector between consecutive roadmap nodes
const PathConnector: React.FC<{ fromOffsetIdx: number; toOffsetIdx: number; isCompleted: boolean }> = ({
  fromOffsetIdx,
  toOffsetIdx,
  isCompleted,
}) => {
  // 0 = center (x=100), 1 = right (x=155), 2 = left (x=45)
  const getX = (offset: number) => {
    if (offset === 1) return 155;
    if (offset === 2) return 45;
    return 100;
  };

  const x1 = getX(fromOffsetIdx);
  const x2 = getX(toOffsetIdx);
  const pathD = `M ${x1} 0 C ${x1} 22, ${x2} 22, ${x2} 44`;

  return (
    <div className="w-full flex items-center justify-center -my-2.5 pointer-events-none relative z-0">
      <svg width="220" height="44" viewBox="0 0 200 44" fill="none" className="overflow-visible">
        {/* Soft aura backing */}
        <path
          d={pathD}
          stroke={isCompleted ? '#d1fae5' : '#e0f2fe'}
          strokeWidth="6"
          strokeLinecap="round"
        />
        {/* Vibrant Dotted Connecting Path */}
        <path
          d={pathD}
          stroke={isCompleted ? '#10b981' : '#38bdf8'}
          strokeWidth="3.5"
          strokeDasharray="6 8"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
};

export const CurriculumPath: React.FC<CurriculumPathProps> = ({
  onSelectSign,
  onStartArcade,
  completedSignIds,
  streak,
  xp,
  isDemoMode = false,
}) => {
  return (
    <div className="w-full flex flex-col gap-6">
      {/* Quick Play Banner for Mobile & Tablet */}
      <div className="xl:hidden bg-gradient-to-r from-sky-400 to-blue-600 rounded-3xl p-4 text-white shadow-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🎯</span>
          <div>
            <h3 className="font-black text-base">Arcade Mode</h3>
            <p className="text-xs text-sky-100">Pop word bubbles in real time with your camera!</p>
          </div>
        </div>
        <button
          onClick={() => {
            sounds.playTap();
            onStartArcade();
          }}
          className="bg-white text-sky-600 px-4 py-2 rounded-2xl font-black text-xs shadow-sm active:scale-95 flex items-center gap-1.5"
        >
          <Play className="w-3.5 h-3.5 fill-sky-600" />
          Play
        </button>
      </div>

      {/* Main 10-Chapter Curriculum Roadmap */}
      <div className="flex flex-col gap-6">
        {ISL_LEVELS.map((level, levelIdx) => {
          // Chapter 1 is always unlocked. Next chapters unlock if previous chapter has >= 50% completed signs
          const prevLevel = levelIdx > 0 ? ISL_LEVELS[levelIdx - 1] : null;
          const prevCompletedCount = prevLevel
            ? prevLevel.signIds.filter((id) => completedSignIds.includes(id)).length
            : 0;
          const isUnlocked = levelIdx === 0 || prevCompletedCount >= Math.ceil((prevLevel?.signIds.length || 1) / 2);

          const chapterCompletedCount = level.signIds.filter((id) => completedSignIds.includes(id)).length;
          const isChapterFinished = chapterCompletedCount === level.signIds.length;

          return (
            <div
              key={level.id}
              className={`rounded-3xl border-2 transition-all p-5 ${
                isUnlocked
                  ? 'bg-white border-slate-200/90 shadow-xs'
                  : 'bg-slate-50/70 border-slate-200 opacity-60'
              }`}
            >
              {/* Unit Header Card */}
              <div className={`rounded-2xl p-4 text-white shadow-md mb-6 flex items-center justify-between ${
                isChapterFinished
                  ? 'bg-gradient-to-r from-emerald-500 to-teal-500'
                  : 'bg-gradient-to-r from-sky-500 to-cyan-500 shadow-sky-500/15'
              }`}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-extrabold uppercase tracking-widest text-sky-100">
                      Level {levelIdx + 1} • {chapterCompletedCount}/{level.signIds.length} Mastered
                    </span>
                    {isChapterFinished && (
                      <span className="bg-white/20 text-white text-[10px] font-extrabold px-2 py-0.5 rounded-full">
                        Completed
                      </span>
                    )}
                  </div>
                  <h2 className="text-lg font-black">{level.title}</h2>
                  <p className="text-xs text-sky-100 font-medium">{level.hindiTitle}</p>
                </div>
                {/* Properly centered XP Reward Badge */}
                <div className="px-3.5 py-1.5 min-w-[72px] h-9 rounded-xl bg-white/20 backdrop-blur-xs flex items-center justify-center font-black text-xs text-white whitespace-nowrap shadow-2xs">
                  +{level.xpReward} XP
                </div>
              </div>

              {/* Node Path with Dotted Guide Curves */}
              <div className="flex flex-col items-center py-2 relative">
                {level.signIds.map((signId, nodeIdx) => {
                  const sign = ISL_SIGNS[signId];
                  if (!sign) return null;

                  const isDone = completedSignIds.includes(signId);
                  const offsets = ['translate-x-0', 'translate-x-12 sm:translate-x-16', '-translate-x-12 sm:-translate-x-16'];
                  const offsetIdx = nodeIdx % offsets.length;
                  const offsetClass = offsets[offsetIdx];

                  const prevOffsetIdx = nodeIdx > 0 ? (nodeIdx - 1) % offsets.length : 0;
                  const prevSignId = nodeIdx > 0 ? level.signIds[nodeIdx - 1] : null;
                  const isPrevDone = prevSignId ? completedSignIds.includes(prevSignId) : false;

                  return (
                    <React.Fragment key={signId}>
                      {/* Dotted path connector between consecutive nodes */}
                      {nodeIdx > 0 && (
                        <PathConnector
                          fromOffsetIdx={prevOffsetIdx}
                          toOffsetIdx={offsetIdx}
                          isCompleted={isDone && isPrevDone}
                        />
                      )}

                      <div className={`flex flex-col items-center group ${offsetClass} relative z-10 my-2`}>
                        {/* Interactive Node Button */}
                        <button
                          disabled={!isUnlocked}
                          onClick={() => {
                            sounds.playTap();
                            onSelectSign(sign);
                          }}
                          className={`w-18 h-18 sm:w-22 sm:h-22 rounded-3xl flex items-center justify-center text-3xl sm:text-4xl transition-all duration-200 shadow-md relative ${
                            isDone
                              ? 'bg-emerald-500 border-b-4 border-emerald-600 text-white hover:bg-emerald-400 active:translate-y-1'
                              : isUnlocked
                              ? 'bg-sky-500 border-b-4 border-sky-600 text-white hover:bg-sky-400 active:translate-y-1 hover:scale-105'
                              : 'bg-slate-200 border-b-4 border-slate-300 text-slate-400 cursor-not-allowed'
                          }`}
                        >
                          {isDone ? (
                            <Check className="w-8 h-8 stroke-[3]" />
                          ) : !isUnlocked ? (
                            <Lock className="w-6 h-6" />
                          ) : (
                            <span>{sign.iconEmoji}</span>
                          )}

                          {/* Video Available Indicator Dot */}
                          {sign.hasGuideVideo && isUnlocked && !isDone && (
                            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-amber-400 border-2 border-white flex items-center justify-center text-[10px] text-amber-950 font-black shadow-xs" title="Video Guide Available">
                              ▶
                            </span>
                          )}
                        </button>

                        {/* Label Badge */}
                        <div className="mt-2 text-center">
                          <span className="font-extrabold text-xs text-slate-800 block">
                            {sign.name}
                          </span>
                          <span className="text-[11px] font-semibold text-slate-400">
                            {sign.hindiName}
                          </span>
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Daily Challenges Widget in Center (Affected by Demo Mode) */}
      <div className="bg-white rounded-3xl p-5 border-2 border-slate-200/80 shadow-xs flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h4 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-amber-500" />
            Daily Goals
          </h4>
          <span className="text-[11px] font-bold text-sky-600">Daily Reset</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {/* Goal 1 */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700">Master 5 ISL Signs</span>
              <span className="font-extrabold text-sky-600">
                {isDemoMode ? 4 : Math.min(5, completedSignIds.length)} / 5
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-sky-500 h-full rounded-full transition-all"
                style={{ width: `${((isDemoMode ? 4 : completedSignIds.length) / 5) * 100}%` }}
              />
            </div>
          </div>

          {/* Goal 2 */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-700">Earn 300 XP</span>
              <span className="font-extrabold text-purple-600">
                {isDemoMode ? 250 : Math.min(300, xp)} / 300
              </span>
            </div>
            <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-purple-500 h-full rounded-full transition-all"
                style={{ width: `${((isDemoMode ? 250 : xp) / 300) * 100}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
