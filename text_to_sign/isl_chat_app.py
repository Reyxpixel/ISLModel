"""The whole two-way ISL chat in one window (no server, no extra terminals).

    double-click start_chat.bat
    or: .venv\\Scripts\\python isl_chat_app.py               (from this folder)
        .venv\\Scripts\\python isl_chat_app.py --no-camera   (typing only, no webcam)

Left : the deaf person signs to the webcam. Press Space (or click "Sign"), sign after the
       countdown, then press 1, 2 or 3 (or click a guess) to send it. Space again redoes it.
       The box under the camera is for typing instead (names, words the model doesn't know).
Right: Kunal's 3D hands sign every message the hearing person types (English -> ISL gloss
       with nlp_tool.py -> renderer).
Bottom: the conversation, and the hearing person's typing box. Signed messages are also read
       aloud (untick "Read signs aloud" to stop that).

Both people use this one computer. For two laptops use chat_server.py + chat_client.py.
"""
import argparse
import ctypes
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if sys.stderr is None:  # started with pythonw (start_chat.bat): keep errors in a log file
    sys.stderr = sys.stdout = open(os.path.join(HERE, "isl_chat_app.log"), "a", buffering=1)

import chat_client  # noqa: E402  Renderer, SignReader, REPO

BG, PANEL, TEXT, MUTED = "#f4f5f7", "#ffffff", "#1f2933", "#66707a"
ACCENT, HEARING, DEAF = "#2563eb", "#9a3412", "#1d4ed8"
RENDER_BG = "#1a2633"
FONT = "Segoe UI"


# ---------------------------------------------------------------- renderer in a panel
class EmbeddedRenderer(chat_client.Renderer):
    """Kunal's renderer.exe, with its "Rendering: X" lines passed back to the window."""

    def __init__(self, exe, fingerspell=True):
        self.vocab = chat_client.renderer_vocabulary(os.path.join(HERE, "words.data"))
        with open(os.path.join(HERE, "alphabets.data"), encoding="utf-8", errors="replace") as f:
            self.letters = {t.upper() for line in f for t in line.split("//")[0].split()
                            if len(t) == 1 and t.isalpha()}  # letters that have a hand shape
        self.fingerspell = fingerspell
        self.proc = subprocess.Popen([exe], cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.events = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            if line.startswith("Rendering:"):
                self.events.put(line.split(":", 1)[1].strip())


class Win32:
    """Just enough Win32 to move the renderer's window into a Tk frame."""

    def __init__(self):
        from ctypes import wintypes as wt
        self.wt, u = wt, ctypes.windll.user32
        self.u = u
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
        u.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
        u.SetParent.argtypes = [wt.HWND, wt.HWND]
        u.SetWindowPos.argtypes = [wt.HWND, wt.HWND] + [ctypes.c_int] * 4 + [ctypes.c_uint]
        u.MoveWindow.argtypes = [wt.HWND] + [ctypes.c_int] * 4 + [wt.BOOL]
        u.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
        u.IsWindowVisible.argtypes = [wt.HWND]
        u.IsWindow.argtypes = [wt.HWND]

    def window_of(self, pid):
        found = []
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, self.wt.HWND, self.wt.LPARAM)

        def check(hwnd, _):
            owner = self.wt.DWORD()
            self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value == pid and self.u.IsWindowVisible(hwnd):
                found.append(hwnd)
                return False
            return True
        self.u.EnumWindows(proc_type(check), 0)
        return found[0] if found else None

    def embed(self, hwnd, parent, w, h):
        style = self.u.GetWindowLongPtrW(hwnd, -16)                       # GWL_STYLE
        style &= ~(0x80000000 | 0x00C00000 | 0x00040000 | 0x00080000 | 0x00020000 | 0x00010000)
        style |= 0x40000000                                                # WS_CHILD
        self.u.SetParent(hwnd, parent)
        self.u.SetWindowLongPtrW(hwnd, -16, style)
        ex = self.u.GetWindowLongPtrW(hwnd, -20) & ~0x00040000              # no taskbar button
        self.u.SetWindowLongPtrW(hwnd, -20, ex)
        self.u.SetWindowPos(hwnd, None, 0, 0, w, h, 0x0004 | 0x0020 | 0x0040)  # NOZORDER|FRAMECHANGED|SHOW

    def resize(self, hwnd, w, h):
        if self.u.IsWindow(hwnd):
            self.u.MoveWindow(hwnd, 0, 0, w, h, True)


# ---------------------------------------------------------------- webcam + our model
class SignCamera(threading.Thread):
    """Reads the webcam, records a take on request and returns the model's top 3 guesses.
    Same recording and preprocessing as chat_client.SignReader / live_demo.py."""

    COUNTDOWN = 2.0

    def __init__(self, reader, camera, seconds):
        super().__init__(daemon=True)
        self.r, self.camera, self.seconds = reader, camera, seconds
        self.state, self.t0 = "idle", 0.0
        self.frame = None                 # latest RGB frame for the window
        self.events = queue.Queue()       # ("guesses", [...]) / ("error", text) / ("state", name)
        self.stop = threading.Event()

    def start_sign(self):
        if self.state in ("idle", "choose"):
            self.t0, self.state = time.time(), "countdown"
            self.events.put(("state", "countdown"))

    def run(self):
        r = self.r
        cv2, np, torch = r.cv2, r.np, r.torch
        cap = cv2.VideoCapture(self.camera, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FPS, 30)
        if not cap.isOpened():
            self.events.put(("error", f"Could not open camera {self.camera}."))
            return
        ts, take, screens, faces, rec_start = 0, [], [], [], 0.0
        while not self.stop.is_set():
            ok, frame = cap.read()
            if not ok:
                self.events.put(("error", "The camera stopped sending pictures."))
                break
            mirrored = cv2.flip(frame, 1)
            display = mirrored.copy()
            h, w, _ = display.shape
            if self.state == "countdown":
                left = self.COUNTDOWN - (time.time() - self.t0)
                cv2.putText(display, f"{max(left, 0):.1f}", (w // 2 - 60, h // 2 + 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 165, 255), 6)
                if left <= 0:
                    self.state, take, screens, faces = "recording", [], [], []
                    rec_start = time.time()
                    self.events.put(("state", "recording"))
            elif self.state == "recording":
                rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)
                hand_world, hand_screen, _, _ = r.extract_landmarks(rgb, ts)
                face = np.zeros((478, 3), np.float32)
                if r.face:
                    res = r.face.detect_for_video(r.mp.Image(image_format=r.mp.ImageFormat.SRGB, data=rgb), ts)
                    if res.face_landmarks:
                        face[:] = [[lm.x, lm.y, lm.z] for lm in res.face_landmarks[0]]
                ts += 33
                take.append(hand_world)
                screens.append(hand_screen)
                faces.append(face)
                for x, y, _ in hand_screen.reshape(-1, 3):
                    if x or y:
                        cv2.circle(display, (int(x * w), int(y * h)), 3, (0, 255, 255), -1)
                elapsed = time.time() - rec_start
                cv2.rectangle(display, (0, h - 12), (int(w * min(elapsed / self.seconds, 1)), h), (0, 0, 255), -1)
                if elapsed >= self.seconds and len(take) >= 2:
                    hands = np.array(take, dtype=np.float32)
                    guesses = []
                    if not np.all(hands == 0):
                        with torch.no_grad():
                            x = r.preprocess(hands, np.array(screens), np.array(faces), with_position=r.with_position)
                            probs = torch.softmax(r.model(torch.from_numpy(x)[None]), 1)[0]
                        top = probs.topk(3)
                        guesses = [(r.labels[i].replace("_", " "), p)
                                   for p, i in zip(top.values.tolist(), top.indices.tolist())]
                    self.state = "choose" if guesses else "idle"
                    self.events.put(("guesses", guesses))
            self.frame = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        cap.release()


# ---------------------------------------------------------------- the window
class App:
    def __init__(self, args):
        self.args = args
        self.root = root = tk.Tk()
        root.title("ISL Chat")
        root.configure(bg=BG)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(1400, int(sw * 0.92))}x{min(860, int(sh * 0.86))}+{int(sw * 0.04)}+{int(sh * 0.03)}")
        root.minsize(980, 640)
        self.to_gloss = self.cam = self.reader = None
        self.guesses, self.render_hwnd, self.photo = [], None, None
        self.win32 = Win32() if os.name == "nt" else None
        self._build()
        self.renderer = EmbeddedRenderer(args.renderer, not args.no_fingerspell)
        self.embed_tries = 0
        root.after(200, self._embed_renderer)
        threading.Thread(target=self._load, daemon=True).start()
        root.after(30, self._tick)
        root.protocol("WM_DELETE_WINDOW", self.close)
        for key in ("<space>", "1", "2", "3"):
            root.bind_all(key, self._key)
        root.bind_all("<Escape>", lambda e: root.focus_set())

    # ---- layout
    def _build(self):
        root = self.root
        root.columnconfigure(0, weight=1, uniform="half")
        root.columnconfigure(1, weight=1, uniform="half")
        root.rowconfigure(0, weight=1)

        def panel(col, title, subtitle):
            f = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground="#d9dde3")
            f.grid(row=0, column=col, sticky="nsew", padx=(12 if col == 0 else 6, 6 if col == 0 else 12), pady=(12, 6))
            tk.Label(f, text=title, bg=PANEL, fg=TEXT, font=(FONT, 13, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
            tk.Label(f, text=subtitle, bg=PANEL, fg=MUTED, font=(FONT, 9)).pack(anchor="w", padx=12, pady=(0, 6))
            return f

        # left: the deaf person signs
        left = panel(0, "Deaf person - sign to the camera",
                     "Space: sign   1 / 2 / 3: send a guess   Space again: redo")
        self.cam_label = tk.Label(left, bg="#111", fg="#ccc", font=(FONT, 11),
                                  text="Loading the sign model..." if not self.args.no_camera else "Camera off (--no-camera)")
        self.cam_label.pack(fill="both", expand=True, padx=12)
        row = tk.Frame(left, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(8, 2))
        self.sign_btn = tk.Button(row, takefocus=0, text="Sign  (Space)", font=(FONT, 10, "bold"), bg=ACCENT, fg="white",
                                  activebackground="#1d4ed8", disabledforeground="#c7d2fe",
                                  relief="flat", padx=12, pady=4,
                                  state="disabled", command=self.start_sign)
        self.sign_btn.pack(side="left")
        self.guess_btns = []
        for k in range(3):
            b = tk.Button(row, takefocus=0, text="", font=(FONT, 10), relief="flat", bg=PANEL, padx=10, pady=4,
                          state="disabled", command=lambda k=k: self.send_guess(k))
            b.pack(side="left", padx=(8, 0))
            self.guess_btns.append(b)
        self.cam_status = tk.Label(left, text="", bg=PANEL, fg=MUTED, font=(FONT, 9))
        self.cam_status.pack(anchor="w", padx=12)
        row = tk.Frame(left, bg=PANEL)
        row.pack(fill="x", padx=12, pady=(2, 12))
        tk.Label(row, text="or type:", bg=PANEL, fg=MUTED, font=(FONT, 10)).pack(side="left")
        self.deaf_entry = tk.Entry(row, font=(FONT, 11), relief="solid", bd=1)
        self.deaf_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=3)
        self.deaf_entry.bind("<Return>", lambda e: self.send_deaf_typed())
        tk.Button(row, takefocus=0, text="Send", relief="flat", bg="#e8edf5", padx=10,
                  command=self.send_deaf_typed).pack(side="left")

        # right: the renderer signs what the hearing person writes
        right = panel(1, "Signed for the deaf person", "Kunal's renderer plays every message from the hearing person")
        self.render_area = tk.Frame(right, bg=RENDER_BG)
        self.render_area.pack(fill="both", expand=True, padx=12)
        self.render_area.bind("<Configure>", self._resize_renderer)
        self.caption = tk.Label(right, text="", bg=PANEL, fg=TEXT, font=(FONT, 15, "bold"))
        self.caption.pack(pady=(8, 2))
        self.gloss_label = tk.Label(right, text="", bg=PANEL, fg=MUTED, font=(FONT, 10))
        self.gloss_label.pack(pady=(0, 12))

        # bottom: conversation + hearing person's box
        bottom = tk.Frame(root, bg=PANEL, highlightthickness=1, highlightbackground="#d9dde3")
        bottom.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(6, 12))
        self.log = tk.Text(bottom, height=7, font=(FONT, 11), bg=PANEL, fg=TEXT, relief="flat",
                           wrap="word", state="disabled", padx=10, pady=6)
        self.log.pack(fill="x", padx=2, pady=(2, 0))
        self.log.tag_configure("hearing", foreground=HEARING, font=(FONT, 11, "bold"))
        self.log.tag_configure("deaf", foreground=DEAF, font=(FONT, 11, "bold"))
        self.log.tag_configure("note", foreground=MUTED, font=(FONT, 9))
        row = tk.Frame(bottom, bg=PANEL)
        row.pack(fill="x", padx=10, pady=(4, 10))
        tk.Label(row, text="Hearing person:", bg=PANEL, fg=HEARING, font=(FONT, 11, "bold")).pack(side="left")
        self.hearing_entry = tk.Entry(row, font=(FONT, 12), relief="solid", bd=1)
        self.hearing_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=4)
        self.hearing_entry.bind("<Return>", lambda e: self.send_hearing())
        tk.Button(row, takefocus=0, text="Send", font=(FONT, 10, "bold"), relief="flat", bg=ACCENT, fg="white",
                  padx=14, command=self.send_hearing).pack(side="left")
        self.speak = tk.BooleanVar(value=not self.args.mute)
        tk.Checkbutton(row, takefocus=0, text="Read signs aloud", variable=self.speak, bg=PANEL,
                       font=(FONT, 9)).pack(side="left", padx=(10, 0))
        self.write_log("note", "Loading English to ISL (spaCy)" +
                       ("" if self.args.no_camera else " and the sign model") + "...")

    # ---- start-up
    def _load(self):
        from nlp_tool import convert_to_isl  # Kunal's English -> ISL gloss
        self.to_gloss = convert_to_isl
        self.root.after(0, self.write_log, "note", "Ready. Type in the hearing box, or press Space to sign.")
        if self.args.no_camera:
            return
        try:
            self.reader = chat_client.SignReader(self.args.model, self.args.seconds, self.args.camera)
        except Exception as e:  # noqa: BLE001  shown in the window instead of crashing it
            self.root.after(0, self.cam_label.configure, {"text": f"Sign model failed to load:\n{e}"})
            return
        self.cam = SignCamera(self.reader, self.args.camera, self.args.seconds)
        self.cam.start()
        self.root.after(0, self.sign_btn.configure, {"state": "normal"})

    def _embed_renderer(self):
        if not self.win32 or self.renderer.proc.poll() is not None:
            return
        hwnd = self.win32.window_of(self.renderer.proc.pid)
        if hwnd:
            self.render_hwnd = hwnd
            self.root.update_idletasks()
            self.win32.embed(hwnd, self.render_area.winfo_id(),
                             self.render_area.winfo_width(), self.render_area.winfo_height())
        elif self.embed_tries < 100:
            self.embed_tries += 1
            self.root.after(100, self._embed_renderer)

    def _resize_renderer(self, event):
        if self.render_hwnd:
            self.win32.resize(self.render_hwnd, event.width, event.height)

    # ---- every 30 ms: camera picture, guesses, what the renderer is playing
    def _tick(self):
        if self.cam and self.cam.frame is not None:
            from PIL import Image, ImageTk
            img = Image.fromarray(self.cam.frame)
            w, h = max(self.cam_label.winfo_width(), 50), max(self.cam_label.winfo_height(), 50)
            scale = min(w / img.width, h / img.height)
            img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))))
            self.photo = ImageTk.PhotoImage(img)
            self.cam_label.configure(image=self.photo, text="")
        while self.cam and not self.cam.events.empty():
            kind, value = self.cam.events.get()
            if kind == "state":
                self.cam_status.configure(text="Get ready..." if value == "countdown" else "Sign now!", fg=ACCENT)
                self._show_guesses([])
            elif kind == "guesses":
                self._show_guesses(value)
                self.cam_status.configure(text="Press 1, 2 or 3 to send - Space to sign again" if value
                                          else "No hands seen - press Space to try again", fg=MUTED)
            elif kind == "error":
                self.cam_status.configure(text=value, fg="#b91c1c")
        while not self.renderer.events.empty():
            word = self.renderer.events.get()
            if len(word) == 1:
                missing = "" if word in self.renderer.letters else "  (no hand shape for this letter yet)"
                self.caption.configure(text=f"Fingerspelling: {word}{missing}")
            else:
                self.caption.configure(text=word.replace("_SIGN", "").replace("_", " ").title())
        self.root.after(30, self._tick)

    def _show_guesses(self, guesses):
        self.guesses = guesses
        for k, b in enumerate(self.guess_btns):
            if k < len(guesses):
                word, p = guesses[k]
                b.configure(text=f"{k + 1}  {word}  {p:.0%}", state="normal", bg="#e8edf5")
            else:
                b.configure(text="", state="disabled", bg=PANEL)  # invisible until there are guesses

    # ---- actions
    def _key(self, event):
        if isinstance(event.widget, tk.Entry):
            return None  # typing, not a shortcut
        if event.keysym == "space":
            self.start_sign()
        elif event.char in "123":
            self.send_guess(int(event.char) - 1)
        return "break"

    def start_sign(self):
        if self.cam:
            self.cam.start_sign()

    def send_guess(self, k):
        if k < len(self.guesses):
            self.deaf_says(self.guesses[k][0], signed=True)
            self._show_guesses([])
            self.cam.state = "idle"
            self.cam_status.configure(text="Sent. Press Space to sign the next word.", fg=MUTED)

    def send_deaf_typed(self):
        text = self.deaf_entry.get().strip()
        if text:
            self.deaf_entry.delete(0, "end")
            self.deaf_says(text, signed=False)

    def deaf_says(self, text, signed):
        self.write_log("deaf", "Deaf person" + (" (signed)" if signed else ""), text)
        if self.speak.get():
            say(text)

    def send_hearing(self):
        text = self.hearing_entry.get().strip()
        if not text:
            return
        if not self.to_gloss:
            self.write_log("note", "Still loading English to ISL, try again in a moment.")
            return
        self.hearing_entry.delete(0, "end")
        gloss = self.to_gloss(text)
        played = self.renderer.play(gloss)
        self.write_log("hearing", "Hearing person", text)
        self.write_log("note", f"    ISL: {gloss}" + (f"    (played as {played})" if played != gloss else ""))
        self.gloss_label.configure(text=f"Last message in ISL: {gloss}")

    def write_log(self, tag, who, text=None):
        self.log.configure(state="normal")
        if text is None:
            self.log.insert("end", who + "\n", tag)
        else:
            self.log.insert("end", who + ": ", tag)
            self.log.insert("end", text + "\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def close(self):
        if self.cam:
            self.cam.stop.set()
        self.renderer.close()
        self.root.destroy()


def say(text):
    """Reads text aloud with the Windows speech voice, without blocking the window."""
    if os.name != "nt":
        return
    subprocess.Popen(["powershell", "-NoProfile", "-Command",
                      "Add-Type -AssemblyName System.Speech; "
                      "(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak($env:ISL_SAY)"],
                     env=dict(os.environ, ISL_SAY=text), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-camera", action="store_true", help="typing only, don't open the webcam")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--model", default=os.path.join(chat_client.REPO, "models", "include_position.pt"))
    ap.add_argument("--seconds", type=float, default=2.5, help="length of each signed take")
    ap.add_argument("--renderer", default=os.path.join(HERE, "renderer.exe" if os.name == "nt" else "renderer"))
    ap.add_argument("--no-fingerspell", action="store_true")
    ap.add_argument("--mute", action="store_true", help="don't read signed messages aloud")
    args = ap.parse_args()
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text on scaled screens
        except (AttributeError, OSError):
            pass
    App(args).root.mainloop()


if __name__ == "__main__":
    main()
