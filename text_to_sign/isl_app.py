"""Two-way ISL conversation in one window.

    python isl_app.py                 (or double-click start_app.bat)

Left:   webcam. Press Space (or the button), sign once, then pick the right guess with 1, 2 or 3.
        The chosen word goes into the conversation and can be read aloud.
Right:  the signer. Whatever the hearing person types is turned into ISL gloss by Kunal's
        nlp_tool.py and signed by the avatar. Words it has no recording for are fingerspelled;
        type a name in square brackets, e.g. [Manan], to spell it.
Bottom: the conversation and the hearing person's typing box.

Needs signs.npz (python build_signs.py ...), Kunal's renderer.cpp (for his hand shader),
words_kunal_original.data or words.data, alphabets.data, and the ISLModel folder next to this one
for the webcam model. Errors go to isl_app.log.
"""
import argparse
import logging
import os
import re
import subprocess
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
logging.basicConfig(filename=os.path.join(HERE, "isl_app.log"), level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

from signer_view import set_default_gl_format, SignerView  # noqa: E402

set_default_gl_format()

import numpy as np  # noqa: E402
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer  # noqa: E402
from PySide6.QtGui import QImage, QPixmap, QFont, QKeySequence, QShortcut  # noqa: E402
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout,  # noqa: E402
                               QLineEdit, QTextBrowser, QCheckBox, QSlider, QSplitter, QSizePolicy)

from signer import SignLibrary, SignerPlayer  # noqa: E402


# --------------------------------------------------------------------------------- webcam side
class CameraWorker(QThread):
    """Webcam + MediaPipe + our BiLSTM, the same recording as live_demo.py, off the GUI thread."""
    frame = Signal(QImage)
    status = Signal(str)
    guesses = Signal(list)

    def __init__(self, model, seconds, camera):
        super().__init__()
        self.model_path, self.seconds, self.camera = model, seconds, camera
        self.want_take = False
        self.running = True

    def run(self):
        try:
            self.status.emit("Loading the sign model...")
            from chat_client import SignReader   # loads mpipe, MediaPipe and the BiLSTM
            r = SignReader(self.model_path, self.seconds, self.camera)
            cv2, np_, torch = r.cv2, r.np, r.torch
            cap = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(self.camera)
            cap.set(cv2.CAP_PROP_FPS, 30)
            if not cap.isOpened():
                self.status.emit("Couldn't open the webcam.")
                return
            self.status.emit(f"Ready: {len(r.labels)} signs. Press Space and sign.")
            state, t0, rec_start, ts = "idle", 0.0, 0.0, 0
            take, screens, faces = [], [], []
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    self.status.emit("The webcam stopped sending pictures.")
                    break
                mirrored = cv2.flip(frame, 1)
                show = mirrored.copy()
                if self.want_take and state == "idle":
                    self.want_take, state, t0 = False, "countdown", time.time()
                if state == "countdown":
                    left = 2.0 - (time.time() - t0)
                    cv2.putText(show, f"GET READY {left:.1f}", (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 165, 255), 4)
                    if left <= 0:
                        state, take, screens, faces, rec_start = "recording", [], [], [], time.time()
                elif state == "recording":
                    rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
                    hand_world, hand_screen, _, _ = r.extract_landmarks(rgb, ts)
                    face = np_.zeros((478, 3), np_.float32)
                    if r.face:
                        res = r.face.detect_for_video(r.mp.Image(image_format=r.mp.ImageFormat.SRGB, data=rgb), ts)
                        if res.face_landmarks:
                            face[:] = [[lm.x, lm.y, lm.z] for lm in res.face_landmarks[0]]
                    ts += 33
                    take.append(hand_world)
                    screens.append(hand_screen)
                    faces.append(face)
                    h, w, _ = show.shape
                    for x, y, _ in hand_screen.reshape(-1, 3):
                        if x or y:
                            cv2.circle(show, (int(x * w), int(y * h)), 3, (0, 255, 255), -1)
                    el = time.time() - rec_start
                    cv2.circle(show, (30, 30), 12, (0, 0, 255), -1)
                    cv2.putText(show, f"SIGN NOW {max(0.0, self.seconds - el):.1f}", (55, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
                    if el >= self.seconds and len(take) >= 2:
                        state = "idle"
                        hands = np_.array(take, dtype=np_.float32)
                        if np_.all(hands == 0):
                            self.guesses.emit([])
                            self.status.emit("No hands seen. Press Space to try again.")
                        else:
                            with torch.no_grad():
                                x = r.preprocess(hands, np_.array(screens), np_.array(faces), with_position=r.with_position)
                                probs = torch.softmax(r.model(torch.from_numpy(x)[None]), 1)[0]
                            top = probs.topk(3)
                            self.guesses.emit([(r.labels[i].replace("_", " "), float(p))
                                               for p, i in zip(top.values.tolist(), top.indices.tolist())])
                            self.status.emit("Pick the right word (1, 2, 3) or press Space to sign again.")
                rgb = cv2.cvtColor(show, cv2.COLOR_BGR2RGB)
                h, w, _ = rgb.shape
                self.frame.emit(QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy())
            cap.release()
        except Exception:
            logging.error(traceback.format_exc())
            self.status.emit("Webcam side failed, see isl_app.log")


def say(text):
    """Read text aloud with Windows' built-in voice (text goes in on stdin, never into the command)."""
    if os.name != "nt":
        return
    try:
        p = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             "Add-Type -AssemblyName System.Speech; "
             "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak([Console]::In.ReadToEnd())"],
            stdin=subprocess.PIPE, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        p.stdin.write(text.encode("utf-8"))
        p.stdin.close()
    except Exception:
        logging.error(traceback.format_exc())


# --------------------------------------------------------------------------------- main window
class App(QWidget):
    text_ready = Signal(str)            # English typed while the language model was loading
    nlp_ready = Signal()                # the English-to-ISL step has loaded

    def __init__(self, args):
        super().__init__()
        self.setWindowTitle("ISL conversation")
        self.lib = SignLibrary(signs_path=args.signs, sigma=args.smoothing)
        self.player = SignerPlayer(self.lib, speed=args.speed)
        self.player.on_item = self.show_item
        self.to_gloss = None
        self.pending = []
        self.current_guesses = []

        # left: webcam
        self.video = QLabel("Starting the webcam...")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(400, 300)
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setStyleSheet("background:#20262e; color:#ccc; border-radius:6px;")
        self.cam_status = QLabel("")
        self.sign_btn = QPushButton("Sign  (Space)")
        self.sign_btn.clicked.connect(self.start_take)
        self.guess_btns = []
        guess_row = QHBoxLayout()
        for k in range(3):
            b = QPushButton("")
            b.setEnabled(False)
            b.clicked.connect(lambda _=False, k=k: self.send_guess(k))
            self.guess_btns.append(b)
            guess_row.addWidget(b)
        left = QVBoxLayout()
        title_l = QLabel("Deaf person: sign to the camera")
        title_l.setFont(QFont("Segoe UI", 11, QFont.Bold))
        left.addWidget(title_l)
        left.addWidget(self.video, 1)
        left.addWidget(self.cam_status)
        left.addWidget(self.sign_btn)
        left.addLayout(guess_row)

        # right: signer
        self.view = SignerView(self.player, facing=not args.mirror)
        self.caption = QLabel(" ")
        self.caption.setAlignment(Qt.AlignCenter)
        self.caption.setFont(QFont("Segoe UI", 18, QFont.Bold))
        self.speed = QSlider(Qt.Horizontal)
        self.speed.setRange(40, 150)
        self.speed.setValue(int(args.speed * 100))
        self.speed.valueChanged.connect(lambda v: setattr(self.player, "speed", v / 100))
        self.speed_lbl = QLabel(f"Speed {args.speed:.1f}x")
        self.speed.valueChanged.connect(lambda v: self.speed_lbl.setText(f"Speed {v / 100:.1f}x"))
        self.mirror = QCheckBox("Mirror view")
        self.mirror.setChecked(args.mirror)
        self.mirror.toggled.connect(lambda on: setattr(self.view, "facing", not on))
        self.hands3d = QCheckBox("3D hands")
        self.hands3d.setChecked(True)
        self.hands3d.setToolTip("Off: Kunal's original hand look")
        self.hands3d.toggled.connect(lambda on: setattr(self.view, "look", "3d" if on else "kunal"))
        self.replay_btn = QPushButton("Replay")
        self.replay_btn.clicked.connect(self.replay)
        ctl = QHBoxLayout()
        ctl.addWidget(self.speed_lbl)
        ctl.addWidget(self.speed, 1)
        ctl.addWidget(self.mirror)
        ctl.addWidget(self.hands3d)
        ctl.addWidget(self.replay_btn)
        right = QVBoxLayout()
        title_r = QLabel("Hearing person's words, signed")
        title_r.setFont(QFont("Segoe UI", 11, QFont.Bold))
        right.addWidget(title_r)
        right.addWidget(self.view, 1)
        right.addWidget(self.caption)
        right.addLayout(ctl)

        top = QSplitter(Qt.Horizontal)
        lw, rw = QWidget(), QWidget()
        lw.setLayout(left)
        rw.setLayout(right)
        top.addWidget(lw)
        top.addWidget(rw)
        top.setSizes([560, 560])

        # bottom: conversation
        self.log = QTextBrowser()
        self.log.setMinimumHeight(90)
        self.entry = QLineEdit()
        self.entry.setMinimumHeight(34)
        self.entry.setPlaceholderText("Click here, type in English and press Enter  ([Name] to fingerspell)")
        self.entry.returnPressed.connect(self.send_text)
        send = QPushButton("Send")
        send.clicked.connect(self.send_text)
        self.speak = QCheckBox("Read signed words aloud")
        self.speak.setChecked(True)
        row = QHBoxLayout()
        type_lbl = QLabel("Hearing person types here:")
        type_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        row.addWidget(type_lbl)
        row.addWidget(self.entry, 1)
        row.addWidget(send)
        row.addWidget(self.speak)

        outer = QVBoxLayout(self)
        outer.addWidget(top, 3)
        outer.addWidget(self.log, 1)
        outer.addLayout(row)
        # Fit the screen: on a scaled laptop screen 1200x820 ran past the taskbar and hid the
        # typing box at the bottom.
        avail = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1200, avail.width() - 40), min(820, avail.height() - 60))
        self.move(avail.x() + (avail.width() - self.width()) // 2, avail.y() + 10)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.space)
        for k in range(3):
            QShortcut(QKeySequence(str(k + 1)), self, activated=lambda k=k: self.key_guess(k))

        self.camera = CameraWorker(args.model, args.seconds, args.camera)
        self.camera.frame.connect(self.show_frame)
        self.camera.status.connect(self.cam_status.setText)
        self.camera.guesses.connect(self.show_guesses)
        self.camera.start()

        self.text_ready.connect(self.play_text)
        self.nlp_ready.connect(lambda: self.add_log(
            "<i>Ready. Hearing person: click the box at the bottom, type English and press Enter.</i>"))
        threading.Thread(target=self.load_nlp, daemon=True).start()
        self.add_log("<i>Signer knows %d signs (plus fingerspelling). Loading the English-to-ISL step...</i>"
                     % len(self.lib.vocabulary))

    # ---- text -> sign
    def load_nlp(self):
        try:
            from nlp_tool import convert_to_isl
            self.to_gloss = convert_to_isl
            self.nlp_ready.emit()
            for text in self.pending:
                self.text_ready.emit(text)
            self.pending.clear()
        except Exception:
            logging.error(traceback.format_exc())

    def send_text(self):
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.clear()
        self.add_log(f"<b>Hearing person:</b> {self.esc(text)}")
        if self.to_gloss is None:
            self.pending.append(text)
            self.add_log("<i>(still loading the language model, will sign it in a moment)</i>")
            return
        self.play_text(text)

    def english_to_items(self, text):
        """English -> (gloss, items). Set phrases we recorded as one sign (how are you, good morning,
        thank you) are taken straight from the English, because nlp_tool reorders them
        ("How are you?" -> YOU HOW). Everything else goes through Kunal's nlp_tool as before."""
        phrases = sorted((n.split("_") for n in self.lib.signs if "_" in n and not n.endswith("_SIGN")),
                         key=len, reverse=True)
        words = re.findall(r"\[[^\]]*\]|[A-Za-z']+", text)
        parts, rest, i = [], [], 0
        while i < len(words):
            ph = next((ph for ph in phrases if [w.upper() for w in words[i:i + len(ph)]] == ph), None)
            if ph:
                if rest:
                    parts.append(" ".join(rest))
                    rest = []
                parts.append(ph)
                i += len(ph)
            else:
                rest.append(words[i])
                i += 1
        if not any(isinstance(x, list) for x in parts):
            parts = [text]                       # no set phrase: the whole sentence, as before
        elif rest:
            parts.append(" ".join(rest))
        gloss, items = [], []
        for part in parts:
            if isinstance(part, list):
                gloss.append(" ".join(part))
                items.append("_".join(part))
            else:
                g = self.to_gloss(part)
                gloss.append(g)
                items += self.lib.plan(g)
        return " ".join(gloss), items

    @Slot(str)
    def play_text(self, text):
        try:
            gloss, items = self.english_to_items(text)
        except Exception:
            logging.error(traceback.format_exc())
            self.add_log("<i>Couldn't turn that into ISL, see isl_app.log</i>")
            return
        self.last_items = items
        shown = " ".join(i.replace("_SIGN", "").replace("_", " ") if len(i) > 1 else i for i in items)
        self.add_log(f"&nbsp;&nbsp;<span style='color:#555'>ISL: {self.esc(gloss)}  →  signing: {self.esc(shown)}</span>")
        self.player.play(items)

    def replay(self):
        if getattr(self, "last_items", None):
            self.player.clear()
            self.player.play(list(self.last_items))

    def show_item(self, name):
        word = name.replace("_SIGN", "").replace("_", " ")
        if len(name) > 1:
            self.caption.setText(word)
        else:
            self.caption.setText(f"letter  {name}" + ("" if name in self.lib.letters else "  (no hand shape yet)"))

    # ---- sign -> text
    @Slot(QImage)
    def show_frame(self, img):
        self.video.setPixmap(QPixmap.fromImage(img).scaled(self.video.size(), Qt.KeepAspectRatio,
                                                           Qt.SmoothTransformation))

    def space(self):
        if self.entry.hasFocus() and self.entry.text():
            self.entry.insert(" ")
        else:
            self.start_take()

    def start_take(self):
        self.camera.want_take = True
        for b in self.guess_btns:
            b.setText("")
            b.setEnabled(False)

    @Slot(list)
    def show_guesses(self, guesses):
        self.current_guesses = guesses
        for k, b in enumerate(self.guess_btns):
            if k < len(guesses):
                b.setText(f"{k + 1}.  {guesses[k][0]}   {guesses[k][1]:.0%}")
                b.setEnabled(True)
            else:
                b.setText("")
                b.setEnabled(False)

    def key_guess(self, k):
        if self.entry.hasFocus():
            self.entry.insert(str(k + 1))
        else:
            self.send_guess(k)

    def send_guess(self, k):
        if k >= len(self.current_guesses):
            return
        word = self.current_guesses[k][0]
        self.add_log(f"<b style='color:#1f5f8b'>Deaf person (signed):</b> {self.esc(word)}")
        if self.speak.isChecked():
            say(word)
        self.show_guesses([])
        self.cam_status.setText("Sent. Press Space to sign the next word.")

    # ---- helpers
    @staticmethod
    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def add_log(self, html):
        self.log.append(html)

    def closeEvent(self, e):
        self.camera.running = False
        self.camera.wait(2000)
        super().closeEvent(e)


def default_model():
    """The 91-sign model (9 Nov) if it is there, else the 38-sign INCLUDE one."""
    from chat_client import REPO
    best = os.path.join(REPO, "runs", "all_position_big", "model.pt")
    return best if os.path.exists(best) else os.path.join(REPO, "models", "include_position.pt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=default_model())
    ap.add_argument("--signs", default=os.path.join(HERE, "signs.npz"))
    ap.add_argument("--seconds", type=float, default=2.5)
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--smoothing", type=float, default=1.2, help="0 = raw landmarks")
    ap.add_argument("--mirror", action="store_true", help="show the signer like a mirror")
    args = ap.parse_args()
    app = QApplication(sys.argv)
    w = App(args)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.error(traceback.format_exc())
        raise
