#version 430

// ═══════════════════════════════════════════════════════════════════════════════
// Semi-Lagrangian BFECC advection for velocity and temperature (Phase 4)
//
// BFECC = Back and Forth Error Compensation and Correction
// Provides 2nd-order accuracy using bilinear interpolation with minimal overhead.
//
// References:
//   * Dupont & Liu 2003, "Back and forth error compensation and correction
//     methods for semi-Lagrangian schemes"
//   * Selle et al. 2008, "An unconditionally stable MacCormack method"
//
// Pipeline:
//   1. Semi-Lagrangian backward trace:    φ̃(x) = φⁿ(x − u·dt)
//   2. Forward trace correction:            φ̃̃(x) = φ̃(x + u·dt)
//   3. Error:                               e = (φⁿ − φ̃̃) / 2
//   4. Corrected advection:                 φⁿ⁺¹(x) = φ̃(x) + e(x − u·dt)
//
// Optimized single-pass BFECC using velocity at midpoint (Kim et al. 2005):
//   φⁿ⁺¹ = φ̃(x − u·dt) − (φ̃(x) − φⁿ(x)) / 2
//   (equivalent to semi-Lagrangian with error correction)
//
// Solids are treated as no-slip walls (velocity = 0 inside solids).
// Temperature uses same advection with no-flux BC at walls.
// ═══════════════════════════════════════════════════════════════════════════════

layout(local_size_x = 16, local_size_y = 16) in;

// Input velocity (RG32F: vx, vy)
layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(rg32f, binding = 4) uniform writeonly image2D velOut;

// Temperature (R32F) - matching engine.py conventions
layout(r32f, binding = 11) uniform readonly image2D tempIn;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;

// Cell buffer for solid detection
layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl

uniform uvec2 gridSize;
uniform float dt;
uniform uint ruleStride;
uniform uint enableBFECC;  // Toggle: 0=basic SL, 1=BFECC correction

const uint RHO_MIN = 0x3C800000u; // floatBitsToUint(0.25f)

// Rule struct and getRule are now defined in common.glsl

bool isSolid(ivec2 p) {
    if (!inBounds(p, gridSize)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ, ruleStride).cat == 3;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Bilinear sampler for velocity (returns 0 at solid boundaries)
// ═══════════════════════════════════════════════════════════════════════════════
vec2 sampleVelBilinear(vec2 pos) {
    // Clamp to valid sampling range to prevent out-of-bounds
    vec2 clampedPos = clamp(pos, vec2(0.5), vec2(gridSize) - 0.5);
    vec2 base = floor(clampedPos - 0.5);
    vec2 t = clampedPos - 0.5 - base;
    ivec2 i00 = ivec2(base);
    
    // Clamp indices to valid range [0, gridSize-1]
    ivec2 i10 = clamp(i00 + ivec2(1, 0), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i01 = clamp(i00 + ivec2(0, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i11 = clamp(i00 + ivec2(1, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    i00 = clamp(i00, ivec2(0), ivec2(gridSize) - ivec2(1));
    
    vec2 v00 = isSolid(i00) ? vec2(0.0) : imageLoad(velIn, i00).xy;
    vec2 v10 = isSolid(i10) ? vec2(0.0) : imageLoad(velIn, i10).xy;
    vec2 v01 = isSolid(i01) ? vec2(0.0) : imageLoad(velIn, i01).xy;
    vec2 v11 = isSolid(i11) ? vec2(0.0) : imageLoad(velIn, i11).xy;
    
    vec2 v0 = mix(v00, v10, t.x);
    vec2 v1 = mix(v01, v11, t.x);
    return mix(v0, v1, t.y);
}

// Simple bilinear sampler without solid masking (for error correction)
// Clamps to grid edges to prevent out-of-bounds access
vec2 sampleVelRaw(vec2 pos) {
    vec2 clampedPos = clamp(pos, vec2(0.5), vec2(gridSize) - 0.5);
    vec2 base = floor(clampedPos - 0.5);
    vec2 t = clampedPos - 0.5 - base;
    ivec2 i00 = ivec2(base);
    
    // Clamp indices to valid range [0, gridSize-1]
    ivec2 i10 = clamp(i00 + ivec2(1, 0), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i01 = clamp(i00 + ivec2(0, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i11 = clamp(i00 + ivec2(1, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    i00 = clamp(i00, ivec2(0), ivec2(gridSize) - ivec2(1));
    
    vec2 v00 = imageLoad(velIn, i00).xy;
    vec2 v10 = imageLoad(velIn, i10).xy;
    vec2 v01 = imageLoad(velIn, i01).xy;
    vec2 v11 = imageLoad(velIn, i11).xy;
    
    vec2 v0 = mix(v00, v10, t.x);
    vec2 v1 = mix(v01, v11, t.x);
    return mix(v0, v1, t.y);
}

// Temperature sampler with Neumann BC (no flux through walls)
// Clamps to grid edges to prevent out-of-bounds access
float sampleTempBilinear(vec2 pos, float selfTemp) {
    vec2 clampedPos = clamp(pos, vec2(0.5), vec2(gridSize) - 0.5);
    vec2 base = floor(clampedPos - 0.5);
    vec2 t = clampedPos - 0.5 - base;
    ivec2 i00 = ivec2(base);
    
    // Clamp indices to valid range [0, gridSize-1]
    ivec2 i10 = clamp(i00 + ivec2(1, 0), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i01 = clamp(i00 + ivec2(0, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    ivec2 i11 = clamp(i00 + ivec2(1, 1), ivec2(0), ivec2(gridSize) - ivec2(1));
    i00 = clamp(i00, ivec2(0), ivec2(gridSize) - ivec2(1));
    
    // Neumann BC: at solid boundaries, return self temperature (no flux)
    float t00 = isSolid(i00) ? selfTemp : imageLoad(tempIn, i00).x;
    float t10 = isSolid(i10) ? selfTemp : imageLoad(tempIn, i10).x;
    float t01 = isSolid(i01) ? selfTemp : imageLoad(tempIn, i01).x;
    float t11 = isSolid(i11) ? selfTemp : imageLoad(tempIn, i11).x;
    
    float t0 = mix(t00, t10, t.x);
    float t1 = mix(t01, t11, t.x);
    return mix(t0, t1, t.y);
}

// ═══════════════════════════════════════════════════════════════════════════════
// Semi-Lagrangian advection with optional BFECC correction
// ═══════════════════════════════════════════════════════════════════════════════
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (!inBounds(p, gridSize)) return;
    
    // Get current velocity at this cell
    vec2 vHere = imageLoad(velIn, p).xy;
    float tHere = imageLoad(tempIn, p).x;
    
    // Solid cells: enforce no-slip (zero velocity), temperature unchanged
    if (isSolid(p)) {
        imageStore(velOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        imageStore(tempOut, p, vec4(tHere, 0.0, 0.0, 0.0));
        return;
    }
    
    // ── Semi-Lagrangian backward trace ─────────────────────────────────────────
    // Trace particle at current position back to where it came from
    // X_new = X - v(X) * dt
    
    // Use midpoint velocity for stability (RK2-ish)
    vec2 posMid = vec2(p) - 0.5 * vHere * dt;
    vec2 vMid = sampleVelRaw(posMid);
    vec2 posBack = vec2(p) - vMid * dt;
    
    // Sample velocity and temperature at back-traced position
    vec2 vSL = sampleVelBilinear(posBack);
    float tSL = sampleTempBilinear(posBack, tHere);
    
    // ── BFECC correction (optional) ────────────────────────────────────────────
    if (enableBFECC != 0u) {
        // Forward trace to estimate error
        // X_back = X + vSL * dt
        vec2 posForward = vec2(p) + vSL * dt;
        
        // Sample forward-traced value
        vec2 vForward = sampleVelBilinear(posForward);
        float tForward = sampleTempBilinear(posForward, tHere);
        
        // Error estimate: e = (vHere - vForward) / 2
        vec2 velError = (vHere - vForward) * 0.5;
        float tempError = (tHere - tForward) * 0.5;
        
        // Check if error is small enough for BFECC to be stable
        // If error is too large, fall back to basic semi-Lagrangian
        float errorMag = length(velError);
        const float MAX_BFECC_ERROR = 2.0;  // Threshold for stability
        
        if (errorMag < MAX_BFECC_ERROR) {
            // Backward trace from midpoint to apply correction
            vec2 posCorrected = posBack - velError * dt;
            
            // Apply correction
            vSL = sampleVelBilinear(posCorrected) + velError;
            tSL = sampleTempBilinear(posCorrected, tHere) + tempError;
        }
        // else: error too large, use basic semi-Lagrangian result
    }
    
    // Write results
    imageStore(velOut, p, vec4(vSL, 0.0, 0.0));
    imageStore(tempOut, p, vec4(tSL, 0.0, 0.0, 0.0));
}
