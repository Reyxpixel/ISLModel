"""Turn one recorded take into the fixed-size feature array the model reads.

Used for training and for live prediction, so both see exactly the same input.

Inputs, as saved by mpipe.py / include_to_landmarks.py:
  hands         (frames, 2, 21, 3)  hand shape (world landmarks, metres, relative to the hand)
  hands_screen  (frames, 2, 21, 3)  where the hands are in the frame, 0-1   [optional]
  face          (frames, 478, 3)    where the face is in the frame, 0-1     [optional]
  Hand slots follow mpipe.py's convention (slot 0 holds the signer's left hand because the
  frame is mirrored before detection). All data uses the same convention, so nothing is swapped.
  A hand or face that wasn't detected is all zeros.

Output: (SEQ_LEN, n_features) float32.
  Shape features: per hand 63 coordinates + 1 "hand present" flag = 128.
  With with_position=True, 5 more: each hand's palm centre relative to the face (x, y), measured
  in face widths/heights so it doesn't depend on camera distance or frame size, plus a flag
  saying whether a face was found in the take.
"""
import numpy as np

SEQ_LEN = 32
SHAPE_FEATURES = 2 * (21 * 3 + 1)
POSITION_FEATURES = 5
FEATURES = SHAPE_FEATURES       # shape-only models; position models use n_features(True)
COORD_SCALE = 10.0              # world landmarks are in metres (~0.1); bring them to ~1
POSITION_SCALE = 0.25           # palm offsets are a few face sizes; bring them to ~1
PALM = [0, 5, 9, 13, 17]        # wrist and finger bases


def n_features(with_position):
    return SHAPE_FEATURES + (POSITION_FEATURES if with_position else 0)


def _position_features(hands_screen, face, present):
    n = len(present)
    out = np.zeros((n, POSITION_FEATURES), np.float32)
    if hands_screen is None or face is None:
        return out
    face = np.asarray(face, np.float32)
    has_face = ~np.all(face == 0, axis=(1, 2))
    if not has_face.any():
        return out
    # Frames where the face was missed borrow the nearest frame where it was found
    found = np.flatnonzero(has_face)
    nearest = found[np.abs(np.arange(n)[:, None] - found[None]).argmin(1)]
    f = face[nearest, :, :2]
    centre = f.mean(axis=1)                                      # (n, 2)
    size = np.maximum(f.max(axis=1) - f.min(axis=1), 1e-3)       # face width, height (n, 2)
    palm = np.asarray(hands_screen, np.float32)[:, :, PALM, :2].mean(axis=2)   # (n, 2 hands, 2)
    rel = (palm - centre[:, None]) / size[:, None] * POSITION_SCALE
    rel = np.clip(rel, -5, 5) * present[:, :, None]
    out[:, :4] = rel.reshape(n, 4)
    out[:, 4] = 1.0
    return out


def preprocess(hands, hands_screen=None, face=None, with_position=False, seq_len=SEQ_LEN):
    hands = np.asarray(hands, dtype=np.float32).reshape(-1, 2, 21, 3)
    present = ~np.all(hands == 0, axis=(2, 3))              # (frames, 2)

    feats = np.concatenate([
        hands.reshape(len(hands), 2, 63) * COORD_SCALE,
        present[:, :, None].astype(np.float32),
    ], axis=2).reshape(len(hands), SHAPE_FEATURES)
    if with_position:
        feats = np.concatenate([feats, _position_features(hands_screen, face, present)], axis=1)

    # Drop the frames before the first and after the last detected hand (getting into position)
    any_hand = np.flatnonzero(present.any(axis=1))
    if len(any_hand):
        feats = feats[any_hand[0]:any_hand[-1] + 1]

    # Resample to a fixed number of frames. This also evens out 25 FPS (INCLUDE) vs 30 FPS (webcam).
    # Nearest frame rather than interpolation, so a missing hand never gets blended with a real one.
    idx = np.round(np.linspace(0, len(feats) - 1, seq_len)).astype(int)
    return feats[idx]
