"""Build signs.npz, the signer's vocabulary, from our recorded takes.

    python build_signs.py ..\\dataset_include_positions ..\\dataset_include_more ..\\dataset_mmkay_webcam
    python build_signs.py <folders...> --pick I=..\\dataset_include_positions\\i\\seq_017

Each folder is <folder>/<word>/seq_NNN/landmarks with hands_screen.npy (needed), face_coords.npy
(places the hands relative to the face) and hands.npy (real finger depth). For every word it picks
the cleanest take of a normal length and saves it in scene units (see signer.py). Words in Kunal's
words.data that we don't have are still played from his file by the app.
"""
import argparse
import os

import numpy as np

from signer import take_to_scene

HERE = os.path.dirname(os.path.abspath(__file__))


def takes_in(folder):
    for word in sorted(os.listdir(folder)):
        wdir = os.path.join(folder, word)
        if not os.path.isdir(wdir):
            continue
        for seq in sorted(os.listdir(wdir)):
            lm = os.path.join(wdir, seq, "landmarks")
            if os.path.exists(os.path.join(lm, "hands_screen.npy")):
                yield word, lm


def score(lm):
    """(quality, active length): how often the hands and face are found while signing.
    Takes where the hands never come up above the chest (MediaPipe missed the signing hand and
    only found one hanging low) score much lower, since the signer would show nothing."""
    screen = np.load(os.path.join(lm, "hands_screen.npy"))
    present = np.any(screen != 0, axis=(2, 3))
    anyhand = present.any(1)
    if not anyhand.any():
        return 0.0, 0
    a, b = np.where(anyhand)[0][[0, -1]]
    seg = present[a:b + 1]
    used = [h for h in range(2) if seg[:, h].mean() >= 0.3]
    hand_q = float(np.mean([seg[:, h].mean() for h in used])) if used else 0.0
    face_q = 0.0
    fp = os.path.join(lm, "face_coords.npy")
    if os.path.exists(fp):
        face = np.load(fp)[a:b + 1]
        face_ok = np.any(face != 0, axis=(1, 2))
        face_q = float(face_ok.mean())
        if face_ok.any():
            chin = float(np.median(face[face_ok, 152, 1]))
            face_h = float(np.median(face[face_ok, 152, 1] - face[face_ok, 10, 1]))
            ys = screen[a:b + 1, :, :, 1][seg]          # (hands seen, 21) picture y, down is +
            highest = float(np.percentile(ys.min(1), 5))
            if face_h > 1e-3 and (highest - chin) / face_h > 2.3:
                face_q *= 0.25
                hand_q *= 0.4
    depth = 1.0 if os.path.exists(os.path.join(lm, "hands.npy")) else 0.8
    return hand_q * (0.6 + 0.4 * face_q) * depth, b - a + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--out", default=os.path.join(HERE, "signs.npz"))
    ap.add_argument("--pick", nargs="*", default=[], metavar="WORD=SEQ_FOLDER")
    args = ap.parse_args()

    cands = {}
    for folder in args.folders:
        for word, lm in takes_in(folder):
            name = word.upper().replace(" ", "_")
            if len(name) == 1:
                name += "_SIGN"          # the renderer spells one-letter tokens, so I -> I_SIGN
            q, n = score(lm)
            if n >= 5:
                cands.setdefault(name, []).append((q, n, lm))

    chosen = {}
    for name, cs in cands.items():
        median = np.median([n for _, n, _ in cs])
        cs = [c for c in cs if c[1] >= 0.6 * median] or cs       # skip cut-off takes
        top = max(q for q, _, _ in cs)
        good = [c for c in cs if c[0] >= top - 0.05]
        chosen[name] = min(good, key=lambda c: abs(c[1] - median))
    for pick in args.pick:
        name, seq = pick.split("=", 1)
        name = name.upper()
        if len(name) == 1:
            name += "_SIGN"
        lm = seq if seq.rstrip("\\/").endswith("landmarks") else os.path.join(seq, "landmarks")
        chosen[name] = (*score(lm), lm)

    out = {}
    for name in sorted(chosen):
        q, n, lm = chosen[name]
        # INCLUDE was converted at its native 25 fps; our webcam takes are 30 fps
        s = take_to_scene(lm, fps=25.0 if "include" in lm.lower() else 30.0)
        out[name + "_frames"] = s["frames"].astype(np.float16)
        out[name + "_present"] = s["present"]
        out[name + "_fps"] = np.float32(s["fps"])
        print(f"{name:16s} {len(s['frames']):3d} frames  quality {q:.2f}  <- {lm}")
    np.savez_compressed(args.out, **out)
    print(f"\n{len(chosen)} signs -> {args.out}")


if __name__ == "__main__":
    main()
