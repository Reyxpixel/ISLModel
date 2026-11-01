# ISLModel

Repo for the development of a Bidirectional ISL Model using BiLSTM.

This part covers sign → text: webcam → MediaPipe hand (and face) landmarks → BiLSTM classifier.

| File | What it does |
|---|---|
| `mpipe.py` | Records signs from the webcam and saves the landmarks for each take |
| `include_to_landmarks.py` | Converts the INCLUDE dataset videos into the same format |
| `train.py` | Trains the BiLSTM and reports test accuracy + a confusion matrix |
| `live_demo.py` | Sign in front of the webcam and see what the model predicts |
| `isl_model/` | Data loader, preprocessing and the model, shared by training and the demo |

## Quick start: test the live demo

1. **Install** (Python 3.10 or newer, and a webcam):
   ```
   pip install -r requirements.txt
   ```
2. **Download the two MediaPipe model files** into this folder:
   ```
   curl -o hand_landmarker.task https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
   curl -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
   ```
3. **Get some data** (see [Getting the data](#getting-the-data)). Data and trained models are not
   in the repo because they're too big for git.
4. **Train a model** (a few minutes on a GPU, longer on CPU):
   ```
   python train.py --data ../dataset_include_landmarks --out runs/latest
   ```
   It prints the test accuracy and saves `model.pt`, `report.txt` (per-sign scores) and
   `confusion_matrix.png` in `runs/latest/`.
5. **Run the demo:**
   ```
   python live_demo.py --model runs/latest/model.pt
   ```
   Press **space**, get your hands ready during the 2-second countdown, then sign once. It shows
   its top 3 guesses. Press **q** to quit. Do one sign per take, and keep your face and both hands
   in view.

## Getting the data

Every dataset folder has the same layout, which is what `mpipe.py` writes:

```
<folder>/<word>/seq_001/landmarks/hands.npy
<folder>/<word>/seq_002/landmarks/hands.npy
...
```

Pass one or more such folders to `train.py --data`. The word comes from the folder name.

- **Team recordings:** in the team Google Drive (ask in the group for the link). Download and unzip
  it. Each letter folder (`C words`, `E words`, ...) is one dataset folder:
  ```
  python train.py --data "../ISL/C words" "../ISL/E words" "../ISL/F words" "../ISL/G words"
  ```
- **INCLUDE** (AI4Bharat, CC BY 4.0): download the category zips from
  [Zenodo](https://zenodo.org/records/4010759) and the train/test split files, then convert:
  ```
  python include_to_landmarks.py --src <folder with the zips> --splits <folder with include_train.txt etc.> --out ../dataset_include_positions
  ```
  This also saves hand and face positions, so the result works with `--position`. It writes an
  `index.csv` with INCLUDE's official train/val/test split, which `train.py` uses automatically.
- **Mixing them** is just listing several folders after `--data`. Folders without an `index.csv`
  get a fixed 70/10/20 train/val/test split per word.

## Recording new signs

```
python mpipe.py
```

Type the word and the take length in seconds, click the camera window and press **s**. It keeps
recording takes one after another (2-second countdown before each) until you press **q**.

- Set `ENABLE_FACE_TRACKING = True` (top of `mpipe.py`) for the face-on set. Hand position is
  measured relative to the face, so only face-on recordings can be used with `--position`.
- Make each take long enough to fit the whole sign, and have your hands ready when the countdown
  ends.
- If the script is closed in the middle of a take, delete that word's `seq_temp` folder before
  recording again, otherwise the next recording crashes.

## Training options

```
python train.py --data <folders...> [--position] [--out runs/name] [--epochs 200] [--seed 0]
```

- `--position` also uses where each hand is relative to the face. It needs `hands_screen.npy` and
  `face_coords.npy` in every take, so use it with INCLUDE converted as above or recordings made
  with face tracking on.
- The demo picks up whether a model was trained with `--position` by itself.

## What's saved per take

| File | Shape | Contents |
|---|---|---|
| `hands.npy` | (frames, 2, 21, 3) | Hand shape: 21 joints per hand, in metres, relative to the hand itself |
| `hands_screen.npy` | (frames, 2, 21, 3) | Where each hand is in the frame (0 to 1) |
| `face_coords.npy` | (frames, 478, 3) | Face points in the frame (0 to 1), face tracking on only |
| `face_blendshapes.npy` | (frames, 52) | Facial expression scores, face tracking on only |

A hand or face that wasn't detected is saved as all zeros.

**Hand slots are swapped.** `mpipe.py` mirrors the frame before detection, which flips
MediaPipe's left/right label, so slot 0 holds the signer's *left* hand and slot 1 the *right*.
All the data uses this same convention, so it's consistent and nothing needs changing.

## Results so far

On the 38 INCLUDE signs (official test split, 95 takes, 3 training runs each):

| Model | Test accuracy |
|---|---|
| Hand shape only | 93.7%, 94.7%, 94.7% |
| With hand position | 95.8%, 93.7%, 96.8% |

Hand position fixes "I" vs "you", which differ mainly in where the finger points. Adding the
team's 20 C to G words (2,400 takes) gives 98.4% overall, but their test takes come from the same
person as their training takes, so expect lower accuracy on new signers.

## Known limitations

- Each sign has only about 15 INCLUDE takes, so live accuracy on a new person is lower than the
  test numbers, especially for similar-looking signs (he vs hello, tomorrow vs time).
- The demo records a fixed 2.5 s take (`--seconds` changes it). Very short signs include some
  still frames at the end.
