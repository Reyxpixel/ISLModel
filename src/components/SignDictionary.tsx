import React, { useState } from 'react';
import { Search, Filter, Play, Hand, Sparkles, BookOpen, Video, Layers } from 'lucide-react';
import { ISL_SIGNS } from '../data/islCurriculum';
import { ISLSign, SignCategory } from '../types/isl';
import { sounds } from '../services/audio';

interface SignDictionaryProps {
  onSelectSign: (sign: ISLSign) => void;
}

export const SignDictionary: React.FC<SignDictionaryProps> = ({ onSelectSign }) => {
  const [search, setSearch] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');

  const categories: { id: string; label: string }[] = [
    { id: 'all', label: 'All 91 Signs' },
    { id: 'greetings', label: 'Greetings' },
    { id: 'pronouns', label: 'Pronouns' },
    { id: 'family', label: 'Family' },
    { id: 'people', label: 'People' },
    { id: 'time_basics', label: 'Time Basics' },
    { id: 'days', label: 'Days' },
    { id: 'time_units', label: 'Time Units' },
    { id: 'animals', label: 'Animals' },
    { id: 'colours', label: 'Colours' },
    { id: 'objects', label: 'Objects' },
  ];

  const signsList = Object.values(ISL_SIGNS);

  const filteredSigns = signsList.filter((s) => {
    const matchesCategory = selectedCategory === 'all' || s.category === selectedCategory;
    const matchesSearch =
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      s.hindiName.toLowerCase().includes(search.toLowerCase()) ||
      s.description.toLowerCase().includes(search.toLowerCase()) ||
      s.id.toLowerCase().includes(search.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  return (
    <div className="w-full flex flex-col gap-6">
      {/* Search & Header */}
      <div className="bg-white rounded-3xl p-6 border-2 border-slate-200/80 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-8 h-8 rounded-xl bg-sky-100 text-sky-600 flex items-center justify-center font-bold text-sm">
              📖
            </span>
            <h1 className="font-extrabold text-2xl text-slate-800">
              Indian Sign Language Library (91 Signs)
            </h1>
          </div>
          <p className="text-xs text-slate-500">
            Interactive vocabulary with authentic video guides, 3D landmark signer, and AI real-time recognition.
          </p>
        </div>

        {/* Search Bar */}
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search 91 signs (hello, माँ, time)..."
            className="w-full bg-slate-50 border-2 border-slate-200 rounded-2xl pl-10 pr-4 py-2.5 text-xs font-semibold text-slate-800 placeholder-slate-400 focus:outline-none focus:border-sky-500 transition-colors"
          />
        </div>
      </div>

      {/* Filter Chips */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
        {categories.map((cat) => (
          <button
            key={cat.id}
            onClick={() => {
              sounds.playTap();
              setSelectedCategory(cat.id);
            }}
            className={`px-3.5 py-1.5 rounded-2xl text-xs font-bold whitespace-nowrap transition-all ${
              selectedCategory === cat.id
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Counter summary */}
      <div className="text-xs font-semibold text-slate-500">
        Showing {filteredSigns.length} of {signsList.length} Indian Sign Language gestures
      </div>

      {/* Sign Cards Grid */}
      <div className="grid gap-5 grid-cols-[repeat(auto-fill,minmax(230px,1fr))]">
        {filteredSigns.map((sign) => (
          <div
            key={sign.id}
            className="min-w-0 overflow-hidden bg-white rounded-3xl p-5 border-2 border-slate-200/80 shadow-xs hover:border-sky-300 hover:shadow-md transition-all flex flex-col justify-between group"
          >
            <div>
              {/* Header row */}
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="shrink-0 w-14 h-14 rounded-2xl bg-slate-50 border border-slate-100 flex items-center justify-center text-3xl group-hover:scale-110 transition-transform">
                  {sign.iconEmoji}
                </div>
                <div className="min-w-0 flex flex-col items-end gap-1">
                  <div className="flex flex-wrap items-center justify-end gap-1">
                    {sign.hasGuideVideo && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-1">
                        <Video className="w-2.5 h-2.5" /> Video
                      </span>
                    )}
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                      <Layers className="w-2.5 h-2.5" /> 3D
                    </span>
                  </div>
                  <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                    {sign.difficulty}
                  </span>
                </div>
              </div>

              {/* Title & Hindi */}
              <h3 className="font-black text-lg text-slate-800">{sign.name}</h3>
              <p className="text-xs font-bold text-sky-600 mb-2">{sign.hindiName}</p>
              <p className="text-xs text-slate-600 leading-relaxed mb-3 line-clamp-2">
                {sign.description}
              </p>

              {sign.culturalNote && (
                <div className="bg-sky-50/60 rounded-xl p-2 text-[11px] text-sky-800 mb-3 border border-sky-100">
                  <span className="font-bold">ISL Context:</span> {sign.culturalNote}
                </div>
              )}
            </div>

            {/* Practice Button */}
            <button
              onClick={() => {
                sounds.playTap();
                onSelectSign(sign);
              }}
              className="w-full btn-duo-primary py-2.5 rounded-2xl font-black text-xs flex items-center justify-center gap-1.5 shadow-sm active:scale-95"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              Learn & Practice
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
