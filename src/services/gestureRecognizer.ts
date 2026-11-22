import { HandLandmarkData, LandmarkPoint } from '../types/dataset';

// 21 MediaPipe hand landmark indices
export const LANDMARK_INDEX = {
  WRIST: 0,
  THUMB_CMC: 1,
  THUMB_MCP: 2,
  THUMB_IP: 3,
  THUMB_TIP: 4,
  INDEX_MCP: 5,
  INDEX_PIP: 6,
  INDEX_DIP: 7,
  INDEX_TIP: 8,
  MIDDLE_MCP: 9,
  MIDDLE_PIP: 10,
  MIDDLE_DIP: 11,
  MIDDLE_TIP: 12,
  RING_MCP: 13,
  RING_PIP: 14,
  RING_DIP: 15,
  RING_TIP: 16,
  PINKY_MCP: 17,
  PINKY_PIP: 18,
  PINKY_DIP: 19,
  PINKY_TIP: 20,
};

// Euclidean distance helper in 2D/3D space
export function distance(p1: LandmarkPoint, p2: LandmarkPoint): number {
  const dx = p1.x - p2.x;
  const dy = p1.y - p2.y;
  const dz = (p1.z || 0) - (p2.z || 0);
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

// Check if a finger is extended relative to its MCP joint
export function isFingerExtended(landmarks: LandmarkPoint[], tipIdx: number, pipIdx: number, mcpIdx: number): boolean {
  const tip = landmarks[tipIdx];
  const pip = landmarks[pipIdx];
  const mcp = landmarks[mcpIdx];
  const wrist = landmarks[LANDMARK_INDEX.WRIST];

  // In normalized coords, y decreases as you go UP on the screen
  const distTipWrist = distance(tip, wrist);
  const distPipWrist = distance(pip, wrist);
  const distMcpWrist = distance(mcp, wrist);

  return distTipWrist > distPipWrist && distPipWrist > distMcpWrist * 0.85;
}

export function isThumbExtended(landmarks: LandmarkPoint[]): boolean {
  const tip = landmarks[LANDMARK_INDEX.THUMB_TIP];
  const mcp = landmarks[LANDMARK_INDEX.THUMB_MCP];
  const wrist = landmarks[LANDMARK_INDEX.WRIST];
  const pinkyMcp = landmarks[LANDMARK_INDEX.PINKY_MCP];

  // Thumb extended moves away from pinky base and wrist
  return distance(tip, wrist) > distance(mcp, wrist) * 1.15 && distance(tip, pinkyMcp) > distance(mcp, pinkyMcp) * 0.9;
}

export interface RecognitionResult {
  matchedGesture: string;
  confidence: number; // 0 to 1
  feedbackMessage: string;
  debugDetails?: Record<string, unknown>;
}

export class ISLGestureRecognizer {
  /**
   * Evaluates hand and face landmarks against the target ISL sign gesture
   */
  public evaluate(
    targetGesture: string,
    hands: HandLandmarkData[],
    face?: LandmarkPoint[]
  ): RecognitionResult {
    if (!hands || hands.length === 0) {
      return {
        matchedGesture: 'none',
        confidence: 0,
        feedbackMessage: 'Position your hand(s) in frame to begin',
      };
    }

    const primaryHand = hands[0].landmarks;
    const secondHand = hands.length > 1 ? hands[1].landmarks : null;

    switch (targetGesture) {
      case 'namaste_palms_together': {
        // Namaste requires both hands close to each other, vertical orientation
        if (!secondHand) {
          return {
            matchedGesture: 'single_hand_detected',
            confidence: 0.35,
            feedbackMessage: 'Bring your second hand into view for Namaste 🙏',
          };
        }

        const wristDist = distance(primaryHand[LANDMARK_INDEX.WRIST], secondHand[LANDMARK_INDEX.WRIST]);
        const indexDist = distance(primaryHand[LANDMARK_INDEX.INDEX_TIP], secondHand[LANDMARK_INDEX.INDEX_TIP]);
        const middleDist = distance(primaryHand[LANDMARK_INDEX.MIDDLE_TIP], secondHand[LANDMARK_INDEX.MIDDLE_TIP]);

        // In Namaste, palms/fingers are very close together (< 0.15 in normalized space)
        const avgTipDist = (indexDist + middleDist) / 2;
        const areFingersClose = avgTipDist < 0.22;
        const areWristsClose = wristDist < 0.28;

        // Both hands pointing upwards (wrist y > index tip y)
        const h1Upright = primaryHand[LANDMARK_INDEX.WRIST].y > primaryHand[LANDMARK_INDEX.INDEX_TIP].y;
        const h2Upright = secondHand[LANDMARK_INDEX.WRIST].y > secondHand[LANDMARK_INDEX.INDEX_TIP].y;

        let conf = 0;
        if (areFingersClose && areWristsClose) {
          conf = Math.min(1.0, 0.5 + (0.22 - avgTipDist) * 2.5 + (0.28 - wristDist) * 1.5);
          if (h1Upright && h2Upright) conf = Math.min(1.0, conf + 0.2);
        } else if (areFingersClose || areWristsClose) {
          conf = 0.5;
        } else {
          conf = 0.2;
        }

        return {
          matchedGesture: conf > 0.65 ? 'namaste_palms_together' : 'hands_apart',
          confidence: Math.round(conf * 100) / 100,
          feedbackMessage: conf > 0.75 ? 'Perfect Namaste! Hold steady 🙏' : 'Bring palms together at center chest',
        };
      }

      case 'thumbs_up': {
        const thumbExt = isThumbExtended(primaryHand);
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);

        // Thumb tip should be higher (lower y) than thumb MCP
        const thumbPointingUp = primaryHand[LANDMARK_INDEX.THUMB_TIP].y < primaryHand[LANDMARK_INDEX.THUMB_MCP].y;

        const fingersFolded = !indexExt && !midExt && !ringExt && !pinkyExt;

        let conf = 0;
        if (thumbExt && thumbPointingUp && fingersFolded) {
          conf = 0.95;
        } else if (thumbExt && thumbPointingUp) {
          conf = 0.65;
        } else if (thumbPointingUp) {
          conf = 0.45;
        }

        return {
          matchedGesture: conf > 0.65 ? 'thumbs_up' : 'partial_thumb',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Awesome! Clear thumbs-up 👍' : 'Curl 4 fingers into palm and point thumb up',
        };
      }

      case 'victory_v': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);

        // Index & middle tips should have separation (V-shape)
        const vSeparation = distance(primaryHand[LANDMARK_INDEX.INDEX_TIP], primaryHand[LANDMARK_INDEX.MIDDLE_TIP]);

        let conf = 0;
        if (indexExt && midExt && !ringExt && !pinkyExt) {
          conf = vSeparation > 0.04 ? 0.95 : 0.8;
        } else if (indexExt && midExt) {
          conf = 0.6;
        } else {
          conf = 0.2;
        }

        return {
          matchedGesture: conf > 0.65 ? 'victory_v' : 'two_fingers',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Great Number 2 / Peace sign! ✌️' : 'Extend index & middle fingers up in a V',
        };
      }

      case 'index_pointing_up': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);

        let conf = 0;
        if (indexExt && !midExt && !ringExt && !pinkyExt) {
          conf = 0.95;
        } else if (indexExt && !midExt) {
          conf = 0.65;
        } else {
          conf = 0.25;
        }

        return {
          matchedGesture: conf > 0.65 ? 'index_pointing_up' : 'pointing',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Clear Number 1 sign! ☝️' : 'Point only your index finger upward',
        };
      }

      case 'three_fingers_w': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);

        let conf = 0;
        if (indexExt && midExt && ringExt && !pinkyExt) {
          conf = 0.95;
        } else if (indexExt && midExt && ringExt) {
          conf = 0.75;
        } else {
          conf = 0.3;
        }

        return {
          matchedGesture: conf > 0.65 ? 'three_fingers_w' : 'partial_w',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Great "Water" sign! 💧' : 'Extend 3 fingers (index, middle, ring) upward',
        };
      }

      case 'flat_four_fingers': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);
        const thumbTucked = !isThumbExtended(primaryHand);

        let conf = 0;
        if (indexExt && midExt && ringExt && pinkyExt && thumbTucked) {
          conf = 0.95;
        } else if (indexExt && midExt && ringExt && pinkyExt) {
          conf = 0.8;
        } else {
          conf = 0.35;
        }

        return {
          matchedGesture: conf > 0.65 ? 'flat_four_fingers' : 'open_hand',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Letter B sign held cleanly! 🖐️' : 'Keep 4 fingers straight up, tuck thumb across',
        };
      }

      case 'fist_nod': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);
        const thumbExt = isThumbExtended(primaryHand);

        let conf = 0;
        if (!indexExt && !midExt && !ringExt && !pinkyExt && !thumbExt) {
          conf = 0.95;
        } else if (!indexExt && !midExt && !ringExt && !pinkyExt) {
          conf = 0.8;
        } else {
          conf = 0.3;
        }

        return {
          matchedGesture: conf > 0.65 ? 'fist_nod' : 'open_fingers',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Solid Yes sign! Nod fist gently 👍' : 'Form a neat closed fist at chest height',
        };
      }

      case 'open_palm_wave':
      case 'open_palm_chest': {
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);
        const thumbExt = isThumbExtended(primaryHand);

        let conf = 0;
        if (indexExt && midExt && ringExt && pinkyExt && thumbExt) {
          conf = 0.92;
        } else if (indexExt && midExt && ringExt && pinkyExt) {
          conf = 0.78;
        } else {
          conf = 0.35;
        }

        return {
          matchedGesture: conf > 0.65 ? targetGesture : 'partial_palm',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Open palm recognized cleanly ✋' : 'Show full open palm towards the camera',
        };
      }

      case 'thankyou_chin_to_front': {
        // Flat hand at upper chest or chin level
        const indexExt = isFingerExtended(primaryHand, 8, 6, 5);
        const midExt = isFingerExtended(primaryHand, 12, 10, 9);
        const ringExt = isFingerExtended(primaryHand, 16, 14, 13);
        const pinkyExt = isFingerExtended(primaryHand, 20, 18, 17);

        // Hand is in upper half of the video (y < 0.65)
        const isUpperBody = primaryHand[LANDMARK_INDEX.WRIST].y < 0.65;
        let conf = 0;
        if (indexExt && midExt && ringExt && pinkyExt && isUpperBody) {
          conf = 0.9;
        } else if (indexExt && midExt && ringExt) {
          conf = 0.65;
        } else {
          conf = 0.3;
        }

        return {
          matchedGesture: conf > 0.6 ? 'thankyou_chin_to_front' : 'holding_hand',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Perfect Thank You arc! ✨' : 'Bring flat hand near chin and move smoothly outward',
        };
      }

      case 'help_lift':
      case 'two_hands_close': {
        if (!secondHand) {
          return {
            matchedGesture: 'single_hand',
            confidence: 0.4,
            feedbackMessage: 'Use both hands together for this sign 🤲',
          };
        }
        const wristDist = distance(primaryHand[LANDMARK_INDEX.WRIST], secondHand[LANDMARK_INDEX.WRIST]);
        const conf = wristDist < 0.35 ? 0.88 : 0.5;

        return {
          matchedGesture: conf > 0.65 ? targetGesture : 'hands_apart',
          confidence: conf,
          feedbackMessage: conf > 0.7 ? 'Both hands cooperating! Great form' : 'Bring both hands together in front',
        };
      }

      default: {
        return {
          matchedGesture: 'generic_hand',
          confidence: 0.8,
          feedbackMessage: 'Hand detected! Hold position.',
        };
      }
    }
  }
}

export const gestureRecognizer = new ISLGestureRecognizer();

