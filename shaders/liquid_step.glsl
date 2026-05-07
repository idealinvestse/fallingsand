layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer ReadBuffer  { uint cellsIn[];  };
layout(std430, binding = 1) writeonly buffer WriteBuffer { uint cellsOut[]; };
// RuleBuffer is now defined in common.glsl

// Temperature textures (r32f) — carry through unchanged
layout(r32f, binding = 11) uniform readonly image2D tempTex;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;

// v6.1: Nutrient textures for advection
layout(r32f, binding = 13) uniform readonly image2D nutrientIn;
layout(r32f, binding = 14) uniform writeonly image2D nutrientOut;

// Velocity texture for nutrient advection
layout(rg32f, binding = 3) uniform readonly image2D velTex;

uniform uvec2 gridSize;
uniform uint frame;
uniform float dt;

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

// v6.1: Semi-Lagrangian advection for nutrients (Rule D)
float advectNutrient(ivec2 p, vec2 vel, float dt){
    // Trace back along velocity field
    vec2 sourcePos = vec2(p) - vel * dt;
    ivec2 sourceCell = ivec2(floor(sourcePos + 0.5));
    
    if(!inBounds(sourceCell, gridSize)) return 0.0;
    return imageLoad(nutrientIn, sourceCell).r;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];
    uint typ  = getType(cell);
    float temp = imageLoad(tempTex, p).r;
    uint life = getLife(cell);
    uint flg  = getFlags(cell);

    // Only process liquids (T_WATER, T_OIL, T_LAVA, T_ACID, etc.)
    bool isLiquid = (typ == T_WATER || typ == T_OIL || typ == T_LAVA || typ == T_ACID ||
                     typ == T_MERCURY || typ == T_HONEY || typ == T_QUICKSAND ||
                     typ == T_BRINE || typ == T_MAGMA);
    if(!isLiquid){
        writeCell(idx, p, typ, temp, life, flg);
        return;
    }

    // Load neighbors
    uint n = loadCell(p + ivec2(0, 1));
    uint s = loadCell(p + ivec2(0, -1));
    uint e = loadCell(p + ivec2(1, 0));
    uint w = loadCell(p + ivec2(-1, 0));

    uint tn = getType(n), ts = getType(s), te = getType(e), tw = getType(w);

    // ═══════════════════════════════════════════════════════════════════════════
    // 1. Solubility — dissolve in water if sol > 0
    //    Only writes to self; no data races with neighbors.
    // ═══════════════════════════════════════════════════════════════════════════
    // Simplified: only certain materials dissolve (salt, sugar, etc.)
    bool isSoluble = (typ == T_SALT || typ == T_SUGAR);
    if(isSoluble){
        bool nearWater = (tn == T_WATER || ts == T_WATER || te == T_WATER || tw == T_WATER);
        if(nearWater){
            uint rndSol = hash(idx ^ (frame * 13u));
            if(hashF(rndSol) < 0.05){
                // Dissolve — become air (simplified; in full sim would tint water)
                writeCell(idx, p, T_AIR, temp, 0u, 0u);
                return;
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // 2. Surface tension thermal bias
    //    High-surface-tension liquids lose/gain heat depending on whether
    //    local temperature adjustment — no neighbour writes.
    // ═══════════════════════════════════════════════════════════════════════════
    bool highSurfaceTension = (typ == T_WATER || typ == T_MERCURY);
    if(highSurfaceTension){
        uint sameTypeCount = 0u;
        if(tn == typ) sameTypeCount++;
        if(ts == typ) sameTypeCount++;
        if(te == typ) sameTypeCount++;
        if(tw == typ) sameTypeCount++;

        // Interface penalty: droplets lose heat faster, bulk retains it
        if(sameTypeCount < 2u){
            temp -= 0.5;
        } else if(sameTypeCount >= 3u){
            temp += 0.2;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // 3. Viscosity thermal retention
    //    High-viscosity liquids (honey, lava, quicksand) retain heat.
    // ═══════════════════════════════════════════════════════════════════════════
    bool highViscosity = (typ == T_HONEY || typ == T_LAVA || typ == T_QUICKSAND);
    if(highViscosity){
        temp += 0.1;
    }

    // ── Nutrient advection via fluid flow (Rule D) ──────────────────────
    float nut = imageLoad(nutrientIn, p).r;
    vec2 vel = imageLoad(velTex, p).xy;

    // Only advect nutrients through liquid or if liquid nearby
    bool shouldAdvect = isLiquid || (tn == T_WATER) || (ts == T_WATER) || 
                        (te == T_WATER) || (tw == T_WATER);

    if(shouldAdvect && length(vel) > 0.1){
        // Semi-Lagrangian nutrient transport
        float advectedNut = advectNutrient(p, vel, dt);
        
        // Blend: some diffusion + advection
        float advectionStrength = clamp(length(vel) * 0.5, 0.0, 0.8);
        nut = mix(nut, advectedNut, advectionStrength);
        
        // Water cells gain nutrients from flow (rivers carry sediment)
        if(typ == T_WATER && advectedNut > nut){
            nut = mix(nut, advectedNut, 0.7);
        }
    }

    imageStore(nutrientOut, p, vec4(nut, 0.0, 0.0, 0.0));

    // Default: pass through with possibly modified temperature
    writeCell(idx, p, typ, temp, life, flg);
}
