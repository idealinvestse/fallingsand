// ═══════════════════════════════════════════════════════════════════════════════
// Biology / ecology step shader (Phase 1)
//
// Simulates nutrient cycling, moisture dynamics, and bio-material growth/decay.
//
// Nutrient field:
//   - Diffuses through soil (dirt, mud) and water
//   - Consumed by bio materials (plant, slime) for growth
//   - Replenished by decay of bio materials
//
// Moisture field:
//   - Diffuses through all materials
//   - Evaporates with heat
//   - Consumed by plants for growth
//   - Replenished by water cells
//
// Growth rules:
//   - Bio cells consume nutrients + moisture + warmth → spread to neighbors
//   - Without nutrients or moisture, bio cells decay
//   - Decay returns nutrients to the soil
//
// Reads:  cells (SSBO), rules (SSBO), nutrientIn, moistureIn, tempIn
// Writes: nutrientOut, moistureOut
// ═══════════════════════════════════════════════════════════════════════════════

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer defined in common.glsl (binding = 2)

layout(r32f, binding = 13) uniform readonly  image2D nutrientIn;
layout(r32f, binding = 14) uniform writeonly image2D nutrientOut;
layout(r32f, binding = 15) uniform readonly  image2D moistureIn;
layout(r32f, binding = 16) uniform writeonly image2D moistureOut;
layout(r32f, binding = 11) uniform readonly  image2D tempIn;
layout(r32f, binding = 9) uniform readonly  image2D chargeIn;  // Cross-system coupling

uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float dt;
uniform float nutrientDiffuseRate;   // diffusion speed for nutrients
uniform float moistureDiffuseRate;   // diffusion speed for moisture
uniform float moistureEvapRate;      // evaporation rate per heat unit
uniform float growthRate;            // bio growth speed
uniform float decayRate;             // bio decay speed
uniform float nutrientConsumeRate;   // nutrients consumed per growth
uniform float moistureConsumeRate;   // moisture consumed per growth
uniform float waterMoistureBoost;    // moisture added by water cells
uniform float dirtNutrientRegen;     // passive nutrient regen in dirt

// v6.1 Deep System Interactions uniforms
uniform float biology_electro_stim;       // Default: 0.3 - growth boost from moderate charge
uniform float charge_damage_threshold;   // Default: 500.0 - charge level causing bio damage
uniform float charge_stim_range_low;     // Default: 10.0 - lower bound for electro-stimulation
uniform float charge_stim_range_high;    // Default: 100.0 - upper bound for electro-stimulation
uniform float temp_effect_multiplier;    // Default: 1.0 - global temperature coupling strength

// Bio material IDs defined in common.glsl

bool isBio(uint typ){
    return typ == T_PLANT || typ == T_BLOOD || typ == T_VIRUS || typ == T_SLIME;
}

bool isSoil(uint typ){
    return typ == T_DIRT || typ == T_MUD;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ  = getType(cell);
    Rule r = getRule(typ, ruleStride);

    float nut  = imageLoad(nutrientIn, p).r;
    float moist = imageLoad(moistureIn, p).r;
    float temp  = imageLoad(tempIn, p).r;
    float charge = imageLoad(chargeIn, p).r;  // Cross-system coupling

    // ── Nutrient diffusion (4-neighbor stencil) ──────────────────────────
    float nutSum = 0.0;
    float nutWeight = 0.0;
    ivec2 offsets[4] = {ivec2(1,0), ivec2(-1,0), ivec2(0,1), ivec2(0,-1)};
    for(int i = 0; i < 4; i++){
        ivec2 np = p + offsets[i];
        if(!inBounds(np, gridSize)) continue;
        uint ntyp = getType(cells[uint(np.y) * gridSize.x + uint(np.x)]);
        // Nutrients diffuse through soil and water
        float w = 0.0;
        if(isSoil(ntyp) || ntyp == T_WATER) w = 1.0;
        else if(isBio(ntyp)) w = 0.3;
        if(w > 0.0){
            nutSum += imageLoad(nutrientIn, np).r * w;
            nutWeight += w;
        }
    }
    if(nutWeight > 0.0){
        float nutAvg = nutSum / nutWeight;
        nut += (nutAvg - nut) * nutrientDiffuseRate * dt;
    }

    // ── Moisture diffusion (4-neighbor stencil) ──────────────────────────
    float moistSum = 0.0;
    float moistWeight = 0.0;
    for(int i = 0; i < 4; i++){
        ivec2 np = p + offsets[i];
        if(!inBounds(np, gridSize)) continue;
        moistSum += imageLoad(moistureIn, np).r;
        moistWeight += 1.0;
    }
    if(moistWeight > 0.0){
        float moistAvg = moistSum / moistWeight;
        moist += (moistAvg - moist) * moistureDiffuseRate * dt;
    }

    // ── Moisture evaporation (heat-driven) ───────────────────────────────
    float evap = moist * moistureEvapRate * max(0.0, temp - 96.0) * 0.01 * dt;
    moist = max(0.0, moist - evap);

    // ── Water cells add moisture ─────────────────────────────────────────
    if(typ == T_WATER){
        moist = min(1000.0, moist + waterMoistureBoost * dt);
    }

    // ── Dirt/soil passive nutrient regeneration ──────────────────────────
    if(isSoil(typ)){
        nut = min(1000.0, nut + dirtNutrientRegen * dt);
    }

    // ── Bio growth / decay ───────────────────────────────────────────────
    if(isBio(typ)){
        // v6.1: Cross-system coupling: Electric fields affect growth (Rule B)
        float absCharge = abs(charge);
        float growthModifier = 1.0;

        if(absCharge > charge_stim_range_low && absCharge < charge_stim_range_high) {
            // Electro-stimulation: moderate charge boosts growth
            float stimStrength = (absCharge - charge_stim_range_low) / 
                                (charge_stim_range_high - charge_stim_range_low);
            growthModifier = 1.0 + clamp(stimStrength * biology_electro_stim, 0.0, 1.5);
        } else if(absCharge > charge_damage_threshold) {
            // High charge causes damage (breakdown threshold exceeded)
            float damage = (absCharge - charge_damage_threshold) / charge_damage_threshold;
            growthModifier = max(0.2, 1.0 - damage);  // At least 20% growth rate
        }

        // v6.1: Temperature effect multiplier (Rule E)
        float tempFactor = smoothstep(50.0, 150.0, temp) * temp_effect_multiplier;
        growthModifier *= tempFactor;

        // Growth: needs nutrients, moisture, and warmth
        bool canGrow = nut > 0.1 && moist > 0.1 && temp > 100.0;
        if(canGrow){
            float actualGrowth = growthRate * growthModifier * dt;
            nut   -= nutrientConsumeRate * actualGrowth;
            moist -= moistureConsumeRate * actualGrowth;
        } else {
            // Decay: bio dies without resources, returns nutrients
            float actualDecay = decayRate * dt;
            nut += actualDecay * 0.5;  // half of decay mass becomes nutrients

            // v6.1: High charge accelerates decay (electrocution damage)
            if(absCharge > charge_damage_threshold){
                nut += actualDecay * 0.3;  // Additional nutrient release from damage
                moist += actualDecay * 0.2;  // Cell fluid released
            }
        }
    }

    // ── Clamp and write ──────────────────────────────────────────────────
    nut   = clamp(nut, 0.0, 1000.0);
    moist = clamp(moist, 0.0, 1000.0);

    imageStore(nutrientOut, p, vec4(nut, 0.0, 0.0, 0.0));
    imageStore(moistureOut, p, vec4(moist, 0.0, 0.0, 0.0));
}
