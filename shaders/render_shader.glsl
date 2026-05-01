layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl
layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(r32f,  binding = 5) uniform readonly image2D presTex;   // pressure for overlay
layout(rgba8, binding = 7) uniform writeonly image2D displayTexture;
layout(r32f, binding = 11) uniform readonly image2D tempTex;

uniform uvec2 gridSize;
uniform uint frame;
uniform uint ruleStride;
uniform int showPressure;     // 1 = pressure overlay on gas cells
uniform float ambientPressure;  // for normalising pressure overlay
uniform float ambientTemp;      // for temperature remapping

// Explosion visual effects uniforms
uniform float explosionFlash;      // Screen flash intensity (0.0 to 1.0)
uniform vec2 explosionCenter;      // Center of explosion
uniform float explosionAge;        // Time since explosion (for shockwave)
uniform float explosionMaxAge;     // Max age for shockwave

// Approximate blackbody ramp: dark red -> orange -> yellow -> white.
vec3 blackbody(float t){
    float x = clamp(t, 0.0, 1.0);
    vec3 c0 = vec3(0.03, 0.00, 0.00);
    vec3 c1 = vec3(0.45, 0.03, 0.00);
    vec3 c2 = vec3(0.95, 0.32, 0.02);
    vec3 c3 = vec3(1.00, 0.82, 0.25);
    vec3 c4 = vec3(1.00, 1.00, 0.96);

    if(x < 0.35){
        return mix(c0, c1, smoothstep(0.00, 0.35, x));
    }
    if(x < 0.60){
        return mix(c1, c2, smoothstep(0.35, 0.60, x));
    }
    if(x < 0.82){
        return mix(c2, c3, smoothstep(0.60, 0.82, x));
    }
    return mix(c3, c4, smoothstep(0.82, 1.00, x));
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ = getType(cell);
    float temp = imageLoad(tempTex, p).r;
    uint flg = getFlags(cell);
    Rule rr = getRule(typ, ruleStride);

    vec3 col = rr.color;

    // Add noise to materials (including gas for organic fire/smoke texture)
    if(rr.cat != 3){
        float n = float(hash(idx ^ frame) & 15u) / 255.0 - 0.03;
        if(typ == T_FIRE || typ == T_EMBER || typ == T_BLAST){
            // Warm noise for fire
            col += vec3(n * 0.8, n * 0.4, 0.0);
        } else if(typ == T_SMOKE || typ == T_GAS){
            // Cool noise for smoke
            col += vec3(n * 0.3);
        } else {
            col += vec3(n);
        }
    }

    // Turbulence visualization (velocity-based)
    vec2 v = imageLoad(velTex, p).xy;
    float speed = clamp(length(v) * 0.15, 0.0, 1.0);

    if(rr.turb > 0.1){
        col += vec3(speed * rr.turb * 0.12);
    }

    // Pre-ignition charring: flammable materials darken toward burnTo material.
    if(rr.flamm > 0.0){
        float th = rr.TH;
        float charMix = smoothstep(max(0.0, th - 40.0), th, temp);
        Rule burnRule = getRule(rr.burnTo, ruleStride);
        col = mix(col, burnRule.color, charMix * 0.65);
    }

    // Temperature-driven blackbody glow for all materials.
    float tempN = clamp((temp - ambientTemp) / 2000.0, 0.0, 1.0);
    float tHot = smoothstep(0.0, 1.0, tempN);
    float glowStrength = tHot * (0.3 + rr.emit * 0.7);

    if(typ == T_FIRE || typ == T_LAVA || typ == T_SPARK || typ == T_EMBER || typ == T_BLAST){
        glowStrength = max(glowStrength, tHot * (0.65 + rr.emit * 0.35));
    }

    vec3 bb = blackbody(tempN);
    col = mix(col, bb, glowStrength);
    col += bb * (glowStrength * 0.5);

    // Electric cooldown tint (blue on conductors with active current)
    if(rr.cond > 0.5 && flg > 5u)
        col = mix(col, vec3(0.3, 0.6, 1.0), 0.35);

    // Pump cyan pulse
    if(typ == T_PUMP)
        col = mix(col, vec3(0.0, 1.0, 1.0), 0.3 + 0.2 * sin(float(frame) * 0.25));

    // ═══════════════════════════════════════════════════════════════════════════
    // EXPLOSION VISUAL EFFECTS
    // ═══════════════════════════════════════════════════════════════════════════
    
    // Screen flash
    if(explosionFlash > 0.01) {
        float flash = explosionFlash * 0.8;
        col = mix(col, vec3(1.0, 1.0, 1.0), flash);
    }
    
    // Shockwave ring
    if(explosionAge > 0.0 && explosionAge < explosionMaxAge) {
        vec2 pixelPos = vec2(gl_GlobalInvocationID.x, gl_GlobalInvocationID.y);
        float dist = length(pixelPos - explosionCenter);
        float ringRadius = explosionAge * 80.0; // Ring expands outward
        float ringWidth = 20.0;
        
        // Check if pixel is on the shockwave ring
        if(dist > ringRadius - ringWidth && dist < ringRadius + ringWidth) {
            float ringIntensity = 1.0 - abs(dist - ringRadius) / ringWidth;
            ringIntensity *= (1.0 - explosionAge / explosionMaxAge); // Fade out over time
            vec3 ringColor = vec3(1.0, 0.9, 0.7) * ringIntensity;
            col = mix(col, ringColor, ringIntensity);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PRESSURE OVERLAY: show acoustic pressure in gas cells as blue→red heatmap
    // ═══════════════════════════════════════════════════════════════════════════
    if(showPressure == 1 && rr.cat == 0){
        float pVal = imageLoad(presTex, p).r;
        // Normalise: ambient = 0.5, ±10 deviation maps to full color range
        float pNorm = clamp((pVal - ambientPressure) * 0.05 + 0.5, 0.0, 1.0);
        // Blue (low) → white (ambient) → red (high)
        vec3 pCol;
        if(pNorm < 0.5){
            pCol = mix(vec3(0.0, 0.0, 0.8), vec3(0.9, 0.9, 1.0), pNorm * 2.0);
        } else {
            pCol = mix(vec3(1.0, 0.9, 0.9), vec3(0.8, 0.0, 0.0), (pNorm - 0.5) * 2.0);
        }
        col = mix(col, pCol, 0.7);
    }

    col = clamp(col, 0.0, 1.0);
    imageStore(displayTexture, p, vec4(col, 1.0));
}
