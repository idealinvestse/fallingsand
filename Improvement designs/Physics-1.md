<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# How to improve the physics

Det största lyftet blir att gå från dagens rent lokala 2x2-Margolus-swappar till en modell som även lagrar hastighet och tryck per cell. Just nu styrs rörelsen främst av densitet, viskositet, turbulens, wet-dry-blockering och slumpmässiga swappar, så simulationen får bra “falling sand”-känsla men begränsad tröghet, kollision och vätskebeteende.[^1_1][^1_2]

## Börja här

Först bör du koppla ihop dina fysikflaggor med shadern på riktigt, eftersom launchern och `main-4.py` exponerar `--no-turbulence`, `--no-wet-dry` och `--no-thermal`, men compute-shadern får bara `gridSize`, `frame`, `phase` och `ambientTemp` som uniforms.[^1_3][^1_2][^1_1]
Det betyder att dina checkboxar för fysikfunktioner sannolikt inte påverkar själva simuleringen ännu, så det är svårt att utvärdera förbättringar innan den styrningen fungerar.[^1_2][^1_1][^1_3]

## Rörelsemodell

I dag packas varje cell som `type/temp/life/flags` i ett enda 32-bitarsvärde, så det finns inget riktigt tillstånd för signerad hastighet, impuls eller tryck.[^1_1][^1_2]
Lägg därför till separata buffertar för `vx`, `vy` och gärna `pressure`; då kan vatten behålla fart mellan frames, sand få bättre rasvinkel, och gas få mer trovärdig uppåtströmning i stället för att allt avgörs av om en lokal swap råkar vinna.[^1_1]

## Vätskor och värme

Din nuvarande “pressure”-modell är mycket enkel: shadern sätter bara `pressureL` och `pressureR` när båda cellerna i en kolumn är vätskor och använder det för extra horisontella swappar.[^1_1]
Byt det mot en separat tryck-/masspass där vätskor först beräknar lokal fyllnadsgrad eller kolonntryck och sedan relaxerar mot grannar; det ger bättre kommunicerande kärl, mindre “jitter” och mer naturlig spridning i djupa vattenmassor.[^1_1]

Värme sprids också bara via medeltemperaturen i det aktuella 2x2-blocket, skalerat med materialets `k` och `cool`, vilket lätt ger blockiga värmefronter.[^1_1]
En separat 4- eller 8-grannars värmepass brukar ge mycket stabilare fasövergångar för vatten, is, ånga, eld och lava än att blanda termik direkt i samma lokala Margolus-steg.[^1_2][^1_1]

## Materialbeteenden

Rörelsesteget behandlar mycket via kategori och effektiv densitet, där fasta ämnen mest blockeras av `cat==3`, medan vätskor och gaser får variation genom `visc`, `turb` och några specialregler.[^1_2][^1_1]
Du får mer trovärdig fysik om du skiljer tydligare på pulver, vätskor och gaser: pulver bör få rasvinkel och kompaktion, vätskor bör följa tryck + hastighet + låg kompressibilitet, och gaser bör få starkare buoyancy och diffusion oberoende av vätskereglerna.[^1_2][^1_1]

## Stabilitet

Ett praktiskt fel att rätta är dispatchen: `main-4.py` kör `group_x=WIDTH // 16` och `group_y=HEIGHT // 16`, medan shadern använder `local_size_x=8`, `local_size_y=8` och varje invocation behandlar ett 2x2-block, så kanter blir osimulerade när storleken inte är jämnt delbar med 16.[^1_2][^1_1]
Använd ceil-dispatch eller paddad grid först, annars kan fysiken se “instabil” ut trots att problemet egentligen är att vissa celler aldrig uppdateras.[^1_2][^1_1]

Vill du att jag skissar en konkret nästa version av shadern med `vx/vy/pressure` och exakt vilka delar som bör ligga i separata pass?
<span style="display:none">[^1_4]</span>

<div align="center">⁂</div>

[^1_1]: margolus_sim.glsl

[^1_2]: main-4.py

[^1_3]: launcher-2.py

[^1_4]: launch-3.bat


---

# Vill du att jag skissar en konkret nästa version av shadern med vx/vy/pressure och exakt vilka delar som bör ligga i separata pass? Ja

Ja — jag skulle bygga nästa version som en **hybrid**: behåll din packade materialcell för typ/temperatur/life/flags, men flytta rörelse till separata fält för `vx`, `vy` och `pressure`.[^2_1][^2_2]
Det passar din kod bra eftersom nuvarande shader redan blandar termik, kemi, el, pump, rörelse och rendering i ett enda compute-pass, och det är precis det som gör fysiken svår att förbättra stegvis.[^2_1]

## Datamodell

I dag packas varje cell som `type/temp/life/flags` i ett `uint`, vilket är bra för materialtillstånd men dåligt för signerad hastighet och tryck.[^2_2][^2_1]
Min rekommendation är att låta `cells` fortsätta vara som nu, och lägga till separata GPU-buffertar eller texturer för `velocity`, `pressure`, `divergence` och gärna en enkel `solidMask`, så att rörelse kan lösas utan att du behöver pressa in mer fysik i bitfältet.[^2_2][^2_1]

Ett bra minimum är detta:

```glsl
layout(std430, binding = 0) buffer CellRead  { uint cellsIn[];  };
layout(std430, binding = 1) buffer CellWrite { uint cellsOut[]; };

layout(rg16f, binding = 2) uniform image2D velRead;
layout(rg16f, binding = 3) uniform image2D velWrite;

layout(r16f,  binding = 4) uniform image2D pressureRead;
layout(r16f,  binding = 5) uniform image2D pressureWrite;

layout(r16f,  binding = 6) uniform image2D divergenceTex;
layout(r8ui,  binding = 7) uniform uimage2D solidMask;
```


## Passordning

Nuvarande shader kör steg 1 till 6 i samma pass: termodynamik, kemi, tillståndsmaskin, el, pump, Margolus-rörelse och sedan rendering till `displayTexture`.[^2_1]
Jag skulle dela upp det i separata pass så här: `state/reaction`, `force`, `divergence`, `pressure solve`, `projection`, `advection/intent`, `resolve`, och sist `render`.[^2_1]

Det viktiga är att kemi och materiallogik stannar i `state/reaction`, medan själva vätskefysiken bara läser materialkategorier och producerar rörelse. Dina specialsystem som syra, eld, virus, generator och pump finns redan som lokala regler i shadern, så de passar naturligt i det första passet i stället för i flödeslösaren.[^2_1]

## Rörelselogik

Din nuvarande rörelse bygger på effektiv densitet, viskositet, turbulens, wet-dry-blockering och lokala swappar i 2x2-block.[^2_1]
Det ger bra sandlådekänsla, men nästa steg är att låta varje cell först få krafter och sedan försöka flytta sig enligt sin hastighet, till exempel med $vy += g$ för pulver och vätskor, negativ buoyancy för gas, och dämpning från viskositet eller drag.[^2_2][^2_1]

För vätskor skulle jag göra ett enkelt inkompressibilitetssteg: beräkna divergens, kör 8 till 20 Jacobi-iterationer för tryck, och subtrahera sedan tryckgradienten från hastigheten innan cellerna får välja målcell. Det gör stor skillnad för kommunicerande kärl, stabilare vattenytor och mindre jitter än dagens pseudo-tryck med `pressureL` och `pressureR`.[^2_1]

En bra hybrid är:

- Pulver: behåll Margolus-liknande lokala fallregler.
- Vätskor: använd `vx/vy + pressure`.
- Gaser: använd `vx/vy + buoyancy + diffusion`.
- Solider: skriv bara till `solidMask` och blockera flöde.


## Konkreta pass

Eftersom `main-4.py` i dag bara dispatchar en shader per frame och skickar in `gridSize`, `frame`, `phase` och `ambientTemp`, behöver frame-loopen byggas om till flera dispatchar per frame.[^2_2][^2_1]
Samtidigt bör du koppla dina CLI-flaggor till riktiga uniforms, eftersom launchern och parsern redan har `--no-turbulence`, `--no-wet-dry` och `--no-thermal`, men shadern använder dem inte som uniforms i nuvarande form.[^2_3][^2_2][^2_1]

Jag hade kört ungefär så här i Python:

```python
# 1. state / reactions
state_shader["ambientTemp"] = TEMP_AMBIENT
state_shader.run(group_x=gx, group_y=gy)

# 2. forces
force_shader["dt"] = dt
force_shader["gravity"] = 1.0
force_shader["enableTurbulence"] = int(not args.no_turbulence)
force_shader.run(group_x=gx, group_y=gy)

# 3. divergence
div_shader.run(group_x=gx, group_y=gy)

# 4. pressure iterations
for _ in range(12):
    pressure_shader.run(group_x=gx, group_y=gy)
    pressure_read, pressure_write = pressure_write, pressure_read

# 5. projection
project_shader.run(group_x=gx, group_y=gy)

# 6. advection / movement intent
advect_shader.run(group_x=gx, group_y=gy)

# 7. conflict resolve
resolve_shader.run(group_x=gx, group_y=gy)
cells_read, cells_write = cells_write, cells_read
vel_read, vel_write = vel_write, vel_read

# 8. render
render_shader.run(group_x=gx, group_y=gy)
```


## Praktisk migration

Det säkraste sättet är inte att skriva om allt samtidigt, utan att först bryta ut nuvarande steg 1 till 4 till ett separat `state_shader`, eftersom de redan är logiskt avskilda i kommentarerna i GLSL-koden.[^2_1]
Sedan kan du låta sand, dirt, salt, snow, ash och gunpowder fortsätta gå via Margolus, medan vatten, olja, syra, blod, slime, lava, steam, smoke och gas migreras till `vx/vy/pressure`; det följer redan din materialuppdelning i kategorier och parametrar som `cat`, `density`, `visc`, `turb` och `wd`.[^2_2][^2_1]

Vill du att jag skriver en faktisk första version av `state_shader.glsl` och `force_shader.glsl` anpassad till just din nuvarande `main-4.py`-struktur?

<div align="center">⁂</div>

[^2_1]: margolus_sim.glsl

[^2_2]: main-4.py

[^2_3]: launcher-2.py


---

# Ja

Ja — här är en bra första split: ett `state_shader.glsl` som tar över material-, temperatur- och reaktionslogik, och ett `force_shader.glsl` som börjar bygga riktig rörelse med `vx/vy` utan att du behöver kasta bort din nuvarande `type/temp/life/flags`-packning.[^3_1][^3_2]
Det passar din nuvarande struktur eftersom materialdata redan finns i `PARTICLES` och skickas till GPU som `rules`, medan `main-4.py` redan har en enkel ping-pong-modell för cellbuffer som går att återanvända när du delar upp simuleringen i flera pass.[^3_2][^3_1]

## State shader

Din nuvarande shader gör termik, kemi, tillståndsmaskin, el, pump, rörelse och rendering i samma pass, så första steget bör vara att bryta ut just celltillståndet till ett rent per-cell-pass.[^3_2]
Koden nedan använder samma cellpackning och samma `rules`-layout som din nuvarande shader, men kör per pixel i stället för per 2x2 Margolus-block.[^3_1][^3_2]

```glsl
// state_shader.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer ReadBuffer  { uint cellsIn[];  };
layout(std430, binding = 1) writeonly buffer WriteBuffer { uint cellsOut[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer  { float rules[];    };

uniform uvec2 gridSize;
uniform uint frame;
uniform uint ambientTemp;
uniform int enableThermal;

const uint RULE_STRIDE = 20u;

const uint T_AIR   = 0u;
const uint T_WATER = 2u;
const uint T_STONE = 3u;
const uint T_FIRE  = 4u;
const uint T_SMOKE = 5u;
const uint T_OIL   = 6u;
const uint T_ACID  = 7u;
const uint T_LAVA  = 9u;
const uint T_GAS   = 10u;
const uint T_STEAM = 14u;
const uint T_DIRT  = 16u;
const uint T_MUD   = 17u;
const uint T_BLOOD = 18u;
const uint T_SPARK = 24u;
const uint T_SALT  = 26u;
const uint T_VIRUS = 28u;
const uint T_SLIME = 29u;
const uint T_PUMP  = 30u;
const uint T_GEN   = 31u;

uint getType (uint c){ return c & 0xFFu; }
uint getTemp (uint c){ return (c >> 8u) & 0xFFu; }
uint getLife (uint c){ return (c >> 16u) & 0xFFu; }
uint getFlags(uint c){ return (c >> 24u) & 0xFFu; }

uint packCell(uint t, uint tp, uint l, uint f){
    return (t & 0xFFu) | ((tp & 0xFFu) << 8u) | ((l & 0xFFu) << 16u) | ((f & 0xFFu) << 24u);
}

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

uint hash(uint s){
    s ^= s >> 16u;
    s *= 0x85ebca6bu;
    s ^= s >> 13u;
    s *= 0xc2b2ae35u;
    s ^= s >> 16u;
    return s;
}

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

uint loadCell(ivec2 p){
    if(!inBounds(p)) return packCell(T_STONE, ambientTemp, 0u, 0u);
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    return cellsIn[idx];
}

bool isAcidResist(uint tp){
    return tp == T_AIR || tp == 12u || tp == T_ACID || tp == T_STEAM || tp == T_SMOKE;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];

    uint typ  = getType(cell);
    uint temp = getTemp(cell);
    uint life = getLife(cell);
    uint flg  = getFlags(cell);

    Rule r = getRule(typ);

    uint n = loadCell(p + ivec2(0, 1));
    uint s = loadCell(p + ivec2(0,-1));
    uint e = loadCell(p + ivec2(1, 0));
    uint w = loadCell(p + ivec2(-1,0));

    uint tn = getType(n), ts = getType(s), te = getType(e), tw = getType(w);

    if(enableThermal != 0){
        float sumT = float(temp);
        float count = 1.0;
        sumT += float(getTemp(n)); count += 1.0;
        sumT += float(getTemp(s)); count += 1.0;
        sumT += float(getTemp(e)); count += 1.0;
        sumT += float(getTemp(w)); count += 1.0;

        float avgT = sumT / count;
        float mixed = mix(float(temp), avgT, clamp(r.k * 0.30, 0.0, 1.0));
        mixed -= r.cool * 0.10 * (mixed - float(ambientTemp));
        temp = uint(clamp(int(round(mixed)), 0, 255));
    }

    if(typ == T_FIRE || typ == T_SMOKE || typ == T_STEAM || typ == T_SPARK){
        if(life > 0u) life--;
    }

    bool nearLava  = (tn == T_LAVA || ts == T_LAVA || te == T_LAVA || tw == T_LAVA);
    bool nearWater = (tn == T_WATER || ts == T_WATER || te == T_WATER || tw == T_WATER);
    bool nearDirt  = (tn == T_DIRT || ts == T_DIRT || te == T_DIRT || tw == T_DIRT);
    bool nearAcid  = (tn == T_ACID || ts == T_ACID || te == T_ACID || tw == T_ACID);
    bool nearVirus = (tn == T_VIRUS || ts == T_VIRUS || te == T_VIRUS || tw == T_VIRUS);
    bool nearPump  = (tn == T_PUMP || ts == T_PUMP || te == T_PUMP || tw == T_PUMP);
    bool nearGen   = (tn == T_GEN || ts == T_GEN || te == T_GEN || tw == T_GEN);

    if(typ == T_WATER && nearLava){
        cellsOut[idx] = packCell(T_STEAM, 170u, 20u, 0u);
        return;
    }
    if(typ == T_LAVA && nearWater){
        cellsOut[idx] = packCell(T_STONE, max(temp, 180u), 0u, 0u);
        return;
    }
    if(typ == T_WATER && nearDirt){
        cellsOut[idx] = packCell(T_MUD, 96u, 0u, 0u);
        return;
    }
    if(typ == T_DIRT && nearWater){
        cellsOut[idx] = packCell(T_AIR, ambientTemp, 0u, 0u);
        return;
    }
    if(typ == T_SALT && nearWater){
        uint rnd = hash(idx ^ frame);
        if((rnd & 15u) == 0u){
            cellsOut[idx] = packCell(T_AIR, ambientTemp, 0u, 0u);
            return;
        }
    }
    if(typ != T_ACID && nearAcid && !isAcidResist(typ)){
        uint rnd = hash(idx ^ (frame * 17u));
        if((rnd & 1u) == 0u){
            cellsOut[idx] = packCell(T_AIR, ambientTemp, 0u, 0u);
            return;
        }
    }
    if(typ == T_BLOOD && nearVirus){
        uint rnd = hash(idx ^ (frame * 31u));
        if((rnd & 7u) == 0u){
            cellsOut[idx] = packCell(T_SLIME, 96u, 0u, 0u);
            return;
        }
    }

    bool nearHot = (tn == T_FIRE || ts == T_FIRE || te == T_FIRE || tw == T_FIRE ||
                    tn == T_LAVA || ts == T_LAVA || te == T_LAVA || tw == T_LAVA ||
                    tn == T_SPARK|| ts == T_SPARK|| te == T_SPARK|| tw == T_SPARK);

    if(nearHot){
        temp = min(255u, temp + 10u);
    }

    if(nearGen && r.cond > 0.5 && typ != T_SPARK){
        uint rnd = hash((idx << 1u) ^ frame);
        if((rnd & 7u) == 0u){
            cellsOut[idx] = packCell(T_SPARK, 240u, 8u, 20u);
            return;
        }
    }

    if(nearPump && r.cat == 2){
        flg = min(255u, flg + 8u);
    } else if(flg > 0u && typ != T_PUMP && typ != T_GEN){
        flg = flg > 2u ? flg - 2u : 0u;
    }

    if(typ == T_FIRE){
        temp = min(255u, temp + 4u);
        if(life == 0u){
            cellsOut[idx] = packCell(T_SMOKE, max(110u, temp / 2u), 20u, 0u);
            return;
        }
    } else if(typ == T_SPARK){
        if(life == 0u){
            cellsOut[idx] = packCell(T_FIRE, 220u, 6u, 0u);
            return;
        }
    } else if(typ == T_SMOKE || typ == T_STEAM){
        if(life == 0u && temp <= ambientTemp + 4u){
            cellsOut[idx] = packCell(typ == T_STEAM ? T_WATER : T_AIR, ambientTemp, 0u, 0u);
            return;
        }
    }

    if(r.phiH != typ && temp >= r.TH){
        uint nl = (r.phiH == T_FIRE) ? 20u + uint(r.flamm * 30.0) : ((r.phiH == T_STEAM) ? 24u : 0u);
        cellsOut[idx] = packCell(r.phiH, max(temp, r.TH), nl, 0u);
        return;
    }

    if(r.phiL != typ && temp <= r.TL){
        cellsOut[idx] = packCell(r.phiL, temp, 0u, 0u);
        return;
    }

    if(r.flamm > 0.0 && temp >= max(0u, r.TH - 8u)){
        uint rnd = hash(idx ^ (frame * 97u));
        if((rnd & 3u) != 0u){
            uint nl = 18u + uint(r.flamm * 48.0);
            cellsOut[idx] = packCell(T_FIRE, 220u, nl, 0u);
            return;
        }
    }

    cellsOut[idx] = packCell(typ, temp, life, flg);
}
```


## Force shader

Din nuvarande rörelse använder bara lokala densitetsjämförelser, `visc`, `turb`, wet-dry och slump, så nästa naturliga steg är att börja lagra hastighet separat.[^3_2]
Den här första versionen skriver bara `vx/vy`, läser materialkategori från samma `cells`-buffer som nu, och använder `flags` för pumpimpuls eftersom din nuvarande shader redan använder flaggar för pumpad vätska och el-cooldown.[^3_2]

```glsl
// force_shader.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer ReadBuffer { uint cellsIn[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer { float rules[]; };

layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(rg32f, binding = 4) uniform writeonly image2D velOut;

uniform uvec2 gridSize;
uniform uint frame;
uniform float dt;
uniform float gravity;
uniform int enableTurbulence;

const uint RULE_STRIDE = 20u;

uint getType (uint c){ return c & 0xFFu; }
uint getFlags(uint c){ return (c >> 24u) & 0xFFu; }

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

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

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cellsIn[idx];
    uint typ = getType(cell);
    uint flg = getFlags(cell);
    Rule r = getRule(typ);

    vec2 v = imageLoad(velIn, p).xy;

    if(r.cat == 3){
        imageStore(velOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    float damp = mix(0.995, 0.82, clamp(r.visc, 0.0, 1.0));
    v *= damp;

    if(r.cat == 1){
        v.y += gravity * 1.25 * dt;
    } else if(r.cat == 2){
        v.y += gravity * 0.90 * dt;
    } else if(r.cat == 0){
        v.y -= gravity * (0.55 + max(0.0, -r.density) * 0.25) * dt;
    }

    if(r.cat == 2 && flg > 5u){
        v.y -= gravity * 2.2 * dt;
    }

    if(enableTurbulence != 0 && r.turb > 0.001){
        uint rnd = idx ^ (frame * 131u);
        float nx = hashF(rnd ^ 0xA511E9B3u) * 2.0 - 1.0;
        float ny = hashF(rnd ^ 0x63D83595u) * 2.0 - 1.0;
        v += vec2(nx, ny) * r.turb * 0.35 * dt;
    }

    float maxSpeed = (r.cat == 0) ? 2.5 : ((r.cat == 2) ? 3.0 : 4.0);
    v = clamp(v, vec2(-maxSpeed), vec2(maxSpeed));

    imageStore(velOut, p, vec4(v, 0.0, 0.0));
}
```


## Python-koppling

I din nuvarande loop laddas bara en compute shader från `margolus_sim.glsl`, cellbuffrarna binds på `0/1`, `rules` binds på `2`, och sedan körs exakt ett compute-pass per frame innan renderingen sker.[^3_1][^3_2]
Eftersom gamla shadern också innehåller rörelse och rendering i samma fil går den inte att återanvända som ren renderer utan att du bryter ut steg 6 till ett eget pass, men du kan redan nu börja med `state_shader` och `force_shader` genom att lägga till velocity-texturer och flera dispatchar.[^3_1][^3_2]

Lägg in ungefär detta i `main-4.py`:

```python
# load shaders
state_shader_path = Path(__file__).with_name("state_shader.glsl")
force_shader_path = Path(__file__).with_name("force_shader.glsl")

with open(state_shader_path, "r", encoding="utf-8") as f:
    state_shader = ctx.compute_shader(f.read())

with open(force_shader_path, "r", encoding="utf-8") as f:
    force_shader = ctx.compute_shader(f.read())

# velocity ping-pong
zero_vel = np.zeros((HEIGHT, WIDTH, 2), dtype=np.float32)
vel_a = ctx.texture((WIDTH, HEIGHT), 2, dtype="f4")
vel_b = ctx.texture((WIDTH, HEIGHT), 2, dtype="f4")
vel_a.write(zero_vel.tobytes())
vel_b.write(zero_vel.tobytes())

gx = (WIDTH + 7) // 8
gy = (HEIGHT + 7) // 8
dt = 1.0
```

Och i loopen:

```python
# pass 1: state
read_buf.bind_to_storage_buffer(0)
write_buf.bind_to_storage_buffer(1)
rule_ssbo.bind_to_storage_buffer(2)

state_shader["gridSize"] = (WIDTH, HEIGHT)
state_shader["frame"] = frame
state_shader["ambientTemp"] = TEMP_AMBIENT
state_shader["enableThermal"] = int(not args.no_thermal)
state_shader.run(group_x=gx, group_y=gy, group_z=1)

read_buf, write_buf = write_buf, read_buf

# pass 2: force
read_buf.bind_to_storage_buffer(0)
rule_ssbo.bind_to_storage_buffer(2)
vel_a.bind_to_image(3, read=True, write=False, level=0, format=moderngl.RG32F)
vel_b.bind_to_image(4, read=False, write=True, level=0, format=moderngl.RG32F)

force_shader["gridSize"] = (WIDTH, HEIGHT)
force_shader["frame"] = frame
force_shader["dt"] = dt
force_shader["gravity"] = 1.0
force_shader["enableTurbulence"] = int(not args.no_turbulence)
force_shader.run(group_x=gx, group_y=gy, group_z=1)

vel_a, vel_b = vel_b, vel_a
```

En viktig detalj är att din gamla dispatch använder `WIDTH // 16` och `HEIGHT // 16` därför att gamla shadern hade `local_size=8x8` men lät varje invocation bearbeta ett 2x2-block via `basePos = global * 2 - off`; de nya per-cell-shadrarna ska i stället dispatchas med $(WIDTH+7)//8$ och $(HEIGHT+7)//8$.[^3_1][^3_2]

## Nästa pass

Efter dessa två skulle jag lägga till tre små shaderpass i ordning: `divergence_shader.glsl`, `pressure_shader.glsl` och `project_shader.glsl`, eftersom det är där riktig vätskestabilitet kommer in och där `pressure` börjar göra faktisk nytta.[^3_2]
Sedan kan du lägga ett `resolve_motion_shader.glsl` som använder `vx/vy` för att välja målcell, medan pulver fortfarande får behålla enklare lokala fallregler tills resten av systemet är stabilt.[^3_1][^3_2]

Vill du att jag skriver nästa steg också: `divergence_shader.glsl`, `pressure_shader.glsl` och en enkel `render_cells.glsl` så att du får en komplett första multi-pass-kedja?

<div align="center">⁂</div>

[^3_1]: main-4.py

[^3_2]: margolus_sim.glsl


---

# Ja

Ja — nästa steg är att göra en minimal men komplett multi-pass-kedja: `divergence`, `pressure`, `projection` och `render`. Det passar din nuvarande renderpipeline eftersom `main-4.py` redan visar en `display_texture` via en enkel fullscreen-quad, och din gamla shader redan innehåller färgregler för material, temperaturglow, el-tint och pump-tint som vi kan bryta ut till ett eget renderpass.[^4_1][^4_2]

## Divergence shader

Det här passet läser `vx/vy`, tittar på fasta celler via materialkategori, och skriver ut divergens till en separat `r32f`-textur. Din materialmodell har redan `cat=3` för solids, så det räcker för en första vätsklösare utan extra `solidMask`-buffer.[^4_2][^4_1]

```glsl
// divergence_shader.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer { float rules[]; };

layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(r32f,  binding = 4) uniform writeonly image2D divergenceTex;

uniform uvec2 gridSize;

const uint RULE_STRIDE = 20u;

uint getType(uint c){ return c & 0xFFu; }

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

bool isSolid(ivec2 p){
    if(!inBounds(p)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ).cat == 3;
}

vec2 sampleVel(ivec2 p){
    if(!inBounds(p)) return vec2(0.0);
    if(isSolid(p)) return vec2(0.0);
    return imageLoad(velTex, p).xy;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    if(isSolid(p)){
        imageStore(divergenceTex, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    vec2 vL = sampleVel(p + ivec2(-1, 0));
    vec2 vR = sampleVel(p + ivec2( 1, 0));
    vec2 vD = sampleVel(p + ivec2( 0,-1));
    vec2 vU = sampleVel(p + ivec2( 0, 1));

    float div = 0.5 * ((vR.x - vL.x) + (vU.y - vD.y));
    imageStore(divergenceTex, p, vec4(div, 0.0, 0.0, 0.0));
}
```


## Pressure och projection

Din nuvarande shader har bara ett pseudo-tryck via `pressureL` och `pressureR`, men inget riktigt skalärt tryckfält som projicerar bort kompressibilitet.[^4_2]
Här ersätts det med en standardkedja: Jacobi-iteration på tryck och sedan subtraktion av tryckgradienten från hastigheten.[^4_2]

```glsl
// pressure_shader.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer { float rules[]; };

layout(r32f, binding = 4) uniform readonly image2D divergenceTex;
layout(r32f, binding = 5) uniform readonly image2D pressureIn;
layout(r32f, binding = 6) uniform writeonly image2D pressureOut;

uniform uvec2 gridSize;

const uint RULE_STRIDE = 20u;

uint getType(uint c){ return c & 0xFFu; }

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

bool isSolid(ivec2 p){
    if(!inBounds(p)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ).cat == 3;
}

float samplePressure(ivec2 p){
    if(!inBounds(p) || isSolid(p)) return 0.0;
    return imageLoad(pressureIn, p).x;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    if(isSolid(p)){
        imageStore(pressureOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    float div = imageLoad(divergenceTex, p).x;
    float pL = samplePressure(p + ivec2(-1, 0));
    float pR = samplePressure(p + ivec2( 1, 0));
    float pD = samplePressure(p + ivec2( 0,-1));
    float pU = samplePressure(p + ivec2( 0, 1));

    float pNew = (pL + pR + pD + pU - div) * 0.25;
    imageStore(pressureOut, p, vec4(pNew, 0.0, 0.0, 0.0));
}
```

```glsl
// project_shader.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer { float rules[]; };

layout(rg32f, binding = 3) uniform readonly image2D velIn;
layout(r32f,  binding = 5) uniform readonly image2D pressureTex;
layout(rg32f, binding = 4) uniform writeonly image2D velOut;

uniform uvec2 gridSize;

const uint RULE_STRIDE = 20u;

uint getType(uint c){ return c & 0xFFu; }

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

bool isSolid(ivec2 p){
    if(!inBounds(p)) return true;
    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);
    return getRule(typ).cat == 3;
}

float samplePressure(ivec2 p){
    if(!inBounds(p) || isSolid(p)) return 0.0;
    return imageLoad(pressureTex, p).x;
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    if(isSolid(p)){
        imageStore(velOut, p, vec4(0.0, 0.0, 0.0, 0.0));
        return;
    }

    vec2 v = imageLoad(velIn, p).xy;
    float pL = samplePressure(p + ivec2(-1, 0));
    float pR = samplePressure(p + ivec2( 1, 0));
    float pD = samplePressure(p + ivec2( 0,-1));
    float pU = samplePressure(p + ivec2( 0, 1));

    vec2 gradP = 0.5 * vec2(pR - pL, pU - pD);
    v -= gradP;

    imageStore(velOut, p, vec4(v, 0.0, 0.0, 0.0));
}
```


## Render shader

Din gamla shader skriver färg direkt till `displayTexture` i steg 6 och använder materialfärg, brus, turbulenstint, temperaturglow, el-cooldown och pumppuls.[^4_2]
Det här renderpasset behåller samma idé men gör den frikopplad från fysiken, vilket gör det lättare att felsöka nya rörelsepass utan att visuella regler blandas ihop med simuleringen.[^4_1][^4_2]

```glsl
// render_cells.glsl
#version 430
layout(local_size_x = 8, local_size_y = 8) in;

layout(std430, binding = 0) readonly buffer CellBuffer { uint cells[]; };
layout(std430, binding = 2) readonly buffer RuleBuffer { float rules[]; };
layout(rg32f, binding = 3) uniform readonly image2D velTex;
layout(rgba8, binding = 7) uniform writeonly image2D displayTexture;

uniform uvec2 gridSize;
uniform uint frame;

const uint RULE_STRIDE = 20u;
const uint T_FIRE  = 4u;
const uint T_LAVA  = 9u;
const uint T_PUMP  = 30u;
const uint T_SPARK = 24u;

uint getType (uint c){ return c & 0xFFu; }
uint getTemp (uint c){ return (c >> 8u) & 0xFFu; }
uint getFlags(uint c){ return (c >> 24u) & 0xFFu; }

struct Rule {
    vec3 color;
    float density;
    int cat;
    float flamm;
    float k;
    uint phiH; uint TH;
    uint phiL; uint TL;
    float cond;
    float emit;
    float cool;
    uint burnTo;
    float visc;
    float turb;
    float wd;
};

Rule getRule(uint tp){
    uint o = tp * RULE_STRIDE;
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
    return r;
}

uint hash(uint s){
    s ^= s >> 16u;
    s *= 0x85ebca6bu;
    s ^= s >> 13u;
    s *= 0xc2b2ae35u;
    s ^= s >> 16u;
    return s;
}

bool inBounds(ivec2 p){
    return p.x >= 0 && p.y >= 0 && p.x < int(gridSize.x) && p.y < int(gridSize.y);
}

void main(){
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if(!inBounds(p)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint cell = cells[idx];
    uint typ = getType(cell);
    uint temp = getTemp(cell);
    uint flg = getFlags(cell);
    Rule rr = getRule(typ);

    vec3 col = rr.color;

    if(rr.cat != 0 && rr.cat != 3){
        float n = float(hash(idx ^ frame) & 15u) / 255.0 - 0.03;
        col += vec3(n);
    }

    vec2 v = imageLoad(velTex, p).xy;
    float speed = clamp(length(v) * 0.15, 0.0, 1.0);

    if(rr.turb > 0.1){
        col += vec3(speed * rr.turb * 0.12);
    }

    float glow = max(0.0, (float(temp) - 140.0) / 115.0) * 0.85 + rr.emit * 0.45;
    if(typ == T_FIRE || typ == T_LAVA || typ == T_SPARK)
        col += vec3(glow, glow * 0.45, 0.0);
    else
        col += vec3(glow * 0.30, glow * 0.08, glow * 0.02);

    if(rr.cond > 0.5 && flg > 5u)
        col = mix(col, vec3(0.3, 0.6, 1.0), 0.35);

    if(typ == T_PUMP)
        col = mix(col, vec3(0.0, 1.0, 1.0), 0.3 + 0.2 * sin(float(frame) * 0.25));

    col = clamp(col, 0.0, 1.0);
    imageStore(displayTexture, p, vec4(col, 1.0));
}
```


## Loop i Python

I dag kör `main-4.py` exakt ett compute-pass och en render, men den nya kedjan behöver flera pass per frame och två ping-pong-uppsättningar för både velocity och pressure.[^4_1]
Eftersom din gamla shader band `display_texture` på image binding `3`, medan de nya passen använder både velocity-, divergence-, pressure- och display-images, måste du hålla bindingarna konsekventa per shader och köra varje pass separat.[^4_1][^4_2]

Lägg till texturer ungefär så här:

```python
zero_scalar = np.zeros((HEIGHT, WIDTH), dtype=np.float32)
zero_vec2 = np.zeros((HEIGHT, WIDTH, 2), dtype=np.float32)

vel_a = ctx.texture((WIDTH, HEIGHT), 2, dtype="f4")
vel_b = ctx.texture((WIDTH, HEIGHT), 2, dtype="f4")
vel_a.write(zero_vec2.tobytes())
vel_b.write(zero_vec2.tobytes())

div_tex = ctx.texture((WIDTH, HEIGHT), 1, dtype="f4")
div_tex.write(zero_scalar.tobytes())

pressure_a = ctx.texture((WIDTH, HEIGHT), 1, dtype="f4")
pressure_b = ctx.texture((WIDTH, HEIGHT), 1, dtype="f4")
pressure_a.write(zero_scalar.tobytes())
pressure_b.write(zero_scalar.tobytes())

display_texture = ctx.texture((WIDTH, HEIGHT), 4, dtype="f1")
gx = (WIDTH + 7) // 8
gy = (HEIGHT + 7) // 8
```

Ladda shaders:

```python
with open(Path(__file__).with_name("divergence_shader.glsl"), "r", encoding="utf-8") as f:
    divergence_shader = ctx.compute_shader(f.read())

with open(Path(__file__).with_name("pressure_shader.glsl"), "r", encoding="utf-8") as f:
    pressure_shader = ctx.compute_shader(f.read())

with open(Path(__file__).with_name("project_shader.glsl"), "r", encoding="utf-8") as f:
    project_shader = ctx.compute_shader(f.read())

with open(Path(__file__).with_name("render_cells.glsl"), "r", encoding="utf-8") as f:
    render_shader = ctx.compute_shader(f.read())
```

Och kör ungefär så här i loopen, efter `state_shader` och `force_shader`:[^4_1]

```python
# divergence
read_buf.bind_to_storage_buffer(0)
rule_ssbo.bind_to_storage_buffer(2)
vel_a.bind_to_image(3, read=True, write=False, level=0, format=moderngl.RG32F)
div_tex.bind_to_image(4, read=False, write=True, level=0, format=moderngl.R32F)

divergence_shader["gridSize"] = (WIDTH, HEIGHT)
divergence_shader.run(group_x=gx, group_y=gy, group_z=1)

# pressure solve
for _ in range(16):
    read_buf.bind_to_storage_buffer(0)
    rule_ssbo.bind_to_storage_buffer(2)
    div_tex.bind_to_image(4, read=True, write=False, level=0, format=moderngl.R32F)
    pressure_a.bind_to_image(5, read=True, write=False, level=0, format=moderngl.R32F)
    pressure_b.bind_to_image(6, read=False, write=True, level=0, format=moderngl.R32F)

    pressure_shader["gridSize"] = (WIDTH, HEIGHT)
    pressure_shader.run(group_x=gx, group_y=gy, group_z=1)

    pressure_a, pressure_b = pressure_b, pressure_a

# projection
read_buf.bind_to_storage_buffer(0)
rule_ssbo.bind_to_storage_buffer(2)
vel_a.bind_to_image(3, read=True, write=False, level=0, format=moderngl.RG32F)
pressure_a.bind_to_image(5, read=True, write=False, level=0, format=moderngl.R32F)
vel_b.bind_to_image(4, read=False, write=True, level=0, format=moderngl.RG32F)

project_shader["gridSize"] = (WIDTH, HEIGHT)
project_shader.run(group_x=gx, group_y=gy, group_z=1)

vel_a, vel_b = vel_b, vel_a

# render
read_buf.bind_to_storage_buffer(0)
rule_ssbo.bind_to_storage_buffer(2)
vel_a.bind_to_image(3, read=True, write=False, level=0, format=moderngl.RG32F)
display_texture.bind_to_image(7, read=False, write=True, level=0, format=moderngl.RGBA8)

render_shader["gridSize"] = (WIDTH, HEIGHT)
render_shader["frame"] = frame
render_shader.run(group_x=gx, group_y=gy, group_z=1)
```


## Vad som saknas

Den här kedjan gör redan något viktigt: materialtillstånd är separerat från rörelse, hastighet kan projiceras med riktigt tryck, och renderingen är egen.[^4_2][^4_1]
Det som fortfarande saknas är själva celltransporten enligt `vx/vy`, alltså ett `resolve_motion_shader.glsl` eller `advect_cells_shader.glsl`; utan det får du stabilare velocityfält men ännu inte full fysisk omplacering av vätskor enligt hastighetsfältet.[^4_2]

Min rekommenderade ordning nu är:

- Behåll nuvarande Margolus-rörelse tillfälligt för pulver.
- Lägg till ett separat `resolve_motion_shader.glsl` för vätskor och gaser.
- Flytta sedan successivt vatten, olja, syra, blod, slime, steam, smoke och gas från swaplogik till velocity-baserad transport.[^4_1][^4_2]

Vill du att jag skriver just det sista pusslet nu: ett första `resolve_motion_shader.glsl` som faktiskt flyttar vätskor och gaser mellan celler med hjälp av `vx/vy`?

<div align="center">⁂</div>

[^4_1]: main-4.py

[^4_2]: margolus_sim.glsl

