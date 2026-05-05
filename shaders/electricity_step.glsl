// ═══════════════════════════════════════════════════════════════════════════════
// Electricity propagation shader (Phase 1)
//
// Propagates electric charge/potential through conductive materials using a
// 4-neighbour stencil weighted by per-material electrical conductivity (cond).
// Insulators (cond ≈ 0) block flow; conductors (cond > 0) allow charge to
// equalise with neighbours.  Optional decay term prevents runaway accumulation.
//
// Reads:  chargeIn (r32f image), cells (SSBO), rules (SSBO)
// Writes: chargeOut (r32f image)
// ═══════════════════════════════════════════════════════════════════════════════

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer defined in common.glsl (binding = 2)

layout(r32f, binding = 9)  uniform readonly  image2D chargeIn;
layout(r32f, binding = 10) uniform writeonly image2D chargeOut;

uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float dt;
uniform float chargeDecay;      // per-frame exponential decay (0 = none)
uniform float maxCharge;        // hard cap to prevent runaway

float neighbourCharge(ivec2 p, float selfCharge){
    return inBounds(p, gridSize) ? imageLoad(chargeIn, p).r : selfCharge;
}

float neighbourCond(ivec2 p, float selfCond){
    if(!inBounds(p, gridSize)) return 0.0; // domain wall = insulator
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    return getRule(getType(cells[idx]), ruleStride).cond;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ  = getType(cell);
    Rule r = getRule(typ, ruleStride);

    float q = imageLoad(chargeIn, p).r;

    // Only propagate if this cell has any conductivity.
    // Insulators keep their charge frozen (useful for stored charge).
    float qNew = q;
    if(r.cond > 0.0){
        ivec2 pL = p + ivec2(-1, 0);
        ivec2 pR = p + ivec2( 1, 0);
        ivec2 pD = p + ivec2( 0,-1);
        ivec2 pU = p + ivec2( 0, 1);

        float qL = neighbourCharge(pL, q);
        float qR = neighbourCharge(pR, q);
        float qD = neighbourCharge(pD, q);
        float qU = neighbourCharge(pU, q);

        float cL = neighbourCond(pL, r.cond);
        float cR = neighbourCond(pR, r.cond);
        float cD = neighbourCond(pD, r.cond);
        float cU = neighbourCond(pU, r.cond);

        // Flux proportional to conductivity-weighted charge gradient.
        // Harmonic mean of the two face conductivities gives correct
        // series resistance across a material boundary.
        float flux = 0.0;
        float wL = (r.cond * cL) / max(r.cond + cL, 1e-6) * 2.0;
        float wR = (r.cond * cR) / max(r.cond + cR, 1e-6) * 2.0;
        float wD = (r.cond * cD) / max(r.cond + cD, 1e-6) * 2.0;
        float wU = (r.cond * cU) / max(r.cond + cU, 1e-6) * 2.0;
        flux = wL*(qL - q) + wR*(qR - q) + wD*(qD - q) + wU*(qU - q);

        // Explicit update with dt scaling; clamp for stability.
        float rate = 4.0; // heuristic diffusion speed
        qNew = q + clamp(flux * rate * dt, -maxCharge, maxCharge);
    }

    // Decay toward zero (leakage)
    if(chargeDecay > 0.0){
        qNew = mix(qNew, 0.0, clamp(chargeDecay * dt, 0.0, 1.0));
    }

    // Hard cap
    qNew = clamp(qNew, -maxCharge, maxCharge);

    imageStore(chargeOut, p, vec4(qNew, 0.0, 0.0, 0.0));
}
