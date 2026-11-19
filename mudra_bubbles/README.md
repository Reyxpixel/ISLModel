# Mudra Bubbles

An ISL practice game that collects sign data while you play. Word bubbles float on the left and
your camera is on the right. Sign the glowing word and the bubble pops. Every take is saved in the
same format as `mpipe.py`, so it can go straight into `train.py` and `predict.py`.

## Run it

It uses the model, `isl_model/` and the `.task` files from the repo folder one level up, so there is
nothing new to install beyond `requirements.txt`.

```
cd mudra_bubbles
python mudra_bubbles.py                 # asks for the player's name
python mudra_bubbles.py --player manan
python mudra_bubbles.py --practice      # pops on any clean take, shows the model's guess only
```

Or double-click `play.bat`.

| Key | What it does |
|---|---|
| space | 2 s countdown, then sign the glowing word (2.5 s take, `--seconds` to change) |
| h | replay the how-to clip for the glowing word |
| n | skip this bubble |
| m | switch between model mode and practice mode |
| r | new round |
| q | quit |

A round is 10 targets. In **model mode** a bubble pops if the word is in the model's top 3
(100 points for top 1, 50 for top 2 or 3). In **practice mode** it pops whenever the hands were
seen for at least 30% of the take, and the model's guess is only shown. Use practice mode for words
the model doesn't know yet, or if the model is struggling with a new person or webcam.

Each take lasts a fixed number of seconds, not a fixed number of frames, because webcams drop to
fewer frames per second in a dim room.

## How-to clips

When a word becomes the target, a short clip of someone signing it plays (twice) in the camera
panel, mirrored so it matches your own camera view. Press space to start signing whenever you're
ready, or h to watch it again. `--no-guide` turns the automatic clip off.

The clips are in `guides/<word>.mp4`: 38 INCLUDE signs (AI4Bharat, CC BY 4.0, credit and source of
each clip in `guides/CREDITS.txt`) and 9 of the team's words recorded by Vansh (hammer, handkerchief,
hen, hole, horse, in, individual, introduction, iron). Drop in your own `guides/<word>.mp4` for any
other word. Words without a clip still play, just without the video.

## Words

Default: 21 words the model knows well: hello, thank you, we, how are you, I, you, they, she,
good morning, good night, good evening, and the team's words hammer, handkerchief, hen, hole, horse,
in, individual, introduction, iron, it. Pick your own with `--words hello we good_morning`; run with a
word the model doesn't know and it prints the list.

**New words** the model doesn't know yet can be recorded in practice mode:
`--practice --words water food mother`. They pop on any clean take, nothing is guessed, and once
each has 20 or so takes, retraining adds them to the model.

## Recording in different lighting and with different people

Every take saves the player name, an optional `--note` and the take's average brightness in
`meta.json`. So for each lighting setup, start a session with a note:

```
python mudra_bubbles.py --player manan --note "daylight, window behind"
python mudra_bubbles.py --player reyansh --note "night, tube light"
```

## What gets saved

`game_data/<word>/seq_NNN/`, one folder per take (`game_data/` is not committed to git; share it
on Drive like the other recordings):

| File | Contents |
|---|---|
| `landmarks/hands.npy` | (frames, 2, 21, 3) hand shape, same as mpipe.py |
| `landmarks/hands_screen.npy` | (frames, 2, 21, 3) where the hands are in the frame |
| `landmarks/face_coords.npy` | (frames, 478, 3) face points (face tracking is always on) |
| `landmarks/face_blendshapes.npy` | (frames, 52) |
| `video.mp4` | the take before mirroring, like mpipe.py, so `reextract.py` works on it |
| `meta.json` | target word, player, mode, model's top 3, popped or not, try number, real FPS, note, brightness, known_word |

The word folder is the target word, even when the bubble didn't pop, because the player was trying
to sign it. Use `popped` in `meta.json` to filter if needed. Takes with no hands at all aren't saved.

Check or train on the saved takes with the repo's tools:

```
cd ..
python predict.py mudra_bubbles/game_data
python train.py --data ../dataset_include_positions mudra_bubbles/game_data --position
```
