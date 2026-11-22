# 🤟 SignIt — Interactive Indian Sign Language (ISL) Game & AI Dataset Collector

> A modern, clean, Duolingo-inspired web app to teach **Indian Sign Language (ISL)** interactively through games like **SignBurst Arcade** while ethically crowdsourcing synchronized video and 3D landmark data to train computer vision models.

---

## 🌟 Key Highlights

- **Dual-Purpose Design**:
  1. **Gamified Education**: Duolingo-style learning path + SignBurst arcade bubble popping game tailored to authentic Indian Sign Language gestures.
  2. **Model Training & Crowdsourcing**: Captures synchronized webcam video (`.webm`) and Google MediaPipe 3D Landmark sequences (`.json`) with every sign attempt.
- **Aesthetic**: Minimalist, clean white canvas (`#ffffff`, `#f8fafc`) with cheerful light-blue & sky-blue accents (`#0ea5e9`, `#38bdf8`), 3D pressable buttons, smooth animations, and zero-latency Web Audio sound synthesizer.
- **Google Vision Models**: Powered by **Google MediaPipe Hand Landmarker** (21 3D landmarks per hand) and **Face Landmarker** (capturing non-manual facial grammatical cues crucial to ISL).
- **Demo Mode Control**: Explicit Demo Mode toggle above the camera arena prevents any false positives when the camera is inactive.
- **Responsive 3-Column Layout**: Left navigation rail, center game arena, and right community leaderboard & daily streak sidebar.

---

## 🎮 Game Modes

### 1. Duolingo-Style Learn Path (`/path`)
- **Serpentine Curriculum Path**: Progress through structured units (Greetings, Quick Responses, Daily Needs, Numbers & Alphabets).
- **Interactive Step Tutor**:
  - **Study Step**: Visual reference, cultural context (English + Hindi e.g. *Namaste / नमस्ते*, *Water / पानी*), and facial expression guidance.
  - **Camera Practice Step**: Real-time camera mirror with glowing sky-blue landmark skeleton, live confidence gauge, and 1.2s hold validation.
  - **Victory Celebration**: Earn XP, Gems, and maintain your daily streak!

### 2. SignBurst ISL Arcade (`/arcade`)
- **Fast-Paced Bubble Popping**:
  - Buoyant bubbles float across the arena with ISL signs.
  - Match the hand sign in front of your camera to **BURST** the target bubble!
  - Rack up combos (2x, 3x, 4x Combo! 🔥), build high scores, and beat the clock.
- **Instant Audio & Haptic Feedback**: Synthesized marimba pops, success chords, and combo fanfares generated with the Web Audio API.

### 3. Sign Dictionary (`/dictionary`)
- Searchable visual index of ISL vocabulary filtered by category (Greetings, Basics, Daily Needs, Feelings, Numbers, Alphabet).
- One-click launch into camera practice for any sign.

---

## 🔬 AI Research Dataset Hub (`/dataset`)

Every practice and SignBurst attempt automatically buffers:
1. **Video Stream**: High-resolution synchronized clip recorded via `MediaRecorder`.
2. **Google Landmarker JSON**: 3D coordinate sequences `(x, y, z)` for 21 hand joints + face contour keypoints matching Google's dataset format.
3. **Local Persistence**: Stored client-side inside browser `IndexedDB` with zero data leakage.

### One-Click Dataset Export
Click **"Dataset"** in the top navigation to:
- Inspect recorded video clips alongside the raw 3D landmark JSON.
- Click **"Export Dataset (.ZIP)"** to download a complete training bundle:
  - `manifest.json`: Full sample index, labels, timestamps, contributor ID.
  - `dataset_manifest.csv`: Tabular metadata ready for Pandas / PyTorch Dataset.
  - `landmarks/{sample_id}.json`: 3D landmark frame sequences.
  - `videos/{sample_id}.webm`: Raw video recordings.
  - `README.md`: Python ML training starter script.

---

## 🚀 Getting Started

```bash
# Clone or open workspace
cd c:\Users\bansa\Desktop\Projects\Signit

# Install dependencies (already installed)
npm install

# Start development server
npm run dev
```

Open **`http://localhost:5173`** in your browser!
