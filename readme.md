# ISLModel

Repo for the development of a Bidirectional ISL Model using BiLSTM.

This part covers sign → text: webcam → MediaPipe hand (and face) landmarks → BiLSTM classifier.

| File | What it does |
|---|---|
| `live_demo.py` | Sign in front of the webcam and see what the model predicts |
| `predict.py` | Run a trained model on recorded takes, no webcam needed |
| `models/` | Two trained models, ready to use, with their results |
| `train.py` | Trains the BiLSTM and reports test accuracy + a confusion matrix |
| `mpipe.py` | Records signs from the webcam and saves the landmarks for each take |
| `include_to_landmarks.py` | Converts the INCLUDE dataset videos into the same format |
| `reextract.py` | Re-extracts landmarks from the videos `mpipe.py` saves, no re-recording needed |
| `isl_model/` | Data loader, preprocessing and the model, shared by everything above |
| `*.task` | MediaPipe's hand and face models (from Google), used by all the scripts |

## Quick start: try the live demo

Needs Python 3.10 or newer and a webcam. Run everything from this folder.

```
pip install -r requirements.txt
python live_demo.py
```

Press **space**, get your hands ready during the 2-second countdown, then sign once. It shows its
top 3 guesses. Press **q** to quit. Do one sign per take, and keep your face and both hands in view.

It knows these 38 signs: afternoon, alright, evening, friday, good afternoon, good evening,
good morning, good night, he, hello, hour, how are you, i, it, minute, monday, month, morning,
night, pleased, saturday, second, she, sunday, thank you, they, thursday, time, today, tomorrow,
tuesday, we, wednesday, week, year, yesterday, you, you (plural). Reliable ones to start with:
hello, thank you, we, how are you. Reference videos for each sign are in the INCLUDE dataset.

To try the model that also knows the team's 20 C to G words (cabbage, cake, chew, cone,
confident, egg, enemy, eraser, erect, escape, face, father, fear, few, fill, gas stove, ghost,
give, go, grow):

```
python live_demo.py --model models/include_plus_vansh.pt
```

## The trained models

| Model | Signs | Uses | Test accuracy |
|---|---|---|---|
| `models/include_position.pt` (default) | 38 INCLUDE signs | hand shape + hand position relative to the face | 96.8% (92/95) |
| `models/include_plus_vansh.pt` | 38 INCLUDE + 20 team words | hand shape only | 98.4% (566/575) |

Each has a confusion matrix (`*_confusion.png`) and per-sign scores (`*_report.txt`) next to it.
Test takes come from the same signers as the training takes, so expect lower accuracy on new
people.

## Test on recordings without a webcam

```
python predict.py ../dataset_landmarks_only/hello
python predict.py "../ISL/E words" --model models/include_plus_vansh.pt
```

Point it at a word folder, a folder of word folders, or a single `seq_NNN` take. It prints the
top guess for each take and how many it got right. Note that the team's recordings were also used
for training `include_plus_vansh.pt`, so it will score near 100% on them.

## Train your own model

Get the data first (next section), then:

```
python train.py --data ../dataset_include_landmarks --out runs/latest
python live_demo.py --model runs/latest/model.pt
```

Training takes a few minutes on a GPU, longer on CPU. It prints the test accuracy and saves
`model.pt`, `report.txt` and `confusion_matrix.png` in the `--out` folder.

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
- Each take is also saved as `video.mp4` (`SAVE_VIDEO = True`, about 0.3 to 0.7 MB per take). If the
  landmark extraction ever changes, re-run it on the saved videos instead of recording again:
  ```
  python reextract.py dataset_landmarks_only --out dataset_reextracted
  ```
  This always extracts with face tracking on, so a recording with video doesn't need a separate
  face-on and face-off set: both can come from the same takes.
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
