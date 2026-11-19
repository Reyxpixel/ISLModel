#include <GL/glew.h>
#include <GLFW/glfw3.h>

#include <iostream>
#include <fstream>
#include <sstream>
#include <vector>
#include <utility>
#include <map>
#include <string>
#include <algorithm>
#include <cctype>
#include <initializer_list>
#include <thread>
#include <mutex>
#include <atomic>
#include <cmath>
#include <queue> // Added for the Playback Queue

// ================= GLOBAL DICTIONARIES =================
std::map<std::string, std::vector<std::pair<float, float>>> alphabets_dict;
std::map<std::string, std::vector<std::vector<std::pair<float, float>>>> words_dict;

std::string to_upper(std::string str) {
    std::transform(str.begin(), str.end(), str.begin(), ::toupper);
    return str;
}

// ================= FILE PARSERS =================
void load_alphabets(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Warning: Could not open " << filename << std::endl;
        return;
    }
    std::string line, current_letter = "";
    while (std::getline(file, line)) {
        size_t comment_pos = line.find("//");
        if (comment_pos != std::string::npos) line = line.substr(0, comment_pos);

        std::replace(line.begin(), line.end(), '{', ' ');
        std::replace(line.begin(), line.end(), '}', ' ');
        std::replace(line.begin(), line.end(), ',', ' ');

        std::stringstream ss(line);
        std::string token;
        while (ss >> token) {
            if (std::isalpha(token[0]) && token.length() == 1) {
                current_letter = to_upper(token);
            } else {
                try {
                    float x = std::stof(token);
                    std::string next;
                    if (ss >> next) {
                        float y = std::stof(next);
                        if (!current_letter.empty()) {
                            alphabets_dict[current_letter].push_back({x, y});
                        }
                    }
                } catch(...) {}
            }
        }
    }
    std::cout << "Loaded " << alphabets_dict.size() << " static alphabets." << std::endl;
}

void load_words(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Warning: Could not open " << filename << std::endl;
        return;
    }
    std::string line, current_word = "";
    int current_frame = -1;

    while (std::getline(file, line)) {
        size_t comment_pos = line.find("//");
        if (comment_pos != std::string::npos) {
            size_t frame_pos = line.find("Frame", comment_pos);
            if (frame_pos != std::string::npos) {
                std::stringstream ss(line.substr(frame_pos + 5));
                ss >> current_frame;
            }
            line = line.substr(0, comment_pos);
        }

        std::replace(line.begin(), line.end(), '{', ' ');
        std::replace(line.begin(), line.end(), '}', ' ');
        std::replace(line.begin(), line.end(), ',', ' ');

        std::stringstream ss(line);
        std::string token;
        while (ss >> token) {
            if (std::isalpha(token[0])) {
                if (token != "std" && token != "vector" && token.find("SEQ") == std::string::npos) {
                    current_word = to_upper(token);
                    current_frame = -1;
                }
            } else {
                try {
                    float x = std::stof(token);
                    std::string next_token;
                    if (ss >> next_token) {
                        float y = std::stof(next_token);
                        if (!current_word.empty() && current_frame != -1) {
                            if (words_dict[current_word].size() <= (size_t)current_frame) {
                                words_dict[current_word].resize(current_frame + 1);
                            }
                            words_dict[current_word][current_frame].push_back({x, y});
                        }
                    }
                } catch (...) {}
            }
        }
    }
    std::cout << "Loaded " << words_dict.size() << " animated words." << std::endl;
}

// ================= MOTION CLEAN-UP (added for the chat app) =================
// Recorded landmarks shake from frame to frame, and in some words a second hand flickers
// in and out. Each word is tidied once at load time: the second hand is kept for the whole
// word or dropped, and every point is smoothed over time with a small centred Gaussian
// (centred, so the sign keeps its timing). renderer_kunal_original.cpp has the code before this.
const float word_smoothing_sigma = 1.0f;   // in frames; 0 turns smoothing off
const double transition_seconds = 0.25;    // blend from one word/letter into the next

void clean_up_words() {
    for (auto& entry : words_dict) {
        auto& seq = entry.second;
        seq.erase(std::remove_if(seq.begin(), seq.end(),
                  [](const std::vector<std::pair<float, float>>& f) { return f.size() < 21; }),
                  seq.end());
        if (seq.empty()) continue;

        int with_second = 0;
        for (const auto& f : seq) if (f.size() >= 42) ++with_second;
        bool keep_second = with_second * 2 >= (int)seq.size();
        for (size_t i = 0; i < seq.size(); ++i) {
            if (!keep_second) { seq[i].resize(21); continue; }
            if (seq[i].size() >= 42) { seq[i].resize(42); continue; }
            for (size_t d = 1; d < seq.size(); ++d) {   // borrow it from the nearest frame
                const std::vector<std::pair<float, float>>* donor = nullptr;
                if (i >= d && seq[i - d].size() >= 42) donor = &seq[i - d];
                else if (i + d < seq.size() && seq[i + d].size() >= 42) donor = &seq[i + d];
                if (donor) {
                    std::vector<std::pair<float, float>> second(donor->begin() + 21, donor->begin() + 42);
                    seq[i].insert(seq[i].end(), second.begin(), second.end());
                    break;
                }
            }
        }

        if (word_smoothing_sigma <= 0.0f || seq.size() < 3) continue;
        int radius = (int)std::ceil(3.0f * word_smoothing_sigma);
        std::vector<float> kernel(2 * radius + 1);
        for (int k = -radius; k <= radius; ++k)
            kernel[k + radius] = std::exp(-0.5f * (k / word_smoothing_sigma) * (k / word_smoothing_sigma));
        const auto original = seq;
        int n = (int)seq.size();
        size_t points = seq[0].size();
        for (int i = 0; i < n; ++i) {
            for (size_t p = 0; p < points; ++p) {
                float sx = 0.0f, sy = 0.0f, sw = 0.0f;
                for (int k = -radius; k <= radius; ++k) {
                    int j = i + k;
                    if (j < 0 || j >= n) continue;
                    float w = kernel[k + radius];
                    sx += w * original[j][p].first;
                    sy += w * original[j][p].second;
                    sw += w;
                }
                seq[i][p] = {sx / sw, sy / sw};
            }
        }
    }
}

// Catmull-Rom: a smooth curve through the frames instead of straight lines between them.
float catmull_rom(float p0, float p1, float p2, float p3, float t) {
    return 0.5f * (2.0f * p1 + (p2 - p0) * t
                   + (2.0f * p0 - 5.0f * p1 + 4.0f * p2 - p3) * t * t
                   + (3.0f * p1 - p0 - 3.0f * p2 + p3) * t * t * t);
}

// ================= HAND STRUCTURE =================
struct Joint { float x, y; };
struct Hand { Joint joints[21]; };

struct Vec2 { float x, y; };
struct Vec3 { float x, y, z; };

static Vec2 operator+(Vec2 a, Vec2 b) { return {a.x + b.x, a.y + b.y}; }
static Vec2 operator-(Vec2 a, Vec2 b) { return {a.x - b.x, a.y - b.y}; }
static Vec2 operator*(Vec2 a, float s) { return {a.x * s, a.y * s}; }
static float dot(Vec2 a, Vec2 b) { return a.x * b.x + a.y * b.y; }
static float length(Vec2 a) { return std::sqrt(dot(a, a)); }
static Vec2 normalized(Vec2 a, Vec2 fallback = {1.0f, 0.0f}) {
    float n = length(a);
    return n > 1e-6f ? a * (1.0f / n) : fallback;
}
static Vec3 operator+(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
static Vec3 operator*(Vec3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
static float dot(Vec3 a, Vec3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static Vec3 normalized(Vec3 a, Vec3 fallback = {0.0f, 0.0f, 1.0f}) {
    float n = std::sqrt(dot(a, a));
    return n > 1e-6f ? a * (1.0f / n) : fallback;
}

// Editable lighting controls. Positive x is screen-right and positive y is up.
const Vec3 hand_light_direction = {0.35f, 0.55f, 0.75f}; // slightly adjusted top-right, toward viewer
const float hand_ambient = 0.40f;
const float hand_diffuse_strength = 0.65f;
const float hand_specular_strength = 0.025f;

// Editable thickness controls (multipliers on the automatically derived radii).
// finger_thickness_scale: all five digits. 1.0 = original thick look, lower = slimmer.
// thumb_thickness_scale: extra multiplier applied to the thumb only, on top of the
// finger scale (e.g. 0.60 = thumb is 60% as thick as it would otherwise be).
const float finger_thickness_scale = 0.65f;
const float thumb_thickness_scale = 0.60f;
// Global playback speed. 1.0 = real-time (30 fps), 0.5 = half speed.
const double playback_speed_factor = 0.5;

GLuint hand_sdf_program = 0;
struct HandSdfUniforms {
    GLint joints = -1, light_direction = -1;
    GLint ambient = -1, diffuse = -1, specular = -1;
    GLint palm_half_depth = -1, palm_depth_offset = -1, debug_view = -1;
} hand_sdf_uniforms;

// 0 = combined hand, 1 = palm only, 2 = fingers only.
const int hand_sdf_debug_view = 0;
const float palm_half_depth = 0.028f;
// The palm slab is centered at z = -palm_depth_offset (pushed away from the viewer).
// The landmark data has no Z, so finger depth is synthesized relative to the palm's front face.
const float palm_depth_offset = 0.012f;
const float palm_front_z = palm_half_depth - palm_depth_offset;
// Gap kept between the palm's front face and the underside of any finger that lies over it.
const float finger_palm_clearance = 0.008f;

// Smoothed per-hand segment lengths allow gradual adaptation to different signs
// while preventing frame-to-frame landmark noise from changing bone lengths.
struct PoseState {
    bool initialized = false;
    float lengths[5][4] = {};
};

const int finger_chains[5][5] = {
    {0,1,2,3,4}, {0,5,6,7,8}, {0,9,10,11,12},
    {0,13,14,15,16}, {0,17,18,19,20}
};

int connections[][2] = {
    {0,1},{1,2},{2,3},{3,4},
    {0,5},{5,6},{6,7},{7,8},
    {0,9},{9,10},{10,11},{11,12},
    {0,13},{13,14},{14,15},{15,16},
    {0,17},{17,18},{18,19},{19,20}
};

// ================= QUEUE SYSTEM =================
std::mutex queue_mutex;
std::queue<std::string> display_queue;

void terminal_listener() {
    std::string raw_input;
    while (std::getline(std::cin, raw_input)) {
        if (raw_input.empty()) continue;

        // Split the full sentence by spaces
        std::stringstream ss(raw_input);
        std::string word;

        std::lock_guard<std::mutex> lock(queue_mutex);
        while (ss >> word)
        {
            if (word.size() >= 2 && word.front() == '[' && word.back() == ']') {

                std::string name = word.substr(1, word.size() - 2);

                for (char c : name) {
                    if (std::isalpha(static_cast<unsigned char>(c))) {
                        display_queue.push(std::string(1, std::toupper(c)));
                    }
                }
            }
            else {
                display_queue.push(to_upper(word));
            }
        }
    }
}

// ================= POSE CORRECTION =================
// Five short FABRIK chains share the wrist root. Each chain follows the observed
// fingertip target while retaining its slowly smoothed segment lengths.
void correct_hand_pose(Hand& hand, PoseState& state) {
    Vec2 raw[21];
    for (int i = 0; i < 21; ++i) raw[i] = {hand.joints[i].x, hand.joints[i].y};

    for (int f = 0; f < 5; ++f) {
        for (int s = 0; s < 4; ++s) {
            int a = finger_chains[f][s], b = finger_chains[f][s + 1];
            float observed = length(raw[b] - raw[a]);
            if (!state.initialized) state.lengths[f][s] = observed;
            else state.lengths[f][s] = 0.92f * state.lengths[f][s] + 0.08f * observed;
        }

        Vec2 p[5];
        for (int j = 0; j < 5; ++j) p[j] = raw[finger_chains[f][j]];
        Vec2 root = p[0], target = p[4];
        float total = 0.0f;
        for (int s = 0; s < 4; ++s) total += state.lengths[f][s];

        if (length(target - root) >= total) {
            Vec2 dir = normalized(target - root);
            for (int s = 0; s < 4; ++s) p[s + 1] = p[s] + dir * state.lengths[f][s];
        } else {
            for (int iteration = 0; iteration < 5; ++iteration) {
                p[4] = target;
                for (int s = 3; s >= 0; --s) {
                    Vec2 dir = normalized(p[s] - p[s + 1], normalized(raw[finger_chains[f][s]] - raw[finger_chains[f][s + 1]]));
                    p[s] = p[s + 1] + dir * state.lengths[f][s];
                }
                p[0] = root;
                for (int s = 0; s < 4; ++s) {
                    Vec2 dir = normalized(p[s + 1] - p[s], normalized(raw[finger_chains[f][s + 1]] - raw[finger_chains[f][s]]));
                    p[s + 1] = p[s] + dir * state.lengths[f][s];
                }
            }
        }
        for (int j = 1; j < 5; ++j) {
            int index = finger_chains[f][j];
            hand.joints[index] = {p[j].x, p[j].y};
        }
    }
    state.initialized = true;
}

// ================= STABLE HAND GEOMETRY =================
float finger_radius(float bone_length, int segment, float max_radius = 0.085f) {
    // Thick, nearly uniform fingers: the radius is derived from the proximal
    // bone and only tapers very slightly toward the tip (see draw_hand_surface).
    const float taper[] = {0.32f, 0.31f, 0.30f, 0.29f};
    float factor = taper[std::max(0, std::min(segment, 3))];
    float cap = std::max(0.030f, std::min(0.085f, max_radius));
    return std::max(0.030f, std::min(cap, bone_length * factor));
}

float smooth_profile(float t) {
    t = std::max(0.0f, std::min(1.0f, t));
    return t * t * (3.0f - 2.0f * t);
}

// Signed distance (negative inside) from a point to the palm polygon
// (wrist, thumb MCP, index/middle/ring/pinky MCP). Mirrors palmFootprintSdf in the shader.
float palm_footprint_distance(const Vec2* joint, Vec2 p) {
    const int outline[6] = {0, 2, 5, 9, 13, 17};
    float min_distance_squared = 1e6f;
    bool inside = false;
    for (int edge = 0; edge < 6; ++edge) {
        Vec2 a = joint[outline[edge]];
        Vec2 b = joint[outline[(edge + 1) % 6]];
        Vec2 ab = b - a;
        float denom = std::max(dot(ab, ab), 1e-6f);
        float t = std::max(0.0f, std::min(1.0f, dot(p - a, ab) / denom));
        Vec2 delta = p - (a + ab * t);
        min_distance_squared = std::min(min_distance_squared, dot(delta, delta));
        if ((a.y > p.y) != (b.y > p.y)) {
            float crossing_x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y);
            if (p.x < crossing_x) inside = !inside;
        }
    }
    float d = std::sqrt(min_distance_squared);
    return inside ? -d : d;
}

const char* hand_vertex_shader = R"GLSL(
#version 120
varying vec2 vWorldXY;
void main() {
    gl_Position = ftransform();
    vWorldXY = gl_Vertex.xy;
}
)GLSL";

const char* hand_fragment_shader = R"GLSL(
#version 120
varying vec2 vWorldXY;
uniform vec4 uJoints[21];
uniform vec3 uLightDirection;
uniform float uAmbient;
uniform float uDiffuseStrength;
uniform float uSpecularStrength;
uniform float uPalmHalfDepth;
uniform int uDebugView;
uniform float uPalmDepthOffset;

float sdCapsule(vec3 p, vec3 a, vec3 b, float radius) {
    vec3 ab = b - a;
    float t = clamp(dot(p - a, ab) / max(dot(ab, ab), 0.000001), 0.0, 1.0);
    return length(p - (a + ab * t)) - radius;
}

float smoothUnion(float a, float b, float k) {
    float h = max(k - abs(a - b), 0.0) / k;
    return min(a, b) - h * h * k * 0.25;
}

int chainIndex(int finger, int segment) {
    return finger == 0 ? segment : 4 * finger + segment;
}

float palmCapsuleSdf(vec3 p, int aIndex, int bIndex, float radiusXY) {
    // Closest point is found in XY, while Z has its own explicitly controlled
    // half-depth. This keeps the palm broad in its landmark plane and thin in Z.
    vec2 a = uJoints[aIndex].xy;
    vec2 b = uJoints[bIndex].xy;
    vec2 ab = b - a;
    float t = clamp(dot(p.xy - a, ab) / max(dot(ab, ab), 0.000001), 0.0, 1.0);
    vec2 delta = p.xy - (a + ab * t);
    float zDepth = max(uPalmHalfDepth, 0.0001);
    float scaledDistance = sqrt(dot(delta, delta) / (radiusXY * radiusXY)
                              + (p.z * p.z) / (zDepth * zDepth));
    return (scaledDistance - 1.0) * min(radiusXY, zDepth);
}

float palmRadius(int aIndex, int bIndex) {
    float span = length(uJoints[bIndex].xy - uJoints[aIndex].xy);
    return clamp(span * 0.13, 0.035, 0.052);
}

int palmOutlineIndex(int point) {
    if (point == 0) return 0;
    if (point == 1) return 2;
    if (point == 2) return 5;
    if (point == 3) return 9;
    if (point == 4) return 13;
    return 17;
}

float palmFootprintSdf(vec2 p) {
    float minDistanceSquared = 1e6;
    bool inside = false;
    for (int edge = 0; edge < 6; ++edge) {
        int aIndex = palmOutlineIndex(edge);
        int nextPoint = edge == 5 ? 0 : edge + 1;
        int bIndex = palmOutlineIndex(nextPoint);
        vec2 a = uJoints[aIndex].xy;
        vec2 b = uJoints[bIndex].xy;
        vec2 ab = b - a;
        float t = clamp(dot(p - a, ab) / max(dot(ab, ab), 0.000001), 0.0, 1.0);
        vec2 delta = p - (a + ab * t);
        minDistanceSquared = min(minDistanceSquared, dot(delta, delta));

        bool crosses = (a.y > p.y) != (b.y > p.y);
        float verticalSpan = b.y - a.y;
        float safeVerticalSpan = abs(verticalSpan) > 0.000001
            ? verticalSpan : (verticalSpan < 0.0 ? -0.000001 : 0.000001);
        float crossingX = a.x + (p.y - a.y) * (b.x - a.x) / safeVerticalSpan;
        if (crosses && p.x < crossingX) inside = !inside;
    }
    float distanceToEdge = sqrt(minDistanceSquared);
    return inside ? -distanceToEdge : distanceToEdge;
}

float palmInteriorSdf(vec3 p) {
    // Rounded extrusion follows the wrist/MCP footprint. The rounding is
    // included within the existing palm half-depth, so total Z thickness stays fixed.
    const float rounding = 0.012;
    float footprint = palmFootprintSdf(p.xy);
    float depth = abs(p.z) - max(uPalmHalfDepth - rounding, 0.0001);
    vec2 outside = max(vec2(footprint, depth), vec2(0.0));
    return min(max(footprint, depth), 0.0) + length(outside) - rounding;
}

float palmSdf(vec3 p) {
    // Evaluate the unchanged palm volume in translated local Z space.
    // Querying at z + offset shifts the rendered palm toward -Z.
    p.z += uPalmDepthOffset;
    // The existing perimeter capsules and center supports are smoothly
    // unioned with the polygon fill, whose thumb-side edge passes through joint 2.
    float d = palmCapsuleSdf(p, 0, 5, palmRadius(0, 5));
    d = smoothUnion(d, palmCapsuleSdf(p, 5, 9, palmRadius(5, 9)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 9, 13, palmRadius(9, 13)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 13, 17, palmRadius(13, 17)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 17, 0, palmRadius(17, 0)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 0, 9, palmRadius(0, 9)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 0, 13, palmRadius(0, 13)), 0.018);
    // Thumb base: the straight wrist->thumb-MCP outline edge can leave a gap
    // behind the thumb's CMC joint, so the palm also follows wrist -> CMC -> MCP.
    d = smoothUnion(d, palmCapsuleSdf(p, 0, 1, palmRadius(0, 1)), 0.018);
    d = smoothUnion(d, palmCapsuleSdf(p, 1, 2, palmRadius(1, 2)), 0.018);
    d = smoothUnion(d, palmInteriorSdf(p), 0.018);
    return d;
}

float thumbSdf(vec3 p) {
    float d = 1e3;
    // Keep the existing four thumb spans, using the shared finger radius profile.
    for (int segment = 0; segment < 4; ++segment) {
        int aIndex = segment;
        int bIndex = segment + 1;
        vec3 a = uJoints[aIndex].xyz;
        vec3 b = uJoints[bIndex].xyz;
        vec3 ab = b - a;
        float t = clamp(dot(p - a, ab) / max(dot(ab, ab), 0.000001), 0.0, 1.0);
        float radiusA = max(uJoints[aIndex].w, 0.018);
        float radiusB = max(uJoints[bIndex].w, 0.018);
        float radius = mix(radiusA, radiusB, smoothstep(0.0, 1.0, t));
        d = smoothUnion(d, length(p - (a + ab * t)) - radius, 0.018);
    }
    return d;
}

vec3 fingerPoint(int finger, int point) {
    return uJoints[finger * 4 + point + 1].xyz;
}

float fingerPointRadius(int finger, int point) {
    return max(uJoints[finger * 4 + point + 1].w, 0.018);
}

vec3 fingerTangent(int finger, int point) {
    if (point == 0) return fingerPoint(finger, 1) - fingerPoint(finger, 0);
    if (point == 3) return fingerPoint(finger, 3) - fingerPoint(finger, 2);
    return 0.5 * (fingerPoint(finger, point + 1) - fingerPoint(finger, point - 1));
}

vec3 hermitePoint(vec3 a, vec3 b, vec3 tangentA, vec3 tangentB, float t) {
    float t2 = t * t, t3 = t2 * t;
    return (2.0*t3 - 3.0*t2 + 1.0) * a
         + (t3 - 2.0*t2 + t) * tangentA
         + (-2.0*t3 + 3.0*t2) * b
         + (t3 - t2) * tangentB;
}

vec3 hermiteDerivative(vec3 a, vec3 b, vec3 tangentA, vec3 tangentB, float t) {
    float t2 = t * t;
    return (6.0*t2 - 6.0*t) * a
         + (3.0*t2 - 4.0*t + 1.0) * tangentA
         + (-6.0*t2 + 6.0*t) * b
         + (3.0*t2 - 2.0*t) * tangentB;
}

vec3 hermiteSecondDerivative(vec3 a, vec3 b, vec3 tangentA, vec3 tangentB, float t) {
    return (12.0*t - 6.0) * a
         + (6.0*t - 4.0) * tangentA
         + (-12.0*t + 6.0) * b
         + (6.0*t - 2.0) * tangentB;
}

float fingerCurveSpanSdf(vec3 p, vec3 a, vec3 b, vec3 tangentA, vec3 tangentB,
                         float radiusA, float radiusB) {
    vec3 chord = b - a;
    float t = clamp(dot(p - a, chord) / max(dot(chord, chord), 0.000001), 0.0, 1.0);
    // Refine the closest centerline parameter directly on the cubic curve.
    for (int refine = 0; refine < 2; ++refine) {
        vec3 curve = hermitePoint(a, b, tangentA, tangentB, t);
        vec3 first = hermiteDerivative(a, b, tangentA, tangentB, t);
        vec3 second = hermiteSecondDerivative(a, b, tangentA, tangentB, t);
        vec3 offset = curve - p;
        float denominator = dot(first, first) + dot(offset, second);
        if (abs(denominator) > 0.000001)
            t = clamp(t - dot(offset, first) / denominator, 0.0, 1.0);
    }
    vec3 closest = hermitePoint(a, b, tangentA, tangentB, t);
    float radius = mix(radiusA, radiusB, smoothstep(0.0, 1.0, t));
    return length(p - closest) - radius;
}

float smoothFingerSdf(vec3 p) {
    float d = 1e3;
    // MCP-to-tip cubic centerlines pass smoothly through each finger's
    // existing four landmarks. Shared tangents make joints C1-continuous.
    for (int finger = 1; finger < 5; ++finger) {
        for (int span = 0; span < 3; ++span) {
            vec3 a = fingerPoint(finger, span);
            vec3 b = fingerPoint(finger, span + 1);
            vec3 tangentA = fingerTangent(finger, span);
            vec3 tangentB = fingerTangent(finger, span + 1);
            float radiusA = fingerPointRadius(finger, span);
            float radiusB = fingerPointRadius(finger, span + 1);

            // Early-out (result-preserving): the Hermite curve lies within the convex hull
            // of its Bezier control points, so it cannot get closer than this bound.
            vec3 c1 = a + tangentA * (1.0 / 3.0);
            vec3 c2 = b - tangentB * (1.0 / 3.0);
            vec3 center = 0.25 * (a + c1 + c2 + b);
            float hullRadius = sqrt(max(max(dot(a - center, a - center), dot(c1 - center, c1 - center)),
                                        max(dot(c2 - center, c2 - center), dot(b - center, b - center))));
            float lowerBound = length(p - center) - hullRadius - max(radiusA, radiusB);
            if (lowerBound > d + 0.018) continue;

            float spanSdf = fingerCurveSpanSdf(p, a, b, tangentA, tangentB,
                                               radiusA, radiusB);
            d = smoothUnion(d, spanSdf, 0.018);
        }
    }
    return d;
}

float fingerSdf(vec3 p) {
    return smoothUnion(thumbSdf(p), smoothFingerSdf(p), 0.018);
}

float handSdf(vec3 p, out float fingerWeight) {
    if (uDebugView == 1) {
        fingerWeight = 0.0;
        return palmSdf(p);
    }
    if (uDebugView == 2) {
        fingerWeight = 1.0;
        return fingerSdf(p);
    }

    float palmDistance = palmSdf(p);
    float fingerDistance = fingerSdf(p);
    // Material ownership follows the nearest component surface, not the most
    // negative SDF value; a buried component must not tint the visible shell.
    float palmSurfaceDistance = abs(palmDistance);
    float fingerSurfaceDistance = abs(fingerDistance);
    float transition = clamp(0.5 + (palmSurfaceDistance - fingerSurfaceDistance) / (2.0 * 0.018),
                             0.0, 1.0);
    fingerWeight = transition * transition * (3.0 - 2.0 * transition);
    return smoothUnion(palmDistance, fingerDistance, 0.018);
}

float handSdf(vec3 p) {
    float unusedFingerWeight = 0.0;
    return handSdf(p, unusedFingerWeight);
}

float jointTint(vec3 p) {
    float tint = 0.0;
    for (int finger = 0; finger < 5; ++finger) {
        for (int joint = 1; joint < 4; ++joint) {
            int index = chainIndex(finger, joint);
            float radius = max(uJoints[index].w * 1.35, 0.025);
            float amount = 1.0 - smoothstep(radius * 0.45, radius, length(p - uJoints[index].xyz));
            tint = max(tint, amount * 0.45);
        }
    }
    return tint;
}

void main() {
    vec3 rayOrigin = vec3(vWorldXY, 1.4);
    vec3 rayDirection = vec3(0.0, 0.0, -1.0);
    float t = 0.0;
    vec3 p = rayOrigin;
    bool hit = false;
    float fingerWeight = 0.0;
    for (int step = 0; step < 45; ++step) {
        p = rayOrigin + rayDirection * t;
        float distanceToSurface = handSdf(p, fingerWeight);
        if (distanceToSurface < 0.0015) {
            hit = true;
            break;
        }
        t += max(distanceToSurface * 0.90, 0.004);
        if (t > 2.8) break;
    }
    if (!hit) discard;

    float epsilon = 0.0025;
    // Four-tap tetrahedral gradient gives the SDF normal at lower shader cost.
    vec3 k1 = vec3(1.0, -1.0, -1.0), k2 = vec3(-1.0, -1.0, 1.0);
    vec3 k3 = vec3(-1.0, 1.0, -1.0), k4 = vec3(1.0, 1.0, 1.0);
    vec3 normal = normalize(
        k1 * handSdf(p + k1 * epsilon) + k2 * handSdf(p + k2 * epsilon) +
        k3 * handSdf(p + k3 * epsilon) + k4 * handSdf(p + k4 * epsilon));
    vec3 light = normalize(uLightDirection);
    vec3 view = vec3(0.0, 0.0, 1.0);
    vec3 halfway = normalize(light + view);
    float diffuse = max(dot(normal, light), 0.0);
    float specular = pow(max(dot(normal, halfway), 0.0), 18.0);
    //vec3 palmSkin = vec3(1, 0.0, 0.0);
    //vec3 fingerSkin = vec3(0.0, 1, 0.0);
    vec3 palmSkin   = vec3(0.74, 0.60, 0.52);
    vec3 fingerSkin = vec3(0.84, 0.69, 0.59);
    vec3 skin = mix(palmSkin, fingerSkin, fingerWeight);
    skin = mix(skin, vec3(0.79, 0.64, 0.56), jointTint(p));
    vec3 color = skin * (uAmbient + uDiffuseStrength * diffuse)
               + vec3(1.0) * (uSpecularStrength * specular);
    gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
)GLSL";

GLuint compile_hand_shader(GLenum type, const char* source) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint compiled = GL_FALSE;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    if (!compiled) {
        char log[1024] = {};
        glGetShaderInfoLog(shader, sizeof(log), NULL, log);
        std::cerr << "Hand shader compilation failed: " << log << std::endl;
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}

GLuint create_hand_sdf_program() {
    GLuint vertex = compile_hand_shader(GL_VERTEX_SHADER, hand_vertex_shader);
    GLuint fragment = compile_hand_shader(GL_FRAGMENT_SHADER, hand_fragment_shader);
    if (!vertex || !fragment) {
        if (vertex) glDeleteShader(vertex);
        if (fragment) glDeleteShader(fragment);
        return 0;
    }
    GLuint program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glLinkProgram(program);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    GLint linked = GL_FALSE;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (!linked) {
        char log[1024] = {};
        glGetProgramInfoLog(program, sizeof(log), NULL, log);
        std::cerr << "Hand shader link failed: " << log << std::endl;
        glDeleteProgram(program);
        return 0;
    }
    hand_sdf_uniforms.joints = glGetUniformLocation(program, "uJoints");
    hand_sdf_uniforms.light_direction = glGetUniformLocation(program, "uLightDirection");
    hand_sdf_uniforms.ambient = glGetUniformLocation(program, "uAmbient");
    hand_sdf_uniforms.diffuse = glGetUniformLocation(program, "uDiffuseStrength");
    hand_sdf_uniforms.specular = glGetUniformLocation(program, "uSpecularStrength");
    hand_sdf_uniforms.palm_half_depth = glGetUniformLocation(program, "uPalmHalfDepth");
    hand_sdf_uniforms.palm_depth_offset = glGetUniformLocation(program, "uPalmDepthOffset");
    hand_sdf_uniforms.debug_view = glGetUniformLocation(program, "uDebugView");
    return program;
}

void emit_disk(Vec2 center, float radius, int segments = 12) {
    const float tau = 6.28318530718f;
    for (int i = 0; i < segments; ++i) {
        float a0 = tau * i / segments, a1 = tau * (i + 1) / segments;
        glVertex2f(center.x, center.y);
        glVertex2f(center.x + std::cos(a0) * radius, center.y + std::sin(a0) * radius);
        glVertex2f(center.x + std::cos(a1) * radius, center.y + std::sin(a1) * radius);
    }
}

void emit_capsule(Vec2 a, Vec2 b, float radius) {
    Vec2 axis = normalized(b - a, {0.0f, 1.0f});
    Vec2 normal{-axis.y * radius, axis.x * radius};
    Vec2 a0 = a + normal, a1 = a - normal, b0 = b + normal, b1 = b - normal;
    glVertex2f(a0.x, a0.y); glVertex2f(a1.x, a1.y); glVertex2f(b1.x, b1.y);
    glVertex2f(a0.x, a0.y); glVertex2f(b1.x, b1.y); glVertex2f(b0.x, b0.y);
    emit_disk(a, radius);
    emit_disk(b, radius);
}

void draw_hand_surface(const Hand& hand) {
    if (!hand_sdf_program) return;

    Vec2 joint[21];
    float joint_data[21 * 4] = {};
    for (int i = 0; i < 21; ++i) {
        joint[i] = {hand.joints[i].x, hand.joints[i].y};
        joint_data[i * 4 + 0] = joint[i].x;
        joint_data[i * 4 + 1] = joint[i].y;
        joint_data[i * 4 + 2] = 0.0f;
    }

    // Knuckle spacing bounds the finger radius so thick fingers never fuse with
    // their neighbours, whatever scale the current sign was normalized to.
    float knuckle_span = length(joint[5] - joint[17]);
    float radius_cap = knuckle_span > 1e-4f ? knuckle_span * 0.14f : 0.085f;

    // Store a smooth radius profile at each existing joint, parameterized by
    // normalized cumulative chain length. Joint positions/topology are unchanged.
    float joint_along[21] = {};
    for (int f = 0; f < 5; ++f) {
        int first_segment = (f == 0) ? 0 : 1;
        float segment_lengths[4] = {};
        float cumulative[5] = {};
        float total_length = 0.0f;
        for (int s = first_segment; s < 4; ++s) {
            int a = finger_chains[f][s], b = finger_chains[f][s + 1];
            segment_lengths[s] = length(joint[b] - joint[a]);
            cumulative[s + 1] = cumulative[s] + segment_lengths[s];
            total_length += segment_lengths[s];
        }

        // Ensure all fingers have a consistent base radius derived from the hand's width,
        // rather than individual bone lengths which can be noisy or disproportionate in the dataset.
        float base_radius = std::max(0.030f, radius_cap * 0.95f);
        base_radius *= finger_thickness_scale * (f == 0 ? thumb_thickness_scale : 1.0f);
        base_radius = std::max(0.020f, base_radius);
        const float tip_taper = 0.12f;

        for (int joint_in_chain = first_segment; joint_in_chain <= 4; ++joint_in_chain) {
            float along = total_length > 1e-6f ? cumulative[joint_in_chain] / total_length : 0.0f;
            float radius = base_radius * (1.0f - tip_taper * smooth_profile(along));
            int joint_index = finger_chains[f][joint_in_chain];
            joint_data[joint_index * 4 + 3] = radius;
            joint_along[joint_index] = along;
        }
    }

    // The landmarks carry no Z, so synthesize finger depth from the 2D pose:
    //  * the chain rises smoothly from the palm plane (base) to the tip, and the
    //    tip always clears the palm's front face;
    //  * any joint whose footprint lies over the palm (curled fingers, a thumb
    //    folded across the palm) is lifted in front of the palm's front face.
    // A finger can therefore never end up buried inside the palm slab.
    for (int f = 0; f < 5; ++f) {
        for (int joint_in_chain = 1; joint_in_chain <= 4; ++joint_in_chain) {
            int index = finger_chains[f][joint_in_chain];
            float radius = joint_data[index * 4 + 3];
            float required_z = palm_front_z + radius + finger_palm_clearance;

            float ramp_z = required_z * smooth_profile(joint_along[index]);

            // 0 at the palm-attached knuckle, ramping to full for the outer joints.
            float lift_gate = joint_in_chain == 1 ? 0.0f : (joint_in_chain == 2 ? 0.7f : 1.0f);
            float distance_to_palm = palm_footprint_distance(joint, joint[index]);
            float overlap = distance_to_palm <= 0.0f
                ? 1.0f
                : 1.0f - smooth_profile(distance_to_palm / (radius + 0.06f));

            joint_data[index * 4 + 2] = std::max(ramp_z, overlap * lift_gate * required_z);
        }
    }

    float min_x = 1e9f, max_x = -1e9f, min_y = 1e9f, max_y = -1e9f;
    for (const Vec2& p : joint) {
        min_x = std::min(min_x, p.x); max_x = std::max(max_x, p.x);
        min_y = std::min(min_y, p.y); max_y = std::max(max_y, p.y);
    }
    const float margin = 0.12f; // covers the palm capsule radii and finger tips
    min_x -= margin; max_x += margin; min_y -= margin; max_y += margin;

    glUseProgram(hand_sdf_program);
    glUniform4fv(hand_sdf_uniforms.joints, 21, joint_data);
    glUniform3f(hand_sdf_uniforms.light_direction,
                hand_light_direction.x, hand_light_direction.y, hand_light_direction.z);
    glUniform1f(hand_sdf_uniforms.ambient, hand_ambient);
    glUniform1f(hand_sdf_uniforms.diffuse, hand_diffuse_strength);
    glUniform1f(hand_sdf_uniforms.specular, hand_specular_strength);
    glUniform1f(hand_sdf_uniforms.palm_half_depth, palm_half_depth);
    glUniform1f(hand_sdf_uniforms.palm_depth_offset, palm_depth_offset);
    glUniform1i(hand_sdf_uniforms.debug_view, hand_sdf_debug_view);

    // Rasterize only the joint bounds; every covered pixel ray-marches the 3D SDF.
    glBegin(GL_QUADS);
    glVertex2f(min_x, min_y); glVertex2f(max_x, min_y);
    glVertex2f(max_x, max_y); glVertex2f(min_x, max_y);
    glEnd();
    glUseProgram(0);
}

void draw_debug_skeleton(const Hand& hand) {
    glColor3f(0.95f, 0.82f, 0.25f);
    glBegin(GL_TRIANGLES);
    for (const auto& c : connections) {
        Vec2 a{hand.joints[c[0]].x, hand.joints[c[0]].y};
        Vec2 b{hand.joints[c[1]].x, hand.joints[c[1]].y};
        emit_capsule(a, b, 0.018f);
    }
    for (int i = 0; i < 21; ++i) emit_disk({hand.joints[i].x, hand.joints[i].y}, 0.027f);
    glEnd();
}

// Viewport + projection follow the window size and keep its aspect ratio, so hands are not
// stretched sideways in a wide window. view_half_height sets the zoom: a sign spans about
// +-0.9, so 1.6 leaves room around it (Kunal's original used a fixed +-3.0 in both axes).
const double view_half_height = 1.6;

void set_view(int width, int height) {
    if (width <= 0 || height <= 0) return;
    glViewport(0, 0, width, height);
    double aspect = (double)width / height;
    glMatrixMode(GL_PROJECTION);
    glLoadIdentity();
    glOrtho(-view_half_height * aspect, view_half_height * aspect,
            -view_half_height, view_half_height, -1, 1);
    glMatrixMode(GL_MODELVIEW);
}

// ================= MAIN =================
int main() {
    load_alphabets("alphabets.data");
    load_words("words.data");
    clean_up_words();

    glfwSetErrorCallback([](int error, const char* description) {
        std::cerr << "GLFW Error (" << error << "): " << description << std::endl;
    });

    if (!glfwInit()) return -1;

    glfwWindowHint(GLFW_DOUBLEBUFFER, GLFW_TRUE);
    GLFWwindow* window = glfwCreateWindow(800, 600, "ISL Unified Renderer", NULL, NULL);
    if (!window) {
        glfwTerminate();
        return -1;
    }

    glfwMakeContextCurrent(window);
    glfwSwapInterval(1); // Present only on refresh to prevent tearing.
    glewExperimental = GL_TRUE;
    glewInit();
    hand_sdf_program = create_hand_sdf_program();
    if (!hand_sdf_program) {
        std::cerr << "Could not initialize the volumetric hand renderer." << std::endl;
        glfwDestroyWindow(window);
        glfwTerminate();
        return -1;
    }

    glfwSetFramebufferSizeCallback(window, [](GLFWwindow*, int width, int height) {
        set_view(width, height);
    });
    int framebuffer_width = 0, framebuffer_height = 0;
    glfwGetFramebufferSize(window, &framebuffer_width, &framebuffer_height);
    set_view(framebuffer_width, framebuffer_height);
    glDisable(GL_DEPTH_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);

    std::cout << "\nRenderer active. Type a full sentence and press Enter...\n";

    std::thread(terminal_listener).detach();

    // Playback State Machine
    std::string current_input = "";
    int current_frame_idx = 0;
    bool is_playing = false;
    PoseState pose_state1, pose_state2;
    float current_word_cx = 0.5f, current_word_cy = 0.5f, current_word_scale = 1.0f;
    // Last pose drawn, and the pose the current item blends in from (see transition_seconds).
    Hand last_hand1, last_hand2, from_hand1, from_hand2;
    bool last_valid = false, last_has_second = false, from_valid = false, from_has_second = false;

    double base_fps = 30.0;
    double speed_factor = playback_speed_factor;
    double frame_duration = 1.0 / (base_fps * speed_factor);
    double item_start_time = 0.0; // Timer to track how long a static alphabet stays on screen
    int render_mode = 3; // 1 = raw skeleton, 2 = IK skeleton, 3 = generated hand

    // ================= RENDERING LOOP =================
    while (!glfwWindowShouldClose(window)) {
        glfwPollEvents();
        int requested_mode = render_mode;
        if (glfwGetKey(window, GLFW_KEY_1) == GLFW_PRESS) requested_mode = 1;
        if (glfwGetKey(window, GLFW_KEY_2) == GLFW_PRESS) requested_mode = 2;
        if (glfwGetKey(window, GLFW_KEY_3) == GLFW_PRESS) requested_mode = 3;
        if (requested_mode != render_mode) {
            render_mode = requested_mode;
            const char* mode_name = render_mode == 1 ? "raw skeleton" :
                                    render_mode == 2 ? "IK skeleton" : "hand surface";
            std::string title = std::string("ISL Unified Renderer - ") + mode_name + " (1/2/3)";
            glfwSetWindowTitle(window, title.c_str());
        }

        double current_time = glfwGetTime();
        bool animation_finished = false;

        // 1. Playback Timer Logic
        if (is_playing && !current_input.empty()) {
            if (current_input.length() == 1) {
                // Static Alphabets stay on screen for a fixed duration
                if (current_time - item_start_time >= 1.5) {
                    animation_finished = true;
                }
            } else {
                // Animated Words
                auto word_it = words_dict.find(current_input);
                if (word_it != words_dict.end() && !word_it->second.empty()) {
                    int max_frames = (int)word_it->second.size();
                    // Time-based playback: the frame is a function of elapsed time,
                    // so playback speed never depends on how fast we render.
                    double elapsed_frames = std::max(0.0, (current_time - item_start_time) / frame_duration);
                    current_frame_idx = (int)elapsed_frames;
                    if (current_frame_idx >= max_frames) {
                        animation_finished = true;
                    }
                } else {
                    // Safety check: If a word isn't in our dictionary, instantly skip it
                    animation_finished = true;
                }
            }
        }

        // 2. Queue Management
        if (animation_finished || !is_playing) {
            std::lock_guard<std::mutex> lock(queue_mutex);
            if (!display_queue.empty()) {
                current_input = display_queue.front();
                display_queue.pop();
                current_frame_idx = 0;
                is_playing = true;

                // Reset timers and IK pose state for the new word/alphabet
                item_start_time = glfwGetTime();
                from_hand1 = last_hand1; from_hand2 = last_hand2;
                from_valid = last_valid; from_has_second = last_has_second;
                pose_state1.initialized = false;
                pose_state2.initialized = false;

                // Precalculate global bounding box for the entire word animation
                // This ensures large/messy words from the dataset don't break the renderer scale
                if (current_input.length() > 1) {
                    auto word_it = words_dict.find(current_input);
                    if (word_it != words_dict.end() && !word_it->second.empty()) {
                        float min_x = 1e9, max_x = -1e9, min_y = 1e9, max_y = -1e9;
                        for (const auto& frame : word_it->second) {
                            for (const auto& pt : frame) {
                                min_x = std::min(min_x, pt.first);
                                max_x = std::max(max_x, pt.first);
                                min_y = std::min(min_y, pt.second);
                                max_y = std::max(max_y, pt.second);
                            }
                        }
                        current_word_cx = (min_x + max_x) / 2.0f;
                        current_word_cy = (min_y + max_y) / 2.0f;
                        current_word_scale = std::max(max_x - min_x, max_y - min_y);
                        if (current_word_scale < 0.0001f) current_word_scale = 1.0f;
                    }
                }

                std::cout << "Rendering: " << current_input << std::endl;
            } else {
                // Queue is empty, wait for more input
                is_playing = false;
                current_input = "";
            }
        }

        std::vector<std::pair<float, float>> active_points;
        bool data_found = false;

        if (is_playing && !current_input.empty()) {
            if (current_input.length() == 1) {
                auto letter_it = alphabets_dict.find(current_input);
                if (letter_it != alphabets_dict.end()) {
                    active_points = letter_it->second;
                    data_found = true;
                }
            } else {
                auto word_it = words_dict.find(current_input);
                if (word_it != words_dict.end() && current_frame_idx < (int)word_it->second.size()) {
                    const auto& sequence = word_it->second;
                    int max_frames = (int)sequence.size();
                    // Smooth curve through the neighbouring frames (play-once: clamp at the ends).
                    int i1 = current_frame_idx;
                    int i0 = std::max(i1 - 1, 0);
                    int i2 = std::min(i1 + 1, max_frames - 1);
                    int i3 = std::min(i1 + 2, max_frames - 1);
                    double elapsed_frames = std::max(0.0, (current_time - item_start_time) / frame_duration);
                    float blend = (float)std::max(0.0, std::min(1.0, elapsed_frames - current_frame_idx));
                    const auto& f0 = sequence[i0];
                    const auto& f1 = sequence[i1];
                    const auto& f2 = sequence[i2];
                    const auto& f3 = sequence[i3];
                    active_points = f1;
                    if (f0.size() == f1.size() && f2.size() == f1.size() && f3.size() == f1.size()) {
                        for (size_t i = 0; i < f1.size(); ++i) {
                            active_points[i].first = catmull_rom(f0[i].first, f1[i].first, f2[i].first, f3[i].first, blend);
                            active_points[i].second = catmull_rom(f0[i].second, f1[i].second, f2[i].second, f3[i].second, blend);
                        }
                    }
                    data_found = true;
                }
            }
        }

        glClearColor(0.1f, 0.15f, 0.2f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        glLoadIdentity();

        if (data_found && active_points.size() >= 21) {
            Hand hand1, hand2;
            bool has_second_hand = (active_points.size() >= 42);

            // Using the same dynamic scale factor for both alphabets and words now
            float global_scale = 1.8f;

            if (current_input.length() == 1) {
                // ==========================================
                // ALPHABETS: Dynamic Bounding Box Normalization
                // ==========================================
                int total_points = has_second_hand ? 42 : 21;
                float min_x = 1e9, max_x = -1e9, min_y = 1e9, max_y = -1e9;

                for (int i = 0; i < total_points; i++) {
                    min_x = std::min(min_x, active_points[i].first);
                    max_x = std::max(max_x, active_points[i].first);
                    min_y = std::min(min_y, active_points[i].second);
                    max_y = std::max(max_y, active_points[i].second);
                }

                float cx = (min_x + max_x) / 2.0f;
                float cy = (min_y + max_y) / 2.0f;
                float scale = std::max(max_x - min_x, max_y - min_y);
                if (scale < 0.0001f) scale = 1.0f;

                for (int i = 0; i < 21; i++) {
                    hand1.joints[i].x = ((active_points[i].first - cx) / scale) * global_scale;
                    hand1.joints[i].y = -((active_points[i].second - cy) / scale) * global_scale;

                    if (has_second_hand) {
                        hand2.joints[i].x = ((active_points[i + 21].first - cx) / scale) * global_scale;
                        hand2.joints[i].y = -((active_points[i + 21].second - cy) / scale) * global_scale;
                    }
                }
            } else {
                // ==========================================
                // WORDS: Dynamic Global Normalization
                // ==========================================
                for (int i = 0; i < 21; i++) {
                    float nx1 = active_points[i].first;
                    float ny1 = active_points[i].second;

                    // Now all words, old and new, will perfectly fit the viewport
                    hand1.joints[i].x = ((nx1 - current_word_cx) / current_word_scale) * global_scale;
                    hand1.joints[i].y = -((ny1 - current_word_cy) / current_word_scale) * global_scale;

                    if (has_second_hand) {
                        float nx2 = active_points[i + 21].first;
                        float ny2 = active_points[i + 21].second;

                        hand2.joints[i].x = ((nx2 - current_word_cx) / current_word_scale) * global_scale;
                        hand2.joints[i].y = -((ny2 - current_word_cy) / current_word_scale) * global_scale;
                    }
                }
            }

            // Ease in from the previous word/letter instead of jumping to the new pose.
            double since_start = current_time - item_start_time;
            if (from_valid && since_start < transition_seconds) {
                float s = smooth_profile((float)(since_start / transition_seconds));
                for (int i = 0; i < 21; ++i) {
                    hand1.joints[i].x = from_hand1.joints[i].x + (hand1.joints[i].x - from_hand1.joints[i].x) * s;
                    hand1.joints[i].y = from_hand1.joints[i].y + (hand1.joints[i].y - from_hand1.joints[i].y) * s;
                    if (has_second_hand && from_has_second) {
                        hand2.joints[i].x = from_hand2.joints[i].x + (hand2.joints[i].x - from_hand2.joints[i].x) * s;
                        hand2.joints[i].y = from_hand2.joints[i].y + (hand2.joints[i].y - from_hand2.joints[i].y) * s;
                    }
                }
            }
            last_hand1 = hand1; last_hand2 = hand2;
            last_valid = true; last_has_second = has_second_hand;

            Hand raw_hand1 = hand1;
            correct_hand_pose(hand1, pose_state1);
            if (render_mode == 1) draw_debug_skeleton(raw_hand1);
            else if (render_mode == 2) draw_debug_skeleton(hand1);
            else draw_hand_surface(hand1);
            if (has_second_hand) {
                Hand raw_hand2 = hand2;
                correct_hand_pose(hand2, pose_state2);
                if (render_mode == 1) draw_debug_skeleton(raw_hand2);
                else if (render_mode == 2) draw_debug_skeleton(hand2);
                else draw_hand_surface(hand2);
            }
        } else {
            last_valid = false;   // idle: the next sign starts fresh instead of sliding in
        }

        glfwSwapBuffers(window);
    }

    glDeleteProgram(hand_sdf_program);
    glfwTerminate();
    return 0;
}
