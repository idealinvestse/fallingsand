layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer ReadBuffer  { uint cellsIn[];  };
layout(std430, binding = 1) writeonly buffer WriteBuffer { uint cellsOut[]; };
// RuleBuffer is now defined in common.glsl

// Temperature textures (r32f) — carry through unchanged
layout(r32f, binding = 11) uniform readonly image2D tempTex;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;

uniform uvec2 gridSize;
uniform uint frame;
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

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];
    uint typ  = getType(cell);
    float temp = imageLoad(tempTex, p).r;
    uint life = getLife(cell);
    uint flg  = getFlags(cell);

    Rule r = getRule(typ, ruleStride);

    // Only process liquids (cat == 2)
    if(r.cat != 2){
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
    if(r.sol > 0.0){
        bool nearWater = (tn == T_WATER || ts == T_WATER || te == T_WATER || tw == T_WATER);
        if(nearWater){
            uint rndSol = hash(idx ^ (frame * 13u));
            if(hashF(rndSol) < r.sol * 0.05){
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
    if(r.st > 0.15){
        uint sameTypeCount = 0u;
        if(tn == typ) sameTypeCount++;
        if(ts == typ) sameTypeCount++;
        if(te == typ) sameTypeCount++;
        if(tw == typ) sameTypeCount++;

        // Interface penalty: droplets lose heat faster, bulk retains it
        if(sameTypeCount < 2u){
            temp -= r.st * 0.5;
        } else if(sameTypeCount >= 3u){
            temp += r.st * 0.2;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // 3. Viscosity thermal retention
    //    High-viscosity liquids (honey, lava, quicksand) retain heat.
    // ═══════════════════════════════════════════════════════════════════════════
    if(r.visc > 0.5){
        temp += r.visc * 0.1;
    }

    // Default: pass through with possibly modified temperature
    writeCell(idx, p, typ, temp, life, flg);
}
