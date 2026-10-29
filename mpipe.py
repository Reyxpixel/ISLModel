import os
import time
import cv2
import shutil
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ---------------- PRE-REQUISITES ----------------
DATA_DIR = "dataset_landmarks_only"
HAND_MODEL_PATH = "hand_landmarker.task"
FACE_MODEL_PATH = "face_landmarker.task"
COUNTDOWN_SECONDS = 2.0 
TARGET_FPS = 30
ENABLE_FACE_TRACKING = False  

# The physical bone connections for skeleton
HAND_CONNECTIONS = [
    (0,1), (1,2), (2,3), (3,4),       # Thumb
    (5,6), (6,7), (7,8),              # Index
    (9,10), (10,11), (11,12),         # Middle
    (13,14), (14,15), (15,16),        # Ring
    (17,18), (18,19), (19,20),        # Pinky
    (0,5), (5,9), (9,13), (13,17), (0,17) # Palm
]
# ------------------------------------------------

# --- 1. HAND INITIALIZATION (Always On) ---
base_hand = python.BaseOptions(model_asset_path=HAND_MODEL_PATH)
hand_options = vision.HandLandmarkerOptions(
    base_options=base_hand, 
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2, 
    min_hand_detection_confidence=0.6,
    min_hand_presence_confidence=0.6,
    min_tracking_confidence=0.5)
hand_detector = vision.HandLandmarker.create_from_options(hand_options)

# --- 2. FACE INITIALIZATION (Conditional) ---
face_detector = None
if ENABLE_FACE_TRACKING:
    base_face = python.BaseOptions(model_asset_path=FACE_MODEL_PATH)
    face_options = vision.FaceLandmarkerOptions(
        base_options=base_face, 
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True) 
    face_detector = vision.FaceLandmarker.create_from_options(face_options)


def extract_landmarks(rgb_frame, timestamp_ms):
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    
    # Pre-fill with ZEROS
    hand_world_arr = np.zeros((2, 21, 3), dtype=np.float32) 
    hand_screen_arr = np.zeros((2, 21, 3), dtype=np.float32)
    face_screen_arr = np.zeros((478, 3), dtype=np.float32)  
    face_blendshapes_arr = np.zeros((52,), dtype=np.float32)

    # --- HAND EXTRACTION ---
    hand_res = hand_detector.detect_for_video(mp_image, timestamp_ms)
    if hand_res.hand_world_landmarks and hand_res.handedness:
        for idx in range(len(hand_res.hand_world_landmarks)):
            label = hand_res.handedness[idx][0].category_name
            h_idx = 0 if label == 'Right' else 1
            
            for lm_idx, lm in enumerate(hand_res.hand_world_landmarks[idx]):
                hand_world_arr[h_idx, lm_idx] = [lm.x, lm.y, lm.z]
                
            for lm_idx, lm in enumerate(hand_res.hand_landmarks[idx]):
                hand_screen_arr[h_idx, lm_idx] = [lm.x, lm.y, lm.z]

    # --- FACE EXTRACTION ---
    if ENABLE_FACE_TRACKING and face_detector:
        face_res = face_detector.detect_for_video(mp_image, timestamp_ms)
        if face_res.face_landmarks:
            for lm_idx, lm in enumerate(face_res.face_landmarks[0]):
                face_screen_arr[lm_idx] = [lm.x, lm.y, lm.z]
                
        if face_res.face_blendshapes:
            for idx, blendshape in enumerate(face_res.face_blendshapes[0]):
                face_blendshapes_arr[idx] = blendshape.score

    return hand_world_arr, hand_screen_arr, face_screen_arr, face_blendshapes_arr


def get_next_sequence_id(sign_dir):
    if not os.path.exists(sign_dir): return 1
    existing = [int(f.replace("seq_", "")) for f in os.listdir(sign_dir) if f.startswith("seq_")]
    return max(existing, default=0) + 1


def format_txt_output(frame_idx, hand_arr, face_screen_arr, face_blend_arr):
    hand_str = f"Frame: {frame_idx}\n"
    for h_idx in range(2):
        hand_str += f"  Hand {h_idx} ({'Right' if h_idx==0 else 'Left'}):\n"
        if np.all(hand_arr[h_idx] == 0):
            hand_str += "    MISSING (Zero Array)\n"
        else:
            for lm_idx in range(21):
                x, y, z = hand_arr[h_idx, lm_idx]
                hand_str += f"    LM {lm_idx}: x={x:.4f}, y={y:.4f}, z={z:.4f}\n"
    
    face_str = f"Frame: {frame_idx}\n"
    if not ENABLE_FACE_TRACKING:
        face_str += "  Face: TRACKING DISABLED\n"
    elif np.all(face_screen_arr == 0):
        face_str += "  Face: MISSING\n"
    else:
        face_str += "  [Face coordinates extracted. See .npy for full mesh.]\n"
        for lm_idx in range(52):
            face_str += f"  Blendshape {lm_idx}: {face_blend_arr[lm_idx]:.4f}\n"

    return hand_str + "\n", face_str + "\n"


def main():
    print("\n--- ISL MEDIAPIPE COORDINATE COLLECTOR ---")
    sign_label = input("Enter the word you want to record (e.g., 'apple'): ").strip().lower()
    duration = float(input("Enter duration per take in seconds (e.g., '2.5'): "))
    
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75) 
    
    frames_per_seq = int(duration * TARGET_FPS)

    sign_dir = os.path.join(DATA_DIR, sign_label)
    os.makedirs(sign_dir, exist_ok=True)

    print(f"\n[INFO] Target: {duration} seconds @ {TARGET_FPS} FPS = {frames_per_seq} frames per take.")
    print("Press 's' to start capture, 'v' for hand skeleton, 'f' for face mesh, or 'q' to quit.")

    global_frame_count = 0 
    show_visualizer = True 
    show_face = ENABLE_FACE_TRACKING
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        display_frame = cv2.flip(frame, 1)
        cv2.putText(display_frame, f"Word: {sign_label} | Press 's' to capture", 
                    (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(display_frame, f"Toggles: 'v' (hands) | 'f' (face)", 
                    (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        
        cv2.imshow("Sign Language Data Collector", display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('v'):
            show_visualizer = not show_visualizer
        elif key == ord('f') and ENABLE_FACE_TRACKING:
            show_face = not show_face
        elif key == ord('s'):
            current_seq_id = get_next_sequence_id(sign_dir)
            print("\n[STARTED] Continuous capture. Press 'q' at any time to stop.")
            
            while True:
                stop_batch = False
                
                # --- COUNTDOWN ---
                countdown_start = time.time()
                while time.time() - countdown_start < COUNTDOWN_SECONDS:
                    ret, frame = cap.read()
                    display_frame = cv2.flip(frame, 1)
                    
                    remaining = COUNTDOWN_SECONDS - (time.time() - countdown_start)
                    
                    cv2.putText(display_frame, f"Next: seq_{current_seq_id:03d}", 
                                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(display_frame, f"GET READY: {remaining:.1f}s", 
                                (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 165, 255), 4)
                    
                    cv2.imshow("Sign Language Data Collector", display_frame)
                    
                    key_cd = cv2.waitKey(1) & 0xFF
                    if key_cd == ord('q'):
                        stop_batch = True
                        break
                    elif key_cd == ord('v'):
                        show_visualizer = not show_visualizer
                    elif key_cd == ord('f') and ENABLE_FACE_TRACKING:
                        show_face = not show_face
                
                if stop_batch:
                    print("\n[STOPPED] Continuous capture ended by user.")
                    break

                # --- RECORDING PHASE ---
                temp_seq_dir = os.path.join(sign_dir, "seq_temp")
                lm_dir = os.path.join(temp_seq_dir, "landmarks")
                lm_raw_dir = os.path.join(temp_seq_dir, "landmarks_raw")

                if os.path.exists(temp_seq_dir):
                     shutil.rmtree(temp_seq_dir)

                os.makedirs(lm_dir, exist_ok=True)
                os.makedirs(lm_raw_dir, exist_ok=True)

                seq_hands, seq_hands_screen, seq_face_coords, seq_face_blend = [], [], [], []
                
                hand_txt_path = os.path.join(lm_raw_dir, "hands_raw.txt")
                face_txt_path = os.path.join(lm_raw_dir, "face_raw.txt")
                
                try:
                    with open(hand_txt_path, "w") as h_txt, open(face_txt_path, "w") as f_txt:
                        capture_successful = True
                        
                        # Start measuring actual recording time
                        record_start_time = time.time()
                        
                        for frame_idx in range(frames_per_seq):
                            ret, frame = cap.read()
                            if not ret:
                                capture_successful = False
                                break

                            mirrored = cv2.flip(frame, 1)
                            raw_rgb = cv2.cvtColor(mirrored, cv2.COLOR_BGR2RGB)

                            # --- EXTRACT LANDMARKS ---
                            current_timestamp_ms = int(global_frame_count * (1000 / TARGET_FPS))
                            hand_world, hand_screen, face_screen, face_blend = extract_landmarks(raw_rgb, current_timestamp_ms)
                            
                            global_frame_count += 1 
                            
                            seq_hands.append(hand_world)
                            seq_hands_screen.append(hand_screen)
                            if ENABLE_FACE_TRACKING:
                                seq_face_coords.append(face_screen)
                                seq_face_blend.append(face_blend)

                            h_str, f_str = format_txt_output(frame_idx, hand_world, face_screen, face_blend)
                            h_txt.write(h_str)
                            f_txt.write(f_str)

                            # --- VISUALIZER ---
                            display = mirrored.copy()
                            h_dim, w_dim, _ = display.shape
                            
                            if show_visualizer:
                                for h_idx in range(2):
                                    for connection in HAND_CONNECTIONS:
                                        p1_idx, p2_idx = connection
                                        x1, y1, _ = hand_screen[h_idx, p1_idx]
                                        x2, y2, _ = hand_screen[h_idx, p2_idx]
                                        
                                        if x1 != 0 and x2 != 0: 
                                            pt1 = (int(x1 * w_dim), int(y1 * h_dim))
                                            pt2 = (int(x2 * w_dim), int(y2 * h_dim))
                                            cv2.line(display, pt1, pt2, (0, 255, 0), 2)
                                            
                                    for lm_idx in range(21):
                                        x, y, _ = hand_screen[h_idx, lm_idx]
                                        if x != 0 or y != 0:
                                            cx, cy = int(x * w_dim), int(y * h_dim)
                                            cv2.circle(display, (cx, cy), 4, (0, 255, 255), -1)

                            if show_face and ENABLE_FACE_TRACKING:
                                for lm_idx in range(478):
                                    fx, fy, _ = face_screen[lm_idx]
                                    if fx != 0 or fy != 0:
                                        cx, cy = int(fx * w_dim), int(fy * h_dim)
                                        cv2.circle(display, (cx, cy), 1, (0, 0, 255), -1)

                            cv2.circle(display, (30, 30), 12, (0, 0, 255), -1)
                            progress = int((frame_idx / frames_per_seq) * 400)
                            cv2.rectangle(display, (20, 400), (420, 420), (50, 50, 50), -1)
                            cv2.rectangle(display, (20, 400), (20 + progress, 420), (0, 255, 0), -1)
                            cv2.putText(display, f"RECORDING seq_{current_seq_id:03d}...", (55, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                            
                            cv2.imshow("Sign Language Data Collector", display)
                            
                            key_rec = cv2.waitKey(1) & 0xFF
                            if key_rec == ord('q'):
                                stop_batch = True
                                capture_successful = False
                                break
                            elif key_rec == ord('v'):
                                show_visualizer = not show_visualizer
                            elif key_rec == ord('f') and ENABLE_FACE_TRACKING:
                                show_face = not show_face

                        # Stop measuring actual recording time
                        record_end_time = time.time()

                except Exception as e:
                     print(f"\n[ERROR] Unexpected failure: {e}")
                     capture_successful = False
                     stop_batch = True

                # --- ATOMIC COMMIT ---
                if capture_successful:
                    time_taken = max(record_end_time - record_start_time, 0.0001)
                    actual_fps = frames_per_seq / time_taken
                    
                    # Always save hands
                    np.save(os.path.join(lm_dir, "hands.npy"), np.array(seq_hands))
                    # Where each hand is in the frame (0-1, same mirrored frame as face_coords.npy).
                    # hands.npy only holds hand shape, so this is what gives position and movement.
                    np.save(os.path.join(lm_dir, "hands_screen.npy"), np.array(seq_hands_screen))
                    
                    # Only save face data if tracking is enabled
                    if ENABLE_FACE_TRACKING:
                        np.save(os.path.join(lm_dir, "face_coords.npy"), np.array(seq_face_coords))
                        np.save(os.path.join(lm_dir, "face_blendshapes.npy"), np.array(seq_face_blend))
                    
                    final_seq_dir = os.path.join(sign_dir, f"seq_{current_seq_id:03d}")
                    
                    time.sleep(0.2) 
                    try:
                        os.rename(temp_seq_dir, final_seq_dir)
                    except PermissionError:
                        time.sleep(0.5)
                        shutil.move(temp_seq_dir, final_seq_dir)
                        
                    print(f"[SUCCESS] Saved {final_seq_dir} | Avg Speed: {actual_fps:.1f} FPS")
                    current_seq_id += 1
                else:
                     if os.path.exists(temp_seq_dir):
                         time.sleep(0.2)
                         shutil.rmtree(temp_seq_dir, ignore_errors=True)

                if stop_batch:
                    break

            print("\nReturning to standby. Press 's' to capture, 'v' (hands), 'f' (face), or 'q' to quit.")

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()