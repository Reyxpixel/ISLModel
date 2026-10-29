"""Convert INCLUDE sign videos into hands.npy files in the same format as mpipe.py.

INCLUDE (AI4Bharat, CC BY 4.0): https://zenodo.org/records/4010759

Reads the INCLUDE category zips directly (the source folder is never written to) and saves
    <out>/<word>/seq_NNN/landmarks/hands.npy   # (frames, 2, 21, 3) float32
plus <out>/index.csv mapping every seq to its source video and official train/val/test split.

Extraction matches mpipe.py: same HandLandmarker settings, frame mirrored before detection,
world landmarks saved, same hand slots as mpipe.py (slot 0 = signer's left hand, see readme),
missing hand = zeros. Also saves hands_screen.npy and face_coords.npy (on-screen positions, as the
updated mpipe.py does), so the model can use where the hands are relative to the face.
Videos keep their native length and frame rate (INCLUDE is 25 FPS). Re-running skips videos
that are already converted, so new zips can be added later.

Usage:
    python include_to_landmarks.py --src <folder with INCLUDE zips> [--splits <split txt folder>]
"""
import argparse
import csv
import os
import re
import tempfile
import zipfile
from multiprocessing import Pool

import cv2
import numpy as np

HAND_MODEL_PATH = "hand_landmarker.task"
FACE_MODEL_PATH = "face_landmarker.task"
# INCLUDE signers stand far back, so the face is too small for MediaPipe in the full frame.
# Look for it in this part of the (mirrored) frame instead: top 45%, middle 40%.
FACE_CROP = (0.0, 0.45, 0.3, 0.7)   # y0, y1, x0, x1 as fractions of the frame

_options = None
_face_options = None


def slug(folder_name):
    # "52. Good afternoon" -> "good_afternoon", "46. you (plural)" -> "you_plural"
    name = re.sub(r"^\d+\.\s*", "", folder_name).lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def init_worker(model_path, face_model_path):
    global _options, _face_options
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    _options = vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.6,
        min_hand_presence_confidence=0.6,
        min_tracking_confidence=0.5)
    _face_options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=face_model_path),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5)


def extract_video(path):
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    # A fresh detector per video, so timestamps restart and no hand tracking carries over
    detector = vision.HandLandmarker.create_from_options(_options)
    face_detector = vision.FaceLandmarker.create_from_options(_face_options)
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frames, screens, faces, idx, last_ts = [], [], [], 0, -1
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)
            ts = max(int(idx * 1000 / fps), last_ts + 1)
            last_ts = ts
            res = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
            arr = np.zeros((2, 21, 3), dtype=np.float32)
            screen = np.zeros((2, 21, 3), dtype=np.float32)
            if res.hand_world_landmarks and res.handedness:
                for h in range(len(res.hand_world_landmarks)):
                    # Same slots as mpipe.py. The mirrored frame flips MediaPipe's label,
                    # so slot 0 ends up holding the signer's LEFT hand and slot 1 the right.
                    slot = 0 if res.handedness[h][0].category_name == "Right" else 1
                    arr[slot] = [[lm.x, lm.y, lm.z] for lm in res.hand_world_landmarks[h]]
                    screen[slot] = [[lm.x, lm.y, lm.z] for lm in res.hand_landmarks[h]]
            # Face points mapped back to full-frame 0-1 coordinates, same as mpipe.py's face_coords
            H, W = rgb.shape[:2]
            y0, y1, x0, x1 = (int(FACE_CROP[0] * H), int(FACE_CROP[1] * H), int(FACE_CROP[2] * W), int(FACE_CROP[3] * W))
            crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
            fres = face_detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=crop), ts)
            face = np.zeros((478, 3), dtype=np.float32)
            if fres.face_landmarks:
                face[:] = [[(x0 + lm.x * (x1 - x0)) / W, (y0 + lm.y * (y1 - y0)) / H, lm.z] for lm in fres.face_landmarks[0]]
            frames.append(arr)
            screens.append(screen)
            faces.append(face)
            idx += 1
    finally:
        cap.release()
        detector.close()
        face_detector.close()
    shape = lambda a, s: np.array(a, dtype=np.float32).reshape((-1,) + s)
    return shape(frames, (2, 21, 3)), shape(screens, (2, 21, 3)), shape(faces, (478, 3))


def process(job):
    zip_path, member, out_file = job
    lm_dir = os.path.dirname(out_file)
    if os.path.exists(out_file):    # hands.npy is written last, so it marks a finished take
        return
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        with zipfile.ZipFile(zip_path) as z:
            video = z.extract(member, tmp)
        hands, screen, face = extract_video(video)
    os.makedirs(lm_dir, exist_ok=True)
    np.save(os.path.join(lm_dir, "hands_screen.npy"), screen)
    np.save(os.path.join(lm_dir, "face_coords.npy"), face)
    tmp_out = out_file + ".tmp.npy"
    np.save(tmp_out, hands)
    os.replace(tmp_out, out_file)


def load_splits(splits_dir):
    split_of = {}
    for split in ("train", "val", "test"):
        p = os.path.join(splits_dir, f"include_{split}.txt") if splits_dir else ""
        if p and os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.strip():
                    # Split lists name some .MP4 videos as .MOV, so match without the extension
                    split_of[os.path.splitext(line.strip().replace("\\", "/"))[0].lower()] = split
    return split_of


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder containing the INCLUDE category zips")
    ap.add_argument("--splits", help="folder with include_train/val/test.txt")
    ap.add_argument("--out", default="dataset_include_landmarks")
    ap.add_argument("--model", default=HAND_MODEL_PATH)
    ap.add_argument("--face-model", default=FACE_MODEL_PATH)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, help="only convert the first N videos (for testing)")
    args = ap.parse_args()

    split_of = load_splits(args.splits)
    videos = []
    for name in sorted(os.listdir(args.src)):
        if name.endswith(".zip"):
            zp = os.path.join(args.src, name)
            with zipfile.ZipFile(zp) as z:
                videos += [(zp, m) for m in z.namelist() if m.lower().endswith((".mov", ".mp4"))]
    videos.sort(key=lambda v: v[1])

    rows, jobs, seq_count = [], [], {}
    for zp, member in videos:
        category, folder = member.split("/")[-3], member.split("/")[-2]
        word = slug(folder)
        seq_count[word] = seq_count.get(word, 0) + 1
        seq = f"seq_{seq_count[word]:03d}"
        rows.append({"word": word, "seq": seq, "category": category, "source": member,
                     "split": split_of.get(os.path.splitext(member)[0].lower(), ""), "zip": os.path.basename(zp)})
        jobs.append((zp, member, os.path.join(args.out, word, seq, "landmarks", "hands.npy")))
    if args.limit:
        jobs = jobs[:args.limit]

    print(f"{len(videos)} videos, {len(seq_count)} signs; converting {len(jobs)} with {args.workers} workers")
    os.makedirs(args.out, exist_ok=True)
    with Pool(args.workers, initializer=init_worker, initargs=(args.model, args.face_model)) as pool:
        for n, _ in enumerate(pool.imap_unordered(process, jobs), 1):
            if n % 20 == 0 or n == len(jobs):
                print(f"[{n}/{len(jobs)}] done", flush=True)

    for r in rows:
        f = os.path.join(args.out, r["word"], r["seq"], "landmarks", "hands.npy")
        if os.path.exists(f):
            a = np.load(f)
            r["frames"] = a.shape[0]
            r["frames_with_hand"] = int((~np.all(a == 0, axis=(1, 2, 3))).sum())
    with open(os.path.join(args.out, "index.csv"), "w", newline="", encoding="utf-8") as f:
        fields = ["word", "seq", "category", "split", "frames", "frames_with_hand", "source", "zip"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows([r for r in rows if "frames" in r])
    print("index written:", os.path.join(args.out, "index.csv"))


if __name__ == "__main__":
    main()
