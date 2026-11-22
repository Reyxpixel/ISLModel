import React, { useEffect, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Video, Layers, Sparkles } from 'lucide-react';
import { ISLSign } from '../types/isl';
import { HAND_CONNECTIONS } from '../services/vision';

interface SignVisualizerProps {
  sign: ISLSign;
  className?: string;
  /** Small looping 3D preview only: no tabs, no player controls */
  compact?: boolean;
}

interface AnimationData {
  sign: string;
  fps: number;
  present: boolean[][];
  frames: number[][][][]; // [N][2][21][3]
}

// Scene units come from text_to_sign/signer.py: origin at the middle of the face,
// y up, SCENE_PER_FACE units = one face height (forehead to chin).
const SCENE_PER_FACE = 1.25;
const CANVAS_W = 560;
const CANVAS_H = 420;
const PX_PER_UNIT = 64;             // one face height = 80 px
const HEAD_CY = 138;                // canvas y of the face centre
const VIEW_BOTTOM_Y = -(CANVAS_H - HEAD_CY) / PX_PER_UNIT; // lowest scene y still on screen

const toCanvas = (x: number, y: number) => ({
  x: CANVAS_W / 2 + x * PX_PER_UNIT,
  y: HEAD_CY - y * PX_PER_UNIT,
});

// Webcam takes are filmed close up, so the hands (nearer the lens than the face)
// come out ~30% bigger in face units than the INCLUDE takes filmed from further
// back. Resize each hand about its wrist to one palm length (wrist to middle
// knuckle) so every sign shows the same hand size; the wrist path is unchanged.
// The same close-up perspective also pushes the hands further from the face, so a
// take whose palms measure longer than INCLUDE's (~0.8) is pulled in towards the
// face by that ratio first.
const PALM_LEN = 0.72;
const INCLUDE_PALM_LEN = 0.8;
function palmLen(h: number[][]) {
  const [a, b] = [h[0], h[9]];
  return Math.hypot(b[0] - a[0], b[1] - a[1], (b[2] || 0) - (a[2] || 0));
}
function median(xs: number[]) {
  const v = [...xs].sort((x, y) => x - y);
  return v[Math.floor(v.length / 2)];
}
function normalizeHandSize(data: AnimationData): number[][][][] {
  const all: number[] = [];
  data.frames.forEach((f, i) => [0, 1].forEach((s) => {
    if (f[s] && data.present[i]?.[s]) all.push(palmLen(f[s]));
  }));
  const kp = all.length >= 3 ? Math.max(0.7, Math.min(1, INCLUDE_PALM_LEN / median(all))) : 1;
  const frames = data.frames.map((f) => f.map((h) => h.map((p) => [p[0] * kp, p[1] * kp, (p[2] || 0) * kp])));
  for (let s = 0; s < 2; s++) {
    const lens: number[] = [];
    frames.forEach((f, i) => {
      if (f[s] && data.present[i]?.[s]) lens.push(palmLen(f[s]));
    });
    if (lens.length < 3) continue;
    const k = Math.min(1.4, Math.max(0.6, PALM_LEN / median(lens)));
    frames.forEach((f, i) => {
      const h = f[s];
      if (!h || !(data.present[i]?.[s])) return;
      const w = h[0];
      f[s] = h.map((p) => [w[0] + (p[0] - w[0]) * k, w[1] + (p[1] - w[1]) * k, (w[2] || 0) + ((p[2] || 0) - (w[2] || 0)) * k]);
    });
  }
  return frames;
}

export const SignVisualizer: React.FC<SignVisualizerProps> = ({ sign, className = '', compact = false }) => {
  const [activeView, setActiveView] = useState<'video' | '3d'>(
    compact ? '3d' : 'video'
  );
  const [animData, setAnimData] = useState<AnimationData | null>(null);
  const [isLoadingAnim, setIsLoadingAnim] = useState<boolean>(false);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(0.8);
  const [currentFrame, setCurrentFrame] = useState<number>(0);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(0);
  const frameIndexRef = useRef<number>(0);

  // When sign changes, load animation data and compute dynamic bounding box
  useEffect(() => {
    setActiveView(compact ? '3d' : 'video');
    setIsLoadingAnim(true);
    frameIndexRef.current = 0;
    setCurrentFrame(0);

    fetch(`/animations/${sign.id.toLowerCase()}.json`)
      .then((res) => {
        if (!res.ok) throw new Error('Not found');
        return res.json();
      })
      .then((loaded: AnimationData) => {
        let data = loaded;
        // The frames are already in face-anchored scene units (origin = middle of the
        // signer's face, SCENE_PER_FACE units = one face height; see text_to_sign/signer.py),
        // so every sign shares one scale and position. Only trim the dead frames at the
        // start and end where no hand is up in view yet.
        const inView = (f: number) =>
          [0, 1].some((s) => {
            const hand = data.frames[f]?.[s];
            const shown = data.present[f]?.[s] ?? hand?.some((p) => p[0] !== 0 || p[1] !== 0);
            return !!hand && shown && hand[0][1] > VIEW_BOTTOM_Y;
          });
        let first = 0;
        let last = data.frames.length - 1;
        while (first < last && !inView(first)) first++;
        while (last > first && !inView(last)) last--;
        first = Math.max(0, first - 3);
        last = Math.min(data.frames.length - 1, last + 3);
        data = {
          ...data,
          frames: data.frames.slice(first, last + 1),
          present: data.present.slice(first, last + 1),
        };
        data.frames = normalizeHandSize(data);

        setAnimData(data);
        setIsLoadingAnim(false);
      })
      .catch(() => {
        setAnimData(null);
        setIsLoadingAnim(false);
      });
  }, [sign.id, sign.hasGuideVideo, compact]);

  // 3D Skeleton Animation Loop with Auto-Normalization
  useEffect(() => {
    if (activeView !== '3d' || !animData || animData.frames.length === 0) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const totalFrames = animData.frames.length;
    const baseFps = animData.fps || 30;
    const frameInterval = 1000 / (baseFps * playbackSpeed);

    const render = (time: number) => {
      if (!lastTimeRef.current) lastTimeRef.current = time;
      const elapsed = time - lastTimeRef.current;

      if (isPlaying && elapsed >= frameInterval) {
        lastTimeRef.current = time;
        frameIndexRef.current = (frameIndexRef.current + 1) % totalFrames;
        setCurrentFrame(frameIndexRef.current);
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Deep dark modern gradient background
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
      grad.addColorStop(0, '#090d16');
      grad.addColorStop(1, '#111827');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Soft grid background
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.05)';
      ctx.lineWidth = 1;
      for (let x = 0; x < canvas.width; x += 28) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
      }
      for (let y = 0; y < canvas.height; y += 28) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvas.width, y); ctx.stroke();
      }

      // Body silhouette drawn in the same scene units as the hands, so hands land
      // where they really were relative to the signer's face and shoulders.
      const fh = SCENE_PER_FACE;
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.22)';
      ctx.fillStyle = 'rgba(51, 65, 85, 0.32)';
      ctx.lineWidth = 1.5;
      const head = toCanvas(0, 0.12 * fh);
      ctx.beginPath();
      ctx.ellipse(head.x, head.y, 0.4 * fh * PX_PER_UNIT, 0.66 * fh * PX_PER_UNIT, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      const P = (x: number, y: number) => toCanvas(x * fh, y * fh);
      const pts = {
        neckL: P(-0.2, -0.45), neckR: P(0.2, -0.45),
        trapL: P(-0.55, -0.85), trapR: P(0.55, -0.85),
        shL: P(-1.25, -1.1), shR: P(1.25, -1.1),
        armL: P(-1.45, -1.6), armR: P(1.45, -1.6),
        botL: P(-1.3, -5), botR: P(1.3, -5),
      };
      ctx.beginPath();
      ctx.moveTo(pts.neckL.x, pts.neckL.y);
      ctx.lineTo(pts.neckL.x, pts.trapL.y - 4);
      ctx.quadraticCurveTo(pts.trapL.x, pts.trapL.y, pts.shL.x, pts.shL.y);
      ctx.quadraticCurveTo(pts.armL.x, pts.armL.y - 10, pts.armL.x, pts.armL.y);
      ctx.lineTo(pts.botL.x, pts.botL.y);
      ctx.lineTo(pts.botR.x, pts.botR.y);
      ctx.lineTo(pts.armR.x, pts.armR.y);
      ctx.quadraticCurveTo(pts.armR.x, pts.armR.y - 10, pts.shR.x, pts.shR.y);
      ctx.quadraticCurveTo(pts.trapR.x, pts.trapR.y, pts.neckR.x, pts.trapR.y - 4);
      ctx.lineTo(pts.neckR.x, pts.neckR.y);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      ctx.font = 'bold 11px Plus Jakarta Sans, sans-serif';
      ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
      ctx.fillText('Mirror view', 14, 22);

      const frameData = animData.frames[frameIndexRef.current];

      // Slot 0 = signer's left hand, slot 1 = signer's right hand (shown on the
      // viewer's right, like a mirror)
      for (let s = 0; s < 2; s++) {
        const hand = frameData[s];
        if (!hand) continue;
        const isPresent = animData.present[frameIndexRef.current]?.[s] ?? hand.some((p) => p[0] !== 0 || p[1] !== 0 || p[2] !== 0);
        if (!isPresent) continue;

        const isRight = s === 1;
        const mainColor = isRight ? '#38bdf8' : '#818cf8';
        const palmFill = isRight ? 'rgba(14, 165, 233, 0.22)' : 'rgba(99, 102, 241, 0.22)';
        const glowColor = isRight ? '#0284c7' : '#4f46e5';

        // Project 3D landmarks into centered 2D canvas coordinates
        const pts2D = hand.map((p) => {
          // Perspective depth scaling based on z
          const zDepth = 1 / (1 + (p[2] || 0) * 0.15);
          const c = toCanvas(p[0], p[1]);
          return {
            x: c.x,
            y: c.y,
            z: p[2] || 0,
            scale: Math.max(0.6, Math.min(1.4, zDepth)),
          };
        });

        // 1. Draw Palm Polygon Mesh
        const palmIndices = [0, 5, 9, 13, 17, 0];
        ctx.beginPath();
        ctx.moveTo(pts2D[palmIndices[0]].x, pts2D[palmIndices[0]].y);
        for (let i = 1; i < palmIndices.length; i++) {
          ctx.lineTo(pts2D[palmIndices[i]].x, pts2D[palmIndices[i]].y);
        }
        ctx.closePath();
        ctx.fillStyle = palmFill;
        ctx.fill();
        ctx.strokeStyle = mainColor;
        ctx.lineWidth = 1.8;
        ctx.stroke();

        // 2. Draw Bones
        ctx.lineCap = 'round';
        ctx.shadowColor = glowColor;
        ctx.shadowBlur = 10;

        HAND_CONNECTIONS.forEach(([i, j]) => {
          const p1 = pts2D[i];
          const p2 = pts2D[j];
          if (p1 && p2) {
            ctx.beginPath();
            ctx.moveTo(p1.x, p1.y);
            ctx.lineTo(p2.x, p2.y);
            const boneThickness = Math.max(2, 4.2 * ((p1.scale + p2.scale) / 2));
            ctx.lineWidth = boneThickness;
            ctx.strokeStyle = mainColor;
            ctx.stroke();
          }
        });

        // 3. Draw Joints / Knuckles
        pts2D.forEach((pt, idx) => {
          const isTip = [4, 8, 12, 16, 20].includes(idx);
          const isWrist = idx === 0;
          const r = (isTip ? 5.5 : isWrist ? 6 : 3.5) * pt.scale;

          ctx.beginPath();
          ctx.arc(pt.x, pt.y, r, 0, Math.PI * 2);
          ctx.fillStyle = isTip ? '#ffffff' : mainColor;
          ctx.shadowColor = isTip ? '#ffffff' : glowColor;
          ctx.shadowBlur = isTip ? 14 : 5;
          ctx.fill();
          ctx.strokeStyle = '#0f172a';
          ctx.lineWidth = 1.2;
          ctx.stroke();
        });

        // Hand Label Badge
        const wrist = pts2D[0];
        if (wrist) {
          ctx.font = 'bold 11px Plus Jakarta Sans, sans-serif';
          ctx.fillStyle = isRight ? '#7dd3fc' : '#a5b4fc';
          ctx.shadowBlur = 0;
          ctx.fillText(isRight ? 'Right Hand' : 'Left Hand', wrist.x - 28, wrist.y + 20);
        }
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [activeView, animData, isPlaying, playbackSpeed]);

  const handleScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseInt(e.target.value, 10);
    frameIndexRef.current = val;
    setCurrentFrame(val);
  };

  return (
    <div className={`bg-white rounded-3xl border-2 border-slate-200/90 overflow-hidden shadow-xs flex flex-col ${className}`}>
      {/* Top View Selector Tabs */}
      {!compact && (
      <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 bg-slate-200/80 p-1 rounded-2xl">
          <button
              onClick={() => setActiveView('video')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold transition-all ${
                activeView === 'video'
                  ? 'bg-white text-sky-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Video className="w-3.5 h-3.5 text-sky-500" />
              Video Guide
              {!sign.hasGuideVideo && (
                <span className="text-[9px] font-black uppercase px-1 rounded bg-slate-300/70 text-slate-600">soon</span>
              )}
            </button>

          <button
            onClick={() => setActiveView('3d')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold transition-all ${
              activeView === '3d'
                ? 'bg-white text-indigo-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-indigo-500" />
            3D Landmark Signer
          </button>
        </div>

        {activeView === '3d' && animData && (
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold text-slate-500">Speed:</span>
            {[0.5, 0.8, 1.0].map((s) => (
              <button
                key={s}
                onClick={() => setPlaybackSpeed(s)}
                className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold transition-all ${
                  playbackSpeed === s
                    ? 'bg-sky-500 text-white shadow-xs'
                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-100'
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        )}
      </div>

      )}

      {/* Main Display Area */}
      <div className="relative aspect-4/3 max-h-[420px] bg-slate-950 flex items-center justify-center overflow-hidden">
        {/* Mode 1: Real MP4 Reference Video */}
        {activeView === 'video' && !sign.hasGuideVideo && (
          <div className="w-full h-full flex flex-col items-center justify-center text-center gap-3 p-6 bg-gradient-to-b from-slate-900 to-slate-950">
            <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center">
              <Video className="w-7 h-7 text-slate-500" />
            </div>
            <div>
              <p className="text-white font-black text-sm">Video not available yet</p>
              <p className="text-slate-400 text-xs mt-1 max-w-xs leading-relaxed">
                A signer video for "{sign.name}" will be added once we record it with professional ISL signers.
              </p>
            </div>
            <button
              onClick={() => setActiveView('3d')}
              className="mt-1 flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white text-xs font-black transition-colors"
            >
              <Layers className="w-3.5 h-3.5" />
              Watch it on the 3D signer
            </button>
          </div>
        )}

        {activeView === 'video' && sign.hasGuideVideo && (
          <div className="relative w-full h-full flex items-center justify-center bg-black">
            <video
              src={`/guides/${sign.id.toLowerCase()}.mp4`}
              autoPlay
              loop
              muted
              playsInline
              controls
              className="w-full h-full object-contain"
            />
            <div className="absolute top-3 left-3 pointer-events-none">
              <span className="bg-sky-500/90 text-white text-[10px] font-black uppercase tracking-wider px-2.5 py-1 rounded-full shadow-md backdrop-blur-xs flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                ISL signer · INCLUDE dataset
              </span>
            </div>
            <div className="absolute top-3.5 right-3 pointer-events-none">
              <span className="bg-black/60 text-slate-200 text-[9px] font-semibold px-2 py-0.5 rounded-md">
                AI4Bharat INCLUDE (Sridhar et al. 2020), CC BY 4.0
              </span>
            </div>
          </div>
        )}

        {/* Mode 2: 3D Landmark Signer */}
        {activeView === '3d' && (
          <div className="relative w-full h-full flex flex-col items-center justify-center">
            {isLoadingAnim ? (
              <div className="text-sky-300 text-xs font-semibold animate-pulse flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-sky-400 animate-ping" />
                Centering & scaling 3D sign landmarks...
              </div>
            ) : animData ? (
              <canvas
                ref={canvasRef}
                width={CANVAS_W}
                height={CANVAS_H}
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="p-6 text-center text-slate-400 text-xs">
                No 3D landmark sequence available for this sign.
              </div>
            )}

            {/* 3D Signer Floating Controls */}
            {animData && !compact && (
              <div className="absolute bottom-3 left-3 right-3 bg-slate-900/85 backdrop-blur-md rounded-2xl px-3 py-2 border border-slate-700/60 flex items-center gap-3">
                <button
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="w-8 h-8 rounded-xl bg-sky-500 hover:bg-sky-400 text-white flex items-center justify-center transition-all shadow-md shrink-0"
                >
                  {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white ml-0.5" />}
                </button>

                <div className="flex-1 flex flex-col gap-1">
                  <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>Frame {currentFrame + 1}/{animData.frames.length}</span>
                    <span className="text-sky-300 font-bold">{Math.round(((currentFrame + 1) / animData.frames.length) * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={animData.frames.length - 1}
                    value={currentFrame}
                    onChange={handleScrub}
                    className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-sky-400"
                  />
                </div>

                <button
                  onClick={() => {
                    frameIndexRef.current = 0;
                    setCurrentFrame(0);
                  }}
                  className="p-1.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
                  title="Rewind"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
