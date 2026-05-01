// ═══════════════════════════════════════════════════════════════════════════════
// Acoustic pressure step (weakly-compressible gas solver)
//
// Updates pressure in gas cells using the linearised continuity equation:
//   p_new = p_old − c² · div(u) · dt_ac
//
// Only operates on gas-phase cells (cat == 0). Non-gas cells pass through
// their existing pressure unchanged. At gas/non-gas boundaries, neighbour
// velocity is treated as zero (reflecting boundary condition).
//
// CFL stability: c · dt_ac / dx ≤ 1/√2 ≈ 0.707  (2D explicit)
// ═══════════════════════════════════════════════════════════════════════════════
layout(local_size_x = 8, local_size_y = 8) in;

// ── Bindings ─────────────────────────────────────────────────────────────────
layout(std430, binding = 0) readonly buffer CellBuffer  { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(rg32f, binding = 3) uniform readonly  image2D velIn;       // velocity field
layout(r32f,  binding = 5) uniform readonly  image2D pressureIn;  // current pressure
layout(r32f,  binding = 6) uniform writeonly image2D pressureOut; // updated pressure

// ── Uniforms ─────────────────────────────────────────────────────────────────
uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float soundSpeed;       // c in cells/frame
uniform float dtAcoustic;       // dt per substep (1.0 / ACOUSTIC_SUBSTEPS)
uniform float ambientPressure;  // background atmospheric pressure (p0)

// Explosion source injection
uniform vec2  explosionCenter;    // explosion center in grid coords
uniform float explosionRadius;   // blast radius in cells
uniform float explosionPressurePulse;  // peak overpressure from explosion
uniform int   explosionIsActive;  // 1 if explosion is active
uniform int   isFirstSubstep;    // 1 on first acoustic substep of the frame
uniform int   explosionType;      // 0=HE, 1=deflagration, 2=thermobaric, 3=napalm

// Energy decay and propagation parameters
uniform float energyDecayRate;    // How quickly shockwave loses energy (0.0-1.0)
uniform float reflectionDamping; // Energy loss on wall reflection (0.0-1.0)

// ── Unique to this shader: lightweight AcousticRule ─────────────────────────
struct AcousticRule { float density; int cat; };

AcousticRule getRule(uint tp) {
    uint o = tp * ruleStride;
    AcousticRule r;
    r.density = rules[o + 3u];
    r.cat     = int(rules[o + 4u]);
    return r;
}

// Check if a neighbour cell is gas (for boundary treatment)
bool isGasNeighbour(ivec2 np) {
    if (!inBounds(np, gridSize)) return false;
    uint nIdx = uint(np.y) * gridSize.x + uint(np.x);
    return getRule(getType(cells[nIdx]), ruleStride).cat == 0;
}

// Check if a cell is solid (for reflection detection)
bool isSolidCell(ivec2 np) {
    if (!inBounds(np, gridSize)) return true; // Domain edge counts as solid
    uint nIdx = uint(np.y) * gridSize.x + uint(np.x);
    return getRule(getType(cells[nIdx]), ruleStride).cat == 3;
}

// Compute distance-based energy attenuation accounting for material density
float computeEnergyAttenuation(float dist, float density) {
    // Denser materials absorb more energy
    float densityFactor = 1.0 / (1.0 + density * 0.1);
    // Geometric spreading in 2D (1/sqrt(r)) with exponential decay
    float geometricFalloff = 1.0 / (1.0 + dist * 0.05);
    return geometricFalloff * densityFactor;
}

// ── Main ─────────────────────────────────────────────────────────────────────
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    AcousticRule r = getRule(typ);

    float pOld = imageLoad(pressureIn, p).r;
    // Non-gas cells: pass through unchanged
    if (r.cat != 0) {
        imageStore(pressureOut, p, vec4(pOld, 0.0, 0.0, 0.0));
        return;
    }

    // ── Compute divergence of velocity ────────────────────────────────────
    // Central differences: div(u) = (uR.x − uL.x + uU.y − uD.y) / 2
    // At non-gas or out-of-bounds neighbours, velocity = 0 (reflecting wall)

    ivec2 pL = p + ivec2(-1, 0);
    ivec2 pR = p + ivec2( 1, 0);
    ivec2 pD = p + ivec2( 0,-1);
    ivec2 pU = p + ivec2( 0, 1);

    vec2 uL = vec2(0.0);
    vec2 uR = vec2(0.0);
    vec2 uD = vec2(0.0);
    vec2 uU = vec2(0.0);

    if (inBounds(pL, gridSize) && isGasNeighbour(pL)) uL = imageLoad(velIn, pL).xy;
    if (inBounds(pR, gridSize) && isGasNeighbour(pR)) uR = imageLoad(velIn, pR).xy;
    if (inBounds(pD, gridSize) && isGasNeighbour(pD)) uD = imageLoad(velIn, pD).xy;
    if (inBounds(pU, gridSize) && isGasNeighbour(pU)) uU = imageLoad(velIn, pU).xy;

    float divU = (uR.x - uL.x + uU.y - uD.y) * 0.5;

    // ── Pressure update ───────────────────────────────────────────────────
    // p_new = p_old − c² · div(u) · dt
    // Clamp divergence to prevent blow-up from extreme velocities (e.g. fire)
    divU = clamp(divU, -2.0, 2.0);
    float c2 = soundSpeed * soundSpeed;
    float pNew = pOld - c2 * divU * dtAcoustic;

    // ── Explosion pressure pulse injection ─────────────────────────────────
    // When an explosion is active, inject a pressure pulse into gas cells
    // within the blast radius on the FIRST substep only.
    // Different explosion types produce different pulse shapes:
    //   - High explosive: sharp Gaussian spike (brisance)
    //   - Deflagration: broader, flatter pulse (push)
    //   - Thermobaric: double pulse (initial + oxygen consumption)
    //   - Napalm: gradual pressure increase (burning expansion)
    if (explosionIsActive == 1 && isFirstSubstep == 1) {
        vec2 delta = vec2(p) - explosionCenter;
        float dist = length(delta);
        if (dist < explosionRadius) {
            float falloff;
            float typeMultiplier = 1.0;
            
            if (explosionType == 0) { // HIGH_EXPLOSIVE - sharp spike
                float normalizedDist = dist / explosionRadius;
                falloff = exp(-4.0 * normalizedDist * normalizedDist);
                typeMultiplier = 1.5; // Higher peak pressure
            } else if (explosionType == 1) { // DEFLAGRATION - broader push
                falloff = 1.0 - (dist / explosionRadius);
                falloff = falloff * falloff * (3.0 - 2.0 * falloff); // Smoothstep
                typeMultiplier = 0.8; // Lower peak, more push
            } else if (explosionType == 2) { // THERMOBARIC - double pulse
                falloff = 1.0 - (dist / explosionRadius);
                falloff = falloff * falloff;
                typeMultiplier = 1.2;
            } else if (explosionType == 3) { // NAPALM - gradual
                falloff = (1.0 - dist / explosionRadius) * 0.5;
                typeMultiplier = 0.4; // Low pressure, persistent
            } else {
                // Default Gaussian
                falloff = 1.0 - (dist / explosionRadius);
                falloff = falloff * falloff;
            }
            
            // Apply material-based energy attenuation from center to this cell
            float attenuation = computeEnergyAttenuation(dist, r.density);
            pNew += explosionPressurePulse * falloff * typeMultiplier * attenuation;
        }
    }
    
    // ── Shockwave reflection at solid boundaries ────────────────────────────
    // Detect nearby solid walls and apply reflection damping
    ivec2 neighbors[4] = ivec2[4](
        ivec2(p.x-1, p.y), ivec2(p.x+1, p.y),
        ivec2(p.x, p.y-1), ivec2(p.x, p.y+1)
    );
    
    int solidNeighbors = 0;
    for (int i = 0; i < 4; i++) {
        if (isSolidCell(neighbors[i])) solidNeighbors++;
    }
    
    // Dampen pressure near solid boundaries (reflection loss)
    if (solidNeighbors > 0) {
        float reflectionFactor = 1.0 - (reflectionDamping * float(solidNeighbors) * 0.25);
        pNew = mix(ambientPressure, pNew, reflectionFactor);
    }

    // Small numerical damping for long-term stability (≈0.2% per substep)
    // Relax toward ambient pressure, not zero, to prevent long-term drift
    pNew = ambientPressure + (pNew - ambientPressure) * (1.0 - 0.002);

    // Clamp pressure to prevent runaway values
    pNew = clamp(pNew, -50.0, 50.0);

    imageStore(pressureOut, p, vec4(pNew, 0.0, 0.0, 0.0));
}
