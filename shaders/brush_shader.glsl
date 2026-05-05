#version 430

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) buffer ReadBuffer { uint cellsRead[]; };
layout(std430, binding = 1) buffer WriteBuffer { uint cellsWrite[]; };
// RuleBuffer is now defined in common.glsl

layout(r32f, binding = 11) uniform image2D tempA;
layout(r32f, binding = 12) uniform image2D tempB;
layout(r32f, binding = 9)  uniform image2D chargeA;
layout(r32f, binding = 10) uniform image2D chargeB;

uniform uvec2 gridSize;
uniform ivec2 brushCenter;
uniform uint brushRadius;
uniform uint materialId;
uniform uint brushMode;
uniform float tempDelta;
uniform float materialTemp;
uniform uint materialLife;
uniform float chargeDelta;

uint getType(uint c) { return c & 0xFFu; }
uint getLife(uint c) { return (c >> 8u) & 0xFFu; }
uint getFlags(uint c) { return (c >> 16u) & 0xFFu; }

uint packCell(uint typ, uint life, uint flg) {
    return (typ & 0xFFu) | ((life & 0xFFu) << 8u) | ((flg & 0xFFu) << 16u);
}

bool inBounds(ivec2 p) {
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

void writeBoth(uint idx, uint cell) {
    cellsRead[idx] = cell;
    cellsWrite[idx] = cell;
}

void writeTempBoth(ivec2 p, float temp) {
    imageStore(tempA, p, vec4(temp, 0.0, 0.0, 0.0));
    imageStore(tempB, p, vec4(temp, 0.0, 0.0, 0.0));
}

void writeChargeBoth(ivec2 p, float q) {
    imageStore(chargeA, p, vec4(q, 0.0, 0.0, 0.0));
    imageStore(chargeB, p, vec4(q, 0.0, 0.0, 0.0));
}

void main() {
    ivec2 local = ivec2(gl_GlobalInvocationID.xy);
    ivec2 p = brushCenter - ivec2(int(brushRadius)) + local;
    if (!inBounds(p)) return;

    ivec2 d = p - brushCenter;
    uint r2 = brushRadius * brushRadius;
    if (uint(d.x * d.x + d.y * d.y) > r2) return;
    if (brushMode == 3u && d != ivec2(0)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);

    if (brushMode == 0u || brushMode == 3u) {
        writeBoth(idx, packCell(materialId, materialLife, 0u));
        writeTempBoth(p, materialTemp);
        return;
    }

    if (brushMode == 1u || brushMode == 2u) {
        uint cell = cellsRead[idx];
        float oldTemp = imageLoad(tempA, p).r;
        float newTemp = max(0.0, oldTemp + tempDelta);
        writeBoth(idx, packCell(getType(cell), getLife(cell), getFlags(cell)));
        writeTempBoth(p, newTemp);
    }

    if (brushMode == 4u) {
        float oldCharge = imageLoad(chargeA, p).r;
        float newCharge = oldCharge + chargeDelta;
        writeChargeBoth(p, newCharge);
    }
}
