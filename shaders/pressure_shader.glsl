layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl

layout(r32f, binding = 4) uniform readonly image2D divergenceTex;
layout(r32f, binding = 5) uniform readonly image2D pressureIn;
layout(r32f, binding = 6) uniform writeonly image2D pressureOut;

uniform uvec2 gridSize;
uniform uint ruleStride;
uniform uint iteration;

// ── Variable-density Poisson solver ─────────────────────────────────────────
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

float cellDensity(ivec2 p){
    if(!inBounds(p, gridSize)) return RHO_MIN;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    float rho = abs(getRule(getType(cells[idx]), ruleStride).density);
    return max(rho, RHO_MIN);
}

float faceInvRho(ivec2 self_p, ivec2 neigh_p){
    float a = cellDensity(self_p);
    float b = cellDensity(neigh_p);
    float s = a + b;
    if(s < 1e-6) return 0.0;
    return s / (2.0 * a * b);
}

float samplePressure(ivec2 p, ivec2 self_p){
    if(!inBounds(p, gridSize) || isSolid(p)){
        return imageLoad(pressureIn, self_p).x;
    }
    return imageLoad(pressureIn, p).x;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    if(isSolid(p)){
        imageStore(pressureOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    // Gas cells: pressure is owned by the acoustic solver, not Poisson.
    // Skip update — acoustic step will overwrite with propagated pressure.
    if(isGas(p)){
        imageStore(pressureOut, p, imageLoad(pressureIn, p));
        return;
    }

    // Red-black Gauss-Seidel: checkerboard pattern
    // Even iterations process red cells (x+y even), odd iterations process black cells (x+y odd)
    uint parity = (p.x + p.y) & 1u;
    if((iteration & 1u) != parity){
        // Skip this cell in this iteration
        imageStore(pressureOut, p, imageLoad(pressureIn, p));
        return;
    }

    // Load divergence (already encodes 1/dt scaling from our source term setup)
    float div = imageLoad(divergenceTex, p).x;

    // Face weights: for a Neumann neighbour the weight contribution is 0
    // because p_n − p_self vanishes; we mirror that here by zeroing w_n so
    // that boundary cells don't artificially dominate the sum.
    ivec2 pL = p + ivec2(-1, 0);
    ivec2 pR = p + ivec2( 1, 0);
    ivec2 pD = p + ivec2( 0,-1);
    ivec2 pU = p + ivec2( 0, 1);

    float wL = (inBounds(pL, gridSize) && !isSolid(pL)) ? faceInvRho(p, pL) : 0.0;
    float wR = (inBounds(pR, gridSize) && !isSolid(pR)) ? faceInvRho(p, pR) : 0.0;
    float wD = (inBounds(pD, gridSize) && !isSolid(pD)) ? faceInvRho(p, pD) : 0.0;
    float wU = (inBounds(pU, gridSize) && !isSolid(pU)) ? faceInvRho(p, pU) : 0.0;
    float wSum = wL + wR + wD + wU;

    float pC = imageLoad(pressureIn, p).x;

    // All neighbours closed (isolated cell surrounded by solids): pressure
    // is under-determined → keep previous value.
    if(wSum < 1e-6){
        imageStore(pressureOut, p, vec4(pC, 0.0, 0.0, 0.0));
        return;
    }

    float pL_v = samplePressure(pL, p);
    float pR_v = samplePressure(pR, p);
    float pD_v = samplePressure(pD, p);
    float pU_v = samplePressure(pU, p);

    // p_self = (Σ w_n p_n − div) / Σ w_n
    float pNew = (wL*pL_v + wR*pR_v + wD*pD_v + wU*pU_v - div) / wSum;
    imageStore(pressureOut, p, vec4(pNew, 0.0, 0.0, 0.0));
}
