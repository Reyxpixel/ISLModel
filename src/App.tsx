import React, { useState, useEffect } from 'react';
import { Navbar, ActiveTab } from './components/Navbar';
import { LeftSidebar } from './components/LeftSidebar';
import { RightSidebar } from './components/RightSidebar';
import { CurriculumPath } from './components/CurriculumPath';
import { PopSignArcade } from './components/PopSignArcade';
import { SignDictionary } from './components/SignDictionary';
import { LearnMode } from './components/LearnMode';
import { DataCollectorModal } from './components/DataCollectorModal';
import { ISLSign } from './types/isl';
import { ISL_SIGNS } from './data/islCurriculum';
import { dataRecorder } from './services/dataRecorder';
import { sounds } from './services/audio';

// Local calendar day as YYYY-MM-DD (offset in days, e.g. -1 = yesterday)
function todayKey(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<ActiveTab>('path');
  const [activeLearnSign, setActiveLearnSign] = useState<ISLSign | null>(null);
  const [isDatasetModalOpen, setIsDatasetModalOpen] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  // Master Demo Mode Toggle: controls whether the website is populated with placeholder demo data
  const [isDemoMode, setIsDemoMode] = useState<boolean>(() => {
    const saved = localStorage.getItem('signit_demo_mode');
    return saved !== null ? saved === 'true' : true; // Default ON so user initially sees all demo features
  });

  const toggleDemoMode = () => {
    setIsDemoMode((prev) => {
      const next = !prev;
      localStorage.setItem('signit_demo_mode', next.toString());
      return next;
    });
  };

  // Gamification progress (persisted in localStorage). A new learner starts at zero;
  // Demo Mode adds the placeholder numbers on top (see display values below).
  const [streak, setStreak] = useState<number>(() => {
    const saved = localStorage.getItem('signit_streak');
    const last = localStorage.getItem('signit_last_active');
    // the streak is only alive if the learner practised today or yesterday
    if (!saved || (last !== todayKey() && last !== todayKey(-1))) return 0;
    return parseInt(saved, 10);
  });

  const [xp, setXp] = useState<number>(() => {
    const saved = localStorage.getItem('signit_xp');
    return saved ? parseInt(saved, 10) : 0;
  });

  const [gems, setGems] = useState<number>(() => {
    const saved = localStorage.getItem('signit_gems');
    return saved ? parseInt(saved, 10) : 0;
  });

  const [completedSignIds, setCompletedSignIds] = useState<string[]>(() => {
    const saved = localStorage.getItem('signit_completed_signs');
    return saved ? JSON.parse(saved) : [];
  });

  // Daily quest: signs practised today (goal 3)
  const [questCount, setQuestCount] = useState<number>(() => {
    try {
      const q = JSON.parse(localStorage.getItem('signit_quest') || 'null');
      return q && q.date === todayKey() ? q.count : 0;
    } catch {
      return 0;
    }
  });

  const [recordedSamplesCount, setRecordedSamplesCount] = useState<number>(0);

  // Sync count of recorded samples from IndexedDB
  const refreshSampleCount = async () => {
    try {
      const all = await dataRecorder.getAllSamples();
      setRecordedSamplesCount(all.length);
    } catch {
      // IndexedDB fallback
    }
  };

  useEffect(() => {
    refreshSampleCount();
  }, []);

  const handleScoreEarned = (earnedXp: number, earnedGems: number) => {
    setXp((prev) => {
      const next = prev + earnedXp;
      localStorage.setItem('signit_xp', next.toString());
      return next;
    });

    setGems((prev) => {
      const next = prev + earnedGems;
      localStorage.setItem('signit_gems', next.toString());
      return next;
    });
  };

  const handleSignCompleted = (signId: string, earnedXp: number, earnedGems: number) => {
    handleScoreEarned(earnedXp, earnedGems);

    // daily quest + streak
    const today = todayKey();
    const last = localStorage.getItem('signit_last_active');
    if (last !== today) {
      const nextStreak = last === todayKey(-1) ? streak + 1 : 1;
      setStreak(nextStreak);
      localStorage.setItem('signit_streak', nextStreak.toString());
      localStorage.setItem('signit_last_active', today);
    }
    setQuestCount((prev) => {
      const next = prev + 1;
      localStorage.setItem('signit_quest', JSON.stringify({ date: today, count: next }));
      return next;
    });

    setCompletedSignIds((prev) => {
      if (!prev.includes(signId)) {
        const next = [...prev, signId];
        localStorage.setItem('signit_completed_signs', JSON.stringify(next));
        return next;
      }
      return prev;
    });

    refreshSampleCount();
  };

  const toggleMute = () => {
    const nextState = !isMuted;
    setIsMuted(nextState);
    sounds.setMuted(nextState);
  };

  // Wipes everything this browser holds for the learner: progress, quest, streak,
  // recorded takes (Research Hub) and Demo Mode (so the zeroed numbers show).
  const handleResetAllData = async () => {
    ['signit_streak', 'signit_xp', 'signit_gems', 'signit_completed_signs', 'signit_quest', 'signit_last_active']
      .forEach((k) => localStorage.removeItem(k));
    localStorage.setItem('signit_demo_mode', 'false');
    setStreak(0);
    setXp(0);
    setGems(0);
    setCompletedSignIds([]);
    setQuestCount(0);
    setIsDemoMode(false);
    setActiveLearnSign(null);
    setIsDatasetModalOpen(false);
    await dataRecorder.clearAllSamples();
    await refreshSampleCount();
    sounds.playSuccess();
  };

  const totalSignsCount = Object.keys(ISL_SIGNS).length;

  // Values shown: real progress, plus placeholder numbers while Demo Mode is on
  const displayStreak = isDemoMode ? Math.max(3, streak) : streak;
  const displayXp = isDemoMode ? 250 + xp : xp;
  const displayGems = isDemoMode ? 120 + gems : gems;

  return (
    <div className="h-screen flex flex-col bg-slate-50 text-slate-800 overflow-hidden">
      {/* Top Header Bar with prominent Demo Mode switch */}
      <Navbar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        streak={displayStreak}
        xp={displayXp}
        gems={displayGems}
        recordedSamplesCount={recordedSamplesCount}
        isMuted={isMuted}
        onToggleMute={toggleMute}
        onOpenDatasetModal={() => setIsDatasetModalOpen(true)}
        isDemoMode={isDemoMode}
        onToggleDemoMode={toggleDemoMode}
        onResetAllData={handleResetAllData}
        resetSummary={{
          xp,
          gems,
          streak,
          completedSigns: completedSignIds.length,
          recordedTakes: recordedSamplesCount,
        }}
      />

      {/* Main 3-Column Layout: Left Sidebar + Center Stream + Right Sidebar */}
      <div className="max-w-[1780px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex gap-6 items-stretch justify-center flex-1 min-h-0 overflow-hidden">
        {/* Left Column: Persistent Desktop Navigation & Profile */}
        <LeftSidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          recordedSamplesCount={recordedSamplesCount}
          completedSignsCount={completedSignIds.length}
          questCount={questCount}
          totalSignsCount={totalSignsCount}
          isMuted={isMuted}
          onToggleMute={toggleMute}
          onOpenDatasetModal={() => setIsDatasetModalOpen(true)}
          isDemoMode={isDemoMode}
        />

        {/* Center Column: Active Game / Learning Arena */}
        <main className="flex-1 min-w-0 max-w-5xl 2xl:max-w-6xl w-full h-full overflow-y-auto pr-1 pb-20 lg:pb-6 scrollbar-none">
          {activeTab === 'path' && (
            <CurriculumPath
              onSelectSign={(sign) => setActiveLearnSign(sign)}
              onStartArcade={() => setActiveTab('arcade')}
              completedSignIds={completedSignIds}
              streak={displayStreak}
              xp={displayXp}
              isDemoMode={isDemoMode}
            />
          )}

          {activeTab === 'arcade' && (
            <PopSignArcade
              onScoreEarned={handleScoreEarned}
              onSampleRecorded={refreshSampleCount}
              isDemoMode={isDemoMode}
            />
          )}

          {activeTab === 'dictionary' && (
            <SignDictionary onSelectSign={(sign) => setActiveLearnSign(sign)} />
          )}
        </main>

        {/* Right Column: Streaks, Leaderboard, Mudra of the Day (No model checkpoint box) */}
        <RightSidebar
          streak={displayStreak}
          xp={displayXp}
          onSelectSign={(sign) => setActiveLearnSign(sign)}
          recordedSamplesCount={recordedSamplesCount}
          isDemoMode={isDemoMode}
        />
      </div>

      {/* Interactive Step-by-Step Learning Modal */}
      {activeLearnSign && (
        <LearnMode
          sign={activeLearnSign}
          onClose={() => setActiveLearnSign(null)}
          onComplete={(earnedXp, earnedGems) => {
            handleSignCompleted(activeLearnSign.id, earnedXp, earnedGems);
          }}
          onSampleRecorded={refreshSampleCount}
          isDemoMode={isDemoMode}
        />
      )}

      {/* Research Dataset Hub Modal */}
      <DataCollectorModal
        isOpen={isDatasetModalOpen}
        onClose={() => setIsDatasetModalOpen(false)}
        onDatasetUpdated={refreshSampleCount}
      />
    </div>
  );
}
