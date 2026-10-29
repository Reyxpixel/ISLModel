"""Load recorded takes from one or more dataset folders.

Each folder is laid out the way mpipe.py and include_to_landmarks.py write it:
    <folder>/<word>/seq_NNN/landmarks/hands.npy
If the folder has an index.csv with a "split" column (INCLUDE does), that split is used.
Otherwise every take is assigned to train/val/test by a fixed per-word split, so a new folder
(e.g. Vansh's recordings) works without any code changes. Extra files such as face_coords.npy
are ignored for now.
"""
import csv
import os
import random

import numpy as np

SPLIT_FRACTIONS = {"train": 0.7, "val": 0.1, "test": 0.2}


def _auto_split(seqs, seed):
    seqs = sorted(seqs)
    random.Random(seed).shuffle(seqs)
    n = len(seqs)
    n_test = max(1, round(n * SPLIT_FRACTIONS["test"])) if n >= 3 else 0
    n_val = max(1, round(n * SPLIT_FRACTIONS["val"])) if n >= 5 else 0
    out = {s: "test" for s in seqs[:n_test]}
    out.update({s: "val" for s in seqs[n_test:n_test + n_val]})
    out.update({s: "train" for s in seqs[n_test + n_val:]})
    return out


def load_folder(folder, seed=0):
    """Returns a list of dicts: {"word", "seq", "split", "hands", "source"}."""
    index = os.path.join(folder, "index.csv")
    split_of = {}
    if os.path.exists(index):
        for row in csv.DictReader(open(index, encoding="utf-8")):
            if row.get("split"):
                split_of[(row["word"], row["seq"])] = row["split"]

    takes = []
    for word in sorted(os.listdir(folder)):
        word_dir = os.path.join(folder, word)
        if not os.path.isdir(word_dir):
            continue
        seqs = [s for s in os.listdir(word_dir)
                if s.startswith("seq_") and os.path.exists(os.path.join(word_dir, s, "landmarks", "hands.npy"))]
        auto = _auto_split(seqs, seed)
        for seq in sorted(seqs):
            takes.append({
                "word": word,
                "seq": seq,
                "split": split_of.get((word, seq), auto[seq]),
                "hands": np.load(os.path.join(word_dir, seq, "landmarks", "hands.npy")),
                "source": folder,
            })
    return takes


def load_folders(folders, seed=0):
    takes = []
    for folder in folders:
        takes += load_folder(folder, seed)
    return takes
