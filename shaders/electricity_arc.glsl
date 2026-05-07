// ═══════════════════════════════════════════════════════════════════════════════
// Electricity arc / breakdown shader (Phase 1)
//
// Checks every cell for charge exceeding the material breakdown threshold.
// When breakdown occurs:
//   - Charge is discharged to zero
//   - Temperature spikes (ohmic heating + arc flash)
//   - A small pressure pulse is registered via a temporary divergence boost
//
// Reads:  chargeIn (r32f), cells (SSBO), rules (SSBO), tempIn (r32f)
// Writes: chargeOut (r32f), tempOut (r32f), divergence (r32f)
// ═══════════════════════════════════════════════════════════════════════════════

layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
// RuleBuffer defined in common.glsl (binding = 2)

layout(r32f, binding = 9)  uniform readonly  image2D chargeIn;
layout(r32f, binding = 10) uniform writeonly image2D chargeOut;
layout(r32f, binding = 11) uniform readonly  image2D tempIn;
layout(r32f, binding = 12) uniform writeonly image2D tempOut;
layout(r32f, binding = 4)  uniform writeonly image2D divOut;   // reuse velocity_out binding for divergence pulse
layout(r32f, binding = 15) uniform readonly  image2D moistureIn;  // v6.1: Moisture for wet arc effects

uniform uvec2 gridSize;
uniform uint  ruleStride;
uniform float breakdownThreshold;   // charge level that triggers arc
uniform float arcTempDelta;         // temperature added on breakdown
uniform float arcPressurePulse;     // divergence spike magnitude
uniform float dt;

// v6.1 Deep System Interactions uniforms
uniform float wet_arc_temp_multiplier;     // Default: 0.5 - arc heat reduction when wet

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p, gridSize)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ  = getType(cell);
    Rule r = getRule(typ, ruleStride);

    float q = imageLoad(chargeIn, p).r;
    float temp = imageLoad(tempIn, p).r;
    float moisture = imageLoad(moistureIn, p).r;  // v6.1: Read moisture

    // Arc breakdown: charge exceeds threshold AND material is conductive
    // (arcs only form in / between conductors; insulators just store charge)
    if(abs(q) > breakdownThreshold && r.cond > 0.3){
        // v6.1: Wet arc effects: less heat, more pressure wave
        float wetness = clamp(moisture / 500.0, 0.0, 1.0);  // Normalize 0-1
        float tempMultiplier = mix(1.0, wet_arc_temp_multiplier, wetness);
        float pressureMultiplier = mix(1.0, 2.0, wetness);  // More pressure when wet

        // v6.1: Discharge with moisture-dependent rate
        float dischargeRate = mix(1.0, 0.7, wetness);  // Slower discharge when wet
        q *= (1.0 - dischargeRate);
        if(abs(q) < 1.0) q = 0.0;

        // Temperature spike (reduced when wet)
        temp += arcTempDelta * tempMultiplier;

        // Divergence pulse (enhanced when wet - steam generation)
        float pulse = arcPressurePulse * pressureMultiplier;
        imageStore(divOut, p, vec4(pulse, 0.0, 0.0, 0.0));
    } else {
        // No arc: preserve divergence (write zero so we don't clobber)
        imageStore(divOut, p, vec4(0.0, 0.0, 0.0, 0.0));
    }

    imageStore(chargeOut, p, vec4(q, 0.0, 0.0, 0.0));
    imageStore(tempOut, p, vec4(temp, 0.0, 0.0, 0.0));
}
