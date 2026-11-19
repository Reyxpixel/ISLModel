// Turn one recorded take into the model's input, in the browser.
// A line-by-line port of isl_model/preprocess.py: the model only works if the browser builds
// exactly the same numbers as training did. test_preprocess.py checks the two match.
//
// frames: one entry per camera frame of the take, each
//   {
//     hands:       [2][21][3]   hand shape: MediaPipe worldLandmarks (metres), x/y/z
//     handsScreen: [2][21][3]   hand position: MediaPipe landmarks (0-1 of the frame), x/y/z
//     face:        [478][3] or null   MediaPipe face landmarks (0-1 of the frame), x/y/z
//   }
//   Slot 0 is the hand MediaPipe labels "Right", slot 1 "Left", and the frame must be mirrored
//   (flipped left-right) BEFORE detection, as in mpipe.py. A hand that wasn't found is all zeros.
// config: web/model/config.json
// Returns a Float32Array of seq_len * n_features, ready for onnxruntime-web:
//   new ort.Tensor("float32", x, [1, config.seq_len, config.n_features])

const HAND_POINTS = 21;
const PER_HAND = HAND_POINTS * 3 + 1;           // 63 coordinates + "hand present" flag
const SHAPE_FEATURES = 2 * PER_HAND;            // 128
const POSITION_FEATURES = 5;

function isZero(points) {
  for (const p of points) if (p[0] !== 0 || p[1] !== 0 || p[2] !== 0) return false;
  return true;
}

function positionFeatures(frames, present, cfg) {
  const n = frames.length;
  const out = Array.from({ length: n }, () => new Float32Array(POSITION_FEATURES));
  const hasFace = frames.map((f) => !!f.face && !isZero(f.face));
  const found = [];
  hasFace.forEach((h, i) => { if (h) found.push(i); });
  if (!found.length || frames.some((f) => !f.handsScreen)) return out;

  for (let t = 0; t < n; t++) {
    // Frames where the face was missed borrow the nearest frame where it was found (earlier wins a tie)
    let best = found[0];
    for (const i of found) if (Math.abs(i - t) < Math.abs(best - t)) best = i;
    const face = frames[best].face;
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
      const clip = (v) => Math.min(5, Math.max(-5, v));
      out[t][2 * hand] = clip(((px - cx) / w) * cfg.position_scale);
      out[t][2 * hand + 1] = clip(((py - cy) / h) * cfg.position_scale);
    }
    out[t][4] = 1;
  }
  return out;
}

// numpy rounds halves to even; match it so the chosen frames are identical
function roundHalfEven(v) {
  const r = Math.round(v);
  return Math.abs(v % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

export function preprocess(frames, cfg) {
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

  // Drop the frames before the first and after the last detected hand (getting into position)
  const anyHand = present.map((p) => p[0] || p[1]);
  const first = anyHand.indexOf(true), last = anyHand.lastIndexOf(true);
  if (first >= 0) feats = feats.slice(first, last + 1);

  // Resample to seq_len frames (nearest frame, like np.round(np.linspace(...)))
  const out = new Float32Array(cfg.seq_len * nFeat);
  const step = cfg.seq_len > 1 ? (feats.length - 1) / (cfg.seq_len - 1) : 0;
  for (let i = 0; i < cfg.seq_len; i++) {
    const idx = i === cfg.seq_len - 1 ? feats.length - 1 : roundHalfEven(i * step);
    out.set(feats[idx], i * nFeat);
  }
  return out;
}

export function softmax(logits) {
  const m = Math.max(...logits);
  const e = Array.from(logits, (v) => Math.exp(v - m));
  const s = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / s);
}

// The top k guesses as [{label, p}], best first
export function topK(logits, labels, k = 3) {
  return softmax(logits)
    .map((p, i) => ({ label: labels[i], p }))
    .sort((a, b) => b.p - a.p)
    .slice(0, k);
}
