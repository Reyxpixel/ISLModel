import React, { useEffect, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Video, Layers, Sparkles } from 'lucide-react';
import { ISLSign } from '../types/isl';
import { HAND_CONNECTIONS } from '../services/vision';

interface SignVisualizerProps {
  sign: ISLSign;
  className?: string;
}

interface AnimationData {
  sign: string;
  fps: number;
  present: boolean[][];
  frames: number[][][][]; // [N][2][21][3]
}

export const SignVisualizer: React.FC<SignVisualizerProps> = ({ sign, className = '' }) => {
  const [activeView, setActiveView] = useState<'video' | '3d'>(
    sign.hasGuideVideo ? 'video' : '3d'
  );
  const [animData, setAnimData] = useState<AnimationData | null>(null);
  const [isLoadingAnim, setIsLoadingAnim] = useState<boolean>(false);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(0.8);
  const [currentFrame, setCurrentFrame] = useState<number>(0);

  // Bounding box for normalized projection
  const bboxRef = useRef<{ cx: number; cy: number; scale: number }>({ cx: 0, cy: 0, scale: 1 });

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const lastTimeRef = useRef<number>(0);
  const frameIndexRef = useRef<number>(0);

  // When sign changes, load animation data and compute dynamic bounding box
  useEffect(() => {
    setActiveView(sign.hasGuideVideo ? 'video' : '3d');
    setIsLoadingAnim(true);
    frameIndexRef.current = 0;
    setCurrentFrame(0);

    fetch(`/animations/${sign.id.toLowerCase()}.json`)
      .then((res) => {
        if (!res.ok) throw new Error('Not found');
        return res.json();
      })
      .then((data: AnimationData) => {
        // Calculate dynamic bounding box of all non-zero hand points across the entire sign
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;
        let hasPoints = false;

        data.frames.forEach((frame) => {
          for (let s = 0; s < 2; s++) {
            const hand = frame[s];
            if (!hand) continue;
            hand.forEach((p) => {
              if (p[0] !== 0 || p[1] !== 0 || p[2] !== 0) {
                hasPoints = true;
                if (p[0] < minX) minX = p[0];
                if (p[0] > maxX) maxX = p[0];
                if (p[1] < minY) minY = p[1];
                if (p[1] > maxY) maxY = p[1];
              }
            });
          }
        });

        if (hasPoints) {
          const cx = (minX + maxX) / 2;
          const cy = (minY + maxY) / 2;
          const span = Math.max(maxX - minX, maxY - minY, 0.4);
          bboxRef.current = { cx, cy, scale: span };
        } else {
          bboxRef.current = { cx: 0, cy: 0, scale: 1 };
        }

        setAnimData(data);
        setIsLoadingAnim(false);
      })
      .catch(() => {
        setAnimData(null);
        setIsLoadingAnim(false);
      });
  }, [sign.id, sign.hasGuideVideo]);

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

      // Draw subtle human anatomical silhouette contour in the background
      ctx.save();
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.12)';
      ctx.fillStyle = 'rgba(30, 41, 59, 0.25)';
      ctx.lineWidth = 1.5;
      const headCenterX = canvas.width / 2;
      const headCenterY = canvas.height * 0.28;
      // Head
      ctx.beginPath();
      ctx.ellipse(headCenterX, headCenterY, 38, 48, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      // Shoulders / Chest
      ctx.beginPath();
      ctx.moveTo(headCenterX - 35, headCenterY + 45);
      ctx.quadraticCurveTo(headCenterX - 80, headCenterY + 65, headCenterX - 140, headCenterY + 120);
      ctx.lineTo(headCenterX - 150, canvas.height);
      ctx.lineTo(headCenterX + 150, canvas.height);
      ctx.lineTo(headCenterX + 140, headCenterY + 120);
      ctx.quadraticCurveTo(headCenterX + 80, headCenterY + 65, headCenterX + 35, headCenterY + 45);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();

      // Viewport normalization calculations
      const padding = 45;
      const { cx, cy, scale: span } = bboxRef.current;
      const availableW = canvas.width - 2 * padding;
      const availableH = canvas.height - 2 * padding;
      const fitScale = Math.min(availableW, availableH) / Math.max(span, 0.1);

      const frameData = animData.frames[frameIndexRef.current];

      // Render Hands [0: Right, 1: Left]
      for (let s = 0; s < 2; s++) {
        const hand = frameData[s];
        if (!hand) continue;
        const isPresent = animData.present[frameIndexRef.current]?.[s] ?? hand.some((p) => p[0] !== 0 || p[1] !== 0 || p[2] !== 0);
        if (!isPresent) continue;

        const isRight = s === 0;
        const mainColor = isRight ? '#38bdf8' : '#818cf8';
        const palmFill = isRight ? 'rgba(14, 165, 233, 0.22)' : 'rgba(99, 102, 241, 0.22)';
        const glowColor = isRight ? '#0284c7' : '#4f46e5';

        // Project 3D landmarks into centered 2D canvas coordinates
        const pts2D = hand.map((p) => {
          // Perspective depth scaling based on z
          const zDepth = 1 / (1 + (p[2] || 0) * 0.15);
          const xScreen = canvas.width / 2 + (p[0] - cx) * fitScale;
          // In signs.npz: +y is up; in Canvas: +y is down, so we subtract
          const yScreen = canvas.height / 2 - (p[1] - cy) * fitScale;

          return {
            x: xScreen,
            y: yScreen,
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
      <div className="bg-slate-50 px-4 py-2.5 border-b border-slate-200 flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 bg-slate-200/80 p-1 rounded-2xl">
          {sign.hasGuideVideo && (
            <button
              onClick={() => setActiveView('video')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold transition-all ${
                activeView === 'video'
                  ? 'bg-white text-sky-700 shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Video className="w-3.5 h-3.5 text-sky-500" />
              Native Video Guide
            </button>
          )}

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

      {/* Main Display Area */}
      <div className="relative aspect-4/3 max-h-[420px] bg-slate-950 flex items-center justify-center overflow-hidden">
        {/* Mode 1: Real MP4 Reference Video */}
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
                Authentic ISL Native Guide
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
                width={560}
                height={420}
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="p-6 text-center text-slate-400 text-xs">
                No 3D landmark sequence available for this sign.
              </div>
            )}

            {/* 3D Signer Floating Controls */}
            {animData && (
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
