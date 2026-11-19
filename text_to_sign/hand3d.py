"""A real 3D hand for the signer, and a 3D arm solver.

Kunal's shader draws the palm as a flat 2D outline pushed towards the camera, so a hand seen
side-on, or a fist, turns into a flat plate with thin tubes on it. Here every part is 3D:

* Fingers are tapered round cones between the 3D joints, as thick as real fingers
  (neighbouring fingers touch, like a real hand).
* The palm is a rounded slab through the wrist and knuckles, so it turns with the hand.
* The palm side is lighter than the back of the hand, and the nails show on the back,
  so you can tell which way the hand faces.
* Ambient occlusion and a soft outline separate fingers that cross in front of the palm.

The arms are solved in 3D too: the elbow hangs down and the forearm comes towards the viewer
when the hand is near the face, instead of sticking out sideways like a wing.
"""
import math

import numpy as np
from OpenGL import GL as gl

# radius of each joint, as a fraction of the palm length (wrist to middle knuckle)
RADIUS = np.array([0.20, 0.15, 0.125, 0.11, 0.095,
                   0.105, 0.095, 0.085, 0.075,
                   0.110, 0.100, 0.088, 0.078,
                   0.102, 0.093, 0.083, 0.074,
                   0.090, 0.080, 0.072, 0.065], np.float32)
TIPS = [4, 8, 12, 16, 20]
PALM_REF = [(0, 5, 1.024), (0, 9, 1.0), (0, 13, 0.987), (0, 17, 0.882)]   # measured on MediaPipe hands

HAND_VERT = """
#version 120
varying vec2 vXY;
void main() { gl_Position = ftransform(); vXY = gl_Vertex.xy; }
"""

HAND_FRAG = """
#version 120
varying vec2 vXY;
uniform vec3 uJ[21];
uniform float uR[21];
uniform vec3 uPalmar[15];
uniform vec3 uPalmN;
uniform vec3 uWristEnd;
uniform float uWristR;
uniform float uP;          // palm length
uniform float uZTop, uZBot;
uniform float uPixel;
uniform vec3 uLight;

float dot2(vec3 v) { return dot(v, v); }

float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    vec3 ba = b - a;
    float l2 = max(dot(ba, ba), 1e-8);
    float rr = r1 - r2;
    float a2 = l2 - rr * rr;
    float il2 = 1.0 / l2;
    vec3 pa = p - a;
    float y = dot(pa, ba);
    float z = y - l2;
    vec3 xv = pa * l2 - ba * y;
    float x2 = dot(xv, xv);
    float y2 = y * y * l2;
    float z2 = z * z * l2;
    float k = sign(rr) * rr * rr * x2;
    if (sign(z) * a2 * z2 > k) return sqrt(x2 + z2) * il2 - r2;
    if (sign(y) * a2 * y2 < k) return sqrt(x2 + y2) * il2 - r1;
    return (sqrt(x2 * a2 * il2) + y * rr) * il2 - r1;
}

float udTri(vec3 p, vec3 a, vec3 b, vec3 c) {
    vec3 ba = b - a; vec3 pa = p - a;
    vec3 cb = c - b; vec3 pb = p - b;
    vec3 ac = a - c; vec3 pc = p - c;
    vec3 nor = cross(ba, ac);
    if (dot2(nor) < 1e-10) return 1e3;
    float inside = sign(dot(cross(ba, nor), pa)) + sign(dot(cross(cb, nor), pb)) + sign(dot(cross(ac, nor), pc));
    if (inside < 2.0)
        return sqrt(min(min(dot2(ba * clamp(dot(ba, pa) / dot2(ba), 0.0, 1.0) - pa),
                            dot2(cb * clamp(dot(cb, pb) / dot2(cb), 0.0, 1.0) - pb)),
                        dot2(ac * clamp(dot(ac, pc) / dot2(ac), 0.0, 1.0) - pc)));
    return sqrt(dot(nor, pa) * dot(nor, pa) / dot2(nor));
}

float smin(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * k * 0.25;
}

// id: -1 palm, 0..14 finger bone (3 * finger + segment); t: position along that bone
float hand(vec3 p, out float id, out float t) {
    float palmH = 0.12 * uP;
    float palm = udTri(p, uJ[0], uJ[5], uJ[9]);
    palm = min(palm, udTri(p, uJ[0], uJ[9], uJ[13]));
    palm = min(palm, udTri(p, uJ[0], uJ[13], uJ[17]));
    palm = min(palm, udTri(p, uJ[0], uJ[1], uJ[5]));
    palm -= palmH;
    palm = smin(palm, udTri(p, uJ[1], uJ[2], uJ[5]) - 0.07 * uP, 0.08 * uP);          // thumb web
    palm = smin(palm, sdRoundCone(p, uJ[0], uJ[1], 0.17 * uP, uR[1]), 0.10 * uP);     // thumb muscle
    palm = smin(palm, sdRoundCone(p, uWristEnd, uJ[0], uWristR, uR[0]), 0.10 * uP);   // wrist
    float d = palm;
    id = -1.0; t = 0.0;
    for (int f = 0; f < 5; ++f) {
        for (int s = 0; s < 3; ++s) {
            int a = 4 * f + 1 + s;
            float di = sdRoundCone(p, uJ[a], uJ[a + 1], uR[a], uR[a + 1]);
            if (di < d) {
                id = float(3 * f + s);
                vec3 ba = uJ[a + 1] - uJ[a];
                t = clamp(dot(p - uJ[a], ba) / max(dot(ba, ba), 1e-8), 0.0, 1.0);
            }
            d = (s == 0) ? smin(d, di, 0.05 * uP) : min(d, di);
        }
    }
    return d;
}
float hand(vec3 p) { float i, t; return hand(p, i, t); }

void main() {
    vec3 ro = vec3(vXY, uZTop), rd = vec3(0.0, 0.0, -1.0);
    float tmax = uZTop - uZBot;
    float t = 0.0, bestD = 1e3, bestT = 0.0;
    bool hit = false;
    for (int i = 0; i < 90; ++i) {
        float d = hand(ro + rd * t);
        if (d < bestD) { bestD = d; bestT = t; }
        if (d < 0.0015) { hit = true; break; }
        t += max(d * 0.9, 0.0025);
        if (t > tmax) break;
    }
    float coverage = hit ? 1.0 : 1.0 - smoothstep(0.0, uPixel, bestD);
    if (coverage <= 0.0) discard;
    vec3 p = ro + rd * (hit ? t : bestT);

    float id, along;
    hand(p, id, along);
    float e = 0.002;
    vec3 k1 = vec3(1, -1, -1), k2 = vec3(-1, -1, 1), k3 = vec3(-1, 1, -1), k4 = vec3(1, 1, 1);
    vec3 n = normalize(k1 * hand(p + k1 * e) + k2 * hand(p + k2 * e) + k3 * hand(p + k3 * e) + k4 * hand(p + k4 * e));

    // which side of the hand this is: palm side lighter, back of the hand darker, nails on the back
    vec3 palmar = id < 0.0 ? uPalmN : uPalmar[int(id + 0.5)];
    float side = dot(n, palmar);
    vec3 back = vec3(0.88, 0.69, 0.59), front = vec3(0.93, 0.75, 0.67);
    vec3 base = mix(back, front, smoothstep(-0.15, 0.55, side));
    vec3 toElbow = uWristEnd - uJ[0];
    float wrist = clamp(dot(p - uJ[0], toElbow) / max(dot(toElbow, toElbow), 1e-8) * 2.5, 0.0, 1.0);
    base = mix(base, mix(back, front, 0.45), wrist);      // wrist: one even tone, no dark band
    float seg = mod(id + 0.5, 3.0);
    if (id >= 0.0 && seg > 2.0) {     // last segment of a finger: the nail
        float nail = smoothstep(0.45, 0.65, along) * smoothstep(0.35, 0.65, -side);
        base = mix(base, vec3(0.95, 0.82, 0.78), nail * 0.85);
    }

    // ambient occlusion: darkens the gaps between fingers and where they fold onto the palm
    float occ = 0.0, w = 1.0;
    for (int i = 1; i <= 4; ++i) {
        float h = 0.045 * uP * float(i);
        occ += w * max(h - hand(p + n * h), 0.0);
        w *= 0.65;
    }
    float ao = clamp(1.0 - 3.0 * occ / uP, 0.45, 1.0);

    vec3 l = normalize(uLight);
    float diff = max((dot(n, l) + 0.30) / 1.30, 0.0);
    float fill = max(dot(n, normalize(vec3(-l.x, 0.1, 0.8))), 0.0);
    float hemi = 0.55 + 0.45 * n.y;
    float spec = pow(max(dot(n, normalize(l + vec3(0.0, 0.0, 1.0))), 0.0), 24.0) * 0.07;
    vec3 col = base * (0.36 * hemi + 0.62 * diff + 0.18 * fill) * ao;
    col += vec3(0.10, 0.03, 0.02) * (1.0 - diff) * ao;           // warm skin in the shadows
    col += vec3(spec);
    col *= mix(mix(0.72, 1.0, wrist), 1.0, smoothstep(0.05, 0.40, n.z));   // soft outline at the edges
    gl_FragColor = vec4(clamp(col, 0.0, 1.0), coverage);
}
"""


def _norm(v, fallback=(0.0, 0.0, 1.0)):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-6 else np.asarray(fallback, np.float32)


def palm_length(j):
    return float(np.mean([np.linalg.norm(j[b] - j[a]) / ref for a, b, ref in PALM_REF]))


def hand_uniforms(joints, palm_sign, forearm_dir):
    """joints (21, 3) in scene units -> dict of shader uniforms.

    palm_sign: +1 or -1, so that palm_sign * cross(index knuckle - wrist, little knuckle - wrist)
    points out of the palm. forearm_dir: unit 3D vector from the wrist towards the elbow."""
    j = np.asarray(joints, np.float32).copy()
    P = max(palm_length(j), 1e-3)
    r = RADIUS * P
    for t in TIPS:                       # MediaPipe's tip is the end of the finger, not the centre of its tip
        j[t] = j[t] - _norm(j[t] - j[t - 1]) * r[t] * 0.8
    palm_n = _norm(palm_sign * np.cross(j[5] - j[0], j[17] - j[0]))
    lat = _norm(j[17] - j[5], (1, 0, 0))
    up = _norm(j[9] - j[0], (0, 1, 0))
    sgn = 1.0 if np.dot(np.cross(up, lat), palm_n) >= 0 else -1.0
    palmar = np.zeros((15, 3), np.float32)
    for f in range(5):
        for s in range(3):
            a = 4 * f + 1 + s
            u = _norm(j[a + 1] - j[a])
            if f == 0:                   # the thumb bends another way: its pad faces roughly palm-wards
                v = palm_n - u * np.dot(palm_n, u)
                palmar[3 * f + s] = _norm(v, palm_n)
            else:
                palmar[3 * f + s] = _norm(sgn * np.cross(u, lat), palm_n)
    fd = _norm(np.asarray(forearm_dir, np.float32), -up)
    return dict(J=j, R=r, palmar=palmar, palm_n=palm_n.astype(np.float32),
                wrist_end=(j[0] + fd * 0.3 * P).astype(np.float32), wrist_r=0.14 * P, P=P,
                z_top=float(j[:, 2].max() + 0.5 * P), z_bot=float(j[:, 2].min() - 0.5 * P))


class HandDrawer:
    """Compiles the 3D hand shader once and draws one hand per call (blended over the body)."""

    def __init__(self, compile_fn):
        self.prog = compile_fn(HAND_VERT, HAND_FRAG)
        self._loc = {}

    def loc(self, name):
        if name not in self._loc:
            self._loc[name] = gl.glGetUniformLocation(self.prog, name)
        return self._loc[name]

    def draw(self, joints, palm_sign, forearm_dir, pixel, light):
        u = hand_uniforms(joints, palm_sign, forearm_dir)
        gl.glUseProgram(self.prog)
        gl.glUniform3fv(self.loc("uJ"), 21, u["J"])
        gl.glUniform1fv(self.loc("uR"), 21, u["R"])
        gl.glUniform3fv(self.loc("uPalmar"), 15, u["palmar"])
        gl.glUniform3f(self.loc("uPalmN"), *u["palm_n"])
        gl.glUniform3f(self.loc("uWristEnd"), *u["wrist_end"])
        gl.glUniform1f(self.loc("uWristR"), u["wrist_r"])
        gl.glUniform1f(self.loc("uP"), u["P"])
        gl.glUniform1f(self.loc("uZTop"), u["z_top"])
        gl.glUniform1f(self.loc("uZBot"), u["z_bot"])
        gl.glUniform1f(self.loc("uPixel"), pixel)
        gl.glUniform3f(self.loc("uLight"), *light)
        pts = np.vstack([u["J"][:, :2], u["wrist_end"][None, :2]])
        m = 0.35 * u["P"]
        lo, hi = pts.min(0) - m, pts.max(0) + m
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(lo[0], lo[1]); gl.glVertex2f(hi[0], lo[1])
        gl.glVertex2f(hi[0], hi[1]); gl.glVertex2f(lo[0], hi[1])
        gl.glEnd()


# ------------------------------------------------------------------------------ arms
def _two_bone(sh, wr, l1, l2, pole):
    d = wr - sh
    dist = float(np.linalg.norm(d))
    u = d / max(dist, 1e-6)
    if dist >= l1 + l2:                       # out of reach: straight arm
        return sh + u * l1, (dist - l1 - l2)
    dist_c = max(dist, abs(l1 - l2) + 1e-3)
    a = (l1 * l1 - l2 * l2 + dist_c * dist_c) / (2 * dist_c)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    v = pole - sh
    v = v - u * float(np.dot(v, u))
    v = _norm(v, (0, -1, 0))
    return sh + u * a + v * h, 0.0


def solve_arm(shoulder3, wrist_xy, side, l1, l2, scale, prev_z=None):
    """3D wrist and elbow for a hand at wrist_xy (picture plane).

    side: -1 / +1, which way is 'outwards' on screen. The wrist depth is chosen so the elbow hangs
    near a natural spot (below the shoulder, a little out and forward), then smoothed over time
    with prev_z so the arm doesn't jump."""
    sh = np.asarray(shoulder3, np.float32)
    pref = sh + np.array([side * 0.3 * scale, -0.85 * l1, 0.45 * l1], np.float32)
    best, best_cost = None, 1e9
    for z in np.linspace(sh[2] + 0.05 * scale, sh[2] + 0.95 * (l1 + l2), 36):
        wr = np.array([wrist_xy[0], wrist_xy[1], z], np.float32)
        el, over = _two_bone(sh, wr, l1, l2, pref)
        cost = float(np.sum((el - pref) ** 2)) + 40.0 * over * over + 0.05 * (z - sh[2] - 1.2 * scale) ** 2
        if cost < best_cost:
            best, best_cost = z, cost
    z = best if prev_z is None else prev_z + (best - prev_z) * 0.35
    wr = np.array([wrist_xy[0], wrist_xy[1], z], np.float32)
    el, _ = _two_bone(sh, wr, l1, l2, pref)
    return wr, el, z
