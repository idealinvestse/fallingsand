#version 430
// Bloom extract: downsample display texture to half-res, keeping only bright pixels.
layout(local_size_x = 16, local_size_y = 16) in;

layout(rgba8, binding = 7) uniform readonly image2D displayTex;
layout(rgba8, binding = 19) uniform writeonly image2D bloomOut;

uniform uvec2 gridSize;       // full resolution
uniform float bloomThreshold; // luminance threshold (0.0-1.0)
uniform float bloomIntensity; // bloom intensity multiplier

vec3 rgb_to_luminance(vec3 c) {
    return vec3(0.2126, 0.7152, 0.0722) * c;
}

void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    // bloomOut is half-res: gridSize/2
    ivec2 bloomSize = ivec2(gridSize.x / 2u, gridSize.y / 2u);
    if (p.x >= bloomSize.x || p.y >= bloomSize.y) return;

    // Sample 2x2 block from full-res display
    ivec2 base = p * 2;
    vec3 c00 = imageLoad(displayTex, base).rgb;
    vec3 c10 = imageLoad(displayTex, base + ivec2(1, 0)).rgb;
    vec3 c01 = imageLoad(displayTex, base + ivec2(0, 1)).rgb;
    vec3 c11 = imageLoad(displayTex, base + ivec2(1, 1)).rgb;

    // Box filter downsample
    vec3 avg = (c00 + c10 + c01 + c11) * 0.25;

    // Extract bright pixels
    float lum = dot(avg, vec3(0.2126, 0.7152, 0.0722));
    float brightness = max(lum - bloomThreshold, 0.0) / max(1.0 - bloomThreshold, 0.001);

    vec3 bloomColor = avg * brightness * bloomIntensity;
    imageStore(bloomOut, p, vec4(bloomColor, 1.0));
}
