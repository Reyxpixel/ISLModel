// TypeScript port of ISLModel/web/preprocess.js
// Exactly matches the Python preprocessing pipeline so the ONNX model gets identical inputs.

export interface ModelConfig {
  labels: string[];
  with_position: boolean;
  seq_len: number;
  n_features: number;
  coord_scale: number;
  position_scale: number;
  palm: number[];
}

export interface RawFrame {
  hands: number[][][]; // [2][21][3]
  handsScreen: number[][][]; // [2][21][3]
  face: number[][] | null; // [478][3] or null
}

const HAND_POINTS = 21;
const PER_HAND = HAND_POINTS * 3 + 1; // 64
const SHAPE_FEATURES = 2 * PER_HAND; // 128
const POSITION_FEATURES = 5;

function isZero(points: number[][]): boolean {
  for (const p of points) if (p[0] !== 0 || p[1] !== 0 || p[2] !== 0) return false;
  return true;
}

function positionFeatures(
  frames: RawFrame[],
  present: boolean[][],
  cfg: ModelConfig,
): Float32Array[] {
  const n = frames.length;
  const out = Array.from({ length: n }, () => new Float32Array(POSITION_FEATURES));
  const hasFace = frames.map((f) => !!f.face && !isZero(f.face));
  const found: number[] = [];
  hasFace.forEach((h, i) => { if (h) found.push(i); });
  if (!found.length || frames.some((f) => !f.handsScreen)) return out;

  for (let t = 0; t < n; t++) {
    let best = found[0];
    for (const i of found) if (Math.abs(i - t) < Math.abs(best - t)) best = i;
    const face = frames[best].face!;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, sx = 0, sy = 0;
    for (const p of face) {
      const x = Math.fround(p[0]), y = Math.fround(p[1]);
      sx += x; sy += y;
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
    }
    const cx = sx / face.length, cy = sy / face.length;
    const w = Math.max(maxX - minX, 1e-3), h = Math.max(maxY - minY, 1e-3);
    for (let hand = 0; hand < 2; hand++) {
      if (!present[t][hand]) continue;
      let px = 0, py = 0;
      for (const k of cfg.palm) { px += frames[t].handsScreen[hand][k][0]; py += frames[t].handsScreen[hand][k][1]; }
      px /= cfg.palm.length; py /= cfg.palm.length;
      const clip = (v: number) => Math.min(5, Math.max(-5, v));
      out[t][2 * hand] = clip(((px - cx) / w) * cfg.position_scale);
      out[t][2 * hand + 1] = clip(((py - cy) / h) * cfg.position_scale);
    }
    out[t][4] = 1;
  }
  return out;
}

function roundHalfEven(v: number): number {
  const r = Math.round(v);
  return Math.abs(v % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

export function preprocess(frames: RawFrame[], cfg: ModelConfig): Float32Array {
  const nFeat = cfg.n_features;
  const present = frames.map((f) => [!isZero(f.hands[0]), !isZero(f.hands[1])]);

  let feats = frames.map((f, t) => {
    const row = new Float32Array(nFeat);
    for (let hand = 0; hand < 2; hand++) {
      const base = hand * PER_HAND;
      f.hands[hand].forEach((p, k) => {
        row[base + 3 * k] = p[0] * cfg.coord_scale;
        row[base + 3 * k + 1] = p[1] * cfg.coord_scale;
        row[base + 3 * k + 2] = p[2] * cfg.coord_scale;
      });
      row[base + 63] = present[t][hand] ? 1 : 0;
    }
    return row;
  });

  if (cfg.with_position) {
    const pos = positionFeatures(frames, present, cfg);
    feats.forEach((row, t) => row.set(pos[t], SHAPE_FEATURES));
  }

  // Trim to first..last hand-detected window
  const anyHand = present.map((p) => p[0] || p[1]);
  const first = anyHand.indexOf(true), last = anyHand.lastIndexOf(true);
  if (first >= 0) feats = feats.slice(first, last + 1);

  // Resample to seq_len frames
  const out = new Float32Array(cfg.seq_len * nFeat);
  if (feats.length === 0) return out;
  const step = cfg.seq_len > 1 ? (feats.length - 1) / (cfg.seq_len - 1) : 0;
  for (let i = 0; i < cfg.seq_len; i++) {
    const idx = i === cfg.seq_len - 1 ? feats.length - 1 : roundHalfEven(i * step);
    out.set(feats[idx], i * nFeat);
  }
  return out;
}

export function softmax(logits: ArrayLike<number>): number[] {
  const arr = Array.from(logits);
  const m = Math.max(...arr);
  const e = arr.map((v) => Math.exp(v - m));
  const s = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / s);
}

export interface Prediction {
  label: string;
  p: number;
}

export function topK(logits: ArrayLike<number>, labels: string[], k = 3): Prediction[] {
  return softmax(logits)
    .map((p, i) => ({ label: labels[i], p }))
    .sort((a, b) => b.p - a.p)
    .slice(0, k);
}

