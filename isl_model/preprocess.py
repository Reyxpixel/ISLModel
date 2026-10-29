"""Turn one recorded take into the fixed-size feature array the model reads.

Used for training and for live prediction, so both see exactly the same input.

Input: hands array from mpipe.py / include_to_landmarks.py, shape (frames, 2, 21, 3).
  Hand slots follow mpipe.py's convention (slot 0 holds the signer's left hand because the
  frame is mirrored before detection). All data uses the same convention, so nothing is swapped.
  A hand that wasn't detected is all zeros.
Output: (SEQ_LEN, FEATURES) float32.
"""
import numpy as np

SEQ_LEN = 32                    # every take is resampled to this many frames
FEATURES = 2 * (21 * 3 + 1)     # per hand: 63 coordinates + 1 "hand present" flag
COORD_SCALE = 10.0              # world landmarks are in metres (~0.1); bring them to ~1


def preprocess(hands, seq_len=SEQ_LEN):
    hands = np.asarray(hands, dtype=np.float32).reshape(-1, 2, 21, 3)
    present = ~np.all(hands == 0, axis=(2, 3))              # (frames, 2)

    # Drop the frames before the first and after the last detected hand (getting into position)
    any_hand = np.flatnonzero(present.any(axis=1))
    if len(any_hand):
        hands = hands[any_hand[0]:any_hand[-1] + 1]
        present = present[any_hand[0]:any_hand[-1] + 1]

    feats = np.concatenate([
        hands.reshape(len(hands), 2, 63) * COORD_SCALE,
        present[:, :, None].astype(np.float32),
    ], axis=2).reshape(len(hands), FEATURES)

    # Resample to a fixed number of frames. This also evens out 25 FPS (INCLUDE) vs 30 FPS (webcam).
    # Nearest frame rather than interpolation, so a missing hand never gets blended with a real one.
    idx = np.round(np.linspace(0, len(feats) - 1, seq_len)).astype(int)
    return feats[idx]
