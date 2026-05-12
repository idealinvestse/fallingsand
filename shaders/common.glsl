#version 430

// ═══════════════════════════════════════════════════════════════════════════════
// Common GLSL definitions for Falling Sand simulation
// This file is preprocessed into shaders at load time
// ═══════════════════════════════════════════════════════════════════════════════

// ── Auto-Generated Bindings ───────────────────────────────────────────────────
// Note: Binding declarations are now inline in each shader to avoid conflicts
// Shaders include this file for helper functions only

// ── Rules Buffer (needed by getRule helper) ───────────────────────────────────
layout(std430, binding = 2) readonly buffer Rules { float rules[]; };

// ── Sparse Region Optimization ──────────────────────────────────────────────────
uniform uvec4 sparseRegion;  // (x, y, width, height) of active region
uniform bool sparseEnabled;

bool inSparseRegion(ivec2 p, uvec4 region) {
    if (!sparseEnabled) return true;
    return p.x >= int(region.x) && p.x < int(region.x + region.z) &&
           p.y >= int(region.y) && p.y < int(region.y + region.w);
}

// ── Material IDs ─────────────────────────────────────────────────────────────
const uint T_AIR   = 0u;  const uint T_SAND  = 1u;  const uint T_WATER = 2u;
const uint T_STONE = 3u;  const uint T_FIRE  = 4u;  const uint T_SMOKE = 5u;
const uint T_OIL   = 6u;  const uint T_ACID  = 7u;  const uint T_PLANT = 8u;
const uint T_LAVA  = 9u;  const uint T_GAS   = 10u; const uint T_WOOD  = 11u;
const uint T_GLASS = 12u; const uint T_ICE   = 13u; const uint T_STEAM = 14u;
const uint T_SNOW  = 15u; const uint T_DIRT  = 16u; const uint T_MUD   = 17u;
const uint T_BLOOD = 18u; const uint T_GPOW  = 19u; const uint T_C4    = 20u;
const uint T_CONCRETE = 21u; const uint T_METAL = 22u; const uint T_RUST = 23u;
const uint T_SPARK = 24u; const uint T_ASH   = 25u;
const uint T_SALT  = 26u; const uint T_SUGAR = 27u; const uint T_VIRUS = 28u; const uint T_SLIME = 29u;
const uint T_PUMP  = 30u; const uint T_GEN   = 31u;
const uint T_OXYGEN   = 32u;
const uint T_EMBER    = 33u;
const uint T_SHRAPNEL = 34u;
const uint T_BLAST    = 35u;
const uint T_COAL     = 36u;
const uint T_NAPALM   = 37u;
const uint T_FUSE     = 38u;
const uint T_DYNAMITE = 39u;
const uint T_THERMITE = 40u;
const uint T_MERCURY  = 41u;
const uint T_HONEY    = 42u;
const uint T_BLEACH   = 43u;
const uint T_CEMENT   = 44u;
const uint T_QUICKSAND = 45u;
const uint T_BRINE    = 46u;
const uint T_SAP      = 47u;
const uint T_MAGMA    = 48u;
const uint T_MAGNET   = 49u;
const uint T_MAGNET_SOUTH = 50u;
const uint T_PLASMA   = 51u;
const uint T_LIGHTNING_PLASMA = 52u;
const uint T_GLASS_NEW = 53u;
const uint T_OBSIDIAN = 54u;
const uint T_THERMITE_ENHANCED = 55u;
const uint T_ACID_GLASS = 56u;

// ── Cell packing utilities ───────────────────────────────────────────────────
uint getType (uint c){ return c & 0xFFu; }
uint getLife (uint c){ return (c >> 8u) & 0xFFu; }
uint getFlags(uint c){ return (c >> 16u) & 0xFFu; }

uint packCell(uint typ, uint life, uint flg){
    return (typ & 0xFFu) | ((life & 0xFFu) << 8u) | ((flg & 0xFFu) << 16u);
}

// ── Rule struct and loader ───────────────────────────────────────────────────
struct Rule {
    vec3 color;
    float density;
    int cat;        // 0=Gas, 1=Powder, 2=Liquid, 3=Solid
    float flamm;
    float k;        // Thermal conductivity
    uint phiH; uint TH;  // Phase transition high
    uint phiL; uint TL;  // Phase transition low
    float cond;     // Electrical conductivity
    float emit;     // Emissivity
    float cool;     // Cooling rate
    uint burnTo;    // Material when burned
    float visc;     // Viscosity (0=water, 1=lava)
    float turb;     // Turbulence coefficient
    float wd;       // Wet/dry flag
    // New fields
    float cp;       // Heat capacity
    uint mp;        // Melting point
    uint bp;        // Boiling point
    float st;       // Surface tension
    float sol;      // Solubility
    float coh;      // Cohesion (powder pile angle)
    float rest;     // Restitution (bounce from solids)
    int sf;         // State family (0=Powder, 1=Liquid, 2=Gas, 3=Solid, 4=Energetic, 5=Bio)
    // Reaction slots (3 reactions, 5 fields each)
    uint rxn1_p;    // Reaction 1 partner type
    uint rxn1_ps;   // Reaction 1 product self
    uint rxn1_pn;   // Reaction 1 product neighbor
    float rxn1_prob;// Reaction 1 probability
    uint rxn1_tt;   // Reaction 1 temp threshold
    uint rxn2_p;
    uint rxn2_ps;
    uint rxn2_pn;
    float rxn2_prob;
    uint rxn2_tt;
    uint rxn3_p;
    uint rxn3_ps;
    uint rxn3_pn;
    float rxn3_prob;
    uint rxn3_tt;
    // Explosive properties (6 floats)
    float expPow;   // Explosion power
    uint detTemp;   // Detonation temperature
    uint blastRad;  // Blast radius
    uint blastDur;  // Blast duration
    uint fragType;  // Fragment type
    float swSpeed;  // Shockwave speed
    // Oxygen / combustion properties
    float o2Req;    // Oxygen requirement to sustain combustion
    float o2Yield;  // Oxygen consumed per combustion tick
    // Magnetic properties (4 floats)
    float magPol;   // Magnetic polarity (-1 to 1)
    float magPerm;  // Magnetic permeability
    float magCoerc; // Magnetic coercivity
    float magCurie; // Curie temperature
    // Plasma properties (4 floats)
    float plasIon;  // Ionization energy
    float plasDens; // Plasma density
    float plasConf; // Confinement field
    float plasRecomb; // Recombination rate
    // Glass properties (4 floats)
    float glassTrans;   // Transparency
    float glassRefract; // Refractive index
    float glassShatter; // Shatter threshold
    float glassThermal; // Thermal shock resistance
};

// Note: ruleStride is now a uniform, not a constant
Rule getRule(uint tp, uint stride){
    uint o = tp * stride;
    Rule r;
    r.color   = vec3(rules[o+0u], rules[o+1u], rules[o+2u]);
    r.density = rules[o+3u];
    r.cat     = int(rules[o+4u]);
    r.flamm   = rules[o+5u];
    r.k       = rules[o+6u];
    r.phiH    = uint(rules[o+7u]);
    r.TH      = uint(rules[o+8u]);
    r.phiL    = uint(rules[o+9u]);
    r.TL      = uint(rules[o+10u]);
    r.cond    = rules[o+11u];
    r.emit    = rules[o+12u];
    r.cool    = rules[o+13u];
    r.burnTo  = uint(rules[o+14u]);
    r.visc    = rules[o+15u];
    r.turb    = rules[o+16u];
    r.wd      = rules[o+17u];
    // New fields
    r.cp      = rules[o+18u];
    r.mp      = uint(rules[o+19u]);
    r.bp      = uint(rules[o+20u]);
    r.st      = rules[o+21u];
    r.sol     = rules[o+22u];
    r.coh     = rules[o+23u];
    r.rest    = rules[o+24u];
    r.sf      = int(rules[o+25u]);
    // Reaction slots
    r.rxn1_p  = uint(rules[o+26u]);
    r.rxn1_ps = uint(rules[o+27u]);
    r.rxn1_pn = uint(rules[o+28u]);
    r.rxn1_prob = rules[o+29u];
    r.rxn1_tt = uint(rules[o+30u]);
    r.rxn2_p  = uint(rules[o+31u]);
    r.rxn2_ps = uint(rules[o+32u]);
    r.rxn2_pn = uint(rules[o+33u]);
    r.rxn2_prob = rules[o+34u];
    r.rxn2_tt = uint(rules[o+35u]);
    r.rxn3_p  = uint(rules[o+36u]);
    r.rxn3_ps = uint(rules[o+37u]);
    r.rxn3_pn = uint(rules[o+38u]);
    r.rxn3_prob = rules[o+39u];
    r.rxn3_tt = uint(rules[o+40u]);
    // Explosive properties (offset 41)
    r.expPow   = rules[o+41u];
    r.detTemp  = uint(rules[o+42u]);
    r.blastRad = uint(rules[o+43u]);
    r.blastDur = uint(rules[o+44u]);
    r.fragType = uint(rules[o+45u]);
    r.swSpeed  = rules[o+46u];
    // Oxygen / combustion properties (offset 47)
    r.o2Req    = rules[o+47u];
    r.o2Yield  = rules[o+48u];
    // Magnetic properties (offset 49-52)
    r.magPol   = rules[o+49u];
    r.magPerm  = rules[o+50u];
    r.magCoerc = rules[o+51u];
    r.magCurie = rules[o+52u];
    // Plasma properties (offset 53-56)
    r.plasIon  = rules[o+53u];
    r.plasDens = rules[o+54u];
    r.plasConf = rules[o+55u];
    r.plasRecomb = rules[o+56u];
    // Glass properties (offset 57-60)
    r.glassTrans   = rules[o+57u];
    r.glassRefract = rules[o+58u];
    r.glassShatter = rules[o+59u];
    r.glassThermal = rules[o+60u];
    return r;
}

// ── Hash functions ───────────────────────────────────────────────────────────
uint hash(uint s){
    s ^= s >> 16u;
    s *= 0x85ebca6bu;
    s ^= s >> 13u;
    s *= 0xc2b2ae35u;
    s ^= s >> 16u;
    return s;
}

float hashF(uint s){
    return float(hash(s)) / 4294967295.0;
}

// ── Boundary checking ────────────────────────────────────────────────────────
bool inBounds(ivec2 p, uvec2 gridSize){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

// ── Material category helpers ─────────────────────────────────────────────────
bool isAcidResist(uint tp){
    return tp == T_AIR || tp == T_ACID || tp == T_STEAM || tp == T_SMOKE;
}

bool isCombustible(uint tp){
    return tp == T_OIL || tp == T_WOOD || tp == T_PLANT || tp == T_GPOW ||
           tp == T_C4 || tp == T_SLIME || tp == T_GAS || tp == T_SUGAR ||
           tp == T_COAL || tp == T_NAPALM || tp == T_THERMITE || tp == T_EMBER;
}

// ── Texture sampling helpers ───────────────────────────────────────────────────
// These helpers assume the textures are bound at specific image units.
// Mass textures (binding 9/10): fractional fill / wet mass per cell
// Temp textures (binding 11/12): continuous float temperature in simulation units
// Wind texture (binding): environmental wind field

float sampleMass(ivec2 p, uvec2 gridSize, image2D massTex){
    if(!inBounds(p, gridSize)) return 0.0;
    return imageLoad(massTex, p).r;
}

float sampleTemp(ivec2 p, uvec2 gridSize, image2D tempTex){
    if(!inBounds(p, gridSize)) return 96.0; // Return ambient fallback
    return imageLoad(tempTex, p).r;
}

vec2 sampleWind(ivec2 p, uvec2 gridSize, image2D windTex){
    if(!inBounds(p, gridSize)) return vec2(0.0);
    return imageLoad(windTex, p).rg;
}

// ── Cell writing helper ───────────────────────────────────────────────────────
// Writes a cell to both the cell buffer and temperature texture
// Note: This helper needs access to cellsOut buffer and tempOut uniform, which vary by shader
// Shaders must declare their own cellsOut buffer and tempOut uniform, then implement:
// cellsOut[idx] = packCell(typ, life, flg);
// imageStore(tempOut, p, vec4(temp, 0.0, 0.0, 0.0));

// ── Blast/shrapnel flag packing ───────────────────────────────────────────────
// Flags layout for T_BLAST and T_SHRAPNEL cells:
//   bits [0..2] = direction octant (0=E,1=NE,2=N,3=NW,4=W,5=SW,6=S,7=SE)
//   bits [3..7] = power 0..31 (scaled from expPow)
uint packBlastFlags(uint dirOct, uint pow5){
    return (dirOct & 0x7u) | ((pow5 & 0x1Fu) << 3u);
}
uint unpackBlastDir(uint f){ return f & 0x7u; }
uint unpackBlastPow(uint f){ return (f >> 3u) & 0x1Fu; }

// ── Octant from integer offset (target - source). Returns 0..7. ────────────────
uint octantFromOffset(ivec2 d){
    if(d.x > 0 && d.y == 0) return 0u; // E
    if(d.x > 0 && d.y > 0)  return 1u; // NE
    if(d.x == 0 && d.y > 0)  return 2u; // N
    if(d.x < 0 && d.y > 0)  return 3u; // NW
    if(d.x < 0 && d.y == 0) return 4u; // W
    if(d.x < 0 && d.y < 0)  return 5u; // SW
    if(d.x == 0 && d.y < 0) return 6u; // S
    return 7u;                          // SE
}

// ── Material strength for blast destruction (higher = harder to destroy) ───────
uint getMaterialStrength(uint tp){
    if(tp == T_GLASS) return 1u;
    if(tp == T_WOOD) return 2u;
    if(tp == T_ASH) return 1u;
    if(tp == T_SNOW) return 1u;
    if(tp == T_ICE) return 2u;
    if(tp == T_STONE) return 3u;
    if(tp == T_METAL) return 4u;
    if(tp == T_CONCRETE) return 5u;
    if(tp == T_SAND) return 2u;
    if(tp == T_DIRT) return 2u;
    return 2u; // Default medium strength
}

// ── Check if material is ground/terrain (can form craters) ─────────────────────
bool isGroundMaterial(uint tp){
    return tp == T_STONE || tp == T_SAND || tp == T_DIRT || tp == T_CONCRETE || tp == T_SNOW;
}

// ── Compute crater depth based on blast power and material strength ────────────
float computeCraterDepth(uint blastPower, uint matStrength, float distRatio){
    float depthFactor = 1.0 - distRatio;
    float powerFactor = float(blastPower) / 31.0;
    float resistanceFactor = 1.0 / (1.0 + float(matStrength) * 0.2);
    return depthFactor * depthFactor * powerFactor * resistanceFactor;
}

// ── Fragment type for each material when blasted ───────────────────────────────
uint getFragmentType(uint tp){
    if(tp == T_STONE || tp == T_CONCRETE) return T_SAND;
    if(tp == T_METAL) return T_SHRAPNEL;
    if(tp == T_GLASS) return T_SHRAPNEL;
    if(tp == T_WOOD) return T_EMBER;
    if(tp == T_PLANT) return T_ASH;
    return T_SHRAPNEL;
}
