// ═══════════════════════════════════════════════════════════════════════════════
// Uniform Buffer Objects for simulation configuration
// Reduces uniform updates from ~20 per pass to 1 UBO update
// ═══════════════════════════════════════════════════════════════════════════════

// Simulation configuration UBO (binding 3)
layout(std140, binding = 3) uniform SimConfig {
    uvec2 gridSize;
    uint frame;
    float dt;
    float ambientTemp;
    uint ruleStride;
    int enableThermal;
    int enableTurbulence;
    int enableWetDry;
    float gravity;
    float vorticityStrength;
} config;

// Explosion physics UBO (binding 4)
layout(std140, binding = 4) uniform ExplosionConfig {
    vec2 center;
    float radius;
    float force;
    int isActive;
    float age;
    float maxAge;
    int type;
    float soundSpeed;
    float dtAcoustic;
    float energyDecayRate;
    float reflectionDamping;
} explosion;

// Explosion visual effects UBO (binding 5)
layout(std140, binding = 5) uniform ExplosionVfxConfig {
    float flash;
    float pressurePulse;
    int isFirstSubstep;
} explosionVfx;

// Wind configuration UBO (binding 6)
layout(std140, binding = 6) uniform WindConfig {
    vec2 vector;
    int enabled;
} wind;
