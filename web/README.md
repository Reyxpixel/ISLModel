# Sign → text in the browser

Everything needed to run the sign recogniser in a web page, with no Python server: MediaPipe
(JavaScript) finds the hands and face, and the BiLSTM runs with onnxruntime-web.

| File | What it is |
|---|---|
| `model/model.onnx` | The default model (`models/include_position.pt`: 91 signs, with hand position) |
| `model/config.json` | Its sign names (`labels`, in output order) and the preprocessing settings |
| `preprocess.js` | Turns a take's MediaPipe output into the model's input. A port of `isl_model/preprocess.py` |
| `index.html` | A minimal working page: webcam, press space, sign, see the top 3 guesses |
| `export_onnx.py` | Re-creates `model/` from a `.pt` file, after retraining |
| `test_preprocess.py` | Checks `preprocess.js` and the ONNX model give the same answers as the Python code |

## Try it

Browsers only allow the webcam on `localhost` or https, so serve the repo folder (not `web/`, the
page loads `../hand_landmarker.task` and `../face_landmarker.task`):

```
python -m http.server 8000
```

Then open http://localhost:8000/web/. Press space, get ready during the 2 s countdown, sign for
2.5 s. You can also pick a video file instead of the webcam. Tested in Chrome on saved takes:
hello 90% and handkerchief 90%, the same numbers the Python version gives on those videos.

## Using it in your own app

The steps for one take, all in `index.html`:

1. **Mirror the frame before detection.** Draw the video flipped left-right onto a canvas and run
   MediaPipe on the canvas. The training data was recorded that way (`mpipe.py` flips the frame),
   so the hand labels and positions only match if you do the same.
2. **Run HandLandmarker and FaceLandmarker** in `VIDEO` mode on every frame of the take, with the
   same settings as `mpipe.py`: 2 hands, detection and presence confidence 0.6, tracking 0.5; 1 face,
   0.5 and 0.5.
3. **Store each frame** as `{hands, handsScreen, face}`:
   - `hands[slot]` = the hand's `worldLandmarks` (21 × [x, y, z]), `handsScreen[slot]` = its
     `landmarks`. **Slot 0 is the hand MediaPipe labels "Right", slot 1 "Left".** A hand that
     wasn't found is 21 × [0, 0, 0].
   - `face` = `faceLandmarks[0]` (478 × [x, y, z]), or `null` if no face was found.
4. **Take length:** 2.5 seconds of real time, however many frames that gives (a slow webcam gives
   fewer; the model resamples every take to 32 frames).
5. `preprocess(frames, config)` → `Float32Array`, then
   `session.run({features: new ort.Tensor("float32", x, [1, 32, config.n_features])})` →
   `logits`. `topK(logits, config.labels, 3)` gives the top 3 with probabilities.

If the top guess is below about 50%, it's better to say "not sure" than to show it: in an earlier
test the model was about 90% sure when right and about 56% when wrong.

Libraries used by the page (from the jsDelivr CDN): `@mediapipe/tasks-vision@0.10.14` and
`onnxruntime-web@1.20.1`.

## After retraining

```
pip install onnx onnxruntime
python web/export_onnx.py --model models/include_position.pt
python web/test_preprocess.py ../dataset_mmkay_webcam
```

`export_onnx.py` checks the ONNX model against PyTorch (difference ~1e-8). `test_preprocess.py`
runs real takes through both the Python and the JS preprocessing (needs Node.js); on 60 takes from
INCLUDE, Vansh's low-light set, the webcam set and Mudra Bubbles, the largest difference was ~2e-6
and the top guess agreed on all 60. If you change `isl_model/preprocess.py`, change
`preprocess.js` the same way and run the test.
