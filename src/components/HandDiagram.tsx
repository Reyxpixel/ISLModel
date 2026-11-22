import React from 'react';

interface HandDiagramProps {
  signId: string;
  className?: string;
}

export const HandDiagram: React.FC<HandDiagramProps> = ({ signId, className = 'w-36 h-36' }) => {
  // Renders custom, modern vector SVG diagrams for Indian Sign Language hand postures
  switch (signId) {
    case 'hello':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-sky-50 stroke-sky-200" strokeWidth="2" strokeDasharray="4 4" />
          {/* Head & Temple Reference */}
          <path d="M45 75 C45 45 65 35 85 35 C105 35 115 48 115 70 C115 88 102 96 92 100" stroke="#cbd5e1" strokeWidth="2" strokeDasharray="3 3" />
          {/* Wave Motion Curves */}
          <path d="M125 50 Q138 65 125 80" stroke="#0ea5e9" strokeWidth="3" strokeLinecap="round" />
          <path d="M133 45 Q148 65 133 85" stroke="#38bdf8" strokeWidth="2.5" strokeLinecap="round" />
          {/* Raised Open Hand at Temple */}
          <path
            d="M68 130 C65 110 68 95 72 82 C72 70 76 52 80 50 C83 48 86 50 87 56 L89 82 C91 70 94 48 97 46 C100 44 103 47 103 54 L103 82 C105 72 108 52 112 50 C115 48 118 51 117 58 L114 88 C116 80 120 68 123 68 C126 68 128 72 126 80 L120 108 C115 125 98 132 82 132 Z"
            className="fill-sky-400 stroke-sky-700"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Sparkles */}
          <path d="M92 25 L94 30 L99 31 L95 34 L96 39 L92 36 L88 39 L89 34 L85 31 L90 30 Z" fill="#38bdf8" />
          <text x="80" y="150" textAnchor="middle" className="fill-sky-700 text-[11px] font-black">
            Wave Greeting 👋
          </text>
        </svg>
      );

    case 'namaste':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          {/* Background Aura */}
          <circle cx="80" cy="80" r="70" className="fill-sky-50 stroke-sky-200" strokeWidth="2" strokeDasharray="4 4" />
          {/* Left Palm */}
          <path
            d="M74 135 C74 110 65 85 62 60 C61 50 67 45 71 47 C75 49 76 65 77 80 C78 52 82 40 85 43 C87 45 86 65 85 85 C87 50 91 42 94 45 C97 48 95 70 93 90 C96 60 99 55 102 58 C104 61 101 80 97 100 C101 85 106 82 108 85 C111 89 104 105 98 118 C90 135 82 135 74 135 Z"
            className="fill-sky-400/20 stroke-sky-600"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Right Palm Mirror */}
          <path
            d="M86 135 C86 110 95 85 98 60 C99 50 93 45 89 47 C85 49 84 65 83 80 C82 52 78 40 75 43 C73 45 74 65 75 85 C73 50 69 42 66 45 C63 48 65 70 67 90 C64 60 61 55 58 58 C56 61 59 80 63 100 C59 85 54 82 52 85 C49 89 56 105 62 118 C70 135 78 135 86 135 Z"
            className="fill-sky-500 stroke-sky-700"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Energy Sparks */}
          <path d="M80 20 L80 32 M55 30 L64 39 M105 30 L96 39" stroke="#0ea5e9" strokeWidth="3" strokeLinecap="round" />
          {/* Direction indicator */}
          <path d="M42 90 L52 90 M118 90 L108 90" stroke="#0284c7" strokeWidth="3" strokeLinecap="round" />
          <polygon points="56,90 50,86 50,94" fill="#0284c7" />
          <polygon points="104,90 110,86 110,94" fill="#0284c7" />
        </svg>
      );

    case 'thankyou':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-emerald-50 stroke-emerald-200" strokeWidth="2" />
          {/* Face Silhouette Reference */}
          <path d="M40 50 C40 30 60 25 75 25 C90 25 100 35 100 55 C100 70 85 75 75 80 C70 85 65 95 65 110" stroke="#cbd5e1" strokeWidth="2.5" strokeDasharray="3 3" />
          {/* Chin Indicator */}
          <circle cx="75" cy="80" r="4" fill="#10b981" />
          {/* Hand starting at chin and moving forward */}
          <path
            d="M75 80 C85 75 100 72 115 72 C118 72 120 74 120 77 C120 80 118 82 112 85 L95 95 C88 98 80 95 75 80 Z"
            className="fill-emerald-400 stroke-emerald-700"
            strokeWidth="3"
            strokeLinejoin="round"
          />
          {/* Movement Arc Arrow */}
          <path d="M78 88 Q105 95 125 110" stroke="#059669" strokeWidth="3.5" strokeLinecap="round" />
          <polygon points="130,113 120,112 126,104" fill="#059669" />
          <text x="80" y="145" textAnchor="middle" className="fill-emerald-700 text-[11px] font-bold">
            Chin ➔ Forward
          </text>
        </svg>
      );

    case 'water':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-sky-50 stroke-sky-200" strokeWidth="2" />
          {/* Water Droplet */}
          <path d="M125 35 C125 35 140 55 140 68 C140 76 133 83 125 83 C117 83 110 76 110 68 C110 55 125 35 125 35 Z" fill="#38bdf8" />
          {/* 3 Fingers "W" Shape */}
          <path
            d="M50 120 L50 95 C50 90 55 88 58 92 C62 96 65 110 68 115 C68 100 68 70 72 65 C75 60 78 62 79 70 L80 100 C80 85 85 58 89 55 C92 52 95 54 96 62 L97 98 C97 80 103 68 106 68 C109 68 111 72 111 82 L109 110 C107 125 95 135 75 135 C60 135 50 130 50 120 Z"
            className="fill-sky-400 stroke-sky-700"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Tap Motion lines at mouth */}
          <path d="M90 40 L90 48 M102 45 L100 52" stroke="#0284c7" strokeWidth="2.5" strokeLinecap="round" />
          <text x="80" y="150" textAnchor="middle" className="fill-sky-700 text-[11px] font-bold">
            3 Fingers "W"
          </text>
        </svg>
      );

    case 'good':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-amber-50 stroke-amber-200" strokeWidth="2" />
          {/* Thumbs Up Hand */}
          <path
            d="M60 125 C50 125 45 115 45 105 L45 90 C45 85 50 80 55 80 L70 80 L70 50 C70 40 76 32 82 32 C87 32 90 38 90 48 L87 75 L110 75 C116 75 120 80 119 86 L115 105 C114 112 108 125 95 125 Z"
            className="fill-amber-400 stroke-amber-600"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Star Accents */}
          <path d="M125 35 L128 42 L135 43 L130 48 L132 55 L125 51 L118 55 L120 48 L115 43 L122 42 Z" fill="#f59e0b" />
          <text x="80" y="148" textAnchor="middle" className="fill-amber-700 text-[11px] font-bold">
            Thumbs Up 👍
          </text>
        </svg>
      );

    case 'number2':
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-cyan-50 stroke-cyan-200" strokeWidth="2" />
          {/* V / Peace Hand */}
          <path
            d="M60 130 C50 130 48 115 48 100 L50 85 C50 80 55 78 60 82 L65 90 C65 75 66 50 70 45 C73 40 76 42 78 48 L82 85 C83 75 88 45 92 42 C95 39 98 42 98 48 L96 92 C100 88 105 88 108 92 C110 96 108 105 105 115 C100 128 85 130 60 130 Z"
            className="fill-cyan-400 stroke-cyan-700"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text x="80" y="148" textAnchor="middle" className="fill-cyan-700 text-[11px] font-bold">
            Numeral 2 / "V" ✌️
          </text>
        </svg>
      );

    default:
      return (
        <svg viewBox="0 0 160 160" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="80" cy="80" r="70" className="fill-slate-50 stroke-slate-200" strokeWidth="2" />
          {/* General Open Hand */}
          <path
            d="M50 130 L50 95 C50 90 54 88 58 92 L62 100 C62 80 64 62 68 58 C71 54 74 56 75 62 L78 95 C80 80 84 52 87 50 C90 48 93 50 94 56 L95 95 C97 80 101 60 104 58 C107 56 109 58 110 65 L108 105 C105 125 90 132 75 132 Z"
            className="fill-sky-400 stroke-sky-700"
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <text x="80" y="150" textAnchor="middle" className="fill-slate-600 text-[11px] font-bold">
            Open Hand Form
          </text>
        </svg>
      );
  }
};

