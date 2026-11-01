"""Run a trained model on recorded takes, without a webcam or retraining.

    python predict.py "../ISL/E words"                        # every word folder inside
    python predict.py ../dataset_landmarks_only/hello         # one word
    python predict.py ../dataset_landmarks_only/hello/seq_001 # one take

Prints the top guess for each take and, when the folder names are words the model knows,
how many it got right.
"""
import argparse
import os

import numpy as np
import torch

from isl_model.model import SignBiLSTM
from isl_model.preprocess import preprocess


def find_takes(path):
    """Yields (word, take folder) for a dataset folder, a word folder or a single take."""
    path = os.path.normpath(path)
    if os.path.exists(os.path.join(path, "landmarks", "hands.npy")):
        yield os.path.basename(os.path.dirname(path)), path
        return
    for name in sorted(os.listdir(path)):
        sub = os.path.join(path, name)
        if name.startswith("seq_") and os.path.exists(os.path.join(sub, "landmarks", "hands.npy")):
            yield os.path.basename(path), sub
        elif os.path.isdir(sub) and not name.startswith("seq_"):
            yield from find_takes(sub)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="dataset folder, word folder or single seq_NNN folder")
    ap.add_argument("--model", default="models/include_position.pt")
    args = ap.parse_args()

    ckpt = torch.load(args.model, map_location="cpu")
    labels, with_position = ckpt["labels"], ckpt.get("with_position", False)
    model = SignBiLSTM(ckpt["features"], len(labels))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    right = known = total = 0
    for word, take in find_takes(args.path):
        lm = os.path.join(take, "landmarks")
        load = lambda n: np.load(os.path.join(lm, n)) if os.path.exists(os.path.join(lm, n)) else None
        x = preprocess(load("hands.npy"), load("hands_screen.npy"), load("face_coords.npy"), with_position=with_position)
        with torch.no_grad():
            probs = torch.softmax(model(torch.from_numpy(x)[None]), 1)[0]
        i = int(probs.argmax())
        label = word.lower()
        if label not in labels:          # INCLUDE words are saved as e.g. "thank_you"
            label = label.replace(" ", "_")
        mark = ""
        if label in labels:
            known += 1
            right += labels[i] == label
            mark = "  ok" if labels[i] == label else "  WRONG"
        total += 1
        print(f"{os.path.relpath(take, args.path) if take != os.path.normpath(args.path) else take}: "
              f"{labels[i]} ({probs[i]:.0%}){mark}")
    if known:
        print(f"\n{right}/{known} correct on takes of words this model knows ({total} takes checked)")
    elif total:
        print(f"\n{total} takes checked; none of these folder names are words this model knows")


if __name__ == "__main__":
    main()
