"""Opens isl_app without the webcam, types a few sentences and saves screenshots in the signer_test folder."""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
sys.argv = ["isl_app.py"]
import isl_app  # noqa: E402
import signer_view  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

paints = [0]
_orig = signer_view.SignerView.paintGL


def counted(self):
    paints[0] += 1
    _orig(self)


signer_view.SignerView.paintGL = counted

OUT = os.path.join(HERE, "signer_test")
os.makedirs(OUT, exist_ok=True)
app = QApplication([])
args = argparse.Namespace(model=isl_app.default_model(),
                          signs=os.path.join(HERE, "signs.npz"), seconds=2.5, camera=9,
                          speed=1.0, smoothing=1.2, mirror=False)
w = isl_app.App(args)
w.resize(1200, 820)
w.show()


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        app.processEvents()
        time.sleep(0.005)


pump(8)          # let spaCy load
sentences = ["Hello, thank you.", "Good morning, how are you?", "I will see you tomorrow.",
             "My name is [Manan].", "What is your name?"]
for n, text in enumerate(sentences, 1):
    w.entry.setText(text)
    w.send_text()
    p0, t0 = paints[0], time.time()
    for k, at in enumerate([0.6, 1.3, 2.2, 3.4]):
        pump(at - (time.time() - t0))
        w.view.grabFramebuffer().save(os.path.join(OUT, f"s{n}_{k}.png"))
    if n == 1:
        w.grab().save(os.path.join(OUT, "window.png"))
    while w.player.busy() and time.time() - t0 < 30:
        pump(0.1)
    print(f"sentence {n}: {(paints[0] - p0) / (time.time() - t0):.0f} frames per second")
    pump(0.6)
# the same moment of HOW ARE YOU in both looks, and mirrored
for name, look, mirror in (("look_3d", "3d", False), ("look_kunal", "kunal", False), ("mirror", "3d", True)):
    w.view.look = look
    w.mirror.setChecked(mirror)
    w.entry.setText("How are you?")
    w.send_text()
    pump(1.3)
    w.view.grabFramebuffer().save(os.path.join(OUT, name + ".png"))
    while w.player.busy():
        pump(0.1)
    pump(0.6)
print(w.log.toPlainText())
print("webcam status:", w.cam_status.text())
w.close()
