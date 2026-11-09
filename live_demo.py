"""Live webcam demo: sign in front of the camera and see what the trained model predicts.

    python live_demo.py                                     # 91 signs, with hand position
    python live_demo.py --model models/include_plus_vansh.pt   # 58 signs, hand shape only

Press space, hold your hands ready during the countdown, then sign. After the take, the top 3
guesses are shown. Press q to quit.

Landmarks come from mpipe.py's own extract_landmarks (same MediaPipe settings, same mirrored
frame), so live input matches the recorded training data. Needs hand_landmarker.task in the
folder you run it from, and face_landmarker.task for models trained with --position.
"""
import argparse
import time

import cv2
import mediapipe as mp
import numpy as np
import torch
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from mpipe import extract_landmarks                 # importing mpipe loads the hand detector
from isl_model.model import SignBiLSTM
from isl_model.preprocess import preprocess

WINDOW = "ISL live demo"


def put(img, text, y, scale=0.7, color=(255, 255, 255), thick=2):
    cv2.putText(img, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/include_position.pt")
    ap.add_argument("--seconds", type=float, default=2.5, help="length of each take")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    ckpt = torch.load(args.model, map_location="cpu")
    labels = ckpt["labels"]
    model = SignBiLSTM(ckpt["features"], len(labels))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    with_position = ckpt.get("with_position", False)
    face_detector = None
    if with_position:
        # Same settings as mpipe.py's face tracking
        face_detector = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path="face_landmarker.task"),
            running_mode=vision.RunningMode.VIDEO, num_faces=1,
            min_face_detection_confidence=0.5, min_tracking_confidence=0.5))
    print(f"{len(labels)} signs, hand position {'on' if with_position else 'off'}")

    cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FPS, 30)
    state, t0, take, screens, faces, result, ts = "idle", 0.0, [], [], [], None, 0
    rec_start = 0.0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        mirrored = cv2.flip(frame, 1)
        display = mirrored.copy()

        if state == "countdown":
            left = 2.0 - (time.time() - t0)
            put(display, f"GET READY: {left:.1f}s", 240, 1.5, (0, 165, 255), 4)
            if left <= 0:
                state, take, screens, faces = "recording", [], [], []
                rec_start = time.time()
        elif state == "recording":
            rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
            hand_world, hand_screen, _, _ = extract_landmarks(rgb, ts)
            face = np.zeros((478, 3), np.float32)
            if face_detector:
                fres = face_detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
                if fres.face_landmarks:
                    face[:] = [[lm.x, lm.y, lm.z] for lm in fres.face_landmarks[0]]
            ts += 33
            take.append(hand_world)
            screens.append(hand_screen)
            faces.append(face)
            h, w, _ = display.shape
            for x, y, _ in hand_screen.reshape(-1, 3):
                if x or y:
                    cv2.circle(display, (int(x * w), int(y * h)), 3, (0, 255, 255), -1)
            cv2.circle(display, (30, 30), 12, (0, 0, 255), -1)
            # Each take lasts --seconds of real time. A dim room makes the webcam drop to fewer
            # frames per second; counting frames instead would make takes drag on in the dark.
            elapsed = time.time() - rec_start
            put(display, f"SIGN NOW ({max(0.0, args.seconds - elapsed):.1f}s)", 38, 0.7, (0, 0, 255))
            if elapsed >= args.seconds and len(take) >= 2:
                hands = np.array(take, dtype=np.float32)
                if np.all(hands == 0):
                    result = [("no hands detected", 0.0)]
                else:
                    with torch.no_grad():
                        x = preprocess(hands, np.array(screens), np.array(faces), with_position=with_position)
                        probs = torch.softmax(model(torch.from_numpy(x)[None]), 1)[0]
                    top = probs.topk(3)
                    result = [(labels[i], p) for p, i in zip(top.values.tolist(), top.indices.tolist())]
                state = "idle"
        else:
            put(display, "space: record a sign   q: quit", 30, 0.6, (200, 200, 200), 1)
            if result:
                word, p = result[0]
                put(display, f"{word.replace('_', ' ').upper()}", 90, 1.4, (0, 255, 0), 3)
                for k, (wd, pk) in enumerate(result):
                    put(display, f"{k + 1}. {wd.replace('_', ' ')}  {pk:.0%}", 130 + 28 * k, 0.6)

        cv2.imshow(WINDOW, display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord(" ") and state == "idle":
            state, t0 = "countdown", time.time()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
