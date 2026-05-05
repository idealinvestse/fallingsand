#version 430
// Bloom blur: separable gaussian blur (horizontal or vertical pass).
// Dispatch twice: first with direction=0 (horizontal), then direction=1 (vertical).
layout(local_size_x = 16, local_size_y = 16) in;

layout(rgba8, binding = 19) uniform readonly image2D bloomIn;
layout(rgba8, binding = 20) uniform writeonly image2D bloomOut;

uniform uvec2 gridSize;       // full resolution (bloom is half)
uniform int blurDirection;    // 0 = horizontal, 1 = vertical

// 9-tap gaussian kernel (sigma ≈ 2.0)
const float weights[5] = float[](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);

void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 bloomSize = ivec2(gridSize.x / 2u, gridSize.y / 2u);
    if (p.x >= bloomSize.x || p.y >= bloomSize.y) return;

    vec3 center = imageLoad(bloomIn, p).rgb;
    vec3 result = center * weights[0];

    ivec2 step = (blurDirection == 0) ? ivec2(1, 0) : ivec2(0, 1);

    for (int i = 1; i < 5; i++) {
        ivec2 offset = step * i;
        ivec2 pos1 = p + offset;
        ivec2 pos2 = p - offset;

        if (pos1.x >= 0 && pos1.y >= 0 && pos1.x < bloomSize.x && pos1.y < bloomSize.y) {
            result += imageLoad(bloomIn, pos1).rgb * weights[i];
        }
        if (pos2.x >= 0 && pos2.y >= 0 && pos2.x < bloomSize.x && pos2.y < bloomSize.y) {
            result += imageLoad(bloomIn, pos2).rgb * weights[i];
        }
    }

    imageStore(bloomOut, p, vec4(result, 1.0));
}
