layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(r32f,  binding = 5) uniform readonly image2D pressureTex;
layout(rg32f, binding = 4) uniform writeonly image2D velOut;

uniform uvec2 gridSize;
uniform uint ruleStride;

// ── Variable-density projection ─────────────────────────────────────────────
const float RHO_MIN = 0.1;

bool isSolid(ivec2 p){
    if(!inBounds(p, gridSize)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ, ruleStride).cat == 3;
}

bool isGas(ivec2 p){
    if(!inBounds(p, gridSize)) return false;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ, ruleStride).cat == 0;
}

float cellDensityAbs(ivec2 p){
    if(!inBounds(p, gridSize)) return RHO_MIN;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    float rho = abs(getRule(getType(cells[idx]), ruleStride).density);
    return max(rho, RHO_MIN);
}

float samplePressure(ivec2 p, ivec2 self_p){
    if(!inBounds(p, gridSize) || isSolid(p)){
        return imageLoad(pressureTex, self_p).x;
    }
    return imageLoad(pressureTex, p).x;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint selfTyp = getType(cells[uint(p.y) * gridSize.x + uint(p.x)]);
    if(isSolid(p) || getRule(selfTyp, ruleStride).cat == 1){
        imageStore(velOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    vec2 v = imageLoad(velIn, p).xy;

    // Sample pressure at neighbors (with Neumann BCs)
    float pL = samplePressure(p + ivec2(-1, 0), p);
    float pR = samplePressure(p + ivec2( 1, 0), p);
    float pD = samplePressure(p + ivec2( 0, -1), p);
    float pU = samplePressure(p + ivec2( 0, 1), p);

    // Density-weighted gradient: acceleration = −∇p/ρ_self.
    // Using cell-centred ρ is a standard simplification for collocated grids;
    // it matches the face-density Poisson stencil closely enough that the
    // projected field remains approximately divergence-free.
    float rhoSelf = max(abs(getRule(selfTyp, ruleStride).density), RHO_MIN);
    vec2 gradP = 0.5 * vec2(pR - pL, pU - pD);
    v -= gradP / rhoSelf;

    imageStore(velOut, p, vec4(v, 0.0, 0.0));
}