"""Re-extract landmarks from the videos mpipe.py saves (SAVE_VIDEO = True), into a new folder.

    python reextract.py dataset_landmarks_only --out dataset_reextracted

Use this when the landmark extraction changes (new settings, new features) so the team doesn't
have to record again. Each <word>/seq_NNN/video.mp4 becomes <out>/<word>/seq_NNN/landmarks/ with
hands.npy, hands_screen.npy, face_coords.npy and face_blendshapes.npy, extracted the same way as
mpipe.py with face tracking on. Takes without a video are skipped. The input folder isn't changed.
"""
import argparse
import os

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def detectors():
    # Same settings as mpipe.py
    hands = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="hand_landmarker.task"),
        running_mode=vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=0.6, min_hand_presence_confidence=0.6, min_tracking_confidence=0.5))
    face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path="face_landmarker.task"),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
        min_face_detection_confidence=0.5, min_tracking_confidence=0.5, output_face_blendshapes=True))
    return hands, face


def extract(video_path):
    hand_det, face_det = detectors()     # fresh per video, so no tracking carries over between takes
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    world, screen, face, blend = [], [], [], []
    idx = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)   # mirrored, like mpipe.py
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts = int(idx * 1000 / fps)
            w, s = np.zeros((2, 21, 3), np.float32), np.zeros((2, 21, 3), np.float32)
            res = hand_det.detect_for_video(image, ts)
            if res.hand_world_landmarks and res.handedness:
                for h in range(len(res.hand_world_landmarks)):
                    slot = 0 if res.handedness[h][0].category_name == "Right" else 1   # same slots as mpipe.py
                    w[slot] = [[lm.x, lm.y, lm.z] for lm in res.hand_world_landmarks[h]]
                    s[slot] = [[lm.x, lm.y, lm.z] for lm in res.hand_landmarks[h]]
            f, b = np.zeros((478, 3), np.float32), np.zeros((52,), np.float32)
            fres = face_det.detect_for_video(image, ts)
            if fres.face_landmarks:
                f[:] = [[lm.x, lm.y, lm.z] for lm in fres.face_landmarks[0]]
            if fres.face_blendshapes:
                b[:] = [c.score for c in fres.face_blendshapes[0]]
            world.append(w); screen.append(s); face.append(f); blend.append(b)
            idx += 1
    finally:
        cap.release()
        hand_det.close()
        face_det.close()
    return {"hands.npy": world, "hands_screen.npy": screen, "face_coords.npy": face, "face_blendshapes.npy": blend}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="dataset folder recorded by mpipe.py with SAVE_VIDEO = True")
    ap.add_argument("--out", required=True, help="new folder to write the re-extracted landmarks to")
    args = ap.parse_args()

    done = skipped = 0
    for word in sorted(os.listdir(args.src)):
        word_dir = os.path.join(args.src, word)
        if not os.path.isdir(word_dir):
            continue
        for seq in sorted(os.listdir(word_dir)):
            video = os.path.join(word_dir, seq, "video.mp4")
            if not seq.startswith("seq_") or seq == "seq_temp":
                continue
            if not os.path.exists(video):
                skipped += 1
                continue
            out = os.path.join(args.out, word, seq, "landmarks")
            os.makedirs(out, exist_ok=True)
            for name, frames in extract(video).items():
                np.save(os.path.join(out, name), np.array(frames, dtype=np.float32))
            done += 1
            print(f"{word}/{seq}")
    print(f"\nRe-extracted {done} takes into {args.out}" + (f" ({skipped} without a video skipped)" if skipped else ""))


if __name__ == "__main__":
    main()
