# Implementeringsrapport - Fysikgranskning

## Datum: 2026-04-17

## Åtgärdade Problem

### 1. ✅ Material-ID:n i common.glsl (MEDEL)
**Problem**: Material ID 21 (concrete), 23 (rust), 27 (sugar) saknades i `shaders/common.glsl` men fanns i `materials.py`.

**Fix**: Lade till konstanter i `common.glsl`:
```glsl
const uint T_CONCRETE = 21u; const uint T_METAL = 22u; const uint T_RUST = 23u;
...
const uint T_SALT  = 26u; const uint T_SUGAR = 27u; ...
```

**Verifikation**: Shader laddas korrekt, material-ID:n är nu konsistenta.

---

### 2. ✅ Dubbel Värmediffusion (MEDEL)
**Problem**: Både `state_shader.glsl` och `heat_shader.glsl` applicerade termisk diffusion → för snabb värmeöverföring.

**Fix**: Förenklade termisk hantering i `state_shader.glsl`:
- Ta bort 4-grannars harmonisk-medelvärde diffusion
- Behåll endast Newton-avkylning för tillståndsmaskin-konsistens
- Värmediffusion sköts nu enbart av `heat_shader.glsl`

**Före**:
```glsl
// THERMAL DIFFUSION (4-neighbor)
if(enableThermal != 0){
    float kN = min(r.k, getRule(tn).k); ...
    float avgT = sumT / totalWeight;
    float mixed = mix(float(temp), avgT, clamp(r.k * 0.30, 0.0, 1.0));
    mixed -= r.cool * 0.10 * (mixed - float(ambientTemp));
    temp = uint(clamp(int(round(mixed)), 0, 255));
}
```

**Efter**:
```glsl
// THERMAL DIFFUSION NOTE: Disabled here - heat diffusion is handled by heat_shader.glsl
if(enableThermal != 0){
    float mixed = float(temp);
    mixed -= r.cool * 0.10 * (mixed - float(ambientTemp));
    temp = uint(clamp(int(round(mixed)), 0, 255));
}
```

**Resultat**: Värmeöverföring är nu mer fysikaliskt rimlig (ej dubblerad).

---

### 3. ✅ Eld-självupphettning (LÅG)
**Problem**: Eld ökade sin temperatur obegränsat (+4/frame), når 255 på ~4 sekunder.

**Fix**: Begränsad självupphettning i `state_shader.glsl`:
```glsl
if(typ == T_FIRE){
    if(temp < 220u) {
        temp = min(220u, temp + 4u);
    }
    // ...
}
```

**Resultat**: Eld maxar vid ~220, vilket är mer rimligt för en simulerad flamma.

---

## Tester

| Test Suite | Resultat |
|------------|----------|
| test_cli.py | ✅ 14 passed |
| test_levels.py | ✅ 6 passed |
| test_shader_logic.py | ✅ 27 passed |
| Shader loading | ✅ 10/10 shaders OK |

**Total**: 47 tester klara, inga regressioner.

---

## Fysikalisk Rimlighet - Uppdaterad Bedömning

| Aspekt | Före | Efter |
|--------|------|-------|
| Material-konsistens | ⚠️ Saknade ID:n | ✅ Alla ID:n definierade |
| Värmeöverföring | ⚠️ Dubbel applicering | ✅ Enkel, korrekt |
| Eld-beteende | ⚠️ Runaway-temperatur | ✅ Begränsad, rimlig |
| Gravitation | ✅ Korrekt | ✅ Korrekt |
| Uppdrift | ✅ Rimlig | ✅ Rimlig |

---

## Återstående Problem (Ej Åtgärdade)

| Prioritet | Problem | Anledning |
|-----------|---------|-----------|
| 🔴 LÅG | Pump-kraft tecken | Verifierat korrekt i force_shader.glsl:239-241 |
| 🟢 LÅG | Hårdkodade explosion-probabilities | Designval, fungerar korrekt |

---

## Sammanfattning

Alla identifierade fysik-problem av medelhög prioritet eller högre har åtgärdats. Simuleringen är nu mer fysikaliskt konsistent med:
- Korrekt material-referenser i shaders
- Rimlig värmeöverföring (ej dubblerad)
- Begränsad eld-temperatur för mer realistiskt beteende
