"""Train the BiLSTM sign classifier on one or more landmark dataset folders.

    python train.py --data ../dataset_include_landmarks
    python train.py --data ../dataset_include_landmarks ../dataset_landmarks_only   # add new recordings

Writes to --out (default runs/latest): model.pt, metrics.json, report.txt, confusion_matrix.png.
"""
import argparse
import json
import os
import random

import numpy as np
import torch
from torch import nn

from isl_model.data import load_folders
from isl_model.model import SignBiLSTM
from isl_model.preprocess import SEQ_LEN, n_features, preprocess


def augment(take, rng):
    """Small random changes so the model doesn't memorise exact takes."""
    hands = take["hands"].copy()
    present = ~np.all(hands == 0, axis=(2, 3))
    n = len(hands)
    # Random trim of up to 10% at each end, which also varies the signing speed after resampling
    a, b = rng.integers(0, max(1, n // 10) + 1, size=2)
    cut = slice(a, n - b or None)
    hands, present = hands[cut], present[cut]
    screen = take["hands_screen"][cut] if take.get("hands_screen") is not None else None
    face = take["face"][cut] if take.get("face") is not None else None
    if screen is not None:
        screen = screen + rng.normal(0, 0.005, screen.shape).astype(np.float32)
    # Random size (hand size varies between people) and a small tilt around the camera axis
    angle = rng.uniform(-0.2, 0.2)
    rot = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]], np.float32)
    hands = hands @ rot.T * rng.uniform(0.85, 1.15)
    hands += rng.normal(0, 0.002, hands.shape).astype(np.float32)
    hands[~present] = 0                          # keep missing hands exactly zero
    return hands, screen, face


def to_tensor(takes, labels, with_position, rng=None):
    def features(t):
        hands, screen, face = augment(t, rng) if rng is not None else (t["hands"], t.get("hands_screen"), t.get("face"))
        return preprocess(hands, screen, face, with_position=with_position)
    x = np.stack([features(t) for t in takes])
    y = np.array([labels.index(t["word"]) for t in takes])
    return torch.from_numpy(x), torch.from_numpy(y)


def evaluate(model, x, y, device):
    model.eval()
    with torch.no_grad():
        pred = model(x.to(device)).argmax(1).cpu()
    return (pred == y).float().mean().item(), pred


def save_confusion(y, pred, labels, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y, pred, labels=range(len(labels)))
    size = max(6, 0.32 * len(labels))
    fig, ax = plt.subplots(figsize=(size + 1.5, size))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels, rotation=90, fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    ax.set_xlabel("Predicted sign")
    ax.set_ylabel("True sign")
    ax.set_title(title)
    for i in range(len(labels)):
        for j in range(len(labels)):
            if cm[i, j]:
                ax.text(j, i, cm[i, j], ha="center", va="center", fontsize=7,
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True, help="one or more dataset folders")
    ap.add_argument("--out", default=os.path.join("runs", "latest"))
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--position", action="store_true",
                    help="also use where the hands are relative to the face (needs hands_screen.npy + face_coords.npy)")
    args = ap.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    takes = load_folders(args.data, seed=args.seed)
    labels = sorted({t["word"] for t in takes})
    split = {s: [t for t in takes if t["split"] == s] for s in ("train", "val", "test")}
    print(f"{len(takes)} takes, {len(labels)} signs | train {len(split['train'])}, "
          f"val {len(split['val'])}, test {len(split['test'])} | device {device}")

    if args.position:
        have = sum(t.get("hands_screen") is not None and t.get("face") is not None for t in takes)
        print(f"position data in {have}/{len(takes)} takes")
    x_val, y_val = to_tensor(split["val"], labels, args.position)
    x_test, y_test = to_tensor(split["test"], labels, args.position)
    features = n_features(args.position)

    model = SignBiLSTM(features, len(labels)).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    loss_fn = nn.CrossEntropyLoss(label_smoothing=0.1)

    os.makedirs(args.out, exist_ok=True)
    best_val, best_state, best_epoch = -1.0, None, 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        x, y = to_tensor(split["train"], labels, args.position, rng)    # fresh augmentation every epoch
        perm = torch.randperm(len(y))
        for i in range(0, len(y), 32):
            b = perm[i:i + 32]
            opt.zero_grad()
            loss = loss_fn(model(x[b].to(device)), y[b].to(device))
            loss.backward()
            opt.step()
        sched.step()
        val_acc, _ = evaluate(model, x_val, y_val, device)
        if val_acc > best_val:
            best_val, best_epoch = val_acc, epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        if epoch % 20 == 0 or epoch == 1:
            print(f"epoch {epoch:3d}  loss {loss.item():.3f}  val acc {val_acc:.3f}  (best {best_val:.3f} @ {best_epoch})")

    model.load_state_dict(best_state)
    test_acc, pred = evaluate(model, x_test, y_test, device)
    print(f"\nTest accuracy: {test_acc:.3f} ({int((pred == y_test).sum())}/{len(y_test)}), "
          f"best val {best_val:.3f} at epoch {best_epoch}")

    from sklearn.metrics import classification_report
    report = classification_report(y_test, pred, labels=range(len(labels)), target_names=labels, zero_division=0)
    open(os.path.join(args.out, "report.txt"), "w").write(report)
    save_confusion(y_test.numpy(), pred.numpy(), labels, os.path.join(args.out, "confusion_matrix.png"),
                   f"Test set: {test_acc:.1%} correct ({len(y_test)} takes, {len(labels)} signs)")
    torch.save({"state_dict": best_state, "labels": labels, "seq_len": SEQ_LEN, "features": features,
                "with_position": args.position},
               os.path.join(args.out, "model.pt"))
    json.dump({"test_accuracy": test_acc, "best_val_accuracy": best_val, "best_epoch": best_epoch,
               "n_test": len(y_test), "n_train": len(split["train"]), "n_val": len(split["val"]),
               "signs": labels, "data": args.data, "seed": args.seed,
               "with_position": args.position},
              open(os.path.join(args.out, "metrics.json"), "w"), indent=2)
    print("saved to", args.out)


if __name__ == "__main__":
    main()
