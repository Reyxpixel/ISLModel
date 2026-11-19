"""One side of a two-way ISL conversation (Python version of Kunal's client.cpp, plus our model).

Start chat_server.py first, then (from any folder):

    python chat_client.py --role hearing          # types English, reads replies
    python chat_client.py --role deaf --sign      # signs to the webcam, sees replies as hands

hearing: type a message and press Enter. Messages from the other side are printed.
deaf:    every incoming English message is turned into ISL gloss by Kunal's nlp_tool.py and
         played by Kunal's renderer. With --sign, a webcam window opens: press space and sign;
         the top 3 guesses from our BiLSTM appear, press 1, 2 or 3 to send one (or space to redo).
         Typing in the terminal also works.

Text and gloss words the renderer has no animation for are fingerspelled, unless
--no-fingerspell is given.
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# ISLModel folder (mpipe.py, isl_model/, models/, *.task): this folder's parent if the scripts
# sit inside the repo, otherwise a sibling ISLModel folder.
REPO = os.path.dirname(HERE)
if not os.path.isdir(os.path.join(REPO, "isl_model")):
    REPO = os.path.join(REPO, "ISLModel")
sys.path.insert(0, REPO)  # for mpipe and isl_model when signing


# ---------------------------------------------------------------- text -> sign side
def renderer_vocabulary(path):
    """Word names in words.data, read the same way renderer.cpp's load_words does."""
    words = set()
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.split("//", 1)[0]
            for tok in re.split(r"[\s{},]+", line):
                if tok and tok[0].isalpha() and tok not in ("std", "vector") and "SEQ" not in tok:
                    words.add(tok.upper())
    return words


class Renderer:
    """Starts Kunal's renderer and feeds it one gloss line at a time (like client.cpp does)."""

    def __init__(self, exe, fingerspell=True, show_log=False):
        self.vocab = renderer_vocabulary(os.path.join(HERE, "words.data"))
        self.fingerspell = fingerspell
        self.proc = subprocess.Popen(
            [exe], cwd=HERE, stdin=subprocess.PIPE, text=True,
            stdout=None if show_log else subprocess.DEVNULL,
            stderr=None if show_log else subprocess.DEVNULL)

    def play(self, gloss):
        tokens, words, i = [], gloss.split(), 0
        merged = []
        while i < len(words):  # "GOOD MORNING" -> GOOD_MORNING when that animation exists
            pair = f"{words[i]}_{words[i + 1]}".upper() if i + 1 < len(words) else ""
            if pair in self.vocab:
                merged.append(pair)
                i += 2
            else:
                merged.append(words[i])
                i += 1
        for tok in merged:
            if len(tok) == 1 and f"{tok}_SIGN".upper() in self.vocab:
                tok = f"{tok}_SIGN".upper()  # one-letter words (I) are stored as I_SIGN
            if tok.startswith("[") or tok.upper() in self.vocab or not self.fingerspell:
                tokens.append(tok)
            elif tok.isalpha():
                tokens.append(f"[{tok}]")  # renderer spells [WORD] letter by letter
        line = " ".join(tokens)
        if line and self.proc.poll() is None:
            self.proc.stdin.write(line + "\n")
            self.proc.stdin.flush()
        return line

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()


# ---------------------------------------------------------------- sign -> text side
class SignReader:
    """Webcam + our BiLSTM, same recording and preprocessing as live_demo.py."""

    def __init__(self, model_path, seconds, camera):
        model_path = os.path.abspath(model_path)
        os.chdir(REPO)  # mpipe loads hand_landmarker.task from the current folder
        import cv2
        import mediapipe as mp
        import numpy as np
        import torch
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
        from mpipe import extract_landmarks
        from isl_model.model import SignBiLSTM
        from isl_model.preprocess import preprocess

        self.cv2, self.mp, self.np, self.torch = cv2, mp, np, torch
        self.extract_landmarks, self.preprocess = extract_landmarks, preprocess
        ckpt = torch.load(model_path, map_location="cpu")
        self.labels = ckpt["labels"]
        self.model = SignBiLSTM(ckpt["features"], len(self.labels))
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()
        self.with_position = ckpt.get("with_position", False)
        self.face = None
        if self.with_position:
            self.face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path="face_landmarker.task"),
                running_mode=vision.RunningMode.VIDEO, num_faces=1,
                min_face_detection_confidence=0.5, min_tracking_confidence=0.5))
        self.seconds, self.camera = seconds, camera

    def run(self, send, stop):
        cv2, np, torch = self.cv2, self.np, self.torch
        win = "ISL chat - sign here"
        cap = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FPS, 30)
        state, t0, rec_start, ts = "idle", 0.0, 0.0, 0
        take, screens, faces, guesses, last_sent = [], [], [], [], ""

        def put(img, text, y, scale=0.7, color=(255, 255, 255), thick=2):
            cv2.putText(img, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick)

        while cap.isOpened() and not stop.is_set():
            ok, frame = cap.read()
            if not ok:
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
                hand_world, hand_screen, _, _ = self.extract_landmarks(rgb, ts)
                face = np.zeros((478, 3), np.float32)
                if self.face:
                    res = self.face.detect_for_video(
                        self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb), ts)
                    if res.face_landmarks:
                        face[:] = [[lm.x, lm.y, lm.z] for lm in res.face_landmarks[0]]
                ts += 33
                take.append(hand_world)
                screens.append(hand_screen)
                faces.append(face)
                h, w, _ = display.shape
                for x, y, _ in hand_screen.reshape(-1, 3):
                    if x or y:
                        cv2.circle(display, (int(x * w), int(y * h)), 3, (0, 255, 255), -1)
                elapsed = time.time() - rec_start
                put(display, f"SIGN NOW ({max(0.0, self.seconds - elapsed):.1f}s)", 38, 0.7, (0, 0, 255))
                if elapsed >= self.seconds and len(take) >= 2:
                    hands = np.array(take, dtype=np.float32)
                    guesses = []
                    if not np.all(hands == 0):
                        with torch.no_grad():
                            x = self.preprocess(hands, np.array(screens), np.array(faces),
                                                with_position=self.with_position)
                            probs = torch.softmax(self.model(torch.from_numpy(x)[None]), 1)[0]
                        top = probs.topk(3)
                        guesses = [(self.labels[i].replace("_", " "), p)
                                   for p, i in zip(top.values.tolist(), top.indices.tolist())]
                    state = "choose" if guesses else "idle"
            elif state == "choose":
                put(display, "press 1/2/3 to send, space to redo", 30, 0.6, (200, 200, 200), 1)
                for k, (wd, p) in enumerate(guesses):
                    put(display, f"{k + 1}. {wd}  {p:.0%}", 80 + 34 * k, 0.9, (0, 255, 0) if k == 0 else (255, 255, 255))
            else:
                put(display, "space: sign   q: quit", 30, 0.6, (200, 200, 200), 1)
                if last_sent:
                    put(display, f"sent: {last_sent}", 70, 0.8, (0, 255, 0))

            cv2.imshow(win, display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord(" ") and state in ("idle", "choose"):
                state, t0 = "countdown", time.time()
            elif state == "choose" and key in (ord("1"), ord("2"), ord("3")):
                k = key - ord("1")
                if k < len(guesses):
                    last_sent = guesses[k][0]
                    send(last_sent)
                    state = "idle"

        cap.release()
        cv2.destroyAllWindows()
        stop.set()


# ---------------------------------------------------------------- chat
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=["deaf", "hearing"], required=True)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--sign", action="store_true", help="deaf role: sign to the webcam")
    ap.add_argument("--model", default=os.path.join(REPO, "models", "include_position.pt"))
    ap.add_argument("--seconds", type=float, default=2.5, help="length of each signed take")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--renderer", default=os.path.join(HERE, "renderer.exe" if os.name == "nt" else "renderer"))
    ap.add_argument("--no-fingerspell", action="store_true")
    ap.add_argument("--renderer-log", action="store_true", help="show the renderer's own output")
    args = ap.parse_args()

    sock = socket.create_connection((args.host, args.port))
    stop = threading.Event()
    renderer = to_gloss = None
    if args.role == "deaf":
        from nlp_tool import convert_to_isl  # Kunal's English -> ISL gloss (loads spaCy)
        to_gloss = convert_to_isl
        renderer = Renderer(args.renderer, not args.no_fingerspell, args.renderer_log)

    def send(text):
        sock.sendall(text.encode())
        if args.sign:
            print(f"You (signed): {text}\nYou: ", end="", flush=True)

    def receive():
        while not stop.is_set():
            try:
                data = sock.recv(1024)
            except OSError:
                break
            if not data:
                print("\n[Disconnected from server]")
                break
            msg = data.decode(errors="replace").strip()
            if renderer:
                gloss = to_gloss(msg)
                played = renderer.play(gloss)
                print(f"\n=============================\nIncoming English : {msg}\n"
                      f"ISL gloss        : {gloss}\nRendered as      : {played}\n"
                      f"=============================\nYou: ", end="", flush=True)
            else:
                print(f"\n[Incoming]: {msg}\nYou: ", end="", flush=True)
        stop.set()

    def type_messages():
        while not stop.is_set():
            try:
                text = input("You: ")
            except (EOFError, KeyboardInterrupt):
                break
            if text.strip() == "exit":
                break
            if text.strip():
                sock.sendall(text.encode())
        stop.set()

    threading.Thread(target=receive, daemon=True).start()
    try:
        if args.sign:
            # OpenCV windows must live on the main thread, so typing moves to a helper thread
            threading.Thread(target=type_messages, daemon=True).start()
            print("Loading the sign model...")
            SignReader(args.model, args.seconds, args.camera).run(send, stop)
        else:
            type_messages()
    finally:
        stop.set()
        sock.close()
        if renderer:
            renderer.close()


if __name__ == "__main__":
    main()
