"""Check web/preprocess.js builds the same model input as isl_model/preprocess.py, and that the
ONNX model then gives the same answer as the PyTorch model.

    python web/test_preprocess.py ../dataset_mmkay_webcam ../mudra_bubbles/game_data

Takes a few recorded takes from each folder, runs both versions, and prints the largest
difference and how many top-1 guesses agree. Needs Node.js, onnx and onnxruntime.
"""
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import onnxruntime as ort
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from isl_model.model import SignBiLSTM                     # noqa: E402
from isl_model.preprocess import preprocess                # noqa: E402

NODE_SCRIPT = """
import { readFileSync, writeFileSync } from "fs";
import { preprocess } from "./preprocess.mjs";
const { cfg, takes } = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = takes.map((t) => Array.from(preprocess(t, cfg)));
writeFileSync(process.argv[3], JSON.stringify(out));
"""


def main():
    folders = sys.argv[1:] or [os.path.join(HERE, "..", "..", "dataset_mmkay_webcam")]
    cfg = json.load(open(os.path.join(HERE, "model", "config.json")))
    takes = []
    for folder in folders:
        found = sorted(glob.glob(os.path.join(folder, "*", "seq_*", "landmarks", "hands.npy")))
        takes += random.Random(0).sample(found, min(15, len(found)))
    data, ref = [], []
    for path in takes:
        d = os.path.dirname(path)
        hands = np.load(path)
        screen = np.load(os.path.join(d, "hands_screen.npy"))
        face = np.load(os.path.join(d, "face_coords.npy"))
        data.append([{"hands": hands[t].tolist(), "handsScreen": screen[t].tolist(), "face": face[t].tolist()}
                     for t in range(len(hands))])
        ref.append(preprocess(hands, screen, face, with_position=cfg["with_position"]))

    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(HERE, "preprocess.js"), os.path.join(tmp, "preprocess.mjs"))
        with open(os.path.join(tmp, "run.mjs"), "w") as f:
            f.write(NODE_SCRIPT)
        with open(os.path.join(tmp, "in.json"), "w") as f:
            json.dump({"cfg": cfg, "takes": data}, f)
        subprocess.run(["node", "run.mjs", "in.json", "out.json"], cwd=tmp, check=True)
        js = [np.array(x, np.float32).reshape(cfg["seq_len"], cfg["n_features"])
              for x in json.load(open(os.path.join(tmp, "out.json")))]

    ckpt = torch.load(os.path.join(HERE, "..", "models", "include_position.pt"), map_location="cpu")
    model = SignBiLSTM(ckpt["features"], len(ckpt["labels"]))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    sess = ort.InferenceSession(os.path.join(HERE, "model", "model.onnx"))
    diff, agree = 0.0, 0
    for r, j in zip(ref, js):
        diff = max(diff, float(np.abs(r - j).max()))
        with torch.no_grad():
            torch_top = int(model(torch.from_numpy(r)[None]).argmax())
        onnx_top = int(sess.run(None, {"features": j[None]})[0].argmax())
        agree += torch_top == onnx_top
    print(f"{len(takes)} takes: largest feature difference {diff:.2e}, "
          f"top guess agrees on {agree}/{len(takes)} (Python + PyTorch vs JS + ONNX)")


if __name__ == "__main__":
    main()
