#version 430

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
layout(rg32f, binding = 3) uniform readonly  image2D velIn;  // Cross-system coupling
layout(r32f, binding = 15) uniform readonly  image2D moistureIn;  // v6.1: Moisture for conductivity

uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float dt;
uniform float chargeDecay;      // per-frame exponential decay (0 = none)
uniform float maxCharge;        // hard cap to prevent runaway

// v6.1 Deep System Interactions uniforms
uniform float electricity_moisture_boost;  // Default: 2.0 - conductivity multiplier per moisture
uniform float wet_arc_temp_multiplier;     // Default: 0.5 - arc heat reduction when wet
uniform float electrolysis_strength;         // Default: 0.3 - charge transport via liquid velocity

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
    vec2 v = imageLoad(velIn, p).xy;  // Cross-system coupling
    float moisture = imageLoad(moistureIn, p).r;  // v6.1: Read moisture

    // Only propagate if this cell has any conductivity.
    // Insulators keep their charge frozen (useful for stored charge).
    float qNew = q;
    if(r.cond > 0.0){
        // v6.1: Moisture-based conductivity boost (Rule A)
        float moistureBoost = 1.0 + moisture * electricity_moisture_boost;
        float effectiveCond = r.cond * moistureBoost;

        // v7.0: Plasma has maximum conductivity and faster propagation
        if(r.sf == 3){  // plasma state family
            effectiveCond = 1.0;  // Override to maximum
        }

        ivec2 pL = p + ivec2(-1, 0);
        ivec2 pR = p + ivec2( 1, 0);
        ivec2 pD = p + ivec2( 0,-1);
        ivec2 pU = p + ivec2( 0, 1);

        float qL = neighbourCharge(pL, q);
        float qR = neighbourCharge(pR, q);
        float qD = neighbourCharge(pD, q);
        float qU = neighbourCharge(pU, q);

        // v6.1: Use moisture-enhanced conductivity for neighbors too
        float cL = neighbourCond(pL, effectiveCond);
        float cR = neighbourCond(pR, effectiveCond);
        float cD = neighbourCond(pD, effectiveCond);
        float cU = neighbourCond(pU, effectiveCond);

        // Flux proportional to conductivity-weighted charge gradient.
        // Harmonic mean of the two face conductivities gives correct
        // series resistance across a material boundary.
        float flux = 0.0;
        float wL = (effectiveCond * cL) / max(effectiveCond + cL, 1e-6) * 2.0;
        float wR = (effectiveCond * cR) / max(effectiveCond + cR, 1e-6) * 2.0;
        float wD = (effectiveCond * cD) / max(effectiveCond + cD, 1e-6) * 2.0;
        float wU = (effectiveCond * cU) / max(effectiveCond + cU, 1e-6) * 2.0;
        flux = wL*(qL - q) + wR*(qR - q) + wD*(qD - q) + wU*(qU - q);

        // v6.1: Higher propagation speed when moisture is present (wet conductor effect)
        // v7.0: Plasma has faster propagation rate
        float rate = 4.0 * (1.0 + moisture * 0.5);
        if(r.sf == 3){  // plasma state family
            rate = 8.0;  // Faster propagation in plasma
        }
        qNew = q + clamp(flux * rate * dt, -maxCharge, maxCharge);
    }

    // v6.1: Electrolysis - charged liquid cells conduct via velocity (Rule A part 2)
    if(r.cat == 2 && length(v) > 0.5 && abs(q) > 10.0) {
        ivec2 velDir = ivec2(int(sign(v.x)), int(sign(v.y)));
        ivec2 target = p + velDir;
        if(inBounds(target, gridSize)){
            // Velocity field transports charge downstream
            float transport = q * electrolysis_strength * length(v) * dt;
            qNew -= transport;  // Lose charge to downstream
        }
    }

    // Cross-system coupling: Velocity-dependent charge advection
    // Moving conductors carry charge downstream
    if(length(v) > 1.0 && r.cond > 0.0){
        ivec2 upwind = p - ivec2(int(sign(v.x)), int(sign(v.y)));
        if(inBounds(upwind, gridSize)){
            float upCharge = imageLoad(chargeIn, upwind).r;
            qNew = mix(qNew, upCharge, 0.3 * length(v) * dt);
        }
    }

    // Decay toward zero (leakage)
    if(chargeDecay > 0.0){
        qNew = mix(qNew, 0.0, clamp(chargeDecay * dt, 0.0, 1.0));
    }

    // Hard cap
    qNew = clamp(qNew, -maxCharge, maxCharge);

    imageStore(chargeOut, p, vec4(qNew, 0.0, 0.0, 0.0));
}
