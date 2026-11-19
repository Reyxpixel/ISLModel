"""Mudra Bubbles: an ISL practice game that also collects sign data.

Word bubbles float on the left, your camera is on the right. One bubble is the target.
Press space, get ready during the countdown, then sign the word. If the model recognises it,
the bubble pops. Every take is saved in the same format as ISLModel/mpipe.py, so playing the
game is data collection.

    python mudra_bubbles.py                      # asks for the player's name
    python mudra_bubbles.py --player manan
    python mudra_bubbles.py --practice           # pop on any clean take, model guess shown only
    python mudra_bubbles.py --words hello we you thank_you
    python mudra_bubbles.py --practice --words water food   # new words the model doesn't know yet
    python mudra_bubbles.py --note "evening, tube light"    # saved with every take

Keys: space = sign the target, h = show how to sign it again, n = skip this bubble,
      m = switch model/practice mode, r = new round, q = quit.

When a new word becomes the target, a short clip of how to sign it plays in the camera panel
(from guides/<word>.mp4, if it exists). Press space to start signing at any time.

Saved per take (in game_data/<word>/seq_NNN/):
    landmarks/hands.npy             (frames, 2, 21, 3)  hand shape, same as mpipe.py
    landmarks/hands_screen.npy      (frames, 2, 21, 3)  where the hands are in the frame
    landmarks/face_coords.npy       (frames, 478, 3)    face points (face tracking is always on)
    landmarks/face_blendshapes.npy  (frames, 52)
    video.mp4                       the camera frames before mirroring, like mpipe.py
    meta.json                       word, player, mode, what the model guessed, popped or not,
                                    note, average brightness of the take

Lives in ISLModel/mudra_bubbles (or next to the ISLModel folder): it uses the model, isl_model/ and the
.task files from there.
"""
import argparse
import json
import math
import os
import random
import shutil
import sys
import time

import cv2
import mediapipe as mp
import numpy as np
import torch
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = "Mudra Bubbles"
W, H = 1280, 720
GAME_W = 640                      # left half: bubbles; right half: camera
CAM_W, CAM_H = 640, 480
FPS = 30
COUNTDOWN = 2.0
ROUND_TARGETS = 10
RESULT_SECONDS = 2.2
MIN_HAND_FRAC = 0.3               # practice mode: a take counts if hands were seen this often

# Reliable signs from the default model, per ISLModel/readme.md and its test report
DEFAULT_WORDS = ["hello", "thank_you", "we", "how_are_you", "i", "you", "they", "she",
                 "good_morning", "good_night", "good_evening",
                 # the team's own words (how-to clips are Vansh's recordings)
                 "hammer", "handkerchief", "hen", "hole", "horse", "in", "individual", "introduction", "iron", "it"]
TEAM_CLIP_WORDS = {"hammer", "handkerchief", "hen", "hole", "horse", "in", "individual", "introduction", "iron"}

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (5, 6), (6, 7), (7, 8), (9, 10), (10, 11), (11, 12),
    (13, 14), (14, 15), (15, 16), (17, 18), (18, 19), (19, 20),
    (0, 5), (5, 9), (9, 13), (13, 17), (0, 17)]

# Colours are BGR
BG_TOP, BG_BOTTOM = (60, 34, 18), (110, 70, 28)
INK, MUTED = (245, 240, 235), (190, 175, 160)
GOLD, RED, GREEN = (60, 200, 255), (90, 90, 235), (120, 220, 120)
BUBBLE_COLOURS = [(200, 170, 60), (110, 130, 250), (80, 190, 240), (200, 120, 170),
                  (230, 200, 120), (150, 200, 90), (170, 140, 240), (120, 220, 220)]
FONT = cv2.FONT_HERSHEY_DUPLEX

# Bubble slots in the game area (centre x, centre y)
SLOTS = [(170, 225), (470, 225), (320, 370), (170, 515), (470, 515), (320, 645)]
RADIUS = 62


# ---------------------------------------------------------------- landmarks (same as mpipe.py)

class Tracker:
    """MediaPipe hand + face landmarkers with mpipe.py's settings."""

    def __init__(self, repo):
        self.hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=os.path.join(repo, "hand_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO, num_hands=2,
            min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5))
        self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=os.path.join(repo, "face_landmarker.task")),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            min_face_detection_confidence=0.5, min_tracking_confidence=0.5,
            output_face_blendshapes=True))
        self.hand_ts = 0
        self.face_ts = 0

    def detect_hands(self, rgb):
        """Returns (world (2,21,3), screen (2,21,3)), slots exactly as in mpipe.extract_landmarks."""
        world = np.zeros((2, 21, 3), np.float32)
        screen = np.zeros((2, 21, 3), np.float32)
        res = self.hands.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self.hand_ts)
        self.hand_ts += 1000 // FPS
        if res.hand_world_landmarks and res.handedness:
            for i in range(len(res.hand_world_landmarks)):
                h = 0 if res.handedness[i][0].category_name == "Right" else 1
                world[h] = [[lm.x, lm.y, lm.z] for lm in res.hand_world_landmarks[i]]
                screen[h] = [[lm.x, lm.y, lm.z] for lm in res.hand_landmarks[i]]
        return world, screen

    def detect_face(self, rgb):
        coords = np.zeros((478, 3), np.float32)
        blend = np.zeros((52,), np.float32)
        res = self.face.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), self.face_ts)
        self.face_ts += 1000 // FPS
        if res.face_landmarks:
            coords[:] = [[lm.x, lm.y, lm.z] for lm in res.face_landmarks[0]]
        if res.face_blendshapes:
            blend[:] = [b.score for b in res.face_blendshapes[0]]
        return coords, blend


# ---------------------------------------------------------------- recognition

class Recogniser:
    def __init__(self, model_path):
        from isl_model.model import SignBiLSTM
        from isl_model.preprocess import preprocess
        self.preprocess = preprocess
        ckpt = torch.load(model_path, map_location="cpu")
        self.labels = ckpt["labels"]
        self.with_position = ckpt.get("with_position", False)
        self.model = SignBiLSTM(ckpt["features"], len(self.labels))
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    def top3(self, hands, screens, faces):
        x = self.preprocess(hands, screens, faces, with_position=self.with_position)
        with torch.no_grad():
            probs = torch.softmax(self.model(torch.from_numpy(x)[None]), 1)[0]
        top = probs.topk(3)
        return [(self.labels[i], float(p)) for p, i in zip(top.values.tolist(), top.indices.tolist())]


# ---------------------------------------------------------------- how-to-sign clips

class Guides:
    """guides/<word>.mp4, shown mirrored (like the player's own camera view) and letterboxed."""

    def __init__(self, folder):
        self.folder = folder
        self.cache = {}

    def get(self, word):
        if word not in self.cache:
            self.cache[word] = self._load(os.path.join(self.folder, f"{word}.mp4"))
        return self.cache[word]

    @staticmethod
    def _load(path):
        if not os.path.exists(path):
            return None
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frames = []
        while len(frames) < 400:                         # ~15 s at most
            ok, f = cap.read()
            if not ok:
                break
            f = cv2.flip(f, 1)
            h, w = f.shape[:2]
            k = min(CAM_W / w, CAM_H / h)
            f = cv2.resize(f, (int(w * k), int(h * k)))
            canvas = np.full((CAM_H, CAM_W, 3), 25, np.uint8)
            y, x = (CAM_H - f.shape[0]) // 2, (CAM_W - f.shape[1]) // 2
            canvas[y:y + f.shape[0], x:x + f.shape[1]] = f
            frames.append(canvas)
        cap.release()
        return (frames, fps) if frames else None


# ---------------------------------------------------------------- saving takes

def next_seq(word_dir):
    nums = [int(n[4:]) for n in os.listdir(word_dir) if n.startswith("seq_") and n[4:].isdigit()]
    return max(nums, default=0) + 1


def save_take(data_dir, word, raw_frames, hands, screens, faces, blends, meta):
    word_dir = os.path.join(data_dir, word)
    os.makedirs(word_dir, exist_ok=True)
    tmp = os.path.join(word_dir, f"tmp_{int(time.time() * 1000)}")
    lm = os.path.join(tmp, "landmarks")
    os.makedirs(lm)
    np.save(os.path.join(lm, "hands.npy"), np.asarray(hands, np.float32))
    np.save(os.path.join(lm, "hands_screen.npy"), np.asarray(screens, np.float32))
    np.save(os.path.join(lm, "face_coords.npy"), np.asarray(faces, np.float32))
    np.save(os.path.join(lm, "face_blendshapes.npy"), np.asarray(blends, np.float32))
    fh, fw = raw_frames[0].shape[:2]
    vw = cv2.VideoWriter(os.path.join(tmp, "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (fw, fh))
    for f in raw_frames:
        vw.write(f)
    vw.release()
    final = os.path.join(word_dir, f"seq_{next_seq(word_dir):03d}")
    meta["take"] = os.path.relpath(final, data_dir)
    with open(os.path.join(tmp, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    for attempt in range(3):            # Windows can briefly lock the just-closed video file
        try:
            os.rename(tmp, final)
            break
        except PermissionError:
            time.sleep(0.3)
    else:
        shutil.move(tmp, final)
    return final


def clean_leftovers(data_dir):
    """Remove half-written takes from a run that was closed mid-save."""
    if not os.path.isdir(data_dir):
        return
    for word in os.listdir(data_dir):
        wd = os.path.join(data_dir, word)
        if os.path.isdir(wd):
            for n in os.listdir(wd):
                if n.startswith("tmp_"):
                    shutil.rmtree(os.path.join(wd, n), ignore_errors=True)


def count_word(data_dir, word):
    wd = os.path.join(data_dir, word)
    return sum(1 for s in os.listdir(wd) if s.startswith("seq_")) if os.path.isdir(wd) else 0


def count_takes(data_dir):
    if not os.path.isdir(data_dir):
        return 0
    return sum(1 for w in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, w))
               for s in os.listdir(os.path.join(data_dir, w)) if s.startswith("seq_"))


# ---------------------------------------------------------------- drawing

def pretty(word):
    return word.replace("_", " ")


def text(img, s, org, scale, colour=INK, thick=1, centre=False):
    if centre:
        (tw, th), _ = cv2.getTextSize(s, FONT, scale, thick)
        org = (int(org[0] - tw / 2), int(org[1] + th / 2))
    if thick > 1:                                       # drop shadow only on big text
        cv2.putText(img, s, (int(org[0]) + 2, int(org[1]) + 2), FONT, scale, (20, 15, 10), thick + 1, cv2.LINE_AA)
    cv2.putText(img, s, (int(org[0]), int(org[1])), FONT, scale, colour, thick, cv2.LINE_AA)


def fit_lines(word, max_w):
    """One or two centred lines that fit inside a bubble, and the font scale to use."""
    s = pretty(word)
    options = [[s]]
    if " " in s:
        parts = s.split(" ")
        best = min(range(1, len(parts)), key=lambda k: abs(len(" ".join(parts[:k])) - len(" ".join(parts[k:]))))
        options.append([" ".join(parts[:best]), " ".join(parts[best:])])
    for lines in options:
        for scale in (0.9, 0.8, 0.7):
            if all(cv2.getTextSize(l, FONT, scale, 2)[0][0] <= max_w for l in lines):
                return lines, scale
    lines = options[-1]
    widest = max(cv2.getTextSize(l, FONT, 1.0, 2)[0][0] for l in lines)
    return lines, max(0.45, max_w / widest)


def make_background():
    t = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array(BG_TOP) * (1 - t) + np.array(BG_BOTTOM) * t).astype(np.uint8)
    bg = np.repeat(bg, W, axis=1)
    rng = np.random.default_rng(3)                      # faint fixed specks, like water
    for _ in range(70):
        x, y, r = rng.integers(0, GAME_W), rng.integers(110, H), int(rng.integers(2, 6))
        cv2.circle(bg, (int(x), int(y)), r, (150, 120, 80), 1, cv2.LINE_AA)
    return bg


class Bubble:
    def __init__(self, slot, word, colour, now):
        self.slot, self.word, self.colour = slot, word, colour
        self.phase = random.uniform(0, 2 * math.pi)
        self.born = now                                 # grows in from nothing when created

    def centre(self, now):
        sx, sy = SLOTS[self.slot]
        y = sy + 7 * math.sin(now * 1.6 + self.phase)
        x = sx + 5 * math.sin(now * 0.9 + self.phase * 1.7)
        return int(x), int(y)

    def size(self, now):
        a = min(1.0, max(0.0, (now - self.born - 0.3) / 0.5))   # short gap after a pop, then grow
        return 1 - (1 - a) ** 3

    def draw(self, img, overlay, now, is_target):
        cx, cy = self.centre(now)
        r = int(RADIUS * self.size(now))
        if r < 4:
            return cx, cy
        if is_target:
            pulse = 0.5 + 0.5 * math.sin(now * 5)
            cv2.circle(img, (cx, cy), int(r + 10 + 4 * pulse), GOLD, 3, cv2.LINE_AA)
        cv2.circle(overlay, (cx, cy), r, self.colour, -1, cv2.LINE_AA)
        cv2.circle(overlay, (cx - r // 3, cy - r // 3), r // 4, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), r, tuple(min(255, c + 60) for c in self.colour), 2, cv2.LINE_AA)
        return cx, cy

    def draw_label(self, img, now):
        cx, cy = self.centre(now)
        if self.size(now) < 0.8:
            return
        lines, scale = fit_lines(self.word, RADIUS * 1.6)
        step = int(34 * scale)
        y = cy - (len(lines) - 1) * step / 2
        for l in lines:
            text(img, l, (cx, y), scale, INK, 2, centre=True)
            y += step


class Burst:
    def __init__(self, x, y, colour, now):
        self.x, self.y, self.colour, self.t0 = x, y, colour, now
        self.dots = [(random.uniform(0, 2 * math.pi), random.uniform(80, 220)) for _ in range(16)]

    def draw(self, img, now):
        a = (now - self.t0) / 0.6
        if a >= 1:
            return False
        cv2.circle(img, (self.x, self.y), int(RADIUS * (1 + a)), self.colour, max(1, int(6 * (1 - a))), cv2.LINE_AA)
        for ang, speed in self.dots:
            d = speed * a
            cv2.circle(img, (int(self.x + d * math.cos(ang)), int(self.y + d * math.sin(ang))),
                       max(1, int(7 * (1 - a))), self.colour, -1, cv2.LINE_AA)
        return True


def draw_hands(img, screen, x0, y0, w, h):
    for hand in range(2):
        pts = screen[hand]
        if not pts.any():
            continue
        for a, b in HAND_CONNECTIONS:
            p, q = pts[a], pts[b]
            cv2.line(img, (int(x0 + p[0] * w), int(y0 + p[1] * h)), (int(x0 + q[0] * w), int(y0 + q[1] * h)),
                     (120, 255, 120), 2, cv2.LINE_AA)
        for p in pts:
            cv2.circle(img, (int(x0 + p[0] * w), int(y0 + p[1] * h)), 3, (0, 230, 255), -1, cv2.LINE_AA)


# ---------------------------------------------------------------- game

class Game:
    def __init__(self, words, player, practice, data_dir, recogniser, model_name, seconds, now,
                 guides=None, note=""):
        self.words, self.player, self.practice = words, player, practice
        self.data_dir, self.rec, self.model_name = data_dir, recogniser, model_name
        self.unknown = {w for w in words if w not in recogniser.labels}   # new words: practice mode only
        self.guides, self.note = guides, note
        self.guide, self.guide_t0, self.guide_key = None, 0.0, None
        self.frames_per_take = int(seconds * FPS)
        self.seconds = seconds
        self.word_counts = {w: count_word(data_dir, w) for w in words}
        self.saved_total = count_takes(data_dir)
        self.saved_session = 0
        self.bg = make_background()
        self.new_round(now)

    def new_round(self, now):
        self.score, self.popped, self.done_targets, self.tries = 0, 0, 0, 0
        pool = self.words[:]
        random.shuffle(pool)
        n = min(len(SLOTS), len(pool))                  # one bubble per word, at most 6 on screen
        self.bubbles = [Bubble(i, pool[i], BUBBLE_COLOURS[i % len(BUBBLE_COLOURS)], now - 1) for i in range(n)]
        self.bursts = []
        self.target = random.randrange(len(self.bubbles))
        self.state, self.t0, self.result = "idle", now, None
        self.message = ("Press SPACE, then sign the glowing word", MUTED)

    def pick_target(self):
        choices = [i for i in range(len(self.bubbles)) if i != self.target] or [self.target]
        self.target = random.choice(choices)
        self.tries = 0

    def target_key(self):
        return (self.target, id(self.bubbles[self.target]), self.done_targets)

    def start_guide(self, now):
        """Play the how-to clip for the current target. Returns False if there isn't one."""
        self.guide_key = self.target_key()
        clip = self.guides.get(self.bubbles[self.target].word) if self.guides else None
        if not clip:
            return False
        self.guide, self.guide_t0, self.state = clip, now, "guide"
        return True

    def guide_frame(self, now):
        """Current clip frame, or None when it has played twice."""
        frames, fps = self.guide
        i = int((now - self.guide_t0) * fps)
        if i >= 2 * len(frames):
            return None
        return frames[i % len(frames)].copy()

    def replace_bubble(self, i, now):
        on_screen = {b.word for b in self.bubbles}
        fresh = [w for w in self.words if w not in on_screen] or [self.bubbles[i].word]
        old = self.bubbles[i]
        self.bubbles[i] = Bubble(old.slot, random.choice(fresh), old.colour, now)

    def advance(self, now):
        self.done_targets += 1
        if self.done_targets >= ROUND_TARGETS:
            self.state = "done"
        else:
            self.pick_target()

    def skip(self, now):
        if self.state in ("idle", "result", "guide"):
            self.message = (f"Skipped {pretty(self.bubbles[self.target].word)}", MUTED)
            self.replace_bubble(self.target, now)
            self.state = "idle"
            self.advance(now)

    # A finished take: recognise, decide pop or miss, save
    def finish_take(self, now, raw, hands, screens, faces, blends, fps):
        word = self.bubbles[self.target].word
        hands = np.asarray(hands, np.float32)
        hand_frac = float(np.mean(np.any(hands != 0, axis=(1, 2, 3))))
        if hand_frac == 0:
            self.message = ("No hands seen. Keep both hands in the camera and try again.", RED)
            self.state = "idle"
            return
        top = self.rec.top3(hands, screens, faces)
        guesses = [w for w, _ in top]
        if self.practice:
            popped, points = hand_frac >= MIN_HAND_FRAC, 50
        else:
            popped = word in guesses
            points = 100 if guesses[0] == word else 50
        self.tries += 1
        meta = {"word": word, "player": self.player, "mode": "practice" if self.practice else "model",
                "model": self.model_name, "top3": [{"word": w, "prob": round(p, 4)} for w, p in top],
                "popped": bool(popped), "try": self.tries, "frames": len(hands),
                "hand_frames_fraction": round(hand_frac, 3), "fps": round(fps, 1), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "note": self.note, "known_word": word not in self.unknown,
                "brightness": round(float(np.mean([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean() for f in raw[::5]])), 1)}
        try:
            path = save_take(self.data_dir, word, raw, hands, screens, faces, blends, meta)
            self.saved_session += 1
            self.saved_total += 1
            self.word_counts[word] = self.word_counts.get(word, 0) + 1
            print(f"[saved] {path}  guess={top[0][0]} ({top[0][1]:.0%})  popped={popped}")
        except Exception as e:                                   # never lose the game over a save error
            print(f"[ERROR] could not save take: {e}")
        self.result = top
        if popped:
            self.score += points
            self.popped += 1
            cx, cy = self.bubbles[self.target].centre(now)
            self.bursts.append(Burst(cx, cy, self.bubbles[self.target].colour, now))
            self.message = (f"POP! +{points}", GREEN)
            self.replace_bubble(self.target, now)
            self.advance(now)
        else:
            tip = "  (n = skip)" if self.tries >= 2 else ""
            self.message = (f"Not quite. Try {pretty(word)} again{tip}", GOLD)
        if self.state != "done":
            self.state, self.t0 = "result", now

    def draw(self, cam_view, now):
        img = self.bg.copy()
        # Header
        text(img, "Mudra Bubbles", (24, 48), 1.25, INK, 2)
        mode = "PRACTICE" if self.practice else "MODEL"
        text(img, f"Score {self.score}   Popped {self.popped}   Target {min(self.done_targets + 1, ROUND_TARGETS)}/{ROUND_TARGETS}",
             (26, 86), 0.62, MUTED, 1)
        text(img, mode, (GAME_W - 130, 48), 0.6, GOLD if self.practice else GREEN, 1)
        cv2.line(img, (20, 110), (GAME_W - 20, 110), (150, 120, 90), 1, cv2.LINE_AA)

        # Bubbles (translucent fill, then outlines and labels on top)
        overlay = img.copy()
        for i, b in enumerate(self.bubbles):
            b.draw(img, overlay, now, i == self.target and self.state != "done")
        img[:, :GAME_W] = cv2.addWeighted(overlay[:, :GAME_W], 0.55, img[:, :GAME_W], 0.45, 0)
        for i, b in enumerate(self.bubbles):
            if i == self.target and self.state != "done" and b.size(now) >= 1:
                cx, cy = b.centre(now)
                cv2.circle(img, (cx, cy), RADIUS, GOLD, 3, cv2.LINE_AA)
            b.draw_label(img, now)
        self.bursts = [bu for bu in self.bursts if bu.draw(img, now)]

        # Camera panel
        img[0:CAM_H, GAME_W:GAME_W + CAM_W] = cam_view
        cv2.rectangle(img, (GAME_W, 0), (W - 1, CAM_H), (150, 120, 90), 2)

        # Status panel under the camera
        x0, y0 = GAME_W + 24, CAM_H + 44
        target = pretty(self.bubbles[self.target].word).upper()
        if self.state == "done":
            text(img, "Round over!", (x0, y0), 1.1, GOLD, 2)
            text(img, f"Score {self.score}, popped {self.popped} of {ROUND_TARGETS}", (x0, y0 + 46), 0.75)
            text(img, f"Takes saved this session: {self.saved_session}", (x0, y0 + 84), 0.65, MUTED)
            text(img, "r = play again   q = quit", (x0, y0 + 122), 0.65, MUTED)
        else:
            text(img, f"Sign:  {target}", (x0, y0), 1.0, INK, 2)
            n_saved = self.word_counts.get(self.bubbles[self.target].word, 0)
            text(img, f"{n_saved} saved", (W - 120, y0), 0.5, MUTED, 1)
            msg, colour = self.message
            text(img, msg, (x0, y0 + 44), 0.62, colour, 1)
            if self.result and self.state == "result" and self.bubbles[self.target].word not in self.unknown:
                guess = ",  ".join(f"{pretty(w)} {p:.0%}" for w, p in self.result)
                text(img, f"Model heard: {guess}", (x0, y0 + 80), 0.55, MUTED, 1)
            text(img, "space sign   h how-to   n skip   m mode   r restart   q quit", (x0, H - 46), 0.5, MUTED, 1)
            text(img, f"{self.player}  |  takes saved: {self.saved_total} total, {self.saved_session} now",
                 (x0, H - 18), 0.5, MUTED, 1)
        return img


def camera_overlay(view, state, left, frames_done, frames_total, screen, hands_seen):
    h, w = view.shape[:2]
    if screen is not None:
        draw_hands(view, screen, 0, 0, w, h)
    if state == "countdown":
        n = max(1, math.ceil(left))
        text(view, str(n), (w // 2, h // 2), 4.0, GOLD, 6, centre=True)
        text(view, "get your hands ready", (w // 2, h // 2 + 80), 0.8, INK, 2, centre=True)
    elif state == "recording":
        cv2.circle(view, (30, 30), 12, (0, 0, 255), -1, cv2.LINE_AA)
        text(view, "SIGN NOW", (52, 40), 0.8, (80, 80, 255), 2)
        cv2.rectangle(view, (20, h - 30), (w - 20, h - 16), (50, 50, 50), -1)
        cv2.rectangle(view, (20, h - 30), (20 + int((w - 40) * frames_done / frames_total), h - 16), GREEN, -1)
    elif state in ("idle", "result"):
        colour = GREEN if hands_seen else (150, 150, 150)
        text(view, "hands: in view" if hands_seen else "hands: not seen", (16, h - 18), 0.6, colour, 1)
    return view


class Camera:
    """Webcam like mpipe.py, or a video file (looped) for testing without a camera."""

    def __init__(self, index, video):
        self.video = video
        if video:
            self.cap = cv2.VideoCapture(video)
        else:
            self.cap = cv2.VideoCapture(index, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(index)
            self.cap.set(cv2.CAP_PROP_FPS, FPS)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)

    def read(self):
        ok, frame = self.cap.read()
        if not ok and self.video:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        return ok, frame


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--player", help="player name, saved with every take")
    ap.add_argument("--words", nargs="+", help="words to play; new words the model doesn't know need --practice")
    ap.add_argument("--note", default="", help="saved with every take, e.g. the lighting or room")
    ap.add_argument("--guides", default=os.path.join(HERE, "guides"), help="folder of how-to clips (<word>.mp4)")
    ap.add_argument("--no-guide", action="store_true", help="don't play the how-to clip automatically")
    ap.add_argument("--practice", action="store_true", help="pop on any clean take")
    # Inside the ISLModel repo (ISLModel/mudra_bubbles) or next to it (ISLModel and mudra_bubbles side by side)
    default_repo = os.path.join(HERE, "..")
    if not os.path.exists(os.path.join(default_repo, "isl_model")):
        default_repo = os.path.join(HERE, "..", "ISLModel")
    ap.add_argument("--repo", default=default_repo, help="path to the ISLModel folder")
    ap.add_argument("--model", help="model file (default: ISLModel/models/include_position.pt)")
    ap.add_argument("--data", default=os.path.join(HERE, "game_data"), help="where takes are saved")
    ap.add_argument("--seconds", type=float, default=2.5, help="length of each take")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--video", help=argparse.SUPPRESS)          # testing: use a video file as the camera
    ap.add_argument("--autoplay", action="store_true", help=argparse.SUPPRESS)  # testing: press space by itself
    ap.add_argument("--snap", help=argparse.SUPPRESS)           # testing: save screenshots to this folder
    ap.add_argument("--max-frames", type=int, default=0, help=argparse.SUPPRESS)
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo, "isl_model")):
        sys.exit(f"Can't find the ISLModel folder at {repo}. Pass --repo <path to ISLModel>.")
    sys.path.insert(0, repo)
    model_path = args.model or os.path.join(repo, "models", "include_position.pt")
    rec = Recogniser(model_path)

    words = args.words or [w for w in DEFAULT_WORDS if w in rec.labels]
    words = [w if w in rec.labels else w.strip().lower().replace(" ", "_") for w in words]
    words = [w for w in dict.fromkeys(words) if w]                 # drop duplicates, keep order
    if any(c in w for w in words for c in '\\/:*?"<>|.'):
        sys.exit("Words can only contain letters, numbers, spaces, _ and -")
    unknown = [w for w in words if w not in rec.labels]
    if unknown and not args.practice:
        sys.exit(f"The model doesn't know: {', '.join(unknown)}\n"
                 f"Add --practice to record them anyway (that's how new words get collected).\n"
                 f"It knows: {', '.join(rec.labels)}")
    if unknown:
        print(f"New words (practice mode only, no model guess): {', '.join(unknown)}")

    player = args.player
    if not player:
        player = input("Player name (press Enter for 'player'): ").strip() or "player"
    player = "".join(c for c in player if c.isalnum() or c in " -_").strip() or "player"

    os.makedirs(args.data, exist_ok=True)
    clean_leftovers(args.data)
    tracker = Tracker(repo)
    cam = Camera(args.camera, args.video)
    game = Game(words, player, args.practice, args.data, rec, os.path.basename(model_path), args.seconds,
                time.time() if not args.video else 0.0, guides=Guides(args.guides), note=args.note.strip())
    print(f"Mudra Bubbles: {len(words)} words, {'practice' if args.practice else 'model'} mode, saving to {args.data}")

    raw, hands, screens, faces, blends = [], [], [], [], []
    frame_no, last_screen, rec_start = 0, None, 0.0
    if args.snap:
        os.makedirs(args.snap, exist_ok=True)

    while True:
        ok, frame = cam.read()
        if not ok:
            print("Camera not giving frames. Is another app using it?")
            break
        frame_no += 1
        now = time.time() if not args.video else frame_no / FPS   # video: game time follows the frames
        if frame.shape[1] != CAM_W or frame.shape[0] != CAM_H:
            frame = cv2.resize(frame, (CAM_W, CAM_H))
        mirrored = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
        world, screen = tracker.detect_hands(rgb)
        last_screen = screen

        if game.state == "countdown" and now - game.t0 >= COUNTDOWN:
            game.state = "recording"
            raw, hands, screens, faces, blends = [], [], [], [], []
            rec_start = time.time()
        if game.state == "recording":
            fc, fb = tracker.detect_face(rgb)
            raw.append(frame)
            hands.append(world)
            screens.append(screen)
            faces.append(fc)
            blends.append(fb)
            # End the take after game.seconds of time, not a fixed frame count: in a dim room the
            # webcam drops to ~10 FPS, which made frame-count takes last ~7.5 s.
            rec_elapsed = now - (game.t0 + COUNTDOWN)
            if rec_elapsed >= game.seconds and len(hands) >= 2:
                game.finish_take(now, raw, hands, screens, faces, blends,
                                 len(hands) / max(time.time() - rec_start, 1e-3))
        if game.state == "result" and now - game.t0 >= RESULT_SECONDS:
            game.state = "idle"
        if game.state == "idle" and not args.no_guide and game.guide_key != game.target_key():
            game.start_guide(now)                       # new target: show how to sign it once

        view = None
        if game.state == "guide":
            view = game.guide_frame(now)
            if view is None:
                game.state = "idle"
            else:
                word = pretty(game.bubbles[game.target].word).upper()
                cv2.rectangle(view, (0, 0), (CAM_W, 44), (25, 25, 25), -1)
                text(view, f"HOW TO SIGN:  {word}", (16, 31), 0.8, GOLD, 2)
                credit = "team recording" if game.bubbles[game.target].word in TEAM_CLIP_WORDS else "INCLUDE (CC BY 4.0)"
                text(view, f"space: start signing    h: replay    clip: {credit}", (16, CAM_H - 14), 0.5, INK, 1)
        if view is None:
            view = camera_overlay(mirrored.copy(), game.state, COUNTDOWN - (now - game.t0),
                                  min(game.frames_per_take, int((now - game.t0 - COUNTDOWN) * FPS)),
                                  game.frames_per_take, last_screen, bool(world.any()))
        img = game.draw(view, now)

        if args.snap and frame_no % 15 == 0:
            cv2.imwrite(os.path.join(args.snap, f"frame_{frame_no:05d}.jpg"), img)
        if args.video:
            key = -1
            if args.autoplay and game.state == "idle":
                key = ord(" ")
            if args.max_frames and frame_no >= args.max_frames:
                break
        else:
            cv2.imshow(WINDOW, img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break

        if key == ord(" ") and game.state in ("idle", "result", "guide"):
            game.state, game.t0 = "countdown", now
            game.message = (f"Get ready to sign {pretty(game.bubbles[game.target].word)}", INK)
        elif key == ord("h") and game.state in ("idle", "result", "guide"):
            if not game.start_guide(now):
                game.message = (f"No how-to clip for {pretty(game.bubbles[game.target].word)}", MUTED)
        elif key == ord("n"):
            game.skip(now)
        elif key == ord("m") and game.state in ("idle", "result", "done", "guide"):
            if game.practice and game.unknown:
                game.message = (f"Model mode needs words the model knows ({pretty(sorted(game.unknown)[0])} is new)", RED)
            else:
                game.practice = not game.practice
                game.message = (f"{'Practice' if game.practice else 'Model'} mode", MUTED)
        elif key == ord("r"):
            game.new_round(now)
        elif key == ord("q"):
            break

    cam.cap.release()
    cv2.destroyAllWindows()
    print(f"Saved {game.saved_session} takes this session in {args.data}")


if __name__ == "__main__":
    main()
