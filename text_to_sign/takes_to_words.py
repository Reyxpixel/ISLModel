"""Turn our recorded takes into animations for Kunal's renderer (words.data format).

    python text_to_sign/takes_to_words.py ../dataset_include_positions ../dataset_mmkay_webcam
    python text_to_sign/takes_to_words.py ../dataset_include_positions --words hello thank_you

For every word folder it picks the cleanest take (the one where the hands are found in the most
frames), takes each hand's screen position from hands_screen.npy and writes it in the layout
renderer.cpp reads: the word name, then "// Frame N" and 21 (one hand) or 42 (two hands) x y
pairs per frame. Words already in Kunal's words.data are left as they are unless --replace.
A hand that just hangs at rest is left out, and one-letter words get a _SIGN suffix (I -> I_SIGN),
because the renderer always fingerspells one-letter tokens. chat_client.py maps them back.

The result is written to words_combined.data next to this script: Kunal's words first, then
ours. Point the renderer at it by renaming it to words.data (keep a copy of his original).
"""
import argparse
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def read_words_data(path):
    """Splits a words.data file into {WORD: text block} keeping Kunal's text exactly."""
    blocks, order, current = {}, [], None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.split("//", 1)[0].strip()
            if stripped and re.fullmatch(r"[A-Za-z_]+", stripped):
                current = stripped.upper()
                order.append(current)
                blocks[current] = [line]
            elif current:
                blocks[current].append(line)
    return order, {w: "".join(b) for w, b in blocks.items()}


def takes_in(folder):
    """Yields (word, seq folder) for every take with hands_screen.npy in a dataset folder."""
    for word in sorted(os.listdir(folder)):
        wdir = os.path.join(folder, word)
        if not os.path.isdir(wdir):
            continue
        for seq in sorted(os.listdir(wdir)):
            if os.path.exists(os.path.join(wdir, seq, "landmarks", "hands_screen.npy")):
                yield word, os.path.join(wdir, seq)


def fill_gaps(track):
    """track: (frames, 21, 2), all-zero where the hand wasn't found. Fills gaps from the
    nearest frame where it was found. Returns None if the hand is never found."""
    seen = np.any(track != 0, axis=(1, 2))
    if not seen.any():
        return None
    idx = np.where(seen)[0]
    nearest = idx[np.abs(np.arange(len(track))[:, None] - idx[None, :]).argmin(1)]
    return track[nearest]


def take_to_frames(seq, min_hand_share, flip, rest_y=0.68):
    screen = np.load(os.path.join(seq, "landmarks", "hands_screen.npy"))[..., :2]  # (F, 2, 21, 2)
    found = np.any(screen != 0, axis=(2, 3))                                       # (F, 2)
    any_hand = found.any(1)
    if not any_hand.any():
        return None, 0.0
    first, last = np.where(any_hand)[0][[0, -1]]
    screen, found = screen[first:last + 1], found[first:last + 1]
    hands, used = [], []
    for h in range(2):
        if found[:, h].mean() >= min_hand_share:     # ignore a hand seen only in a few frames
            filled = fill_gaps(screen[:, h])
            if filled is not None:
                hands.append(filled)
                used.append(h)
    if not hands:
        return None, 0.0
    if len(hands) == 2:
        # Drop a hand that just hangs at rest: it barely moves, sits below the signing hand and
        # low in the frame (a still base hand in a two-handed sign is higher, at chest level).
        # A resting hand would make the renderer shrink the sign.
        motion = [np.ptp(hd[:, 0], axis=0).max() for hd in hands]          # wrist travel
        for a, b in ((0, 1), (1, 0)):
            low = hands[a][:, 0, 1].mean()
            if motion[a] < 0.25 * motion[b] and low > hands[b][:, 0, 1].mean() and low > rest_y:
                del hands[a], used[a]
                break
    frames = np.concatenate(hands, axis=1)                                          # (F, 21|42, 2)
    if flip:
        frames[..., 0] = 1.0 - frames[..., 0]
    quality = float(np.mean([found[:, h].mean() for h in used]))
    return frames, quality


def to_block(word, frames):
    lines = [word + "\n"]
    for i, fr in enumerate(frames):
        lines.append(f"// Frame {i}\n")
        lines.append(" ".join(f"{v:.6f}" for v in fr.reshape(-1)) + "\n")
    return "".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+", help="dataset folders (<folder>/<word>/seq_NNN/landmarks)")
    ap.add_argument("--words", nargs="*", help="only these words (folder names)")
    original = os.path.join(HERE, "words_kunal_original.data")  # kept copy once words.data is replaced
    ap.add_argument("--base", default=original if os.path.exists(original) else os.path.join(HERE, "words.data"),
                    help="Kunal's original words.data")
    ap.add_argument("--pick", nargs="*", default=[], metavar="WORD=SEQ_FOLDER",
                    help="use this take for a word, e.g. I_SIGN=../dataset_include_positions/i/seq_017")
    ap.add_argument("--out", default=os.path.join(HERE, "words_combined.data"))
    ap.add_argument("--replace", action="store_true", help="use our take even if Kunal has the word")
    ap.add_argument("--flip", action="store_true", help="mirror left/right (if signs look reversed)")
    ap.add_argument("--min-hand-share", type=float, default=0.3,
                    help="a hand must be found in at least this share of frames to be drawn")
    ap.add_argument("--rest-y", type=float, default=0.68,
                    help="a still hand lower than this (0 top, 1 bottom) counts as resting")
    args = ap.parse_args()

    order, blocks = read_words_data(args.base)
    takes = {}  # WORD -> [(quality, frames, seq)]
    for folder in args.folders:
        for word, seq in takes_in(folder):
            if args.words and word not in args.words:
                continue
            frames, quality = take_to_frames(seq, args.min_hand_share, args.flip, args.rest_y)
            name = word.upper().replace(" ", "_")
            if len(name) == 1:
                name += "_SIGN"   # renderer.cpp plays any one-letter token as a letter, so I -> I_SIGN
            if frames is not None and len(frames) >= 5:
                takes.setdefault(name, []).append((quality, frames, seq))

    # Per word: among the takes where the hands are found almost as often as in the best one,
    # pick the one whose length is closest to the word's usual length (skips cut-off takes).
    best = {}
    for name, cands in takes.items():
        median = np.median([len(f) for _, f, _ in cands])
        cands = [c for c in cands if len(c[1]) >= 0.6 * median] or cands  # drop cut-off takes
        top = max(q for q, _, _ in cands)
        good = [c for c in cands if c[0] >= top - 0.05]
        best[name] = min(good, key=lambda c: abs(len(c[1]) - median))
    for pick in args.pick:                       # hand-picked takes win
        name, seq = pick.split("=", 1)
        frames, quality = take_to_frames(seq, args.min_hand_share, args.flip, args.rest_y)
        if frames is None:
            raise SystemExit(f"--pick {pick}: no hands found in that take")
        best[name.upper()] = (quality, frames, seq)

    added = []
    for name in sorted(best):
        if name in blocks and not args.replace:
            continue
        if name not in blocks:
            order.append(name)
        blocks[name] = to_block(name, best[name][1])
        added.append(name)
        q, frames, seq = best[name]
        print(f"{name:16s} {len(frames):3d} frames, {frames.shape[1] // 21} hand(s), "
              f"hands found {q:.0%}  <- {seq}")

    with open(args.out, "w", encoding="utf-8") as f:
        for name in order:
            f.write(blocks[name])
    print(f"\n{len(added)} words added, {len(order)} in total -> {args.out}")


if __name__ == "__main__":
    main()
