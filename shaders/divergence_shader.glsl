layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(r32f,  binding = 4) uniform writeonly image2D divergenceTex;

uniform uvec2 gridSize;
uniform uint ruleStride;

// ── Unique to this shader: isSolid for divergence calculation ───────────────
bool isSolid(ivec2 p){
    if(!inBounds(p, gridSize)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ, ruleStride).cat == 3;
}

// Free-slip Neumann boundary: at walls / solids we enforce zero normal flow by
// reflecting the normal component of the self-velocity into a ghost cell and
// keeping the tangential component. For side neighbors (±x) we flip v.x and
// keep v.y; for vertical neighbors (±y) we flip v.y and keep v.x. Returning
// plain vec2(0.0) (previous behaviour) injects spurious divergence at walls
// which the pressure solve then tries to cancel, creating artificial suction.
vec2 sampleVelBC(ivec2 p, ivec2 dir, vec2 vSelf){
    if(inBounds(p, gridSize) && !isSolid(p)){
        return imageLoad(velTex, p).xy;
    }
    // Ghost: mirror the normal component across the wall/boundary face.
    vec2 g = vSelf;
    if(dir.x != 0) g.x = -vSelf.x;
    if(dir.y != 0) g.y = -vSelf.y;
    return g;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint selfTyp = getType(cells[uint(p.y) * gridSize.x + uint(p.x)]);
    if(isSolid(p) || getRule(selfTyp, ruleStride).cat == 1){
        imageStore(divergenceTex, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    vec2 vSelf = imageLoad(velTex, p).xy;

    // Sample velocity at neighbors with free-slip ghost cells at walls/solids.
    vec2 vL = sampleVelBC(p + ivec2(-1, 0), ivec2(-1, 0), vSelf);
    vec2 vR = sampleVelBC(p + ivec2( 1, 0), ivec2( 1, 0), vSelf);
    vec2 vD = sampleVelBC(p + ivec2( 0, -1), ivec2( 0, -1), vSelf);
    vec2 vU = sampleVelBC(p + ivec2( 0,  1), ivec2( 0,  1), vSelf);

    // Compute divergence: div(v) = (vR.x - vL.x)/2 + (vU.y - vD.y)/2
    float div = 0.5 * ((vR.x - vL.x) + (vU.y - vD.y));
    imageStore(divergenceTex, p, vec4(div, 0.0, 0.0, 0.0));
}
