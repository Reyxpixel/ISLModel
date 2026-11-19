"""OpenGL view of the signer: a simple body (head, shoulders, arms) plus Kunal's ray-marched hands.

The hand shader is Kunal's, read from renderer.cpp, with three small changes applied on top:
smooth (anti-aliased) edges instead of hard pixel steps, one even skin tone for palm and fingers,
and a soft rim light. The body is a second, simpler ray-marched shader drawn first.
"""
import math
import time

import numpy as np
from OpenGL import GL as gl
from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from hand_renderer import joint_uniforms, palm_dims, read_shaders, LIGHT_DIRECTION, AMBIENT, DIFFUSE, SPECULAR
from signer import SCALE, UPPER_ARM, FOREARM, VIEW_CENTER_Y, VIEW_HALF_H, shoulder
from hand3d import HandDrawer, solve_arm


def set_default_gl_format():
    """Call before creating QApplication: legacy-compatible GL 2.1 (Kunal's shaders use GLSL 120)."""
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 1)
    fmt.setProfile(QSurfaceFormat.CompatibilityProfile)
    fmt.setSamples(4)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)


def patched_hand_shader():
    vert, frag = read_shaders()

    def sub(old, new):
        nonlocal frag
        if old not in frag:
            raise RuntimeError(f"renderer.cpp shader changed, can't find: {old[:60]}")
        frag = frag.replace(old, new)

    sub("uniform float uPalmDepthOffset;", "uniform float uPalmDepthOffset;\nuniform float uPixel;")
    start = frag.index("    for (int step = 0; step < 45; ++step) {")
    end = frag.index("if (!hit) discard;") + len("if (!hit) discard;")
    frag = frag[:start] + """    float bestD = 1e3; vec3 bestP = rayOrigin; float bestW = 0.0;
    for (int step = 0; step < 64; ++step) {
        p = rayOrigin + rayDirection * t;
        float distanceToSurface = handSdf(p, fingerWeight);
        if (distanceToSurface < bestD) { bestD = distanceToSurface; bestP = p; bestW = fingerWeight; }
        if (distanceToSurface < 0.0015) {
            hit = true;
            break;
        }
        t += max(distanceToSurface * 0.90, 0.004);
        if (t > 2.8) break;
    }
    float coverage = 1.0;
    if (!hit) {
        coverage = 1.0 - smoothstep(0.0, uPixel, bestD);
        if (coverage <= 0.0) discard;
        p = bestP; fingerWeight = bestW;
    }""" + frag[end:]
    sub("vec3 palmSkin   = vec3(0.74, 0.60, 0.52);", "vec3 palmSkin   = vec3(0.80, 0.63, 0.53);")
    sub("vec3 fingerSkin = vec3(0.84, 0.69, 0.59);", "vec3 fingerSkin = vec3(0.83, 0.66, 0.56);")
    sub("tint = max(tint, amount * 0.45);", "tint = max(tint, amount * 0.25);")
    # palm edge follows the hand's size instead of renderer.cpp's fixed 0.035..0.052 cap
    sub("return clamp(span * 0.13, 0.035, 0.052);", "return clamp(span * 0.15, 0.035, uPalmHalfDepth * 1.1);")
    # Readable shapes: soft shadow where fingers lie on the palm or on each other (ambient
    # occlusion, 4 samples along the normal) and darker silhouette edges, so overlapping fingers
    # separate instead of merging into one outline.
    sub("gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);",
        "float occlusion = 0.0, total = 0.0, weight = 1.0;\n"
        "    for (int i = 1; i <= 4; ++i) {\n"   # steps of 1-4 palm thicknesses: ignores small bumps
        "        float h = uPalmHalfDepth * 2.0 * float(i);\n"
        "        occlusion += max(h - handSdf(p + normal * h), 0.0) * weight;\n"
        "        total += h * weight;\n"
        "        weight *= 0.6;\n"
        "    }\n"
        "    float ao = clamp(1.0 - 1.3 * occlusion / total, 0.55, 1.0);\n"
        "    float edge = mix(0.62, 1.0, smoothstep(0.0, 0.5, max(normal.z, 0.0)));\n"
        "    color *= ao * edge;\n"
        "    gl_FragColor = vec4(clamp(color, 0.0, 1.0), coverage);")
    return vert, frag


BODY_VERT = """
#version 120
varying vec2 vWorldXY;
void main() { gl_Position = ftransform(); vWorldXY = gl_Vertex.xy; }
"""

BODY_FRAG = """
#version 120
varying vec2 vWorldXY;
uniform vec3 uShoulder[2];
uniform vec3 uElbow[2];
uniform vec3 uWrist[2];
uniform float uS;
uniform float uPixel;
uniform vec3 uLight;

float sdEllipsoid(vec3 p, vec3 r) {
    float k0 = length(p / r);
    float k1 = length(p / (r * r));
    return k0 * (k0 - 1.0) / max(k1, 1e-6);
}
float sdCone(vec3 p, vec3 a, vec3 b, float ra, float rb) {
    vec3 ab = b - a;
    float t = clamp(dot(p - a, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
    return length(p - (a + ab * t)) - mix(ra, rb, t);
}
float sdRoundBox(vec3 p, vec3 b, float r) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0) - r;
}
float smin(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * k * 0.25;
}
vec3 headC() { return vec3(0.0, 0.08, -0.15) * uS; }
vec3 headR() { return vec3(0.47, 0.64, 0.50) * uS; }

// Where the hair starts, in head units (q = offset from the head centre / head radii; y up,
// z towards the viewer): high on the forehead, above the ears at the sides, with a short
// sideburn in front of each ear, and lower at the back of the head.
float hairLine(vec3 q) {
    float t = q.z / max(length(q.xz), 1e-3);                    // 1 front, 0 side, -1 back
    float h = mix(-0.40, 0.30, smoothstep(-0.75, 0.05, t));     // back of the head -> above the ear
    // forehead: a fringe swept to one side, with a gentle wave instead of a ruler-straight edge,
    // and higher at the temples
    float fringe = 0.47 + 0.09 * q.x + 0.025 * sin(q.x * 11.0) + 0.06 * q.x * q.x;
    h = mix(h, fringe, smoothstep(0.30, 0.75, t));
    float burn = smoothstep(0.08, 0.20, t) * (1.0 - smoothstep(0.30, 0.45, t));
    return h - 0.22 * burn;
}

// material: 0 shirt, 1 neck, 2 face and head skin, 3 ears, 4 hair
float body(vec3 p, out float mat) {
    float face = sdEllipsoid(p - headC(), headR());
    float ears = min(sdEllipsoid(p - vec3(0.47, 0.03, -0.18) * uS, vec3(0.08, 0.16, 0.10) * uS),
                     sdEllipsoid(p - vec3(-0.47, 0.03, -0.18) * uS, vec3(0.08, 0.16, 0.10) * uS));
    // hair: a slightly bigger shell over the head, cut off below the hairline, so it has some
    // volume instead of being painted on, and never covers the ears
    vec3 q = (p - headC()) / headR();
    float shell = sdEllipsoid(p - headC() - vec3(0.0, 0.03, -0.02) * uS, headR() * vec3(1.06, 1.05, 1.07));
    float cut = (hairLine(q) - q.y) * 0.45 * uS;
    float k = 0.05 * uS;                                  // rounded edge where the hair ends
    float hair = max(shell, cut) + max(k - abs(shell - cut), 0.0) * max(k - abs(shell - cut), 0.0) * 0.25 / k;
    float head = min(min(face, ears), hair);
    float neck = sdCone(p, vec3(0.0, -0.30, -0.25) * uS, vec3(0.0, -1.05, -0.30) * uS, 0.21 * uS, 0.23 * uS);
    float torso = sdRoundBox(p - vec3(0.0, -2.75, -0.42) * uS, vec3(0.62, 1.45, 0.24) * uS, 0.34 * uS);
    vec3 neckBase = vec3(0.0, -0.98, -0.32) * uS;
    for (int i = 0; i < 2; ++i)   // sloping shoulders from the neck out to each arm
        torso = smin(torso, sdCone(p, neckBase, uShoulder[i], 0.26 * uS, 0.25 * uS), 0.30 * uS);
    float arms = 1e3;
    for (int i = 0; i < 2; ++i) {
        arms = min(arms, sdCone(p, uShoulder[i], uElbow[i], 0.21 * uS, 0.17 * uS));
        arms = min(arms, sdCone(p, uElbow[i], uWrist[i], 0.165 * uS, 0.115 * uS));
    }
    float shirt = smin(torso, arms, 0.12 * uS);
    float skin = smin(neck, head, 0.10 * uS);
    mat = shirt < skin ? 0.0 : (head >= neck ? 1.0 : (hair <= min(face, ears) ? 4.0 : (ears < face ? 3.0 : 2.0)));
    return min(shirt, skin);
}
float body(vec3 p) { float m; return body(p, m); }

vec3 headColor(vec3 p, vec3 skin) {
    vec3 q = (p - headC()) / headR();
    float front = max(q.z, 0.0);
    vec2 e = vec2(abs(q.x), q.y);
    float aa = 0.025;
    vec3 c = skin;
    float faceOn = smoothstep(0.45, 0.60, front);
    c = mix(c, vec3(0.62, 0.36, 0.34), faceOn * (1.0 - smoothstep(0.20 - aa, 0.20 + aa, length((q.xy - vec2(0.0, -0.50)) * vec2(1.0, 4.5)))));   // mouth
    c = mix(c, vec3(0.25, 0.17, 0.13), faceOn * (1.0 - smoothstep(0.02 - aa * 0.5, 0.02 + aa * 0.5, length(max(abs(e - vec2(0.36, 0.295)) - vec2(0.15, 0.0), 0.0)))));  // brows
    c = mix(c, vec3(0.12, 0.10, 0.10), faceOn * (1.0 - smoothstep(0.075 - aa, 0.075 + aa, length((e - vec2(0.36, 0.13)) * vec2(1.0, 1.7)))));  // eyes
    float hl = hairLine(q);   // skin just under the edge of the hair shell is hair-coloured too
    c = mix(c, vec3(0.17, 0.12, 0.10), smoothstep(hl - 0.02, hl + 0.04, q.y));
    return c;
}

void main() {
    vec3 top = vec3(0.95, 0.96, 0.98), bottom = vec3(0.80, 0.84, 0.90);
    float g = clamp((vWorldXY.y / uS + 3.2) / 4.6, 0.0, 1.0);
    vec3 bg = mix(bottom, top, g);
    vec3 ro = vec3(vWorldXY, 3.0 * uS), rd = vec3(0.0, 0.0, -1.0);
    float t = 0.0, bestD = 1e3; vec3 bestP = ro; bool hit = false; vec3 p = ro;
    for (int i = 0; i < 72; ++i) {
        p = ro + rd * t;
        float d = body(p);
        if (d < bestD) { bestD = d; bestP = p; }
        if (d < 0.002 * uS) { hit = true; break; }
        t += max(d * 0.9, 0.004 * uS);
        if (t > 6.0 * uS) break;
    }
    float coverage = hit ? 1.0 : 1.0 - smoothstep(0.0, uPixel, bestD);
    if (coverage <= 0.0) { gl_FragColor = vec4(bg, 1.0); return; }
    if (!hit) p = bestP;
    float mat;
    body(p, mat);
    float e = 0.003 * uS;
    vec3 k1 = vec3(1, -1, -1), k2 = vec3(-1, -1, 1), k3 = vec3(-1, 1, -1), k4 = vec3(1, 1, 1);
    vec3 n = normalize(k1 * body(p + k1 * e) + k2 * body(p + k2 * e) + k3 * body(p + k3 * e) + k4 * body(p + k4 * e));
    vec3 skin = vec3(0.80, 0.63, 0.53);
    vec3 base;
    if (mat < 0.5) base = vec3(0.20, 0.33, 0.45);                    // shirt
    else if (mat < 1.5) base = skin * 0.95;                          // neck
    else if (mat < 2.5) base = headColor(p, skin);                   // face
    else if (mat < 3.5) base = vec3(0.78, 0.59, 0.50);               // ears
    else {                                                           // hair, with faint strands
        vec3 q = (p - headC()) / headR();
        base = vec3(0.17, 0.12, 0.10) * (0.88 + 0.12 * sin(atan(q.x, q.z) * 45.0 + q.y * 8.0));
    }
    vec3 l = normalize(uLight);
    float diff = max(dot(n, l), 0.0);
    float spec = pow(max(dot(n, normalize(l + vec3(0, 0, 1))), 0.0), 20.0) * (mat < 0.5 ? 0.05 : 0.03);
    float rim = pow(1.0 - max(n.z, 0.0), 2.5) * 0.25;
    vec3 col = base * (0.42 + 0.62 * diff) + vec3(spec) + rim * vec3(0.9, 0.92, 1.0) * 0.5;
    gl_FragColor = vec4(mix(bg, clamp(col, 0.0, 1.0), coverage), 1.0);
}
"""


def _compile(vert_src, frag_src):
    def one(kind, src):
        sh = gl.glCreateShader(kind)
        gl.glShaderSource(sh, src)
        gl.glCompileShader(sh)
        if not gl.glGetShaderiv(sh, gl.GL_COMPILE_STATUS):
            raise RuntimeError(gl.glGetShaderInfoLog(sh).decode(errors="replace"))
        return sh
    prog = gl.glCreateProgram()
    v, f = one(gl.GL_VERTEX_SHADER, vert_src), one(gl.GL_FRAGMENT_SHADER, frag_src)
    gl.glAttachShader(prog, v)
    gl.glAttachShader(prog, f)
    gl.glLinkProgram(prog)
    if not gl.glGetProgramiv(prog, gl.GL_LINK_STATUS):
        raise RuntimeError(gl.glGetProgramInfoLog(prog).decode(errors="replace"))
    return prog


def solve_elbow(sh, wr, side, l1=UPPER_ARM * SCALE * 0.92, l2=FOREARM * SCALE * 0.92):
    """2-bone IK in the picture plane; the elbow bends down and outwards."""
    d = wr - sh
    dist = float(np.linalg.norm(d))
    if dist < 1e-4:
        return sh + np.array([side * 0.3, -l1 * 0.9], np.float32)
    u = d / dist
    if dist >= l1 + l2:
        return sh + u * l1 * dist / (l1 + l2)
    dist_c = max(dist, abs(l1 - l2) + 1e-3)
    a = (l1 * l1 - l2 * l2 + dist_c * dist_c) / (2 * dist_c)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    base = sh + u * a
    perp = np.array([-u[1], u[0]], np.float32)
    e1, e2 = base + perp * h, base - perp * h
    s1 = -e1[1] + 0.3 * side * e1[0]
    s2 = -e2[1] + 0.3 * side * e2[0]
    return e1 if s1 > s2 else e2


class SignerView(QOpenGLWidget):
    """Draws whatever pose the player gives, about 60 times a second."""
    itemStarted = Signal(str)

    def __init__(self, player, parent=None, facing=True):
        super().__init__(parent)
        self.player = player
        self.facing = facing          # True: like watching a person; False: like a mirror
        self.z_gain = 1.0
        self.look = "3d"              # "3d": our 3D hand; "kunal": Kunal's hand shader
        self.arm_z = [None, None]
        self.hand3d = None
        self.body_prog = self.hand_prog = None
        self.error = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)
        self.setMinimumSize(360, 400)

    def initializeGL(self):
        try:
            self.body_prog = _compile(BODY_VERT, BODY_FRAG)
            self.hand_prog = _compile(*patched_hand_shader())
            self.hand3d = HandDrawer(_compile)
        except Exception as e:     # shown in the window instead of crashing the app
            self.error = str(e)
            print("Signer view shader error:", e)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_CULL_FACE)

    def _view(self):
        w, h = max(1, self.width()), max(1, self.height())
        hh = VIEW_HALF_H
        hw = hh * w / h
        return hw, hh, 2 * hh / h

    def paintGL(self):
        dpr = self.devicePixelRatioF()
        gl.glViewport(0, 0, int(self.width() * dpr), int(self.height() * dpr))
        gl.glClearColor(0.9, 0.92, 0.95, 1)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        if not self.body_prog or not self.hand_prog:
            return
        hw, hh, px = self._view()
        cy = VIEW_CENTER_Y
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        gl.glOrtho(-hw, hw, cy - hh, cy + hh, -1, 1)
        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

        pose, has_z, _ = self.player.pose_at(time.monotonic())
        pose = pose.copy()
        flip = -1.0 if self.facing else 1.0
        pose[..., 0] *= flip

        # arms: slot 0 is the signer's left hand; after flipping it sits on the viewer's right.
        # Solved in 3D, so a hand near the face brings the forearm forward and the elbow stays down.
        shoulders, elbows, wrists = [], [], []
        l1, l2 = UPPER_ARM * SCALE * 0.92, FOREARM * SCALE * 0.92
        for h, side in ((0, -1), (1, 1)):
            sh = shoulder(side) * [flip, 1]
            sh3 = np.array([sh[0], sh[1] - 0.15 * SCALE, -0.35 * SCALE], np.float32)
            wr, el, self.arm_z[h] = solve_arm(sh3, pose[h, 0, :2], side * flip, l1, l2, SCALE, self.arm_z[h])
            shoulders.append(sh3)
            elbows.append(el)
            wrists.append(wr)

        gl.glUseProgram(self.body_prog)
        loc = lambda n: gl.glGetUniformLocation(self.body_prog, n)
        gl.glUniform3fv(loc("uShoulder"), 2, np.array(shoulders, np.float32))
        gl.glUniform3fv(loc("uElbow"), 2, np.array(elbows, np.float32))
        gl.glUniform3fv(loc("uWrist"), 2, np.array(wrists, np.float32))
        gl.glUniform1f(loc("uS"), SCALE)
        gl.glUniform1f(loc("uPixel"), px * 1.2)
        gl.glUniform3f(loc("uLight"), *LIGHT_DIRECTION)
        gl.glBegin(gl.GL_QUADS)
        gl.glVertex2f(-hw, cy - hh); gl.glVertex2f(hw, cy - hh)
        gl.glVertex2f(hw, cy + hh); gl.glVertex2f(-hw, cy + hh)
        gl.glEnd()

        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        if self.look == "3d" and self.hand3d:
            for h in sorted(range(2), key=lambda h: wrists[h][2]):      # the nearer hand last
                if pose[h, :, 1].max() < cy - hh:
                    continue                       # resting below the picture
                forearm = np.asarray(elbows[h]) - np.asarray(wrists[h])
                light = (LIGHT_DIRECTION[0] * -flip, LIGHT_DIRECTION[1], LIGHT_DIRECTION[2])   # mirror view: mirrored light
                self.hand3d.draw(pose[h], (1.0 if h == 0 else -1.0) * flip, forearm, px * 1.2, light)
            gl.glUseProgram(0)
            gl.glDisable(gl.GL_BLEND)
            return
        gl.glUseProgram(self.hand_prog)
        loc = lambda n: gl.glGetUniformLocation(self.hand_prog, n)
        bottom = cy - hh
        for h in range(2):
            joints = pose[h]
            if joints[:, 1].max() < bottom:
                continue                       # resting below the picture
            data = joint_uniforms(joints[:, :2], joints[:, 2] if has_z else None, self.z_gain)
            gl.glUniform4fv(loc("uJoints"), 21, data)
            gl.glUniform3f(loc("uLightDirection"), *LIGHT_DIRECTION)
            gl.glUniform1f(loc("uAmbient"), AMBIENT)
            gl.glUniform1f(loc("uDiffuseStrength"), DIFFUSE)
            gl.glUniform1f(loc("uSpecularStrength"), SPECULAR)
            palm_half, palm_offset = palm_dims(joints[:, :2])
            gl.glUniform1f(loc("uPalmHalfDepth"), palm_half)
            gl.glUniform1f(loc("uPalmDepthOffset"), palm_offset)
            gl.glUniform1i(loc("uDebugView"), 0)
            gl.glUniform1f(loc("uPixel"), px * 1.2)
            lo, hi = joints[:, :2].min(0) - 0.15, joints[:, :2].max(0) + 0.15
            gl.glBegin(gl.GL_QUADS)
            gl.glVertex2f(lo[0], lo[1]); gl.glVertex2f(hi[0], lo[1])
            gl.glVertex2f(hi[0], hi[1]); gl.glVertex2f(lo[0], hi[1])
            gl.glEnd()
        gl.glUseProgram(0)
        gl.glDisable(gl.GL_BLEND)
