"""Sign data and playback for the on-screen signer (no OpenGL here, so it can be tested alone).

Scene units: the signer's face is the origin and SCALE units = one face height (forehead to chin),
y up. Every sign keeps where it was made relative to the face, so all signs share one body and
one size, instead of each word being stretched to fill the window.

Our recordings (hands_screen.npy + face_coords.npy, and hands.npy for real finger depth) are
turned into scene units by build_signs.py and saved in signs.npz. Every hand is 3D: x and y come
from the picture, depth from MediaPipe's metric 3D hand scaled to the same size. Kunal's words.data
and alphabets.data have no face and no depth, so those are placed with a default framing and their
depth is worked out from how short each finger bone looks (lift_2d).
"""
import os
import time

import numpy as np

from hand_renderer import load_letters, load_words, smooth_track, correct_hand_pose, PoseState

HERE = os.path.dirname(os.path.abspath(__file__))

SCALE = 1.25                # scene units per face height (keeps hands about the size Kunal's shader expects)
SHOULDER_Y, SHOULDER_X = -1.0, 1.0      # in face heights, measured on the reference videos
UPPER_ARM, FOREARM = 1.6, 1.45
REST_WRIST = (1.2, -3.75)   # hands at rest hang below the view
PALM_TO_FACE = 0.68         # wrist->middle-knuckle length / face height (reference videos)
WORLD_M_PER_FACE = 0.135    # metres per face height (palm ~0.092 m / 0.68)
FACE_TOP, FACE_CHIN, CHEEK_L, CHEEK_R = 10, 152, 234, 454
PALM_IDS = [0, 5, 9, 13, 17]
CHAINS = [[0, 1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16], [17, 18, 19, 20]]
# bone lengths / palm length (wrist to middle knuckle), measured on MediaPipe's 3D hands
BONE_LEN = {(0, 1): .403, (1, 2): .315, (2, 3): .349, (3, 4): .295, (5, 6): .257, (6, 7): .249, (7, 8): .267,
            (9, 10): .314, (10, 11): .29, (11, 12): .304, (13, 14): .287, (14, 15): .268, (15, 16): .267,
            (17, 18): .212, (18, 19): .229, (19, 20): .185}
PALM_LEN = [(0, 5, 1.024), (0, 9, 1.0), (0, 13, 0.987), (0, 17, 0.882), (5, 17, 0.643)]
VIEW_CENTER_Y, VIEW_HALF_H = -1.05 * SCALE, 2.2 * SCALE
CHEST_Y = -1.9 * SCALE      # about chest height


def shoulder(side):
    """side -1 = signer's left (slot 0), +1 = right (slot 1), unmirrored scene units."""
    return np.array([side * SHOULDER_X * SCALE, SHOULDER_Y * SCALE], np.float32)


def rest_wrist(side):
    return np.array([side * REST_WRIST[0] * SCALE, REST_WRIST[1] * SCALE], np.float32)


# ------------------------------------------------------------------------------ building signs
def estimate_aspect(screen, world):
    """Video width/height from how screen and metric hand coordinates scale (4:3 or 16:9)."""
    ratios = []
    for f in range(0, len(screen), max(1, len(screen) // 40)):
        for h in range(2):
            s, w = screen[f, h], world[f, h]
            if not s.any() or not w.any():
                continue
            sx = np.polyfit(w[:, 0], s[:, 0], 1)[0]
            sy = np.polyfit(w[:, 1], s[:, 1], 1)[0]
            if abs(sx) > 1e-6:
                ratios.append(sy / sx)
    if not ratios:
        return 4 / 3
    r = float(np.median(ratios))
    return 16 / 9 if abs(r - 16 / 9) < abs(r - 4 / 3) else 4 / 3


def _interp_missing(values, ok):
    """Fill rows where ok is False by linear interpolation (edges hold the nearest value)."""
    if ok.all() or not ok.any():
        return values
    idx = np.arange(len(values))
    out = values.copy()
    flat = values.reshape(len(values), -1)
    for c in range(flat.shape[1]):
        out.reshape(len(values), -1)[:, c] = np.interp(idx, idx[ok], flat[ok, c])
    return out


def world_to_screen_scale(screen, world, present, aspect):
    """Per hand: picture units (image heights) per metre, fitted between the 2D and 3D hands."""
    k = []
    for h in range(2):
        ks = []
        for f in np.where(present[:, h] & np.any(world[:, h] != 0, axis=(1, 2)))[0]:
            s = screen[f, h, :, :2] * [aspect, 1]
            w = world[f, h, :, :2]
            s, w = s - s.mean(0), w - w.mean(0)
            den = float((w * w).sum())
            if den > 1e-9:
                ks.append(float((s * w).sum()) / den)
        k.append(float(np.median(ks)) if ks else np.nan)
    return np.array(k, np.float32)


def lift_2d(frames, present):
    """Give flat 2D hands depth: a finger bone that looks shorter than it really is must be
    pointing towards the viewer, by sqrt(length^2 - seen^2). The palm stays flat (z = 0)."""
    out = frames.copy()
    out[..., 2] = 0
    for h in range(2):
        ok = np.where(present[:, h])[0]
        if not len(ok):
            continue
        xy = frames[ok, h, :, :2]
        seen = [np.linalg.norm(xy[:, b] - xy[:, a], axis=1) / ref for a, b, ref in PALM_LEN]
        palm = float(np.percentile(np.max(seen, axis=0), 90))
        for chain in CHAINS:
            for a, b in zip(chain[:-1], chain[1:]):
                d = np.linalg.norm(xy[:, b] - xy[:, a], axis=1)
                dz = np.sqrt(np.maximum((BONE_LEN[(a, b)] * palm) ** 2 - d ** 2, 0))
                out[ok, h, b, 2] = out[ok, h, a, 2] + dz
    return out


def fix_bone_lengths(frames, present):
    """Keep each finger bone one length for the whole sign (MediaPipe's lengths wobble by ~10%),
    keeping the direction of every bone."""
    out = frames.copy()
    for h in range(2):
        ok = present[:, h]
        if ok.sum() < 2:
            continue
        for chain in CHAINS:
            for a, b in zip(chain[:-1], chain[1:]):
                seg = frames[ok, h, b] - frames[ok, h, a]
                n = np.linalg.norm(seg, axis=1, keepdims=True)
                length = float(np.median(n))
                out[ok, h, b] = out[ok, h, a] + seg / np.maximum(n, 1e-6) * length
    return out


def take_to_scene(lm_dir, aspect=None, fps=30.0):
    """One recorded take -> dict(frames (F, 2, 21, 3) scene units, present (F, 2), has_z, fps)."""
    screen = np.load(os.path.join(lm_dir, "hands_screen.npy")).astype(np.float32)
    world_path = os.path.join(lm_dir, "hands.npy")
    world = np.load(world_path).astype(np.float32) if os.path.exists(world_path) else None
    face_path = os.path.join(lm_dir, "face_coords.npy")
    face = np.load(face_path).astype(np.float32) if os.path.exists(face_path) else None
    present = np.any(screen != 0, axis=(2, 3))
    if aspect is None:
        aspect = estimate_aspect(screen, world) if world is not None else 4 / 3

    face_ok = np.any(face != 0, axis=(1, 2)) if face is not None else np.zeros(len(screen), bool)
    if face_ok.sum() >= 3:
        top, chin = face[:, FACE_TOP, :2], face[:, FACE_CHIN, :2]
        mid_x = (face[:, CHEEK_L, 0] + face[:, CHEEK_R, 0]) / 2
        center = np.stack([mid_x, (top[:, 1] + chin[:, 1]) / 2], 1)
        center = _interp_missing(center, face_ok)
        center = smooth_track(center[:, None, :], 3.0)[:, 0]
        face_h = float(np.median(np.linalg.norm((top - chin)[face_ok] * [aspect, 1], axis=1)))
    else:   # no face: size from the hand, default framing (face high and centred)
        pal = [np.linalg.norm((screen[f, h, 9, :2] - screen[f, h, 0, :2]) * [aspect, 1])
               for f in range(len(screen)) for h in range(2) if present[f, h]]
        face_h = float(np.percentile(pal, 90)) / PALM_TO_FACE if pal else 0.25
        center = np.tile([0.5, 0.22], (len(screen), 1)).astype(np.float32)

    frames = np.zeros(screen.shape, np.float32)
    frames[..., 0] = (screen[..., 0] - center[:, None, None, 0]) * aspect / face_h * SCALE
    frames[..., 1] = -(screen[..., 1] - center[:, None, None, 1]) / face_h * SCALE
    if world is not None:
        # depth from the metric 3D hand, scaled so it matches the hand's size in the picture
        k = world_to_screen_scale(screen, world, present, aspect)
        k = np.where(np.isfinite(k), k, face_h / WORLD_M_PER_FACE)
        z = world[..., 2] - world[:, :, PALM_IDS, 2].mean(-1, keepdims=True)
        frames[..., 2] = -z * k[None, :, None] / face_h * SCALE
        return dict(frames=frames, present=present, has_z=True, fps=float(fps))
    return dict(frames=lift_2d(frames, present), present=present, has_z=True, fps=float(fps))


def words_data_to_scene(seq2d):
    """Kunal's 2D frames (F, 21|42, 2) in image coordinates -> scene dict (default framing)."""
    F, P, _ = seq2d.shape
    screen = np.zeros((F, 2, 21, 3), np.float32)
    hands = [seq2d[:, :21]] + ([seq2d[:, 21:42]] if P >= 42 else [])
    if len(hands) == 2 and hands[0][..., 0].mean() > hands[1][..., 0].mean():
        hands = hands[::-1]                       # slot 0 = the hand on the left
    if len(hands) == 1:
        slot = 0 if hands[0][..., 0].mean() < 0.45 else 1
        screen[:, slot, :, :2] = hands[0]
    else:
        screen[:, 0, :, :2], screen[:, 1, :, :2] = hands
    present = np.any(screen != 0, axis=(2, 3))
    aspect = 4 / 3
    pal = [np.linalg.norm((screen[f, h, 9, :2] - screen[f, h, 0, :2]) * [aspect, 1])
           for f in range(F) for h in range(2) if present[f, h]]
    face_h = float(np.percentile(pal, 90)) / PALM_TO_FACE if pal else 0.25
    frames = np.zeros_like(screen)
    frames[..., 0] = (screen[..., 0] - 0.5) * aspect / face_h * SCALE
    frames[..., 1] = -(screen[..., 1] - 0.22) / face_h * SCALE
    return dict(frames=lift_2d(frames, present), present=present, has_z=True, fps=30.0)


def active_span(wrist):
    """wrist: highest wrist per frame (-inf = no hand). Returns (first, last) frame of the signing,
    without the arm coming up from below the chest at the start and dropping below it at the end.
    Movement above the chest is never cut (MORNING, EVENING etc. move up or down as part of the
    sign), and at most 30% of the take is cut at each end."""
    low = VIEW_CENTER_Y - VIEW_HALF_H
    y = np.maximum(np.where(np.isfinite(wrist), wrist, low - 1.0), low - 1.0)
    seen = np.where(y > low)[0]
    if len(seen) < 4:
        return 0, len(y) - 1
    a, b = int(seen[0]), int(seen[-1])
    cap = int(0.3 * (b - a + 1))
    v = np.gradient(y)
    a0, b0 = a, b
    while a < a0 + cap and y[a] < CHEST_Y and v[a] > 0:      # rising, still below the chest
        a += 1
    while b > b0 - cap and y[b] < CHEST_Y and v[b] < 0:      # dropping, already below the chest
        b -= 1
    return a, b


def prepare(sign, sigma=1.2, max_gap=10, pad=0):
    """Fill short gaps, park missing hands at rest, smooth, and trim to the active part."""
    frames, present = sign["frames"].copy(), sign["present"].copy()
    F = len(frames)
    for h in range(2):
        ok = present[:, h]
        side = -1 if h == 0 else 1
        if not ok.any():           # this hand never shows: keep it at rest the whole time
            frames[:, h] = rest_hand(side)
            continue
        idx = np.where(ok)[0]
        # short gaps between detections: interpolate
        for a, b in zip(idx[:-1], idx[1:]):
            if 1 < b - a <= max_gap:
                t = (np.arange(a + 1, b) - a) / (b - a)
                frames[a + 1:b, h] = frames[a, h] + (frames[b, h] - frames[a, h]) * t[:, None, None]
                ok[a + 1:b] = True
        # the rest: hand hanging at the side, out of view
        frames[~ok, h] = rest_hand(side)
        present[:, h] = ok
    if sigma > 0:
        frames = smooth_track(frames.reshape(F, 42, 3), sigma).reshape(F, 2, 21, 3)
    frames = fix_bone_lengths(frames, present)
    # trim off the arm rising at the start and falling at the end of each take, which made the
    # signer drop its hands between words; the player blends from one sign straight to the next
    a, b = active_span(np.where(present, frames[:, :, 0, 1], -np.inf).max(1))
    a, b = max(0, a - pad), min(F, b + pad + 1)
    frames, present = frames[a:b], present[a:b]
    return dict(sign, frames=frames.astype(np.float32), present=present)


def rest_hand(side):
    """A relaxed hand hanging at the signer's side, fingers down, below the picture."""
    return default_hand() * [side, -1, 1] + np.append(rest_wrist(side), 0)


def default_hand():
    """An open right-ish hand in scene units (wrist at 0, fingers up)."""
    pts = np.array([[0, 0], [-.18, .12], [-.3, .27], [-.38, .4], [-.45, .5], [-.12, .5], [-.14, .72],
                    [-.15, .86], [-.16, .98], [0, .52], [0, .76], [0, .91], [0, 1.04], [.11, .49],
                    [.13, .7], [.14, .84], [.15, .95], [.2, .43], [.25, .59], [.28, .7], [.3, .8]], np.float32)
    out = np.zeros((21, 3), np.float32)
    out[:, :2] = pts * PALM_TO_FACE / 0.52 * SCALE
    return out


# ------------------------------------------------------------------------------ the library
class SignLibrary:
    """Words from signs.npz (ours, with face + depth) and Kunal's words.data (2D), plus letters."""

    def __init__(self, signs_path=os.path.join(HERE, "signs.npz"),
                 words_path=os.path.join(HERE, "words_kunal_original.data"),
                 letters_path=os.path.join(HERE, "alphabets.data"), sigma=1.2):
        self.raw = {}
        if not os.path.exists(words_path):
            words_path = os.path.join(HERE, "words.data")
        if os.path.exists(words_path):
            for w, seq in load_words(words_path).items():
                if w not in ("TEMP", "NGA"):                      # Kunal's test entries
                    self.raw[w] = words_data_to_scene(seq)
        if os.path.exists(signs_path):                           # ours win where both exist
            data = np.load(signs_path, allow_pickle=False)
            for w in [k[:-7] for k in data.files if k.endswith("_frames")]:
                self.raw[w] = dict(frames=data[w + "_frames"].astype(np.float32),
                                   present=data[w + "_present"], has_z=True, fps=float(data[w + "_fps"]))
        self.letters = load_letters(letters_path) if os.path.exists(letters_path) else {}
        self.set_smoothing(sigma)

    def set_smoothing(self, sigma):
        self.sigma = sigma
        self.signs = {w: prepare(s, sigma) for w, s in self.raw.items()}
        self.signs = {w: s for w, s in self.signs.items() if len(s["frames"]) >= 2}

    @property
    def vocabulary(self):
        return set(self.signs)

    def letter_pose(self, letter):
        """A fingerspelled letter: Kunal's static shape, held in front of the chest. Letters missing
        from alphabets.data (H, S, W, Y) show an open hand there, and the caption names the letter."""
        if letter not in self.letters:
            pose = np.stack([rest_hand(-1), default_hand()])
            pose[1, :, :2] += [0.25 * SCALE, -(1.45 + PALM_TO_FACE) * SCALE]
            return pose
        pts = self.letters[letter]
        hands = [pts[:21]] + ([pts[21:42]] if len(pts) >= 42 else [])
        pal = max(np.linalg.norm(h[9] - h[0]) for h in hands)
        s = PALM_TO_FACE * SCALE / max(pal, 1e-6)
        allp = np.concatenate(hands)
        c = (allp.min(0) + allp.max(0)) / 2
        pose = np.zeros((2, 21, 3), np.float32)
        out = [np.c_[(h - c) * [s, -s] + [0.25 * SCALE, -1.45 * SCALE], np.zeros(21)] for h in hands]
        out = [lift_2d(np.stack([o, o])[None], np.array([[True, False]]))[0, 0] for o in out]
        if len(out) == 2:
            out.sort(key=lambda h: h[:, 0].mean())
            pose[0], pose[1] = out
        else:
            pose[1] = out[0]
            pose[0] = rest_hand(-1)
        return pose

    def plan(self, gloss, fingerspell=True):
        """Gloss -> list of sign names / letters (multi-word signs joined, I -> I_SIGN, else spelled)."""
        toks, items, i = gloss.split(), [], 0
        while i < len(toks):
            for n in (3, 2):
                joined = "_".join(toks[i:i + n]).upper()
                if i + n <= len(toks) and joined in self.signs:
                    items.append(joined)
                    i += n
                    break
            else:
                tok = toks[i]
                i += 1
                if tok.startswith("[") and tok.endswith("]"):
                    items += [c.upper() for c in tok[1:-1] if c.isalpha()]
                    continue
                up = tok.upper()
                if len(up) == 1 and f"{up}_SIGN" in self.signs:
                    items.append(f"{up}_SIGN")
                elif up in self.signs:
                    items.append(up)
                elif fingerspell and up.isalpha():
                    items += list(up)
        return items


# ------------------------------------------------------------------------------ playback
def _ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _below(hand):
    """True when the whole hand is under the bottom of the picture."""
    return hand[:, 1].max() < VIEW_CENTER_Y - VIEW_HALF_H


def _lowered(shape, rest):
    """The same hand shape moved down out of the picture, under the resting hand. Blending to
    and from this instead of the fingers-down resting hand keeps the hand from shrinking and
    folding through itself while it comes up or goes down."""
    out = shape - shape[0] + rest[0]
    top = VIEW_CENTER_Y - VIEW_HALF_H - 0.1
    if out[:, 1].max() > top:
        out[:, 1] -= out[:, 1].max() - top
    return out


class SignerPlayer:
    """Plays a queue of signs and letters. pose_at() gives both hands (2, 21, 3) at any moment,
    with smooth transitions between signs and back to rest at the end."""

    def __init__(self, library, speed=1.0, letter_seconds=0.8, blend_seconds=0.25, rest_seconds=0.45):
        self.lib = library
        self.speed, self.letter_seconds = speed, letter_seconds
        self.blend_seconds, self.rest_seconds = blend_seconds, rest_seconds
        self.rest = np.stack([rest_hand(-1), rest_hand(1)])
        self.pose = self.rest.copy()
        self.queue, self.segment, self.seg_start = [], None, 0.0
        self.from_pose, self.states = None, [PoseState(), PoseState()]
        self.on_item = None

    def play(self, items):
        self.queue.extend(items)

    def clear(self):
        self.queue.clear()
        self.segment = None

    def busy(self):
        return self.segment is not None or bool(self.queue)

    def _start_next(self, now):
        from_rest = self.segment is None       # first sign after a pause: rise a little slower
        self.segment = None
        while self.queue:
            name = self.queue.pop(0)
            if len(name) == 1 and name.isalpha():
                self.segment = dict(name=name, letter=self.lib.letter_pose(name),
                                    dur=self.letter_seconds, has_z=True)
            elif name in self.lib.signs:
                s = self.lib.signs[name]
                self.segment = dict(name=name, frames=s["frames"], has_z=s["has_z"],
                                    dur=max(len(s["frames"]) - 1, 14) / (s["fps"] * self.speed))
            if self.segment:
                self.segment["blend"] = 0.45 if from_rest else self.blend_seconds
                self.from_pose, self.seg_start = self.pose.copy(), now
                first = self.segment["letter"] if "letter" in self.segment else self.segment["frames"][0]
                for h in range(2):          # a hand coming up from rest rises in its first shape
                    if _below(self.from_pose[h]) and not _below(first[h]):
                        self.from_pose[h] = _lowered(first[h], self.rest[h])
                self.states = [PoseState(), PoseState()]
                if self.on_item:
                    self.on_item(name)
                return
        # nothing left: glide back to rest
        self.from_pose, self.seg_start = self.pose.copy(), now

    def pose_at(self, now=None):
        """Returns (pose (2, 21, 3), has_z, name or None)."""
        now = time.monotonic() if now is None else now
        if self.segment is None and self.queue:
            self._start_next(now)
        seg = self.segment
        if seg is None:
            if self.from_pose is not None:
                w = _ease((now - self.seg_start) / self.rest_seconds)
                dest = np.stack([self.rest[h] if _below(self.from_pose[h]) else
                                 _lowered(self.from_pose[h], self.rest[h]) for h in range(2)])
                self.pose = self.from_pose + (dest - self.from_pose) * w
                if w >= 1:
                    self.pose = self.rest.copy()
                    self.from_pose = None
            return self.pose, False, None
        t = now - self.seg_start
        if t > seg["dur"]:
            self._start_next(now)
            return self.pose_at(now)
        if "letter" in seg:
            target = seg["letter"]
        else:
            frames = seg["frames"]
            pos = t / seg["dur"] * (len(frames) - 1) if seg["dur"] > 0 else 0
            i = min(int(pos), len(frames) - 2)
            target = frames[i] + (frames[i + 1] - frames[i]) * (pos - i)
        blend = seg.get("blend", self.blend_seconds)
        w = _ease(t / blend) if blend > 0 else 1.0
        if w < 1:
            target = target.copy()
            for h in range(2):          # a hand this sign doesn't use goes down in its last shape
                if _below(target[h]) and not _below(self.from_pose[h]):
                    target[h] = _lowered(self.from_pose[h], self.rest[h])
        pose = self.from_pose + (target - self.from_pose) * w if w < 1 else target.copy()
        if not seg["has_z"]:            # Kunal's 2D data: his FABRIK bone smoothing
            for h in range(2):
                pose[h, :, :2] = correct_hand_pose(pose[h, :, :2], self.states[h])
        self.pose = pose
        return pose, seg["has_z"], seg["name"]
