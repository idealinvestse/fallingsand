// ═══════════════════════════════════════════════════════════════════════════════
// Acoustic velocity step (weakly-compressible gas solver)
//
// Updates velocity in gas cells using the Euler momentum equation:
//   u_new = u_old − grad(p) · dt_ac
//
// Uses uniform gas density (ρ=1) so that c²·ρ = c² and 1/ρ = 1,
// keeping the wave speed exactly equal to the soundSpeed uniform.
// Buoyancy-driven density differences are handled separately by force_shader.
//
// Only operates on gas-phase cells (cat == 0). At gas/non-gas boundaries,
// the pressure gradient is set to zero (reflecting boundary condition).
//
// CFL stability: c · dt_ac / dx ≤ 1/√2 ≈ 0.707  (2D explicit)
// ═══════════════════════════════════════════════════════════════════════════════
layout(local_size_x = 8, local_size_y = 8) in;

// ── Bindings ─────────────────────────────────────────────────────────────────
layout(std430, binding = 0) readonly buffer CellBuffer  { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(rg32f, binding = 3) uniform readonly  image2D velIn;       // current velocity
layout(rg32f, binding = 4) uniform writeonly image2D velOut;       // updated velocity
layout(r32f,  binding = 5) uniform readonly  image2D pressureIn;   // updated pressure (from pressure step)

// ── Uniforms ─────────────────────────────────────────────────────────────────
uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float dtAcoustic;       // dt per substep (1.0 / ACOUSTIC_SUBSTEPS)
uniform float ambientPressure;  // background atmospheric pressure

// ── Unique to this shader: lightweight AcousticRule ─────────────────────────
struct AcousticRule { int cat; };

AcousticRule getRule(uint tp) {
    uint o = tp * ruleStride;
    AcousticRule r;
    r.cat = int(rules[o + 4u]);
    return r;
}

// Check if a neighbour cell is gas (for boundary treatment)
bool isGasNeighbour(ivec2 np) {
    if (!inBounds(np, gridSize)) return false;
    uint nIdx = uint(np.y) * gridSize.x + uint(np.x);
    return getRule(getType(cells[nIdx]), ruleStride).cat == 0;
}

// ── Main ─────────────────────────────────────────────────────────────────────
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    AcousticRule r = getRule(typ);

    vec2 uOld = imageLoad(velIn, p).xy;

    // Non-gas cells: pass through unchanged
    if (r.cat != 0) {
        imageStore(velOut, p, vec4(uOld, 0.0, 0.0));
        return;
    }

    // ── Compute pressure gradient ────────────────────────────────────────
    // Central differences: grad(p) = ((pR − pL)/2, (pU − pD)/2)
    // At non-gas or out-of-bounds neighbours, use own pressure (zero gradient = reflecting wall)

    float pC = imageLoad(pressureIn, p).r;

    ivec2 pL = p + ivec2(-1, 0);
    ivec2 pR = p + ivec2( 1, 0);
    ivec2 pD = p + ivec2( 0,-1);
    ivec2 pU = p + ivec2( 0, 1);

    float pLeft  = (inBounds(pL, gridSize) && isGasNeighbour(pL)) ? imageLoad(pressureIn, pL).r : pC;
    float pRight = (inBounds(pR, gridSize) && isGasNeighbour(pR)) ? imageLoad(pressureIn, pR).r : pC;
    float pDown  = (inBounds(pD, gridSize) && isGasNeighbour(pD)) ? imageLoad(pressureIn, pD).r : pC;
    float pUp    = (inBounds(pU, gridSize) && isGasNeighbour(pU)) ? imageLoad(pressureIn, pU).r : pC;

    vec2 gradP = vec2(pRight - pLeft, pUp - pDown) * 0.5;

    // ── Velocity update ───────────────────────────────────────────────────
    // u_new = u_old − grad(p) · dt    (uniform ρ=1 for gas)
    // Clamp gradient to prevent blow-up from extreme pressure differences
    gradP = clamp(gradP, vec2(-5.0), vec2(5.0));
    vec2 uNew = uOld - gradP * dtAcoustic;
    // Clamp velocity for stability
    uNew = clamp(uNew, vec2(-10.0), vec2(10.0));

    imageStore(velOut, p, vec4(uNew, 0.0, 0.0));
}
