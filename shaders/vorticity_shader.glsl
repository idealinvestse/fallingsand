layout(local_size_x = 16, local_size_y = 16) in;

layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(r32f,  binding = 8) uniform writeonly image2D vorticityTex;

uniform uvec2 gridSize;

vec2 sampleVel(ivec2 p){
    if(!inBounds(p, gridSize)) return vec2(0.0);
    return imageLoad(velTex, p).xy;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    // Sample velocity at neighbors
    vec2 vL = sampleVel(p + ivec2(-1, 0));
    vec2 vR = sampleVel(p + ivec2( 1, 0));
    vec2 vD = sampleVel(p + ivec2( 0, -1));
    vec2 vU = sampleVel(p + ivec2( 0, 1));

    // Compute curl (vorticity) in 2D: ω = ∂v_y/∂x - ∂v_x/∂y
    float curl = 0.5 * ((vU.x - vD.x) - (vR.y - vL.y));

    imageStore(vorticityTex, p, vec4(curl, 0.0, 0.0, 0.0));
}
