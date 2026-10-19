readme.md

Repo for the development of a Bidirectional ISL Model using BiSTL

## Data collection

Hand landmarks are extracted with MediaPipe's hand landmarker. Every take is saved as
`hands.npy` with shape `(frames, 2, 21, 3)`: 2 hand slots, 21 joints each, x/y/z in metres
relative to the hand's own centre (world landmarks). This captures hand shape only, not where
the hand is in the frame. A missing hand is all zeros.

**Hand slots are swapped.** `mpipe.py` mirrors the frame before detection, which flips
MediaPipe's left/right label, so slot 0 (labelled "Right") holds the signer's *left* hand and
slot 1 the *right* hand. Tested: a right-handed "hello" lands in slot 1. All data here uses this
same convention, so it is consistent; swap the slots when loading (`hands[:, ::-1]`) if a
model needs slot 0 to be the right hand.

Setup:

```
pip install -r requirements.txt
curl -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
curl -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
```

- `mpipe.py` records takes from the webcam into `dataset_landmarks_only/<word>/seq_NNN/`.
  Enter the word and take length, press `s` in the camera window to start, `q` to stop.
- `include_to_landmarks.py` converts the [INCLUDE dataset](https://zenodo.org/records/4010759)
  (AI4Bharat, CC BY 4.0) zips into the same format, with an `index.csv` of the official splits:
  `python include_to_landmarks.py --src <zip folder> --splits <split folder>`

Model files and landmark data are not committed (see `.gitignore`).
