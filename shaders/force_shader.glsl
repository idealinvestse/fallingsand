#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(rg32f, binding = 4) uniform writeonly image2D velOut;
layout(r32f,  binding = 8) uniform readonly image2D vorticityTex;
layout(r32f,  binding = 11) uniform readonly image2D tempTex;

uniform uvec2 gridSize;
uniform uint frame;
uniform float dt;
uniform float gravity;
uniform int enableTurbulence;
uniform uint ruleStride;
uniform int enableVorticityConfinement;
uniform float vorticityStrength;
uniform float surfaceTensionStrength;
uniform float thermalBuoyancyScale;

// Explosion impulse uniforms
uniform vec2 explosionCenter;
uniform float explosionRadius;
uniform float explosionForce;
uniform int explosionIsActive;

// Wind vector
uniform float ambientTemp;
uniform vec2 windVector;

// ── Unique to this shader: octantToVec ────────────────────────────────────────
// Unit vector for octant (0=E,1=NE,2=N,3=NW,4=W,5=SW,6=S,7=SE).
vec2 octantToVec(uint oct){
    const float s = 0.70710678;
    if(oct == 0u) return vec2( 1.0,  0.0);
    if(oct == 1u) return vec2(   s,    s);
    if(oct == 2u) return vec2( 0.0,  1.0);
    if(oct == 3u) return vec2(  -s,    s);
    if(oct == 4u) return vec2(-1.0,  0.0);
    if(oct == 5u) return vec2(  -s,   -s);
    if(oct == 6u) return vec2( 0.0, -1.0);
    return               vec2(   s,   -s);
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ = getType(cell);
    uint flg = getFlags(cell);
    Rule r = getRule(typ, ruleStride);

    vec2 v = imageLoad(velIn, p).xy;

    // Solids and powders have zero velocity (powders use CA in advect, not velTex)
    // EXCEPT T_SHRAPNEL which is a high-velocity projectile and needs vel updates.
    if((r.cat == 3 || r.cat == 1) && typ != T_SHRAPNEL){
        imageStore(velOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    // Viscosity damping
    float damp = mix(0.985, 0.82, clamp(r.visc, 0.0, 1.0));
    v *= damp;

    // Viscous diffusion (Laplacian smoothing of velocity, scaled by material viscosity)
    // Only applied to fluids and gases where shear matters.
    if(r.visc > 0.001 && (r.cat == 0 || r.cat == 2)){
        vec2 vL = inBounds(p + ivec2(-1, 0), gridSize) ? imageLoad(velIn, p + ivec2(-1, 0)).xy : v;
        vec2 vR = inBounds(p + ivec2( 1, 0), gridSize) ? imageLoad(velIn, p + ivec2( 1, 0)).xy : v;
        vec2 vD = inBounds(p + ivec2(0, -1), gridSize) ? imageLoad(velIn, p + ivec2(0, -1)).xy : v;
        vec2 vU = inBounds(p + ivec2(0,  1), gridSize) ? imageLoad(velIn, p + ivec2(0,  1)).xy : v;
        vec2 laplacian = (vL + vR + vD + vU) - 4.0 * v;
        float nu = r.visc * 0.15; // kinematic viscosity coefficient
        v += laplacian * nu * dt;
    }

    // Vorticity confinement for enhanced swirling
    if(enableVorticityConfinement != 0 && (r.cat == 0 || r.cat == 2)){
        float omega = imageLoad(vorticityTex, p).x;
        if(abs(omega) > 0.001){
            // Compute gradient of vorticity magnitude
            float omegaL = inBounds(p + ivec2(-1, 0), gridSize) ? imageLoad(vorticityTex, p + ivec2(-1, 0)).x : 0.0;
            float omegaR = inBounds(p + ivec2(1, 0), gridSize) ? imageLoad(vorticityTex, p + ivec2(1, 0)).x : 0.0;
            float omegaD = inBounds(p + ivec2(0, -1), gridSize) ? imageLoad(vorticityTex, p + ivec2(0, -1)).x : 0.0;
            float omegaU = inBounds(p + ivec2(0, 1), gridSize) ? imageLoad(vorticityTex, p + ivec2(0, 1)).x : 0.0;

            vec2 gradOmega = 0.5 * vec2(omegaR - omegaL, omegaU - omegaD);
            float gradOmegaLen = length(gradOmega);

            if(gradOmegaLen > 0.001){
                // Confinement force: f = epsilon * h * (|omega| / |grad omega|) * grad omega_perp
                vec2 confinementDir = vec2(-gradOmega.y, gradOmega.x) / gradOmegaLen;
                float confinementForce = vorticityStrength * abs(omega);
                v += confinementDir * confinementForce * dt;
            }
        }
    }

    // Surface tension for liquids (continuum surface force approximation)
    // Uses the liquid phase indicator field; force = sigma * kappa * grad(phi)
    if(surfaceTensionStrength > 0.001 && r.cat == 2){
        float phiL = 1.0, phiR = 1.0, phiD = 1.0, phiU = 1.0;
        ivec2 pL = p + ivec2(-1, 0);
        ivec2 pR = p + ivec2( 1, 0);
        ivec2 pD = p + ivec2(0, -1);
        ivec2 pU = p + ivec2(0,  1);
        if(inBounds(pL, gridSize)){ Rule rr = getRule(getType(cells[uint(pL.y)*gridSize.x + uint(pL.x)]), ruleStride); phiL = (rr.cat == 2) ? 1.0 : 0.0; }
        if(inBounds(pR, gridSize)){ Rule rr = getRule(getType(cells[uint(pR.y)*gridSize.x + uint(pR.x)]), ruleStride); phiR = (rr.cat == 2) ? 1.0 : 0.0; }
        if(inBounds(pD, gridSize)){ Rule rr = getRule(getType(cells[uint(pD.y)*gridSize.x + uint(pD.x)]), ruleStride); phiD = (rr.cat == 2) ? 1.0 : 0.0; }
        if(inBounds(pU, gridSize)){ Rule rr = getRule(getType(cells[uint(pU.y)*gridSize.x + uint(pU.x)]), ruleStride); phiU = (rr.cat == 2) ? 1.0 : 0.0; }
        vec2 gradPhi = 0.5 * vec2(phiR - phiL, phiU - phiD);
        float lapPhi = (phiL + phiR + phiD + phiU) - 4.0; // center phi_p == 1.0
        v += surfaceTensionStrength * lapPhi * gradPhi * dt;
    }

    // Gravity + thermal convection.
    // Convention: y increases upward (powder falls toward p.y - 1 in advect_shader),
    // so gravity accelerates v.y in the −y direction. Buoyancy acts opposite to gravity
    // and must have a consistent sign regardless of the material's base density sign.
    //
    // Model:
    //   * Liquid:  ρ_eff(T) = ρ_0 * (1 − β · ΔT) with ρ_0 > 0 and β > 0 (thermal
    //              expansion). Buoyancy accel = g · (ρ_0 − ρ_eff)/ρ_ref  (↑ when hot).
    //   * Gas:     Negative ρ encodes "inherently buoyant" (fire/smoke/steam);
    //              positive ρ encodes "heavy gas" (e.g. O₂). Net buoyancy accel is
    //              g · (−ρ_0) (constant rise/sink from density alone) plus a thermal
    //              term g · α · ΔT (hotter → more upward). Signs are independent of ρ₀'s
    //              sign so both positive- and negative-density gases behave correctly.
    float tempF = imageLoad(tempTex, p).r;
    float ambientN = ambientTemp;
    float dT = tempF - ambientN;

    // Liquid thermal-expansion coefficient (dimensionless, scaled for visible effect).
    const float BETA_LIQ  = 0.30;
    // Gas thermal-buoyancy coefficient (per unit ΔT).
    const float ALPHA_GAS = 1.20;
    // Density floor used only for logging/reference; not applied to r.density here.
    const float RHO_REF   = 1.0;

    float effectiveDensity = r.density;
    if(r.cat == 2){
        // Liquid: thermal expansion reduces density when hot.
        effectiveDensity = r.density * (1.0 - BETA_LIQ * dT);
        effectiveDensity = max(effectiveDensity, 0.05);
    }
    // For gases we use (ρ_air − r.density) + thermal term; air is neutral.
    const float RHO_AIR = 0.12;  // Air density — matches materials.py air definition

    if(r.cat == 1){
        // Powder: falls under gravity; micro thermal lift only when very hot.
        v.y -= gravity * 1.25 * dt;
        v.y += gravity * max(0.0, dT) * 0.10 * thermalBuoyancyScale * dt;
    } else if(r.cat == 2){
        // Liquid: gravity + density-based buoyancy (hot liquid rises).
        // Heavier liquids (higher density) fall faster than lighter ones to enable separation.
        float densityScale = r.density / 2.0; // Water (rho=2.0) is the baseline 1.0g
        v.y -= gravity * densityScale * dt;
        
        float liqBuoy = (r.density - effectiveDensity) / RHO_REF;
        v.y += gravity * liqBuoy * 0.35 * thermalBuoyancyScale * dt;
    } else if(r.cat == 0){
        // Gas: buoyancy relative to ambient air density.
        //   Base term: (ρ_air − ρ_0). Air (ρ=0.12) → 0 (neutral, no self-buoyancy).
        //              Buoyant gases (ρ<0.12) → positive (↑ rise).
        //              Heavy gases like O₂ (ρ=0.14) → negative (↓ sink).
        //   Thermal term: α · ΔT always adds upward push when ΔT > 0.
        float baseBuoy = RHO_AIR - r.density;
        float thermBuoy = ALPHA_GAS * dT * thermalBuoyancyScale;
        v.y += gravity * (baseBuoy * 0.55 + thermBuoy * 0.55) * dt;
        if(typ == T_FIRE || typ == T_EMBER || typ == T_BLAST){
            // Extra kick for combustion plumes (hot radiant cells).
            v.y += gravity * max(0.0, tempF - ambientN) * 0.8 * dt;
        }
    }

    // Pump boost (from flags)
    if(r.cat == 2 && flg > 5u){
        v.y += gravity * 2.2 * dt;  // Upward force
    }

    // Explosion radial velocity impulse with shockwave physics
    if(explosionIsActive == 1){
        vec2 dir = vec2(p) - explosionCenter;
        float dist = length(dir);
        if(dist < explosionRadius && dist > 0.1){
            // Calculate blast intensity
            float falloff = 1.0 - (dist / explosionRadius);
            falloff = falloff * falloff; // quadratic falloff

            // Non-solids and shrapnel receive blast force (reduced 0.3× since
            // acoustic pressure pulse now carries most of the blast energy)
            if(r.cat != 3 || typ == T_SHRAPNEL){
                v += normalize(dir) * explosionForce * falloff * 0.3;
            }
            // Solids can be pushed if blast is strong enough
            else if(r.cat == 3 && explosionForce > 5.0){
                float solidPush = (explosionForce - 5.0) * falloff * 0.3;
                v += normalize(dir) * solidPush;
            }

            // Freshly spawned shrapnel/ember gets strong outward velocity
            uint life = getFlags(cell);
            if((typ == T_SHRAPNEL || typ == T_EMBER) && life > 30u){
                v += normalize(dir) * explosionForce * 1.5 * falloff;
            }
        }
    }

    // ─── Radial shockwave from neighboring T_BLAST cells ───────────────────
    // Each adjacent blast cell pushes this cell away from the blast position,
    // scaled by the packed blast power (0..31). This is what actually makes
    // explosions knock surrounding particles outward (prior versions relied on
    // a self-push of the blast cell which did nothing since its velocity was 0).
    //
    // Note: this path is skipped when a user-triggered radial explosion is
    // currently active and overlaps this cell.  Otherwise the geometric radial
    // impulse above and the per-neighbour impulse here would double-count for
    // the duration of the explosion window (typically 3–5 frames), producing
    // unrealistically explosive particle ejection.
    bool hasBlastNeighbour = false;
    if(r.cat != 3 || typ == T_SHRAPNEL){
        vec2 radialImpulse = vec2(0.0);
        ivec2 offs[4] = ivec2[4](ivec2(0,1), ivec2(0,-1), ivec2(1,0), ivec2(-1,0));
        for(int i = 0; i < 4; ++i){
            ivec2 np = p + offs[i];
            if(!inBounds(np, gridSize)) continue;
            uint nc = cells[uint(np.y) * gridSize.x + uint(np.x)];
            if(getType(nc) != T_BLAST) continue;
            uint npow = unpackBlastPow(getFlags(nc));
            if(npow == 0u) continue;
            hasBlastNeighbour = true;
            // Direction: away from blast cell toward this cell.
            vec2 awayDir = vec2(-offs[i]);
            // Occlusion: if cell on the far side (past blast) is dense solid,
            // halve the impulse (crude shadowing).
            ivec2 fp = np + offs[i];  // cell on far side of blast from us
            float occl = 1.0;
            if(inBounds(fp, gridSize)){
                uint fc = cells[uint(fp.y) * gridSize.x + uint(fp.x)];
                Rule fr = getRule(getType(fc), ruleStride);
                if(fr.cat == 3 && fr.density > 5.0) occl = 0.4;
                else if(fr.cat == 2) occl = 0.7;
            }
            float powN = float(npow) / 31.0;
            radialImpulse += awayDir * powN * occl;
        }
        if(dot(radialImpulse, radialImpulse) > 0.0){
            // Scale impulse by material mobility (lighter = easier to push).
            float mobility = (r.cat == 0) ? 3.0 : (r.cat == 2 ? 2.0 : 4.0);
            // De-duplication: when the user-triggered radial explosion is also
            // active and overlaps this cell, both the geometric radial impulse
            // above and this per-neighbour impulse apply to the same region.
            // Halve the contribution in that window so total energy remains
            // roughly conserved across the frames where both act.
            if(explosionIsActive == 1){
                vec2 dirC = vec2(p) - explosionCenter;
                if(dot(dirC, dirC) < explosionRadius * explosionRadius){
                    mobility *= 0.5;
                }
            }
            v += radialImpulse * mobility;
        }
    }

    // Blast cell itself: strong upward/thermal buoyancy and slight outward bias
    if(typ == T_BLAST){
        float blastPower = float(unpackBlastPow(flg)) / 31.0;
        v += octantToVec(unpackBlastDir(flg)) * blastPower * 1.5;
        v.y += blastPower * gravity * 1.5 * dt;
    }

    // Shrapnel velocity from explosions - high speed projectiles.
    // Uses packed dir+power flags set when shrapnel was spawned by the state shader.
    if(typ == T_SHRAPNEL){
        float shrapnelPower = float(unpackBlastPow(flg)) / 31.0;
        if(shrapnelPower > 0.05){
            // Fresh shrapnel (high life) gets its full initial velocity boost.
            uint life = getLife(cell);
            uint maxLife = 45u + uint(shrapnelPower * 60u); // Max life based on power
            
            if(life > 0u){
                vec2 sdir = octantToVec(unpackBlastDir(flg));
                
                // Age ratio: 1.0 = fresh, 0.0 = dying
                float ageRatio = float(life) / float(max(1u, maxLife));
                
                // Velocity decay: fragments slow down over time (air resistance)
                // Fresh fragments have high velocity, old ones coast
                float velocityScale = ageRatio * ageRatio; // Quadratic decay
                
                // Initial kick only on freshly-spawned shrapnel
                if(ageRatio > 0.7){
                    float boost = 4.0 + shrapnelPower * 4.0; // 4-8 range
                    v += sdir * shrapnelPower * boost * velocityScale;
                }
                
                // Add some tumble/rotation effect for realism
                uint tumbleSeed = idx ^ (frame * 137u);
                float tumbleX = (hashF(tumbleSeed) - 0.5) * 0.3 * shrapnelPower;
                float tumbleY = (hashF(tumbleSeed ^ 0x9E3779B9u) - 0.5) * 0.3 * shrapnelPower;
                v += vec2(tumbleX, tumbleY) * velocityScale;
                
                // Ground scatter: when fragment lands, it converts back to material
                // This is handled in state shader based on life decay
            }
            
            // Shrapnel has ballistic trajectory with reduced gravity
            v.y -= gravity * 0.6 * dt; // Heavier than gas, lighter than solids
            
            // Air resistance for fragments
            v *= 0.985; // Slight drag
        }
    }

    // Wind bias for fire/ember
    if((typ == T_FIRE || typ == T_EMBER || typ == T_BLAST) && length(windVector) > 0.01){
        v += windVector * dt * 1.4;
    }

    // Turbulence
    if(enableTurbulence != 0 && r.turb > 0.001){
        uint rnd = idx ^ (frame * 131u);
        float nx = hashF(rnd ^ 0xA511E9B3u) * 2.0 - 1.0;
        float ny = hashF(rnd ^ 0x63D83595u) * 2.0 - 1.0;
        float turbStrength = r.turb * 0.22;
        if(typ == T_FIRE || typ == T_EMBER || typ == T_BLAST){
            turbStrength *= 0.7;
        }
        v += vec2(nx, ny) * turbStrength * dt;
    }

    // Clamp velocity
    float maxSpeed = (r.cat == 0) ? 2.5 : ((r.cat == 2) ? 3.0 : 4.0);
    v = clamp(v, vec2(-maxSpeed), vec2(maxSpeed));

    imageStore(velOut, p, vec4(v, 0.0, 0.0));
}
