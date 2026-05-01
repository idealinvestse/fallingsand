// ═══════════════════════════════════════════════════════════════════════════════
// Heat diffusion shader (Phase 2)
// 
// Performs explicit heat diffusion using a 4-neighbour stencil with per-material
// thermal conductivity (k), heat capacity (cp), and Newton cooling toward ambient.
// Runs iteratively for heat_diffusion_iterations passes per frame.
// 
layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl
// common.glsl is prepended by shader registry

layout(r32f, binding = 11) uniform readonly image2D tempIn;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;

uniform uvec2 gridSize;
uniform uint ruleStride;
uniform float ambientTemp;
uniform float dt;
// Face-averaged thermal conductivity using the harmonic mean of the two adjacent
// cell conductivities. This is the standard finite-volume treatment for
// conjugate heat transfer across a material interface: the face carries a
// series-resistance (1/k_face = 1/k_self + 1/k_n), which prevents spurious
// heat leaks across, e.g., a water / solid-stone boundary with very different k.
float harmonicK(float kSelf, float kN){
    float s = kSelf + kN;
    if(s < 1e-6) return 0.0;
    return 2.0 * kSelf * kN / s;
}

float neighbourTemp(ivec2 p, float tSelf){
    return inBounds(p, gridSize) ? imageLoad(tempIn, p).r : tSelf;
}

float neighbourK(ivec2 p, float kSelf){
    if(!inBounds(p, gridSize)) return kSelf; // mirror -> zero flux at domain wall
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    return getRule(getType(cells[idx]), ruleStride).k;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ = getType(cell);
    Rule r = getRule(typ, ruleStride);

    // Read current temperature in simulation units.
    float temp = imageLoad(tempIn, p).r;

    // Sample neighbour temperatures (mirror / zero-flux at domain edges).
    ivec2 pL = p + ivec2(-1, 0);
    ivec2 pR = p + ivec2( 1, 0);
    ivec2 pD = p + ivec2( 0,-1);
    ivec2 pU = p + ivec2( 0, 1);
    float tL = neighbourTemp(pL, temp);
    float tR = neighbourTemp(pR, temp);
    float tD = neighbourTemp(pD, temp);
    float tU = neighbourTemp(pU, temp);

    // Per-face harmonic conductivity.  Solids/domain walls share the same
    // stencil -- the mirrored temperature already produces zero flux when
    // tN = tSelf, which is the desired adiabatic boundary.
    float kSelf = r.k;
    float kFL = harmonicK(kSelf, neighbourK(pL, kSelf));
    float kFR = harmonicK(kSelf, neighbourK(pR, kSelf));
    float kFD = harmonicK(kSelf, neighbourK(pD, kSelf));
    float kFU = harmonicK(kSelf, neighbourK(pU, kSelf));

    // Explicit FV stencil: T_new = T + (dt/cp) · Σ k_face · (T_n − T_self).
    // The update is stabilised by clamping the total diffusion weight so the
    // equivalent first-order rate stays below 0.25 for extra headroom.
    float cp = max(r.cp, 0.05);
    float w  = dt / cp;
    float flux = kFL * (tL - temp) + kFR * (tR - temp)
               + kFD * (tD - temp) + kFU * (tU - temp);
    float rateCap = 0.25 / max(kFL + kFR + kFD + kFU, 1e-6);
    w = min(w, rateCap);
    float diffused = temp + w * flux;

    // Newton cooling toward ambient temperature
    // Rate proportional to cooling coefficient and inversely proportional to
    // heat capacity, so high-capacity materials retain heat longer.
    float coolingRate = clamp(r.cool * dt / cp, 0.0, 1.0);
    float cooled = mix(diffused, ambientTemp, coolingRate);

    // Emissive radiation cooling using a Stefan-Boltzmann-like model:
    // Q_rad ~ emissivity * (T^4 - T_ambient^4), scaled into simulation units.
    if(r.emit > 0.0){
        const float sigma = 0.02;
        float tSelf = max(cooled, 0.0);
        float tAmb = max(ambientTemp, 0.0);
        float radLoss = r.emit * sigma * (pow(tSelf, 4.0) - pow(tAmb, 4.0)) * dt / cp;
        cooled = max(ambientTemp, cooled - max(radLoss, 0.0));
    }

    imageStore(tempOut, p, vec4(cooled, 0.0, 0.0, 0.0));
}
