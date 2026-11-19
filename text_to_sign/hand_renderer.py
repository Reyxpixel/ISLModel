"""Kunal's 3D hand renderer, ported to Python so it can sit inside one app window.

The look comes from Kunal's own GLSL shader, read straight out of renderer.cpp, and the CPU
steps (per-word scaling, FABRIK bone smoothing, finger thickness and depth) follow renderer.cpp
line by line. What is new:

* Smoothing: every word's landmark track is cleaned before playback (a 3-frame median removes
  one-frame glitches, then a small Gaussian blur removes MediaPipe's frame-to-frame shake).
  The raw data shakes about as much as the sign itself moves for some words.
* Real-time speed by default (renderer.cpp plays at half speed), adjustable.
* The picture keeps its aspect ratio (renderer.cpp stretches it 4:3).
* A short blend between consecutive words instead of a jump (in signer.py).

Used by signer.py / signer_view.py / isl_app.py.
"""
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- constants from renderer.cpp -------------------------------------------------------------
LIGHT_DIRECTION = (0.35, 0.55, 0.75)
AMBIENT, DIFFUSE, SPECULAR = 0.40, 0.65, 0.025
FINGER_THICKNESS, THUMB_THICKNESS = 0.65, 0.60
PALM_HALF_DEPTH, PALM_DEPTH_OFFSET = 0.028, 0.012
# Proportions relative to the hand's own size L (see palm_dims), so a curled finger or a fist reads
# as a real hand instead of thin tubes on a flat card. renderer.cpp's fixed values made fingers about
# half as thick as real ones and the palm about 3% of its length thick (a real palm is about 25%).
FINGER_RADIUS_RATIO, THUMB_RADIUS_RATIO = 0.085, 0.085   # radius at the knuckle / L
PALM_HALF_DEPTH_RATIO = 0.06   # half the palm's thickness / L. Thicker shows ridges between Kunal's palm capsules
PALM_FRONT_Z = PALM_HALF_DEPTH - PALM_DEPTH_OFFSET
FINGER_PALM_CLEARANCE = 0.008
GLOBAL_SCALE = 1.8
VIEW_HALF = 3.0          # renderer.cpp: glOrtho(-3, 3, -3, 3)
FINGER_CHAINS = [[0, 1, 2, 3, 4], [0, 5, 6, 7, 8], [0, 9, 10, 11, 12],
                 [0, 13, 14, 15, 16], [0, 17, 18, 19, 20]]
PALM_OUTLINE = [0, 2, 5, 9, 13, 17]


def read_shaders(cpp_path=os.path.join(HERE, "renderer.cpp")):
    """Kunal's vertex and fragment shaders, exactly as written in renderer.cpp."""
    src = open(cpp_path, encoding="utf-8", errors="replace").read()
    vert = re.search(r'hand_vertex_shader\s*=\s*R"GLSL\((.*?)\)GLSL"', src, re.S).group(1)
    frag = re.search(r'hand_fragment_shader\s*=\s*R"GLSL\((.*?)\)GLSL"', src, re.S).group(1)
    return vert, frag


# ---- data files ------------------------------------------------------------------------------
def load_words(path):
    """words.data -> {WORD: (frames, points, 2) array}, parsed like renderer.cpp's load_words."""
    words, frames_of, current, frame = {}, {}, None, -1
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "//" in line:
                m = re.search(r"Frame\s*(\d+)", line.split("//", 1)[1])
                if m:
                    frame = int(m.group(1))
                line = line.split("//", 1)[0]
            toks = re.split(r"[\s{},]+", line)
            nums = []
            for tok in toks:
                if not tok:
                    continue
                if tok[0].isalpha():
                    if tok not in ("std", "vector") and "SEQ" not in tok:
                        current, frame = tok.upper(), -1
                        frames_of[current] = {}
                    continue
                try:
                    nums.append(float(tok))
                except ValueError:
                    pass
            if current and frame >= 0 and nums:
                frames_of[current].setdefault(frame, []).extend(nums)
    for word, fr in frames_of.items():
        if not fr:
            continue
        seq = [fr[i] for i in sorted(fr)]
        n = min(len(s) for s in seq) // 2
        n = 42 if n >= 42 else 21 if n >= 21 else 0
        if n:
            words[word] = np.array([s[:2 * n] for s in seq], np.float32).reshape(len(seq), n, 2)
    return words


def load_letters(path):
    """alphabets.data -> {LETTER: (points, 2)} like renderer.cpp's load_alphabets."""
    letters, current = {}, None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("//", 1)[0]
            for tok in re.split(r"[\s{},]+", line):
                if not tok:
                    continue
                if tok[0].isalpha() and len(tok) == 1:
                    current = tok.upper()
                    letters.setdefault(current, [])
                elif current:
                    try:
                        letters[current].append(float(tok))
                    except ValueError:
                        pass
    out = {}
    for k, v in letters.items():
        n = len(v) // 2
        n = 42 if n >= 42 else 21 if n >= 21 else 0
        if n:
            out[k] = np.array(v[:2 * n], np.float32).reshape(n, 2)
    return out


# ---- smoothing -------------------------------------------------------------------------------
def smooth_track(track, sigma=1.2):
    """track: (frames, points, 2). Median of 3 frames, then a Gaussian blur over time."""
    if len(track) < 3:
        return track
    padded = np.concatenate([track[:1], track, track[-1:]])
    med = np.median(np.stack([padded[:-2], padded[1:-1], padded[2:]]), axis=0)
    if sigma <= 0:
        return med.astype(np.float32)
    r = max(1, int(round(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    padded = np.concatenate([np.repeat(med[:1], r, 0), med, np.repeat(med[-1:], r, 0)])
    out = np.zeros_like(med)
    for i, w in enumerate(k):
        out += w * padded[i:i + len(med)]
    return out.astype(np.float32)


# ---- per-frame hand geometry (renderer.cpp: correct_hand_pose, draw_hand_surface) -------------
def _norm(v, fallback):
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.asarray(fallback, np.float32)


class PoseState:
    def __init__(self):
        self.lengths = None


def correct_hand_pose(raw, state):
    """FABRIK per finger with slowly smoothed bone lengths (renderer.cpp correct_hand_pose)."""
    out = raw.copy()
    observed = np.array([[np.linalg.norm(raw[c[s + 1]] - raw[c[s]]) for s in range(4)] for c in FINGER_CHAINS])
    if state.lengths is None:
        state.lengths = observed
    else:
        state.lengths = 0.92 * state.lengths + 0.08 * observed
    for f, chain in enumerate(FINGER_CHAINS):
        L = state.lengths[f]
        p = [raw[j].copy() for j in chain]
        root, target, total = p[0].copy(), p[4].copy(), L.sum()
        if np.linalg.norm(target - root) >= total:
            d = _norm(target - root, (1, 0))
            for s in range(4):
                p[s + 1] = p[s] + d * L[s]
        else:
            for _ in range(5):
                p[4] = target
                for s in range(3, -1, -1):
                    d = _norm(p[s] - p[s + 1], _norm(raw[chain[s]] - raw[chain[s + 1]], (1, 0)))
                    p[s] = p[s + 1] + d * L[s]
                p[0] = root
                for s in range(4):
                    d = _norm(p[s + 1] - p[s], _norm(raw[chain[s + 1]] - raw[chain[s]], (1, 0)))
                    p[s + 1] = p[s] + d * L[s]
        for j in range(1, 5):
            out[chain[j]] = p[j]
    return out


def _smooth_profile(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _palm_distance(joint, p):
    d2, inside = 1e6, False
    for e in range(6):
        a, b = joint[PALM_OUTLINE[e]], joint[PALM_OUTLINE[(e + 1) % 6]]
        ab = b - a
        t = min(1.0, max(0.0, float(np.dot(p - a, ab)) / max(float(np.dot(ab, ab)), 1e-6)))
        delta = p - (a + ab * t)
        d2 = min(d2, float(np.dot(delta, delta)))
        if (a[1] > p[1]) != (b[1] > p[1]):
            cx = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < cx:
                inside = not inside
    d = math.sqrt(d2)
    return -d if inside else d


def hand_size(joint):
    """L: the hand's size in scene units, wrist to middle knuckle, robust to the hand turning
    side-on (then the knuckle row shrinks but the wrist-knuckle line usually doesn't, and back)."""
    joint = np.asarray(joint, np.float32)[:, :2]
    return max(float(np.linalg.norm(joint[9] - joint[0])), 1.25 * float(np.linalg.norm(joint[5] - joint[17])), 1e-3)


def palm_dims(joint):
    """(palm half depth, palm depth offset) for this hand, in proportion to its size."""
    half = float(np.clip(PALM_HALF_DEPTH_RATIO * hand_size(joint), PALM_HALF_DEPTH, 0.12))
    return half, half * (PALM_DEPTH_OFFSET / PALM_HALF_DEPTH)


def joint_uniforms(joint, real_z=None, z_gain=1.0):
    """(21, 2) joints -> (21, 4) x, y, z, radius (renderer.cpp draw_hand_surface).

    Without real_z the finger depth is synthesized exactly as renderer.cpp does. With real_z
    (MediaPipe's measured depth, palm at 0, larger = nearer the viewer) that depth is used, and
    only joints over the palm are pushed clear of it, on whichever side they already are.
    Finger thickness and palm depth follow the hand's size (FINGER_RADIUS_RATIO, palm_dims)."""
    joint = np.asarray(joint, np.float32)[:, :2]
    data = np.zeros((21, 4), np.float32)
    data[:, :2] = joint
    along = np.zeros(21, np.float32)
    size = hand_size(joint)
    palm_half, palm_offset = palm_dims(joint)
    palm_front = palm_half - palm_offset
    for f, chain in enumerate(FINGER_CHAINS):
        first = 0 if f == 0 else 1
        seg = np.zeros(4)
        cum = np.zeros(5)
        for s in range(first, 4):
            seg[s] = np.linalg.norm(joint[chain[s + 1]] - joint[chain[s]])
            cum[s + 1] = cum[s] + seg[s]
        total = seg.sum()
        base = max(0.020, size * (THUMB_RADIUS_RATIO if f == 0 else FINGER_RADIUS_RATIO))
        for j in range(first, 5):
            a = cum[j] / total if total > 1e-6 else 0.0
            data[chain[j], 3] = base * (1 - 0.22 * _smooth_profile(a))   # fingertips a bit slimmer
            along[chain[j]] = a
    for f, chain in enumerate(FINGER_CHAINS):
        for j in range(1, 5):
            idx = chain[j]
            radius = data[idx, 3]
            req = palm_front + radius + FINGER_PALM_CLEARANCE
            ramp = req * _smooth_profile(along[idx])
            gate = 0.0 if j == 1 else (0.7 if j == 2 else 1.0)
            dist = _palm_distance(joint, joint[idx])
            overlap = 1.0 if dist <= 0 else 1.0 - _smooth_profile(dist / (radius + 0.06))
            if real_z is None:
                data[idx, 2] = max(ramp, overlap * gate * req)
            else:
                z = float(np.clip(real_z[idx] * z_gain, -0.9, 0.9))
                if z >= -0.01:
                    z = max(z, overlap * gate * req)
                else:
                    behind = palm_half + palm_offset + radius + FINGER_PALM_CLEARANCE
                    z = min(z, -overlap * gate * behind)
                data[idx, 2] = z
    return data
