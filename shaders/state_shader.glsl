#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer ReadBuffer  { uint cellsIn[];  };
layout(std430, binding = 1) writeonly buffer WriteBuffer { uint cellsOut[]; };
// RuleBuffer is now defined in common.glsl

// Temperature textures (r32f) — input from prior simulation passes and output
// for the updated temperature field after state reactions / phase changes.
layout(r32f, binding = 11) uniform readonly image2D tempTex;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;
layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(r32f, binding = 15) uniform readonly image2D moistureIn;
layout(r32f, binding = 17) uniform readonly image2D humidityIn;

uniform uvec2 gridSize;
uniform uint frame;
uniform uint ambientTemp;
uniform int enableThermal;
uniform uint ruleStride;

// ── Cell writing helper ───────────────────────────────────────────────────────
void writeCell(uint idx, ivec2 p, uint typ, float temp, uint life, uint flg){
    cellsOut[idx] = packCell(typ, life, flg);
    imageStore(tempOut, p, vec4(temp, 0.0, 0.0, 0.0));
}

// ── Unique to this shader: loadCell (uses cellsIn buffer) ───────────────────
uint loadCell(ivec2 p){
    if(!inBounds(p, gridSize)) return packCell(T_AIR, 0u, 0u);
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    return cellsIn[idx];
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    // Early-out for sparse regions
    if (!inSparseRegion(p, sparseRegion)) {
        // For state shader, we need to propagate cells even outside active region
        // to maintain grid consistency, so we don't skip entirely
        // but we could optimize by only copying unchanged cells
    }

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];

    uint typ  = getType(cell);
    float temp = imageLoad(tempTex, p).r;
    uint life = getLife(cell);
    uint flg  = getFlags(cell);

    Rule r = getRule(typ, ruleStride);
    float ambientT = float(ambientTemp);
    float highT = r.TH;
    float lowT = r.TL;
    float moisture = clamp(imageLoad(moistureIn, p).r / 500.0, 0.0, 1.0);
    float humidity = clamp(imageLoad(humidityIn, p).r / 500.0, 0.0, 1.0);
    float wetExposure = clamp(max(moisture, humidity * 0.65), 0.0, 1.0);
    float effectiveWet = clamp(wetExposure * (1.0 - r.moistureResist), 0.0, 1.0);
    float wetIgnitionBoost = effectiveWet * r.wetIgnitionPenalty;
    float wetBurnFactor = mix(1.0, r.wetBurnRate, effectiveWet);

    // Load neighbors
    uint n = loadCell(p + ivec2(0, 1));
    uint s = loadCell(p + ivec2(0, -1));
    uint e = loadCell(p + ivec2(1, 0));
    uint w = loadCell(p + ivec2(-1, 0));

    uint tn = getType(n), ts = getType(s), te = getType(e), tw = getType(w);
    int explicitO2Count = 0;
    if(tn == T_OXYGEN) explicitO2Count++;
    if(ts == T_OXYGEN) explicitO2Count++;
    if(te == T_OXYGEN) explicitO2Count++;
    if(tw == T_OXYGEN) explicitO2Count++;
    int airCount = 0;
    if(tn == T_AIR) airCount++;
    if(ts == T_AIR) airCount++;
    if(te == T_AIR) airCount++;
    if(tw == T_AIR) airCount++;
    float oxygenAvailability = clamp(float(explicitO2Count) * 0.35 + float(airCount) * 0.12, 0.0, 1.0);

    // ═══════════════════════════════════════════════════════════════════════════
    // THERMAL NOTE: Heat diffusion + Newton cooling + emissive radiation are
    // handled by heat_shader.glsl. The float temperature is synced above from
    // tempTex. No additional cooling here to avoid double-application.
    // ═══════════════════════════════════════════════════════════════════════════

    // ═══════════════════════════════════════════════════════════════════════════
    // CHEMISTRY & REACTIONS (data-driven from reaction slots)
    // ═══════════════════════════════════════════════════════════════════════════
    // Reactions mutate typ/temp/life in-place so downstream state machine still runs.
    uint neighbors[4] = {tn, ts, te, tw};
    
    bool reacted = false;
    for(int slot = 0; slot < 3 && !reacted; slot++){
        uint partner, prodSelf, prodNeighbor, tempThreshold;
        float prob;
        
        if(slot == 0){
            partner = r.rxn1_p; prodSelf = r.rxn1_ps; prodNeighbor = r.rxn1_pn; 
            prob = r.rxn1_prob; tempThreshold = r.rxn1_tt;
        } else if(slot == 1){
            partner = r.rxn2_p; prodSelf = r.rxn2_ps; prodNeighbor = r.rxn2_pn; 
            prob = r.rxn2_prob; tempThreshold = r.rxn2_tt;
        } else {
            partner = r.rxn3_p; prodSelf = r.rxn3_ps; prodNeighbor = r.rxn3_pn; 
            prob = r.rxn3_prob; tempThreshold = r.rxn3_tt;
        }
        
        if(partner == 0u && prodSelf == 0u) continue;
        if(prob <= 0.0) continue;
        if(tempThreshold > 0u && temp < float(tempThreshold)) continue;
        
        for(int i = 0; i < 4 && !reacted; i++){
            if(neighbors[i] == partner){
                uint rnd = hash(idx ^ (frame * (slot + 1u) * 7u));
                if(hashF(rnd) < prob){
                    // Mutate local state; downstream (phase transitions, life) will run on new typ
                    if(prodSelf == T_STEAM) temp = 170.0;
                    else if(prodSelf == T_STONE) temp = max(temp, 180.0);
                    else if(prodSelf == T_MUD) temp = 96.0;
                    else if(prodSelf == T_AIR) temp = float(ambientTemp);
                    typ = prodSelf;
                    life = 0u;
                    r = getRule(typ, ruleStride); // reload rule for new material
                    
                    // Also mutate neighbor cell if prodNeighbor is specified
                    if(prodNeighbor != 0u){
                        ivec2 npos = p;
                        if(i == 0) npos += ivec2(0, 1);
                        else if(i == 1) npos += ivec2(0, -1);
                        else if(i == 2) npos += ivec2(1, 0);
                        else npos += ivec2(-1, 0);
                        
                        if(inBounds(npos, gridSize)){
                            uint nidx = uint(npos.y) * gridSize.x + uint(npos.x);
                            float ntemp = temp;
                            if(prodNeighbor == T_STEAM) ntemp = 170.0;
                            else if(prodNeighbor == T_STONE) ntemp = max(temp, 180.0);
                            else if(prodNeighbor == T_MUD) ntemp = 96.0;
                            else if(prodNeighbor == T_AIR) ntemp = float(ambientTemp);
                            ivec2 np = ivec2(int(nidx % gridSize.x), int(nidx / gridSize.x));
                            writeCell(nidx, np, prodNeighbor, ntemp, 0u, 0u);
                        }
                    }
                    
                    reacted = true;
                }
            }
        }
    }
    
    // Special case: acid corrosion (still handled separately for now)
    bool nearAcid = (tn == T_ACID || ts == T_ACID || te == T_ACID || tw == T_ACID);
    if(typ != T_ACID && nearAcid && !isAcidResist(typ)){
        uint rnd = hash(idx ^ (frame * 17u));
        if((rnd & 1u) == 0u){
            writeCell(idx, p, T_AIR, float(ambientTemp), 0u, 0u);
            return;
        }
    }
    
    bool nearPump = (tn == T_PUMP || ts == T_PUMP || te == T_PUMP || tw == T_PUMP);
    bool nearGen = (tn == T_GEN || ts == T_GEN || te == T_GEN || tw == T_GEN);
    bool nearVirus = (tn == T_VIRUS || ts == T_VIRUS || te == T_VIRUS || tw == T_VIRUS);
    bool nearBlast = (tn == T_BLAST || ts == T_BLAST || te == T_BLAST || tw == T_BLAST);
    bool nearHot = (tn == T_FIRE || ts == T_FIRE || te == T_FIRE || tw == T_FIRE ||
                    tn == T_LAVA || ts == T_LAVA || te == T_LAVA || tw == T_LAVA ||
                    tn == T_SPARK || ts == T_SPARK || te == T_SPARK || tw == T_SPARK ||
                    tn == T_EMBER || ts == T_EMBER || te == T_EMBER || tw == T_EMBER);
    bool nearMagnet = (tn == T_MAGNET || ts == T_MAGNET || te == T_MAGNET || tw == T_MAGNET);
    bool nearMagnetSouth = (tn == T_MAGNET_SOUTH || ts == T_MAGNET_SOUTH || te == T_MAGNET_SOUTH || tw == T_MAGNET_SOUTH);

    // Virus infection
    if(typ == T_BLOOD && nearVirus){
        uint rnd = hash(idx ^ (frame * 31u));
        if((rnd & 7u) == 0u){
            writeCell(idx, p, T_SLIME, 96.0, 0u, 0u);
            return;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // EXPLOSIVE MATERIALS - Detonation logic
    // ═══════════════════════════════════════════════════════════════════════════
    // Check for detonation conditions based on material properties
    bool isExplosive = (typ == T_GPOW || typ == T_C4 || typ == T_DYNAMITE ||
                        typ == T_THERMITE || typ == T_NAPALM);

    // Determine origin of strongest blast neighbor (used for fragment direction)
    ivec2 blastSrcOff = ivec2(0, 0);
    uint blastSrcPow = 0u;
    if(nearBlast){
        if(tn == T_BLAST){
            uint pow = unpackBlastPow(getFlags(n));
            if(pow > blastSrcPow){ blastSrcPow = pow; blastSrcOff = ivec2(0, 1); }
        }
        if(ts == T_BLAST){
            uint pow = unpackBlastPow(getFlags(s));
            if(pow > blastSrcPow){ blastSrcPow = pow; blastSrcOff = ivec2(0, -1); }
        }
        if(te == T_BLAST){
            uint pow = unpackBlastPow(getFlags(e));
            if(pow > blastSrcPow){ blastSrcPow = pow; blastSrcOff = ivec2(1, 0); }
        }
        if(tw == T_BLAST){
            uint pow = unpackBlastPow(getFlags(w));
            if(pow > blastSrcPow){ blastSrcPow = pow; blastSrcOff = ivec2(-1, 0); }
        }
    }

    if(isExplosive && r.expPow > 0.0){
        // Temperature-based spontaneous detonation
        if(temp >= r.detTemp && temp >= highT - 10.0){
            // Convert to blast with material-specific power (packed dir+pow)
            uint blastLife = max(1u, r.blastDur);
            uint powScaled = uint(clamp(r.expPow * 31.0, 1.0, 31.0));
            uint randDir = hash(idx ^ (frame * 53u)) & 0x7u;
            writeCell(idx, p, T_BLAST, 255.0, blastLife, packBlastFlags(randDir, powScaled));
            return;
        }

        // Near-blast chain detonation (enhanced with material-specific sensitivity)
        if(nearBlast){
            // Base sensitivity from explosive power
            float chainProb = r.expPow;
            
            // Material-specific modifiers
            if(typ == T_C4) chainProb = 0.95;  // Very sensitive
            if(typ == T_GPOW) chainProb = 0.4;  // Moderate sensitivity
            if(typ == T_DYNAMITE) chainProb = 0.7;  // High sensitivity
            if(typ == T_THERMITE) chainProb = 0.6;  // Heat-triggered
            if(typ == T_NAPALM) chainProb = 0.8;  // Fire-spreading
            if(typ == T_THERMITE_ENHANCED) chainProb = 0.7;  // Enhanced thermite
            
            // Distance attenuation: closer = more likely to detonate
            float distRatio = clamp(length(vec2(blastSrcOff)) / 5.0, 0.0, 1.0);
            chainProb *= (1.0 - distRatio * 0.5);
            
            uint rnd = hash(idx ^ (frame * 47u));
            if(hashF(rnd) < chainProb){
                uint blastLife = max(1u, r.blastDur);
                uint powScaled = uint(clamp(r.expPow * 31.0, 1.0, 31.0));
                uint randDir = hash(idx ^ (frame * 61u)) & 0x7u;
                writeCell(idx, p, T_BLAST, 255.0, blastLife, packBlastFlags(randDir, powScaled));
                return;
            }
        }
        
        // Electrical ignition: conductive explosives detonate from sparks
        if(r.cond > 0.3 && nearHot && (tn == T_SPARK || ts == T_SPARK || te == T_SPARK || tw == T_SPARK)){
            uint rnd = hash(idx ^ (frame * 73u));
            if(hashF(rnd) < 0.8){
                uint blastLife = max(1u, r.blastDur);
                uint powScaled = uint(clamp(r.expPow * 31.0, 1.0, 31.0));
                uint randDir = hash(idx ^ (frame * 79u)) & 0x7u;
                writeCell(idx, p, T_BLAST, 255.0, blastLife, packBlastFlags(randDir, powScaled));
                return;
            }
        }
        
        // Magnetic ignition: magnetic materials can trigger thermite
        if((typ == T_THERMITE || typ == T_THERMITE_ENHANCED) && nearMagnet && temp > 150.0){
            uint rnd = hash(idx ^ (frame * 83u));
            if(hashF(rnd) < 0.3){
                writeCell(idx, p, T_BLAST, 255.0, 2u, packBlastFlags(2u, 15u));
                return;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // HEAT FROM NEIGHBORS
    // ═══════════════════════════════════════════════════════════════════════════
    // Octant FROM blast src TO this cell (direction of outward fragment motion)
    uint fragOctant = octantFromOffset(-blastSrcOff);

    if(nearBlast){
        // Shockwave: massive instant heat from explosion
        temp += 80.0;
        // O2 in blast radius → consumed to smoke (oxygen is burned up)
        if(typ == T_OXYGEN){
            writeCell(idx, p, T_SMOKE, temp, 18u, 0u);
            return;
        }
        // Ignite combustibles immediately
        if(r.flamm > 0.0 && temp >= highT - 8.0){
            uint nl = 18u + uint(r.flamm * 48.0);
            writeCell(idx, p, T_FIRE, temp, nl, 0u);
            return;
        }
        // C4 chain detonation
        if(typ == T_C4 && temp >= 200.0){
            uint blastLife = 1u;
            uint powScaled = uint(clamp(r.expPow * 31.0, 1.0, 31.0));
            uint randDir = hash(idx ^ (frame * 53u)) & 0x7u;
            writeCell(idx, p, T_BLAST, 255.0, blastLife, packBlastFlags(randDir, powScaled));
            return;
        }
        // Gunpowder fast deflagration
        if(typ == T_GPOW){
            writeCell(idx, p, T_FIRE, 230.0, 6u, 0u);
            return;
        }
        // Napalm: spreads as ember shower
        if(typ == T_NAPALM && temp >= 150.0){
            uint rnd = hash((idx << 1u) ^ frame);
            if((rnd & 3u) == 0u){
                writeCell(idx, p, T_EMBER, 220.0, 15u, 0u); // Some napalm becomes embers
                return;
            }
        }
        // ═══════════════════════════════════════════════════════════════════════
        // CRATER FORMATION & ENHANCED FRAGMENTATION
        // ═══════════════════════════════════════════════════════════════════════
        uint blastPower = max(1u, blastSrcPow);
        uint matStrength = getMaterialStrength(typ);
        float densityFactor = 1.0 + clamp(r.density * 0.10, 0.0, 2.0);
        float destroyProb = float(blastPower) / (float(matStrength + 2u) * densityFactor);
        uint rnd = hash((idx << 2u) ^ frame);
        
        // Calculate distance from blast source for crater depth
        float distFromBlast = length(vec2(p) - (vec2(p) + vec2(blastSrcOff)));
        float distRatio = clamp(distFromBlast / float(blastPower + 1u), 0.0, 1.0);
        
        // ── Crater formation for ground materials ────────────────────────────
        if(isGroundMaterial(typ) && blastPower > 8u){
            float craterDepth = computeCraterDepth(blastPower, matStrength, distRatio);
            
            // Center of crater: destroy material, eject fragments upward
            if(distRatio < 0.3 && hashF(rnd) < destroyProb * 1.5){
                // Convert to air/fragment at center (material ejected)
                if(typ == T_STONE || typ == T_CONCRETE){
                    // Stone/concrete becomes shrapnel thrown upward
                    uint fragLife = 25u + blastPower * 3u;
                    uint shrapnelFlags = packBlastFlags(2u, blastPower); // Upward (N)
                    writeCell(idx, p, T_SHRAPNEL, temp, fragLife, shrapnelFlags);
                    return;
                } else if(typ == T_SAND || typ == T_DIRT){
                    // Sand/dirt becomes powder ejected
                    if(hashF(rnd ^ 0x1234u) < 0.7){
                        uint fragLife = 15u + blastPower * 2u;
                        uint shrapnelFlags = packBlastFlags(2u, blastPower / 2u);
                        writeCell(idx, p, T_SHRAPNEL, temp, fragLife, shrapnelFlags);
                        return;
                    } else {
                        writeCell(idx, p, T_AIR, float(ambientTemp), 0u, 0u);
                        return;
                    }
                }
            }
            // Crater rim: displaced material forms raised edge
            else if(distRatio > 0.3 && distRatio < 0.6 && hashF(rnd) < destroyProb * 0.5){
                if(typ == T_SAND || typ == T_DIRT){
                    // Pile up at rim - convert to powder with upward velocity
                    uint fragLife = 10u + uint(float(blastPower) * 0.5);
                    uint shrapnelFlags = packBlastFlags(fragOctant, blastPower / 3u);
                    writeCell(idx, p, T_SHRAPNEL, temp, fragLife, shrapnelFlags);
                    return;
                }
            }
            // Outer damage zone: cracked/weakened material
            else if(distRatio < 0.8 && hashF(rnd) < destroyProb * 0.3){
                // Partially damaged - might become rubble
                if(typ == T_STONE || typ == T_CONCRETE){
                    writeCell(idx, p, T_SAND, temp, 0u, 0u);
                    return;
                }
            }
        }
        
        // ── Enhanced fragmentation for solids and powders ─────────────────────
        if(r.cat == 3 || r.cat == 1){
            if(hashF(rnd) < destroyProb){
                // Fragment lifetime carries the initial blast power (life in frames)
                // Larger fragments near center, smaller at edges
                uint fragLife = 20u + uint(float(blastPower) * (1.5 - distRatio));
                // Blast power reduced with distance for smaller fragments
                uint fragmentPower = max(1u, uint(float(blastPower) * (1.0 - distRatio * 0.5)));
                uint shrapnelFlags = packBlastFlags(fragOctant, fragmentPower);

                if(typ == T_GLASS){
                    // Glass always shatters to shrapnel, smaller pieces
                    uint smallFragLife = max(5u, fragLife / 2u);
                    writeCell(idx, p, T_SHRAPNEL, temp, smallFragLife, shrapnelFlags);
                    return;
                } else if(typ == T_METAL){
                    // Metal fragments - harder to destroy but dangerous
                    if(blastPower > 12u && hashF(rnd ^ 0x5A5Au) < 0.4){
                        writeCell(idx, p, T_SHRAPNEL, temp, fragLife, shrapnelFlags);
                        return;
                    }
                    // Otherwise dent/scorch but survive
                    temp += 50.0;
                } else if(typ == T_STONE || typ == T_CONCRETE){
                    // Stone shatters to rubble (sand) + some shrapnel
                    if(hashF(rnd ^ 0xA5A5u) < 0.6){
                        writeCell(idx, p, T_SAND, temp, 0u, 0u);
                    } else {
                        writeCell(idx, p, T_SHRAPNEL, temp, fragLife/2u, shrapnelFlags);
                    }
                    return;
                } else if(typ == T_WOOD || typ == T_PLANT){
                    // Wood splinters to embers or ash
                    if(hashF(rnd ^ 0x33CCu) < 0.7){
                        writeCell(idx, p, T_EMBER, 220.0, 25u, 0u);
                    } else {
                        writeCell(idx, p, T_ASH, max(100.0, temp/2.0), 0u, 0u);
                    }
                    return;
                } else if(typ == T_SAND || typ == T_DIRT || typ == T_ASH){
                    // Loose materials become dust/powder cloud
                    uint dustLife = 8u + uint(float(fragmentPower) * 0.5);
                    writeCell(idx, p, T_SHRAPNEL, temp, dustLife, shrapnelFlags);
                    return;
                } else {
                    uint fragment = getFragmentType(typ);
                    // Size variation: center = larger fragments
                    if(distRatio < 0.5){
                        writeCell(idx, p, fragment, temp, fragLife, shrapnelFlags);
                    } else {
                        // Edges: smaller, shorter-lived fragments
                        writeCell(idx, p, fragment, temp, fragLife / 2u, shrapnelFlags);
                    }
                    return;
                }
            }
        }
    } else if(nearHot){
        // Flammability-scaled heat gain: base 8 + flamm*20
        // Oil (0.8) gets ~24/frame, gas (0.4) gets ~16, wood (0.7) gets ~22 before moisture damping
        // Non-flammable materials still get 8/frame from radiant heat
        float heatGain = (8.0 + r.flamm * 20.0) * (1.0 - effectiveWet * 0.65);
        temp += heatGain;
        // Deterministic fire propagation: flammable cell touching fire/ember/spark
        // with sufficient temperature ignites directly (no low-probability hashing).
        // Skips fire/ember/blast itself and anything already reacted.
        // Materials with o2Req > 0 need at least one O2 or air neighbour to ignite.
        if(r.flamm > 0.0 && typ != T_FIRE && typ != T_EMBER && typ != T_BLAST && typ != T_SPARK
           && temp >= max(0.0, highT - 6.0 + wetIgnitionBoost)){
            bool hasOxidizer = true;  // Default: allow ignition
            if(r.o2Req > 0.0){
                bool weakAirOnly = (r.o2Req <= 0.75 && airCount >= 3) || (r.o2Req <= 0.55 && airCount >= 2) || (r.o2Req <= 0.35 && airCount >= 1);
                bool strongIgnition = temp >= highT + 12.0 + wetIgnitionBoost * 0.75;
                hasOxidizer = explicitO2Count > 0 || (weakAirOnly && strongIgnition);
            }
            if(hasOxidizer){
                if(typ == T_WOOD || typ == T_PLANT || typ == T_SUGAR || typ == T_HONEY || typ == T_SAP){
                    uint nl = 24u + uint(r.flamm * 40.0);
                    writeCell(idx, p, T_CHAR, max(temp, highT), nl, 0u);
                    return;
                }
                if(typ == T_OIL || typ == T_GAS || typ == T_NAPALM || typ == T_COAL){
                    uint rnd = hash(idx ^ (frame * 23u));
                    float sootProb = typ == T_GAS ? 0.08 : (typ == T_COAL ? 0.26 : (typ == T_NAPALM ? 0.22 : 0.18));
                    sootProb *= mix(1.45, 0.45, oxygenAvailability);
                    if(hashF(rnd) < sootProb * (1.0 - effectiveWet * 0.5)){
                        writeCell(idx, p, T_SOOT, max(120.0, temp * 0.65), 28u + uint(24.0 * sootProb), 0u);
                        return;
                    }
                }
                uint nl = (typ == T_OIL) ? 26u : (20u + uint(r.flamm * 60.0));
                uint igniteType = (r.cat == 2 || r.cat == 0) ? T_FIRE : T_EMBER;
                writeCell(idx, p, igniteType, typ == T_OIL ? min(max(temp, highT + 18.0), 210.0) : max(temp, highT), nl, typ == T_OIL ? 1u : 0u);
                return;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // ELECTRICITY: Generator creates sparks
    // ═══════════════════════════════════════════════════════════════════════════
    if(nearGen && r.cond > 0.5 && typ != T_SPARK){
        uint rnd = hash((idx << 1u) ^ frame);
        if((rnd & 7u) == 0u){
            writeCell(idx, p, T_SPARK, 240.0, 8u, 20u);
            return;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PUMP: charges nearby liquids
    // ═══════════════════════════════════════════════════════════════════════════
    if(nearPump && r.cat == 2){
        flg = min(255u, flg + 8u);
    } else if(flg > 0u && typ != T_PUMP && typ != T_GEN){
        // Decay flags (electricity cooldown)
        flg = flg > 2u ? flg - 2u : 0u;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // STATE MACHINE: Phase transitions & decay
    // ═══════════════════════════════════════════════════════════════════════════
    // Life decrement runs here so cells spend a full frame at each life value
    if(typ == T_FIRE || typ == T_SMOKE || typ == T_SOOT || typ == T_STEAM || typ == T_SPARK || typ == T_EMBER || typ == T_BLAST || typ == T_SHRAPNEL){
        if(life > 0u) life--;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // SHRAPNEL: Ground scatter conversion when life expires
    // ═══════════════════════════════════════════════════════════════════════════
    // When fragments land (life reaches 0), they convert back to material piles
    if(typ == T_SHRAPNEL && life == 0u){
        // Extract blast power from flags to determine fragment size
        uint fragPower = unpackBlastPow(flg);
        
        // Determine what material this fragment becomes based on origin
        // For simplicity, larger fragments become sand/rubble, small ones become ash/dust
        if(fragPower > 20u){
            // Large fragments become sand (rubble)
            writeCell(idx, p, T_SAND, temp * 0.5, 0u, 0u);
        } else if(fragPower > 10u){
            // Medium fragments become dirt
            writeCell(idx, p, T_DIRT, temp * 0.4, 0u, 0u);
        } else {
            // Small fragments become ash/dust
            writeCell(idx, p, T_ASH, max(50.0, temp * 0.3), 0u, 0u);
        }
        return;
    }

    if(typ == T_FIRE){
        // Self-heating: fire temperature rises over time
        float oilFireDamp = (flg & 1u) != 0u ? 0.58 : 1.0;
        temp += 4.0 * oilFireDamp * (1.0 - effectiveWet * 0.75);
        // ── Oxygen-dependent combustion ────────────────────────────────────
        // Count O2 neighbours and consume them based on o2Req/o2Yield.
        if(explicitO2Count > 0 && r.o2Req > 0.0){
            // O2 available: sustain combustion
            life = min(255u, life + uint(8.0 * oilFireDamp * (1.0 - effectiveWet * 0.75) * wetBurnFactor));
            // Extra heat when well-fed
            if(explicitO2Count >= 2) temp += 4.0 * oilFireDamp * (1.0 - effectiveWet * 0.75);
        } else {
            // No O2 nearby: suffocation
            bool hasAir = (tn == T_AIR || ts == T_AIR || te == T_AIR || tw == T_AIR);
            if(!hasAir){
                // Enclosed: life decays 2× faster → fire extinguishes
                life = max(0u, life - 2u);
            }
        }
        life = life > uint(effectiveWet * 6.0 * (2.0 - wetBurnFactor)) ? life - uint(effectiveWet * 6.0 * (2.0 - wetBurnFactor)) : 0u;
        if(life == 0u){
            uint fireResidue = oxygenAvailability < 0.25 ? T_SOOT : T_SMOKE;
            writeCell(idx, p, fireResidue, max(110.0, temp / 2.0), fireResidue == T_SOOT ? 28u : 20u, 0u);
            return;
        }
    } else if(typ == T_SPARK){
        if(life == 0u){
            writeCell(idx, p, T_FIRE, 220.0, 6u, 0u);
            return;
        }
    } else if(typ == T_SMOKE || typ == T_SOOT){
        if(life == 0u){
            writeCell(idx, p, T_AIR, float(ambientTemp), 0u, 0u);
            return;
        }
    } else if(typ == T_STEAM){
        if(life == 0u && temp <= ambientT + 4.0){
            writeCell(idx, p, T_WATER, float(ambientTemp), 0u, 0u);
            return;
        }
    } else if(typ == T_OXYGEN){
        // O2 self-consumption: convert to smoke near active combustion.
        // Each O2 cell only writes to itself — no cross-cell races.
        bool nearFire = (tn == T_FIRE || ts == T_FIRE || te == T_FIRE || tw == T_FIRE ||
                         tn == T_EMBER || ts == T_EMBER || te == T_EMBER || tw == T_EMBER ||
                         tn == T_CHAR || ts == T_CHAR || te == T_CHAR || tw == T_CHAR ||
                         tn == T_BLAST || ts == T_BLAST || te == T_BLAST || tw == T_BLAST);
        if(nearFire){
            uint rnd = hash(idx ^ frame);
            bool nearDirtyFuel = (tn == T_OIL || ts == T_OIL || te == T_OIL || tw == T_OIL ||
                                  tn == T_GAS || ts == T_GAS || te == T_GAS || tw == T_GAS ||
                                  tn == T_COAL || ts == T_COAL || te == T_COAL || tw == T_COAL ||
                                  tn == T_NAPALM || ts == T_NAPALM || te == T_NAPALM || tw == T_NAPALM ||
                                  tn == T_SOOT || ts == T_SOOT || te == T_SOOT || tw == T_SOOT);
            if((rnd & 7u) == 0u){  // 1/8 chance per frame per O2 cell
                uint product = (nearDirtyFuel && (rnd & 16u) == 0u) ? T_SOOT : T_SMOKE;
                writeCell(idx, p, product, temp, product == T_SOOT ? 26u : 15u, 0u);
                return;
            }
        }
    } else if(typ == T_BLAST){
        // TBLAST: 1-frame explosion front → fire burst
        if(life == 0u){
            writeCell(idx, p, T_FIRE, 240.0, 18u, 0u);
            return;
        }
    } else if(typ == T_EMBER){
        // Ember: burning debris that ignites neighbors
        temp += 2.0 * (1.0 - effectiveWet * 0.75);
        // ── Oxygen-dependent ember combustion ──────────────────────────────
        if(explicitO2Count > 0 && r.o2Req > 0.0){
            // O2 available: sustain ember combustion
            life = min(255u, life + uint(4.0 * (1.0 - effectiveWet * 0.75) * wetBurnFactor));
            if(explicitO2Count >= 2) temp += 2.0 * (1.0 - effectiveWet * 0.75);
        } else {
            bool hasAir = (tn == T_AIR || ts == T_AIR || te == T_AIR || tw == T_AIR);
            if(!hasAir){
                life = max(0u, life - 1u);  // Suffocate slower than fire
            }
        }
        life = life > uint(effectiveWet * 4.0 * (2.0 - wetBurnFactor)) ? life - uint(effectiveWet * 4.0 * (2.0 - wetBurnFactor)) : 0u;
        if(life == 0u || temp <= ambientT + 10.0){
            writeCell(idx, p, T_ASH, max(100.0, temp / 2.0), 0u, 0u);
            return;
        }
        // Ember ignition: small chance to ignite adjacent combustibles
        uint rnd = hash((idx << 1u) ^ frame);
        if((rnd & 15u) == 0u){
            // Try to ignite a neighbor (simplified: just heat them)
            temp += 3.0; // Extra heat from ember
        }
    } else if(typ == T_CHAR){
        if(temp >= highT && effectiveWet < 0.75){
            bool hasOxidizer = (tn == T_OXYGEN || ts == T_OXYGEN || te == T_OXYGEN || tw == T_OXYGEN ||
                                tn == T_AIR || ts == T_AIR || te == T_AIR || tw == T_AIR);
            if(hasOxidizer){
                writeCell(idx, p, T_EMBER, max(temp, highT), 36u, 0u);
                return;
            }
        }
        if(temp <= ambientT + 8.0 || effectiveWet > 0.8){
            writeCell(idx, p, T_ASH, max(80.0, temp * 0.5), 0u, 0u);
            return;
        }
    } else if(typ == T_HOT_ASH){
        temp += 1.5 * (1.0 - effectiveWet * 0.6);
        if(temp >= highT && effectiveWet < 0.7 && oxygenAvailability > 0.2){
            uint rnd = hash(idx ^ (frame * 41u));
            bool adjacentFuel = false;
            for(int i = 0; i < 4; i++){
                Rule nr = getRule(neighbors[i], ruleStride);
                adjacentFuel = adjacentFuel || (nr.flamm > 0.0 && neighbors[i] != T_FIRE && neighbors[i] != T_EMBER);
            }
            if(adjacentFuel && (rnd & 31u) == 0u){
                writeCell(idx, p, T_EMBER, max(temp, highT), 18u, 0u);
                return;
            }
        }
        if(temp <= ambientT + 12.0 || effectiveWet > 0.85){
            writeCell(idx, p, T_ASH, max(85.0, temp * 0.5), 0u, 0u);
            return;
        }
    } else if(typ == T_FUSE){
        // Fuse: slow-burning solid that propagates to neighbors
        if(temp >= highT){
            temp += 3.0;
            if(life == 0u){
                // When burnt out, emit spark to trigger adjacent explosives
                writeCell(idx, p, T_SPARK, 240.0, 8u, 20u);
                return;
            }
            // Propagate fire to adjacent fuse cells
            uint rnd = hash((idx << 1u) ^ frame);
            if((rnd & 7u) == 0u){
                // Try to ignite a neighbor
                if(tn == T_FUSE){
                    uint nidx = idx - uint(gridSize.x);
                    if(nidx < uint(gridSize.x * gridSize.y)){
                        float neighborTemp = imageLoad(tempTex, ivec2(int(nidx % gridSize.x), int(nidx / gridSize.x))).r;
                        if(neighborTemp < highT){
                            // Can't directly write to neighbor, but we can emit heat
                            // The heat propagation in the next frame will ignite it
                        }
                    }
                }
            }
        }
    } else if(typ == T_DYNAMITE){
        // Dynamite: powerful explosive with fuse delay
        if(temp >= highT){
            temp += 5.0;
            if(life == 0u){
                // Detonate: become blast
                writeCell(idx, p, T_BLAST, 255.0, 1u, 0u);
                return;
            }
            // Fuse countdown: decrease life when hot
            life = max(0u, life - 1u);
        }
    } else if(typ == T_THERMITE){
        // Thermite: extremely hot, melts metal/stone to lava
        temp += 8.0;
        if(temp >= 240.0){
            // Extremely hot - melt adjacent metal/stone
            uint rnd = hash((idx << 1u) ^ frame);
            if((rnd & 15u) == 0u){
                if(tn == T_METAL || tn == T_STONE || tn == T_GLASS){
                    // Convert neighbor to lava directly
                    ivec2 npos = p + ivec2(0, 1);
                    if(inBounds(npos, gridSize)){
                        uint nidx = uint(npos.y) * gridSize.x + uint(npos.x);
                        float ntemp = max(temp, 220.0);
                        writeCell(nidx, npos, T_LAVA, ntemp, 0u, 0u);
                    }
                    temp += 20.0; // Extra heat from exothermic reaction
                }
            }
        }
        if(life == 0u){
            writeCell(idx, p, T_ASH, max(150.0, temp / 3.0), 0u, 0u);
            return;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // MAGNETIC INTERACTIONS
    // ═══════════════════════════════════════════════════════════════════════════
    // Magnetic attraction/repulsion between polarized magnets
    if((typ == T_MAGNET || typ == T_MAGNET_SOUTH) && r.magPerm > 0.5){
        // North magnet repels south magnet, attracts other north magnets
        if(typ == T_MAGNET && nearMagnetSouth && r.magPol > 0.5){
            // Could apply velocity force here (would need integration with velocity field)
            // For now, just track the interaction for potential future implementation
        }
        // South magnet repels north magnet, attracts other south magnets
        if(typ == T_MAGNET_SOUTH && nearMagnet && r.magPol < -0.5){
            // Similar to above
        }
    }
    
    // Curie temperature: lose magnetism when heated above curie point
    if((typ == T_MAGNET || typ == T_MAGNET_SOUTH) && r.magCurie > 0.0 && temp >= r.magCurie){
        // Convert to regular iron/steel when above Curie temp
        // For now, just reduce permeability to simulate demagnetization
        // In a full implementation, this would change the material type
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PLASMA BEHAVIOR
    // ═══════════════════════════════════════════════════════════════════════════
    if(typ == T_PLASMA || typ == T_LIGHTNING_PLASMA){
        // Plasma is extremely hot and glows
        temp += 5.0;
        
        // Plasma recombines to fire/cooler state over time
        if(r.plasRecomb > 0.0){
            uint rnd = hash(idx ^ frame);
            if(hashF(rnd) < r.plasRecomb * 0.01){
                writeCell(idx, p, T_FIRE, temp * 0.7, 12u, 0u);
                return;
            }
        }
        
        // Plasma ignites nearby combustibles instantly
        if(nearHot || r.cond > 0.5){
            for(int i = 0; i < 4; i++){
                uint ntyp = neighbors[i];
                Rule nr = getRule(ntyp, ruleStride);
                if(nr.flamm > 0.0 && ntyp != T_FIRE){
                    ivec2 npos = p;
                    if(i == 0) npos += ivec2(0, 1);
                    else if(i == 1) npos += ivec2(0, -1);
                    else if(i == 2) npos += ivec2(1, 0);
                    else npos += ivec2(-1, 0);
                    
                    if(inBounds(npos, gridSize)){
                        uint nidx = uint(npos.y) * gridSize.x + uint(npos.x);
                        writeCell(nidx, npos, T_FIRE, max(temp, nr.TH), 20u, 0u);
                    }
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // GLASS SHATTERING
    // ═══════════════════════════════════════════════════════════════════════════
    if(typ == T_GLASS_NEW || typ == T_OBSIDIAN){
        // Check for impact conditions (velocity, blast, temperature shock)
        vec2 vel = imageLoad(velIn, p).xy;
        float velMag = length(vel);
        float tempDelta = abs(temp - 96.0); // Deviation from ambient
        
        // Shatter from impact
        if(velMag > r.glassShatter * 0.1){
            uint rnd = hash(idx ^ frame);
            if(hashF(rnd) < 0.7){
                writeCell(idx, p, T_SHRAPNEL, temp, 15u, 0u);
                return;
            }
        }
        
        // Shatter from thermal shock (obsidian is more resistant)
        float shockThreshold = r.glassThermal;
        if(typ == T_OBSIDIAN) shockThreshold *= 0.3; // Obsidian more resistant
        
        if(tempDelta > 100.0 && shockThreshold < 0.5){
            uint rnd = hash(idx ^ frame);
            if(hashF(rnd) < shockThreshold * 2.0){
                writeCell(idx, p, T_SHRAPNEL, temp, 12u, 0u);
                return;
            }
        }
        
        // Glass already shatters in blast logic (lines 333-337)
        // Obsidian is harder to shatter due to higher cohesion
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // Phase transitions with Latent Heat (Phase 6)
    //
    // Phase changes absorb or release energy without temperature change.
    // This prevents unrealistic instant phase changes and conserves energy.
    //
    // Examples:
    //   Water -> Steam: absorbs L_vap (temp drops to compensate)
    //   Steam -> Water: releases L_vap (temp rises to compensate)
    //   Stone -> Lava: absorbs L_fus (heat of fusion)
    //   Lava -> Stone: releases L_fus
    // ═══════════════════════════════════════════════════════════════════════════

    // Latent heat constants (in temperature units, scaled to 0-255 range)
    // These represent the energy cost/benefit of phase changes
    const float LATENT_VAPORIZATION = 32.0;   // Water <-> Steam
    const float LATENT_FUSION = 24.0;         // Stone <-> Lava, Ice <-> Water
    const float LATENT_SUBLIMATION = 48.0;    // Solid <-> Gas direct

    if(r.phiH != typ && temp >= highT){
        uint nl = (r.phiH == T_FIRE) ? 20u + uint(r.flamm * 30.0) : ((r.phiH == T_STEAM) ? 24u : 0u);

        // Calculate latent heat adjustment for high-temperature transitions
        float newTemp = max(temp, highT);

        // Apply latent heat (energy absorbed during heating transition)
        // Water -> Steam, Ice/Snow -> Water, Stone -> Lava
        if (typ == T_WATER && r.phiH == T_STEAM) {
            // Vaporization absorbs energy: final temp is lower than input
            newTemp = max(highT, temp - LATENT_VAPORIZATION);
        } else if ((typ == T_STONE || typ == T_SAND) && r.phiH == T_LAVA) {
            // Fusion absorbs energy
            newTemp = max(highT, temp - LATENT_FUSION);
        } else if ((typ == T_SNOW || typ == T_ICE) && r.phiH == T_WATER) {
            // Melting absorbs energy (both ice and snow)
            newTemp = max(highT, temp - LATENT_FUSION);
        }

        writeCell(idx, p, r.phiH, newTemp, nl, 0u);
        return;
    }

    if(r.phiL != typ && temp <= lowT){
        float newTemp = temp;

        // Apply latent heat (energy released during cooling transition)
        // Steam -> Water, Lava -> Stone, Water -> Ice/Snow
        if (typ == T_STEAM && r.phiL == T_WATER) {
            // Condensation releases energy: final temp is higher
            newTemp = temp + LATENT_VAPORIZATION;
        } else if (typ == T_LAVA && (r.phiL == T_STONE || r.phiL == T_SAND || r.phiL == T_GLASS)) {
            // Solidification releases energy
            newTemp = temp + LATENT_FUSION;
        } else if (typ == T_WATER && (r.phiL == T_SNOW || r.phiL == T_ICE)) {
            // Freezing releases energy (forms either snow or ice)
            newTemp = temp + LATENT_FUSION;
        }

        writeCell(idx, p, r.phiL, newTemp, 0u, 0u);
        return;
    }

    // Spontaneous combustion (requires oxidizer for o2Req > 0 materials)
    if(r.flamm > 0.0 && temp >= max(0.0, highT - 8.0)){
        bool hasOxidizer = true;
        if(r.o2Req > 0.0){
            hasOxidizer = (tn == T_OXYGEN || ts == T_OXYGEN || te == T_OXYGEN || tw == T_OXYGEN ||
                           tn == T_AIR   || ts == T_AIR   || te == T_AIR   || tw == T_AIR);
        }
        if(hasOxidizer){
            uint rnd = hash(idx ^ (frame * 97u));
            if((rnd & 63u) == 0u){
                uint nl = 18u + uint(r.flamm * 48.0);
                writeCell(idx, p, T_FIRE, 220.0, nl, 0u);
                return;
            }
        }
    }

    // Electricity propagation
    if(typ == T_SPARK){
        // Find conductive neighbor with lowest cooldown
        uint bestTarget = idx;
        float bestCond = 0.0;
        uint bestFlags = 255u;

        Rule rn = getRule(tn, ruleStride), rs = getRule(ts, ruleStride), re = getRule(te, ruleStride), rw = getRule(tw, ruleStride);

        // Prefer conductive neighbors with lower cooldown flags
        if(rn.cond > 0.5 && tn != T_SPARK) {
            uint fn = getFlags(n);
            if(fn < bestFlags || (fn == bestFlags && rn.cond > bestCond)) {
                bestCond = rn.cond; bestTarget = uint((p.y + 1) * int(gridSize.x) + p.x); bestFlags = fn;
            }
        }
        if(rs.cond > 0.5 && ts != T_SPARK) {
            uint fs = getFlags(s);
            if(fs < bestFlags || (fs == bestFlags && rs.cond > bestCond)) {
                bestCond = rs.cond; bestTarget = uint((p.y - 1) * int(gridSize.x) + p.x); bestFlags = fs;
            }
        }
        if(re.cond > 0.5 && te != T_SPARK) {
            uint fe = getFlags(e);
            if(fe < bestFlags || (fe == bestFlags && re.cond > bestCond)) {
                bestCond = re.cond; bestTarget = uint(p.y * int(gridSize.x) + p.x + 1); bestFlags = fe;
            }
        }
        if(rw.cond > 0.5 && tw != T_SPARK) {
            uint fw = getFlags(w);
            if(fw < bestFlags || (fw == bestFlags && rw.cond > bestCond)) {
                bestCond = rw.cond; bestTarget = uint(p.y * int(gridSize.x) + p.x - 1); bestFlags = fw;
            }
        }

        // Write spark to best target if valid and cooldown is low
        if(bestTarget != idx && bestFlags < 10u){
            ivec2 bp = ivec2(int(bestTarget % gridSize.x), int(bestTarget / gridSize.x));
            writeCell(bestTarget, bp, T_SPARK, 240.0, 8u, 20u);
        }
    }

    // Default: pass through
    writeCell(idx, p, typ, temp, life, flg);
}
