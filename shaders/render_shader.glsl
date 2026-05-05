layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer is now defined in common.glsl
layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(r32f,  binding = 5) uniform readonly image2D presTex;   // pressure for overlay
layout(rgba8, binding = 7) uniform writeonly image2D displayTexture;
layout(r32f, binding = 11) uniform readonly image2D tempTex;
layout(r32f, binding = 9)  uniform readonly image2D chargeTex;
layout(r32f, binding = 13) uniform readonly image2D nutrientTex;
layout(r32f, binding = 15) uniform readonly image2D moistureTex;
layout(r32f, binding = 17) uniform readonly image2D humidityTex;
layout(rgba8, binding = 19) uniform readonly image2D bloomTex;

uniform uvec2 gridSize;
uniform uint frame;
uniform uint ruleStride;
uniform int showPressure;     // 1 = pressure overlay on gas cells
uniform int debugView;        // 0=none, 1=pressure, 2=charge, 3=nutrient, 4=moisture, 5=humidity
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
    // AMBIENT OCCLUSION: darken cells below solid surfaces
    // ═══════════════════════════════════════════════════════════════════════════
    ivec2 above = p + ivec2(0, -1);
    if(inBounds(above, gridSize)){
        uint aboveCell = cells[uint(above.y) * gridSize.x + uint(above.x)];
        uint aboveTyp = getType(aboveCell);
        Rule aboveRule = getRule(aboveTyp, ruleStride);
        // If cell above is solid and current is not, apply AO shadow
        if(aboveRule.cat == 3 && rr.cat != 3){
            col *= 0.75;
        }
        // Stacked solids: darken based on how many solids above
        if(rr.cat == 3 && aboveRule.cat == 3){
            col *= 0.92;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // EMISSIVE LIGHT PROPAGATION: hot neighbors illuminate surroundings
    // ═══════════════════════════════════════════════════════════════════════════
    if(rr.cat != 3 || typ == T_LAVA){  // non-solids and lava receive light
        vec3 lightSum = vec3(0.0);
        float lightWeight = 0.0;
        ivec2 neighbors[8] = {
            ivec2(1,0), ivec2(-1,0), ivec2(0,1), ivec2(0,-1),
            ivec2(1,1), ivec2(-1,1), ivec2(1,-1), ivec2(-1,-1)
        };
        for(int i = 0; i < 8; i++){
            ivec2 np = p + neighbors[i];
            if(!inBounds(np, gridSize)) continue;
            float nt = imageLoad(tempTex, np).r;
            float nGlow = smoothstep(150.0, 2000.0, nt);
            if(nGlow > 0.01){
                uint nCell = cells[uint(np.y) * gridSize.x + uint(np.x)];
                Rule nRule = getRule(getType(nCell), ruleStride);
                float dist = length(vec2(neighbors[i]));
                float atten = nGlow * nRule.emit / (dist * dist + 0.5);
                lightSum += blackbody(clamp((nt - ambientTemp) / 2000.0, 0.0, 1.0)) * atten;
                lightWeight += atten;
            }
        }
        if(lightWeight > 0.0){
            col += lightSum / max(lightWeight, 0.01) * 0.4;
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // WATER DEPTH: deeper water is darker/more saturated blue
    // ═══════════════════════════════════════════════════════════════════════════
    if(typ == T_WATER){
        int depth = 0;
        ivec2 below = p;
        for(int d = 0; d < 8; d++){
            below += ivec2(0, 1);
            if(!inBounds(below, gridSize)) break;
            if(getType(cells[uint(below.y) * gridSize.x + uint(below.x)]) == T_WATER) depth++;
            else break;
        }
        float depthFactor = clamp(float(depth) / 6.0, 0.0, 1.0);
        col = mix(col, col * vec3(0.3, 0.5, 0.9), depthFactor * 0.6);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // DEBUG OVERLAY: visualize scalar fields as heatmaps
    // ═══════════════════════════════════════════════════════════════════════════
    int dv = debugView;
    if(showPressure == 1 && dv == 0) dv = 1;  // backward compat

    if(dv > 0){
        float val = 0.0;
        float maxVal = 1.0;
        vec3 lowCol  = vec3(0.0, 0.0, 0.3);
        vec3 highCol = vec3(1.0, 0.0, 0.0);

        if(dv == 1){
            // Pressure: blue→white→red
            val = imageLoad(presTex, p).r;
            float pNorm = clamp((val - ambientPressure) * 0.05 + 0.5, 0.0, 1.0);
            vec3 pCol;
            if(pNorm < 0.5){
                pCol = mix(vec3(0.0, 0.0, 0.8), vec3(0.9, 0.9, 1.0), pNorm * 2.0);
            } else {
                pCol = mix(vec3(1.0, 0.9, 0.9), vec3(0.8, 0.0, 0.0), (pNorm - 0.5) * 2.0);
            }
            col = mix(col, pCol, 0.7);
        } else if(dv == 2){
            // Charge: black→yellow→white
            val = imageLoad(chargeTex, p).r;
            float cn = clamp(abs(val) / 500.0, 0.0, 1.0);
            vec3 cCol = mix(vec3(0.0, 0.0, 0.0), vec3(1.0, 1.0, 0.0), smoothstep(0.0, 0.5, cn));
            cCol = mix(cCol, vec3(1.0, 1.0, 1.0), smoothstep(0.5, 1.0, cn));
            col = mix(col, cCol, 0.8);
        } else if(dv == 3){
            // Nutrient: brown→green
            val = imageLoad(nutrientTex, p).r;
            float nn = clamp(val / 200.0, 0.0, 1.0);
            col = mix(vec3(0.1, 0.05, 0.0), vec3(0.0, 0.9, 0.1), nn);
        } else if(dv == 4){
            // Moisture: dry→wet (tan→blue)
            val = imageLoad(moistureTex, p).r;
            float mn = clamp(val / 200.0, 0.0, 1.0);
            col = mix(vec3(0.4, 0.3, 0.1), vec3(0.0, 0.4, 1.0), mn);
        } else if(dv == 5){
            // Humidity: dry→humid (white→cyan)
            val = imageLoad(humidityTex, p).r;
            float hn = clamp(val / 200.0, 0.0, 1.0);
            col = mix(vec3(0.15, 0.15, 0.2), vec3(0.0, 0.9, 1.0), hn);
        }
    }

    col = clamp(col, 0.0, 1.0);

    // ── Bloom composite: sample half-res bloom texture with bilinear ────────
    if (debugView == 0) {
        vec2 bloomUV = (vec2(p) + 0.5) / vec2(gridSize);
        ivec2 bloomSize = ivec2(gridSize.x / 2u, gridSize.y / 2u);
        vec2 bloomCoord = bloomUV * vec2(bloomSize) - 0.5;
        ivec2 bloomBase = ivec2(floor(bloomCoord));
        vec2 bloomT = bloomCoord - vec2(bloomBase);
        bloomBase = clamp(bloomBase, ivec2(0), bloomSize - ivec2(1));
        ivec2 bloomBase1 = clamp(bloomBase + ivec2(1, 0), ivec2(0), bloomSize - ivec2(1));
        ivec2 bloomBase2 = clamp(bloomBase + ivec2(0, 1), ivec2(0), bloomSize - ivec2(1));
        ivec2 bloomBase3 = clamp(bloomBase + ivec2(1, 1), ivec2(0), bloomSize - ivec2(1));
        vec3 b00 = imageLoad(bloomTex, bloomBase).rgb;
        vec3 b10 = imageLoad(bloomTex, bloomBase1).rgb;
        vec3 b01 = imageLoad(bloomTex, bloomBase2).rgb;
        vec3 b11 = imageLoad(bloomTex, bloomBase3).rgb;
        vec3 b0 = mix(b00, b10, bloomT.x);
        vec3 b1 = mix(b01, b11, bloomT.x);
        vec3 bloomSample = mix(b0, b1, bloomT.y);
        col += bloomSample * 0.6;
        col = clamp(col, 0.0, 1.0);
    }

    imageStore(displayTexture, p, vec4(col, 1.0));
}
