"""Export a trained model to ONNX for the browser (onnxruntime-web), plus its labels and settings.

    python web/export_onnx.py                                   # models/include_position.pt
    python web/export_onnx.py --model models/include_plus_vansh.pt --out web/model_vansh

Writes <out>/model.onnx and <out>/config.json, then checks the ONNX model gives the same
probabilities as PyTorch on a few random inputs. Needs: pip install onnx onnxruntime
"""
import argparse
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from isl_model.model import SignBiLSTM                     # noqa: E402
from isl_model import preprocess as pp                     # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/include_position.pt")
    ap.add_argument("--out", default="web/model")
    args = ap.parse_args()

    ckpt = torch.load(args.model, map_location="cpu")
    model = SignBiLSTM(ckpt["features"], len(ckpt["labels"]))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    os.makedirs(args.out, exist_ok=True)
    onnx_path = os.path.join(args.out, "model.onnx")

    x = torch.zeros(1, pp.SEQ_LEN, ckpt["features"])
    torch.onnx.export(model, x, onnx_path, input_names=["features"], output_names=["logits"],
                      dynamic_axes={"features": {0: "batch"}, "logits": {0: "batch"}},
                      opset_version=17, dynamo=False)

    config = {
        "labels": ckpt["labels"],
        "with_position": bool(ckpt.get("with_position", False)),
        "seq_len": pp.SEQ_LEN,
        "n_features": ckpt["features"],
        "coord_scale": pp.COORD_SCALE,
        "position_scale": pp.POSITION_SCALE,
        "palm": pp.PALM,
        "input": "features: float32 [batch, seq_len, n_features]",
        "output": "logits: float32 [batch, n_labels], softmax for probabilities",
    }
    with open(os.path.join(args.out, "config.json"), "w") as f:
        json.dump(config, f, indent=1)

    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path)
    xs = np.random.default_rng(0).normal(size=(4, pp.SEQ_LEN, ckpt["features"])).astype(np.float32)
    with torch.no_grad():
        ref = torch.softmax(model(torch.from_numpy(xs)), 1).numpy()
    got = sess.run(None, {"features": xs})[0]
    got = np.exp(got - got.max(1, keepdims=True)); got /= got.sum(1, keepdims=True)
    print(f"{len(ckpt['labels'])} signs, {ckpt['features']} features, position {config['with_position']}")
    print(f"wrote {onnx_path} ({os.path.getsize(onnx_path) / 1e6:.1f} MB); max difference vs PyTorch {np.abs(ref - got).max():.2e}")


if __name__ == "__main__":
    main()
