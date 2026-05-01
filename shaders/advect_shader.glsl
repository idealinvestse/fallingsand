// ═══════════════════════════════════════════════════════════════════════════════
// Advection / cell transport pass (v5.5 - Phase 5: Velocity-driven)
//
// Contract with the host:
//   * cellsOut has been pre-cleared to packCell(T_AIR, ambientTemp, 0, 0).
//   * reservations SSBO has been pre-cleared to 0.
//
// Semantics:
//   * Air cells (type 0): do nothing (output already air).
//   * Solids (cat==3): write themselves back to cellsOut[idx] (identity).
//   * Powders (cat==1): try to fall straight down, then diagonal, via atomic
//     reservation on target. Winner writes cellsOut[target], loser writes self.
//   * Liquids (cat==2): Velocity-driven cell transport (Phase 5). Velocity field
//     determines primary movement direction. Viscosity affects how strictly
//     we follow the velocity vs allowing CA-style spread.
//   * Gases (cat==0): Velocity-driven convective flow with thermal noise.
//     Buoyancy is encoded in velocity via force_shader.
//
// Phase 5 changes:
//   * Liquids and gases now use velTex to determine movement direction
//   * Velocity is capped to ±1 cell/frame for grid stability
//   * Probabilistic rounding prevents bias with small velocities
//   * CA fallback when velocity is weak or for high-viscosity materials
//
// Race-free because:
//   * Every successful move writes exactly two cells (target + self-air).
//     Losers write exactly one cell (self). Air cells write zero cells.
//   * atomicCompSwap on `reservations` guarantees only one writer per target.
// ═══════════════════════════════════════════════════════════════════════════════

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly  buffer CellBufferIn  { uint cellsIn[];  };
layout(std430, binding = 1) writeonly buffer CellBufferOut { uint cellsOut[]; };
// RuleBuffer is now defined in common.glsl
layout(std430, binding = 8) coherent  buffer ReservationBuf { uint reservations[]; };

layout(rg32f, binding = 3) uniform readonly image2D velTex;

// Temperature textures (r32f) — carried along when cells move via CA
layout(r32f, binding = 11) uniform readonly image2D tempIn;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;

uniform uvec2 gridSize;
uniform uint frame;
uniform uint ruleStride;
uniform uint ambientTemp;
uniform float dt;
uniform uint enableWetDry;

// ── Unique to this shader: lightweight MRule for advection ───────────────────
struct MRule { float density; int cat; float wd; };

MRule getMRule(uint tp){
    uint o = tp * ruleStride;
    MRule r;
    r.density = rules[o+3u];
    r.cat     = int(rules[o+4u]);
    r.wd      = rules[o+17u];
    return r;
}

// ── Unique to this shader: hashU (different from hash) ───────────────────────
uint hashU(uint s){
    s ^= s >> 16u;
    s *= 0x85ebca6bu;
    s ^= s >> 13u;
    s *= 0xc2b2ae35u;
    s ^= s >> 16u;
    return s;
}

bool isSolidAt(ivec2 p){
    if(!inBounds(p, gridSize)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    return getMRule(getType(cellsIn[idx])).cat == 3;
}

bool tryReserve(uint targetIdx, uint myIdx){
    return atomicCompSwap(reservations[targetIdx], 0u, myIdx + 1u) == 0u;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Velocity-driven cell transport (Phase 5)
//
// Sample velocity at cell center and convert to discrete grid direction.
// Velocity is capped to ±1 cell/frame to maintain grid constraints.
// We use a probabilistic approach for sub-cell velocities to avoid bias.
// ═══════════════════════════════════════════════════════════════════════════════

// Sample velocity from velTex at cell position
// Returns zero velocity for out-of-bounds positions (consistency with other shaders)
vec2 sampleVelocity(ivec2 p) {
    if (!inBounds(p, gridSize)) return vec2(0.0);
    return imageLoad(velTex, p).xy;
}

// Convert continuous velocity to discrete step with probabilistic rounding
// Returns target offset (one of 8 neighbours or zero)
ivec2 velocityToOffset(vec2 vel, uint seed) {
    // Cap velocity magnitude to 1 cell/frame for grid stability
    float maxSpeed = 1.0;
    if (length(vel) > maxSpeed) {
        vel = normalize(vel) * maxSpeed;
    }

    // Determine integer offset with probabilistic rounding for fractional parts
    // This prevents bias toward particular directions with small velocities
    float rx = float(hashU(seed) & 0xFFFFu) / 65535.0;  // Random [0,1)
    float ry = float(hashU(seed ^ 0x5A827999u) & 0xFFFFu) / 65535.0;

    int dx = int(floor(abs(vel.x) + rx));
    int dy = int(floor(abs(vel.y) + ry));

    if (vel.x < 0.0) dx = -dx;
    if (vel.y < 0.0) dy = -dy;

    // Clamp to single-step range for grid CA stability
    dx = clamp(dx, -1, 1);
    dy = clamp(dy, -1, 1);

    return ivec2(dx, dy);
}

// Compute priority score for a candidate move based on velocity alignment
// Higher score = more aligned with velocity field
float velocityAlignmentScore(ivec2 from, ivec2 to, vec2 vel) {
    ivec2 delta = to - from;
    if (delta == ivec2(0)) return 0.0;

    vec2 deltaF = vec2(float(delta.x), float(delta.y));
    float deltaLen = length(deltaF);
    if (deltaLen < 0.001) return 0.0;

    // Normalized dot product (-1 to 1, higher = better alignment)
    return dot(normalize(deltaF), normalize(vel));
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx  = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];
    uint typ  = getType(cell);

    // Load this cell's float temperature (authoritative state)
    float myTemp = imageLoad(tempIn, p).r;

    // Air: cellsOut is pre-cleared to air, tempOut is pre-cleared to ambient.
    // Write ambient temp to ensure the output texture is populated.
    if(typ == T_AIR){
        imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
        return;
    }

    MRule r = getMRule(typ);

    // Solids: identity — carry temp through.
    if(r.cat == 3){
        cellsOut[idx] = cell;
        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
        return;
    }

    // ── Powders: straight down, then diagonal down ───────────────────────────
    if(r.cat == 1){
        ivec2 tgts[3];
        tgts[0] = ivec2(p.x,     p.y - 1);
        if((hashU(idx ^ frame) & 1u) == 1u){
            tgts[1] = ivec2(p.x + 1, p.y - 1);
            tgts[2] = ivec2(p.x - 1, p.y - 1);
        } else {
            tgts[1] = ivec2(p.x - 1, p.y - 1);
            tgts[2] = ivec2(p.x + 1, p.y - 1);
        }
        for(int k = 0; k < 3; k++){
            ivec2 t = tgts[k];
            if(!inBounds(t, gridSize)) continue;
            uint tIdx = uint(t.y) * gridSize.x + uint(t.x);
            uint targetCell = cellsIn[tIdx];
            if(getType(targetCell) != T_AIR) continue;
            if(tryReserve(tIdx, idx)){
                cellsOut[tIdx] = cell;
                imageStore(tempOut, t, vec4(myTemp, 0.0, 0.0, 0.0));
                // Self position becomes air — write ambient temp.
                imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
                return;
            }
        }
        // ~3% chance: try flat spread when fully blocked (natural pile relaxation)
        if((hashU(idx ^ (frame * 23u)) & 31u) == 0u){
            bool goRight2 = (hashU(idx ^ (frame * 29u)) & 1u) == 1u;
            ivec2 flatA = ivec2(p.x + (goRight2 ? 1 : -1), p.y);
            ivec2 flatB = ivec2(p.x + (goRight2 ? -1 : 1), p.y);
            for(int k = 0; k < 2; k++){
                ivec2 tf = (k == 0) ? flatA : flatB;
                if(!inBounds(tf, gridSize)) continue;
                uint tfIdx = uint(tf.y) * gridSize.x + uint(tf.x);
                if(getType(cellsIn[tfIdx]) != T_AIR) continue;
                if(tryReserve(tfIdx, idx)){
                    cellsOut[tfIdx] = cell;
                    imageStore(tempOut, tf, vec4(myTemp, 0.0, 0.0, 0.0));
                    imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
                    return;
                }
            }
        }
        cellsOut[idx] = cell;
        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
        return;
    }

    // ── Liquids: Velocity-driven cell transport with CA fallback ──────────
    // Phase 5: Velocity field now drives the primary movement direction.
    // We compute velocity-aligned targets and try them in priority order.
    // Gravity and density still apply as secondary forces via the velocity field.
    if(r.cat == 2){
        // Sample velocity at current position
        vec2 vel = sampleVelocity(p);

        // Viscosity affects how closely we follow the velocity field
        float visc = rules[typ * ruleStride + 15u];
        // High viscosity → more deterministic, stick to velocity direction
        // Low viscosity → allow more random CA-style spread
        bool highVisc = visc > 0.4;

        // Build candidate target list based on velocity direction
        ivec2 targets[5];
        int targetCount = 0;

        // First choice: pure velocity direction (if non-zero)
        ivec2 velOffset = velocityToOffset(vel, idx ^ (frame * 7u));
        if (velOffset != ivec2(0)) {
            targets[targetCount++] = p + velOffset;
        }

        // If velocity is weak or zero, fall back to gravity-biased directions
        if (targetCount == 0 || length(vel) < 0.1) {
            // Gravity fallback: straight down, diagonal down
            bool goRight = (hashU(idx ^ (frame * 7u)) & 1u) == 1u;
            targets[targetCount++] = ivec2(p.x, p.y - 1);                           // down
            targets[targetCount++] = ivec2(p.x + (goRight ? 1 : -1), p.y - 1);      // diag down A
            targets[targetCount++] = ivec2(p.x + (goRight ? -1 : 1), p.y - 1);      // diag down B
        } else {
            // Velocity is significant: add nearby directions for spread
            // Orthogonal directions for natural liquid spreading
            if (abs(vel.x) > abs(vel.y)) {
                // Moving primarily horizontal: add up/down spread
                targets[targetCount++] = ivec2(p.x, p.y + 1);
                targets[targetCount++] = ivec2(p.x, p.y - 1);
            } else {
                // Moving primarily vertical: add left/right spread
                targets[targetCount++] = ivec2(p.x - 1, p.y);
                targets[targetCount++] = ivec2(p.x + 1, p.y);
            }
        }

        // Try velocity-aligned targets in priority order
        for (int k = 0; k < targetCount; k++) {
            ivec2 tc = targets[k];
            if (!inBounds(tc, gridSize)) continue;
            if (isSolidAt(tc)) continue;

            uint tcIdx = uint(tc.y) * gridSize.x + uint(tc.x);
            uint tcType = getType(cellsIn[tcIdx]);
            MRule rt = getMRule(tcType);

            bool canMove = false;
            if (tcType == T_AIR) {
                canMove = true;
            } else if (rt.cat == 2 && r.density > rt.density) {
                // Denser liquid displaces lighter liquid
                canMove = true;
            }

            if (!canMove) continue;

            // Velocity alignment check for high-viscosity liquids
            if (highVisc && k > 0) {
                float align = velocityAlignmentScore(p, tc, vel);
                // Skip if moving strongly against velocity (except for gravity fallback)
                if (align < -0.5 && length(vel) > 0.3) continue;
            }

            if (tryReserve(tcIdx, idx)) {
                cellsOut[tcIdx] = cell;
                imageStore(tempOut, tc, vec4(myTemp, 0.0, 0.0, 0.0));
                if (tcType != T_AIR) {
                    // Swap: displaced lighter liquid goes to our old position
                    float theirTemp = imageLoad(tempIn, tc).r;
                    if (tryReserve(idx, tcIdx)) {
                        cellsOut[idx] = cellsIn[tcIdx];
                        imageStore(tempOut, p, vec4(theirTemp, 0.0, 0.0, 0.0));
                    } else {
                        atomicExchange(reservations[tcIdx], 0u);
                        cellsOut[idx] = cell;
                        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
                    }
                } else {
                    imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
                }
                return;
            }
        }

        // Try flat spread if velocity-driven targets were all blocked
        if (!highVisc) {
            bool goRight = (hashU(idx ^ (frame * 11u)) & 1u) == 1u;
            ivec2 flatDirs[2];
            flatDirs[0] = ivec2(p.x + (goRight ? 1 : -1), p.y);
            flatDirs[1] = ivec2(p.x + (goRight ? -1 : 1), p.y);
            for (int k = 0; k < 2; k++) {
                ivec2 tf = flatDirs[k];
                if (!inBounds(tf, gridSize) || isSolidAt(tf)) continue;
                uint tfIdx = uint(tf.y) * gridSize.x + uint(tf.x);
                if (getType(cellsIn[tfIdx]) == T_AIR && tryReserve(tfIdx, idx)) {
                    cellsOut[tfIdx] = cell;
                    imageStore(tempOut, tf, vec4(myTemp, 0.0, 0.0, 0.0));
                    imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
                    return;
                }
            }
        }

        // Fully blocked — stay put
        cellsOut[idx] = cell;
        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
        return;
    }

    // ── Gases (cat==0): Velocity-driven convective flow ───────────────────
    // Phase 5: Gases are highly responsive to velocity field (convection).
    // Buoyancy is already encoded in the velocity field via force_shader.
    // We follow the velocity primarily, with small thermal noise for diffusion.
    {
        vec2 vel = sampleVelocity(p);

        // Gases have high thermal diffusivity → add random walk component
        // This simulates Brownian motion and small-scale turbulence
        uint noiseSeed = idx ^ (frame * 13u);
        float noiseStrength = 0.15;  // Small random perturbation
        vec2 thermalNoise = vec2(
            float(hashU(noiseSeed) & 0xFFu) / 127.5 - 1.0,
            float(hashU(noiseSeed ^ 0x9E3779B9u) & 0xFFu) / 127.5 - 1.0
        ) * noiseStrength;

        vec2 effectiveVel = vel + thermalNoise;

        // Build velocity-aligned targets
        ivec2 targets[6];
        int targetCount = 0;

        // Primary target: velocity direction
        ivec2 velOffset = velocityToOffset(effectiveVel, noiseSeed);
        if (velOffset != ivec2(0)) {
            targets[targetCount++] = p + velOffset;
        }

        // Buoyancy fallback (when velocity is weak, use density-based direction)
        if (targetCount == 0 || length(vel) < 0.2) {
            bool goRight = (hashU(noiseSeed) & 1u) == 1u;
            if (r.density < -0.05) {
                // Buoyant: prefer upward
                targets[targetCount++] = ivec2(p.x, p.y + 1);
                targets[targetCount++] = ivec2(p.x + (goRight ? 1 : -1), p.y + 1);
                targets[targetCount++] = ivec2(p.x + (goRight ? -1 : 1), p.y + 1);
            } else if (r.density > 0.05) {
                // Heavy gas: prefer downward
                targets[targetCount++] = ivec2(p.x, p.y - 1);
                targets[targetCount++] = ivec2(p.x + (goRight ? 1 : -1), p.y - 1);
                targets[targetCount++] = ivec2(p.x + (goRight ? -1 : 1), p.y - 1);
            }
        }

        // Add lateral spread for all gases (diffusion)
        // This ensures gases don't just form thin lines along velocity
        bool goRight = (hashU(noiseSeed ^ 0x5A827999u) & 1u) == 1u;
        targets[targetCount++] = ivec2(p.x + (goRight ? 1 : -1), p.y);
        targets[targetCount++] = ivec2(p.x + (goRight ? -1 : 1), p.y);

        // Try targets in priority order
        for (int k = 0; k < targetCount; k++) {
            ivec2 tc = targets[k];
            if (!inBounds(tc, gridSize)) continue;
            if (isSolidAt(tc)) continue;

            uint tcIdx = uint(tc.y) * gridSize.x + uint(tc.x);
            uint tcType = getType(cellsIn[tcIdx]);
            MRule rt = getMRule(tcType);

            // Move into air, or displace a heavier cell (density swap)
            if (tcType != T_AIR) {
                if (rt.cat == 3) continue;              // never displace solids
                if (r.density >= rt.density) continue;  // only displace lighter cells
            }

            if (tryReserve(tcIdx, idx)) {
                cellsOut[tcIdx] = cell;
                imageStore(tempOut, tc, vec4(myTemp, 0.0, 0.0, 0.0));
                if (tcType != T_AIR) {
                    // Displaced heavier cell goes to our old spot
                    float theirTemp = imageLoad(tempIn, tc).r;
                    if (tryReserve(idx, tcIdx)) {
                        cellsOut[idx] = cellsIn[tcIdx];
                        imageStore(tempOut, p, vec4(theirTemp, 0.0, 0.0, 0.0));
                    } else {
                        atomicExchange(reservations[tcIdx], 0u);
                        cellsOut[idx] = cell;
                        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
                    }
                } else {
                    imageStore(tempOut, p, vec4(float(ambientTemp), 0.0, 0.0, 0.0));
                }
                return;
            }
        }

        // Fully blocked — stay put
        cellsOut[idx] = cell;
        imageStore(tempOut, p, vec4(myTemp, 0.0, 0.0, 0.0));
    }
}
