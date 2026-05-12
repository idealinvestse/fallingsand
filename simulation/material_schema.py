"""v6 material schema: structured YAML loader, validator, and legacy adapter.

Provides:
- load_materials_v6(path) -> dict[int, MaterialDefV6]
- to_legacy_defs(v6_materials) -> dict[int, dict]  (compatible with current materials.py)
- validate_v6_materials(materials) -> list[str]     (returns warnings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ── v6 structured material definition ────────────────────────────────────────

@dataclass(slots=True)
class DisplayProps:
    color: tuple[int, int, int] = (255, 255, 255)
    emissive: float = 0.0


@dataclass(slots=True)
class PhysicalProps:
    category: str = "solid"
    state_family: str = "solid"
    density: float = 1.0
    viscosity: float = 0.0
    cohesion: float = 0.0
    restitution: float = 0.0
    surface_tension: float = 0.0
    solubility: float = 0.0
    turbulence: float = 0.0
    wet_dry: float = 0.0


@dataclass(slots=True)
class ThermalProps:
    conductivity: float = 0.0
    heat_capacity: float = 1.0
    cooling_rate: float = 0.0
    melting_point: float = 0.0
    boiling_point: float = 0.0
    phase_high_material: str = ""
    phase_high_temp: float = 255.0
    phase_low_material: str = ""
    phase_low_temp: float = 0.0
    default_flame_temp: float = 0.0
    default_flame_life: int = 0


@dataclass(slots=True)
class ElectricalProps:
    conductivity: float = 0.0
    capacitance: float = 0.0
    breakdown_voltage: float = 0.0
    arc_emission: float = 0.0


@dataclass(slots=True)
class ReactionDef:
    partner: str = ""
    product_self: str = ""
    product_neighbor: str = ""
    probability: float = 0.0
    temp_threshold: float = 0.0


@dataclass(slots=True)
class ChemistryProps:
    flammability: float = 0.0
    burn_to: str = ""
    oxygen_requirement: float = 0.0
    oxygen_yield: float = 0.0
    reactions: list[ReactionDef] = field(default_factory=list)


@dataclass(slots=True)
class BiologyProps:
    biomass: float = 0.0
    growth_rate: float = 0.0
    decay_rate: float = 0.0
    nutrient_value: float = 0.0
    predator_mask: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExplosionProps:
    power: float = 0.0
    detonation_temp: float = 255.0
    blast_radius: int = 0
    blast_duration: int = 0
    fragment_type: str = ""
    shockwave_speed: float = 0.0


@dataclass(slots=True)
class MagneticProps:
    polarity: float = 0.0  # -1.0 (south) to 1.0 (north)
    permeability: float = 0.0  # 0=non-magnetic, 1=ferromagnetic
    coercivity: float = 0.0  # Resistance to demagnetization
    curie_temp: float = 0.0  # Temperature at which magnetism is lost


@dataclass(slots=True)
class PlasmaProps:
    ionization_energy: float = 0.0  # Energy required to ionize
    plasma_density: float = 0.0  # Particle density in plasma state
    confinement_field: float = 0.0  # Magnetic confinement strength
    recombination_rate: float = 0.0  # Rate of returning to neutral state


@dataclass(slots=True)
class GlassProps:
    transparency: float = 0.0  # 0=opaque, 1=fully transparent
    refractive_index: float = 1.0  # Light bending (1.0=air, 1.5=glass)
    shatter_threshold: float = 0.0  # Impact force to shatter
    thermal_shock_resistance: float = 0.0  # Resistance to rapid temp changes


@dataclass(slots=True)
class MaterialDefV6:
    id: int
    name: str
    description: str = ""
    display: DisplayProps = field(default_factory=DisplayProps)
    physical: PhysicalProps = field(default_factory=PhysicalProps)
    thermal: ThermalProps = field(default_factory=ThermalProps)
    electrical: ElectricalProps = field(default_factory=ElectricalProps)
    chemistry: ChemistryProps = field(default_factory=ChemistryProps)
    biology: BiologyProps = field(default_factory=BiologyProps)
    explosion: ExplosionProps = field(default_factory=ExplosionProps)
    magnetic: MagneticProps = field(default_factory=MagneticProps)
    plasma: PlasmaProps = field(default_factory=PlasmaProps)
    glass: GlassProps = field(default_factory=GlassProps)


# ── Category / StateFamily string-to-int mapping ──────────────────────────────

CATEGORY_MAP: dict[str, int] = {
    "gas": 0, "powder": 1, "liquid": 2, "solid": 3,
}

STATE_FAMILY_MAP: dict[str, int] = {
    "gas": 0, "liquid": 1, "solid": 2, "plasma": 3,
    "powder": 4, "paste": 5, "gel": 6, "foam": 7,
    "emulsion": 8, "aerosol": 9,
}


# ── YAML loading ──────────────────────────────────────────────────────────────

def _parse_color(raw: Any) -> tuple[int, int, int]:
    if isinstance(raw, list) and len(raw) == 3:
        return (int(raw[0]), int(raw[1]), int(raw[2]))
    if isinstance(raw, str):
        h = raw.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return (255, 255, 255)


def _get_str(d: dict[str, Any], key: str, default: str = "") -> str:
    v = d.get(key, default)
    return str(v) if v is not None else default


def _get_float(d: dict[str, Any], key: str, default: float = 0.0) -> float:
    v = d.get(key, default)
    return float(v) if v is not None else default


def _get_int(d: dict[str, Any], key: str, default: int = 0) -> int:
    v = d.get(key, default)
    return int(v) if v is not None else default


def _get_bool(d: dict[str, Any], key: str, default: bool = False) -> bool:
    v = d.get(key, default)
    return bool(v) if v is not None else default


def _parse_reactions(raw: list[dict[str, Any]]) -> list[ReactionDef]:
    result: list[ReactionDef] = []
    for r in raw[:3]:  # max 3 reaction slots for legacy compat
        result.append(ReactionDef(
            partner=_get_str(r, "partner"),
            product_self=_get_str(r, "product_self", _get_str(r, "self", "")),
            product_neighbor=_get_str(r, "product_neighbor", _get_str(r, "neighbor", "")),
            probability=_get_float(r, "probability"),
            temp_threshold=_get_float(r, "temp_threshold"),
        ))
    return result


def load_materials_v6(path: str | Path) -> dict[int, MaterialDefV6]:
    """Load v6-format materials from a YAML file.

    Returns dict mapping material ID -> MaterialDefV6.
    """
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    schema_version = raw.get("schema_version", 0)
    if schema_version < 6:
        raise ValueError(f"Expected schema_version >= 6, got {schema_version}")

    materials: dict[int, MaterialDefV6] = {}
    name_to_id: dict[str, int] = {}

    raw_materials = raw.get("materials", {})
    for mat_id_str, m in raw_materials.items():
        mat_id = int(mat_id_str)
        name = _get_str(m, "name", f"material_{mat_id}")
        description = _get_str(m, "description", "")
        name_to_id[name] = mat_id

        display_raw = m.get("display", {})
        display = DisplayProps(
            color=_parse_color(display_raw.get("color", [255, 255, 255])),
            emissive=_get_float(display_raw, "emissive"),
        )

        phys_raw = m.get("physical", {})
        physical = PhysicalProps(
            category=_get_str(phys_raw, "category", "solid"),
            state_family=_get_str(phys_raw, "state_family", "solid"),
            density=_get_float(phys_raw, "density", 1.0),
            viscosity=_get_float(phys_raw, "viscosity"),
            cohesion=_get_float(phys_raw, "cohesion"),
            restitution=_get_float(phys_raw, "restitution"),
            surface_tension=_get_float(phys_raw, "surface_tension"),
            solubility=_get_float(phys_raw, "solubility"),
            turbulence=_get_float(phys_raw, "turbulence"),
            wet_dry=_get_float(phys_raw, "wet_dry"),
        )

        therm_raw = m.get("thermal", {})
        thermal = ThermalProps(
            conductivity=_get_float(therm_raw, "conductivity"),
            heat_capacity=_get_float(therm_raw, "heat_capacity", 1.0),
            cooling_rate=_get_float(therm_raw, "cooling_rate"),
            melting_point=_get_float(therm_raw, "melting_point"),
            boiling_point=_get_float(therm_raw, "boiling_point"),
            phase_high_material=_get_str(therm_raw.get("phase_high", {}), "material", ""),
            phase_high_temp=_get_float(therm_raw.get("phase_high", {}), "temp", 255.0),
            phase_low_material=_get_str(therm_raw.get("phase_low", {}), "material", ""),
            phase_low_temp=_get_float(therm_raw.get("phase_low", {}), "temp", 0.0),
            default_flame_temp=_get_float(therm_raw, "default_flame_temp"),
            default_flame_life=_get_int(therm_raw, "default_flame_life"),
        )

        elec_raw = m.get("electrical", {})
        electrical = ElectricalProps(
            conductivity=_get_float(elec_raw, "conductivity"),
            capacitance=_get_float(elec_raw, "capacitance"),
            breakdown_voltage=_get_float(elec_raw, "breakdown_voltage"),
            arc_emission=_get_float(elec_raw, "arc_emission"),
        )

        chem_raw = m.get("chemistry", {})
        chemistry = ChemistryProps(
            flammability=_get_float(chem_raw, "flammability"),
            burn_to=_get_str(chem_raw, "burn_to"),
            oxygen_requirement=_get_float(chem_raw, "oxygen_requirement"),
            oxygen_yield=_get_float(chem_raw, "oxygen_yield"),
            reactions=_parse_reactions(chem_raw.get("reactions", [])),
        )

        bio_raw = m.get("biology", {})
        biology = BiologyProps(
            biomass=_get_float(bio_raw, "biomass"),
            growth_rate=_get_float(bio_raw, "growth_rate"),
            decay_rate=_get_float(bio_raw, "decay_rate"),
            nutrient_value=_get_float(bio_raw, "nutrient_value"),
            predator_mask=bio_raw.get("predator_mask", []),
        )

        expl_raw = m.get("explosion", {})
        explosion = ExplosionProps(
            power=_get_float(expl_raw, "power"),
            detonation_temp=_get_float(expl_raw, "detonation_temp", 255.0),
            blast_radius=_get_int(expl_raw, "blast_radius"),
            blast_duration=_get_int(expl_raw, "blast_duration"),
            fragment_type=_get_str(expl_raw, "fragment_type"),
            shockwave_speed=_get_float(expl_raw, "shockwave_speed"),
        )

        mag_raw = m.get("magnetic", {})
        magnetic = MagneticProps(
            polarity=_get_float(mag_raw, "polarity"),
            permeability=_get_float(mag_raw, "permeability"),
            coercivity=_get_float(mag_raw, "coercivity"),
            curie_temp=_get_float(mag_raw, "curie_temp"),
        )

        plasma_raw = m.get("plasma", {})
        plasma = PlasmaProps(
            ionization_energy=_get_float(plasma_raw, "ionization_energy"),
            plasma_density=_get_float(plasma_raw, "plasma_density"),
            confinement_field=_get_float(plasma_raw, "confinement_field"),
            recombination_rate=_get_float(plasma_raw, "recombination_rate"),
        )

        glass_raw = m.get("glass", {})
        glass = GlassProps(
            transparency=_get_float(glass_raw, "transparency"),
            refractive_index=_get_float(glass_raw, "refractive_index", 1.0),
            shatter_threshold=_get_float(glass_raw, "shatter_threshold"),
            thermal_shock_resistance=_get_float(glass_raw, "thermal_shock_resistance"),
        )

        materials[mat_id] = MaterialDefV6(
            id=mat_id,
            name=name,
            description=description,
            display=display,
            physical=physical,
            thermal=thermal,
            electrical=electrical,
            chemistry=chemistry,
            biology=biology,
            explosion=explosion,
            magnetic=magnetic,
            plasma=plasma,
            glass=glass,
        )

    # Resolve name-based references to IDs
    _resolve_references(materials, name_to_id)

    return materials


def _resolve_references(materials: dict[int, MaterialDefV6], name_to_id: dict[str, int]) -> None:
    """Resolve string-based references (phase materials, burn_to, reactions) to IDs."""
    for mat in materials.values():
        t = mat.thermal
        if t.phase_high_material and t.phase_high_material in name_to_id:
            object.__setattr__(t, 'phase_high_material', name_to_id[t.phase_high_material])
        if t.phase_low_material and t.phase_low_material in name_to_id:
            object.__setattr__(t, 'phase_low_material', name_to_id[t.phase_low_material])

        c = mat.chemistry
        if c.burn_to and c.burn_to in name_to_id:
            object.__setattr__(c, 'burn_to', name_to_id[c.burn_to])

        for rx in c.reactions:
            if rx.partner and rx.partner in name_to_id:
                object.__setattr__(rx, 'partner', name_to_id[rx.partner])
            if rx.product_self and rx.product_self in name_to_id:
                object.__setattr__(rx, 'product_self', name_to_id[rx.product_self])
            if rx.product_neighbor and rx.product_neighbor in name_to_id:
                object.__setattr__(rx, 'product_neighbor', name_to_id[rx.product_neighbor])

        e = mat.explosion
        if e.fragment_type and e.fragment_type in name_to_id:
            object.__setattr__(e, 'fragment_type', name_to_id[e.fragment_type])


# ── Legacy adapter: v6 -> v5 flat dict ────────────────────────────────────────

def to_legacy_defs(v6_materials: dict[int, MaterialDefV6]) -> dict[int, dict[str, Any]]:
    """Convert v6 MaterialDefV6 objects to legacy flat dict format.

    Produces dicts compatible with the current MaterialRegistry._initialize_materials().
    """
    result: dict[int, dict[str, Any]] = {}
    for mat_id, m in v6_materials.items():
        d = m.display
        p = m.physical
        t = m.thermal
        e = m.electrical
        c = m.chemistry
        ex = m.explosion
        mag = m.magnetic
        plas = m.plasma
        gl = m.glass

        # Resolve phase IDs (could be int from resolve or str name)
        phi_h = t.phase_high_material if isinstance(t.phase_high_material, int) else 0
        phi_l = t.phase_low_material if isinstance(t.phase_low_material, int) else 0
        bto = c.burn_to if isinstance(c.burn_to, int) else 0
        frag_t = ex.fragment_type if isinstance(ex.fragment_type, int) else 0

        # Resolve reaction references
        rxns = c.reactions
        rxn1_p = rxns[0].partner if len(rxns) > 0 and isinstance(rxns[0].partner, int) else 0
        rxn1_ps = rxns[0].product_self if len(rxns) > 0 and isinstance(rxns[0].product_self, int) else 0
        rxn1_pn = rxns[0].product_neighbor if len(rxns) > 0 and isinstance(rxns[0].product_neighbor, int) else 0
        rxn1_prob = rxns[0].probability if len(rxns) > 0 else 0.0
        rxn1_tt = rxns[0].temp_threshold if len(rxns) > 0 else 0.0

        rxn2_p = rxns[1].partner if len(rxns) > 1 and isinstance(rxns[1].partner, int) else 0
        rxn2_ps = rxns[1].product_self if len(rxns) > 1 and isinstance(rxns[1].product_self, int) else 0
        rxn2_pn = rxns[1].product_neighbor if len(rxns) > 1 and isinstance(rxns[1].product_neighbor, int) else 0
        rxn2_prob = rxns[1].probability if len(rxns) > 1 else 0.0
        rxn2_tt = rxns[1].temp_threshold if len(rxns) > 1 else 0.0

        rxn3_p = rxns[2].partner if len(rxns) > 2 and isinstance(rxns[2].partner, int) else 0
        rxn3_ps = rxns[2].product_self if len(rxns) > 2 and isinstance(rxns[2].product_self, int) else 0
        rxn3_pn = rxns[2].product_neighbor if len(rxns) > 2 and isinstance(rxns[2].product_neighbor, int) else 0
        rxn3_prob = rxns[2].probability if len(rxns) > 2 else 0.0
        rxn3_tt = rxns[2].temp_threshold if len(rxns) > 2 else 0.0

        result[mat_id] = {
            "name": m.name,
            "color": list(d.color),
            "density": p.density,
            "cat": CATEGORY_MAP.get(p.category, 3),
            "flamm": c.flammability,
            "k": t.conductivity,
            "phi_h": phi_h,
            "Th": t.phase_high_temp,
            "phi_l": phi_l,
            "Tl": t.phase_low_temp,
            "cond": e.conductivity,
            "emit": d.emissive,
            "cool": t.cooling_rate,
            "bto": bto,
            "visc": p.viscosity,
            "turb": p.turbulence,
            "wd": p.wet_dry,
            "dft": t.default_flame_temp,
            "dfl": t.default_flame_life,
            "cp": t.heat_capacity,
            "mp": t.melting_point,
            "bp": t.boiling_point,
            "st": p.surface_tension,
            "sol": p.solubility,
            "coh": p.cohesion,
            "rest": p.restitution,
            "sf": STATE_FAMILY_MAP.get(p.state_family, 2),
            "rxn1_p": rxn1_p,
            "rxn1_ps": rxn1_ps,
            "rxn1_pn": rxn1_pn,
            "rxn1_prob": rxn1_prob,
            "rxn1_tt": rxn1_tt,
            "rxn2_p": rxn2_p,
            "rxn2_ps": rxn2_ps,
            "rxn2_pn": rxn2_pn,
            "rxn2_prob": rxn2_prob,
            "rxn2_tt": rxn2_tt,
            "rxn3_p": rxn3_p,
            "rxn3_ps": rxn3_ps,
            "rxn3_pn": rxn3_pn,
            "rxn3_prob": rxn3_prob,
            "rxn3_tt": rxn3_tt,
            "exp_pow": ex.power,
            "det_temp": ex.detonation_temp,
            "bl_rad": ex.blast_radius,
            "bl_dur": ex.blast_duration,
            "frag_t": frag_t,
            "sw_spd": ex.shockwave_speed,
            "o2_req": c.oxygen_requirement,
            "o2_yield": c.oxygen_yield,
            "mag_pol": mag.polarity,
            "mag_perm": mag.permeability,
            "mag_coerc": mag.coercivity,
            "mag_curie": mag.curie_temp,
            "plas_ion": plas.ionization_energy,
            "plas_dens": plas.plasma_density,
            "plas_conf": plas.confinement_field,
            "plas_recomb": plas.recombination_rate,
            "glass_trans": gl.transparency,
            "glass_refract": gl.refractive_index,
            "glass_shatter": gl.shatter_threshold,
            "glass_thermal": gl.thermal_shock_resistance,
        }
    return result


# ── Validation ────────────────────────────────────────────────────────────────

def validate_v6_materials(materials: dict[int, MaterialDefV6]) -> list[str]:
    """Validate v6 material definitions. Returns list of warning strings."""
    warnings: list[str] = []

    for mat_id, m in materials.items():
        p = m.physical
        if p.category not in CATEGORY_MAP:
            warnings.append(f"[{m.name}] unknown category '{p.category}'")
        if p.state_family not in STATE_FAMILY_MAP:
            warnings.append(f"[{m.name}] unknown state_family '{p.state_family}'")

        if not (0.0 <= p.viscosity <= 1.0):
            warnings.append(f"[{m.name}] viscosity {p.viscosity} out of range [0,1]")
        if not (0.0 <= p.surface_tension <= 1.0):
            warnings.append(f"[{m.name}] surface_tension {p.surface_tension} out of range [0,1]")
        if not (0.0 <= m.chemistry.flammability <= 1.0):
            warnings.append(f"[{m.name}] flammability {m.chemistry.flammability} out of range [0,1]")
        if not (0.0 <= m.electrical.conductivity <= 1.0):
            warnings.append(f"[{m.name}] electrical conductivity {m.electrical.conductivity} out of range [0,1]")

        if p.density <= 0 and p.category != "gas":
            warnings.append(f"[{m.name}] density {p.density} <= 0 (non-gas)")

        # Validate magnetic properties
        mag = m.magnetic
        if not (-1.0 <= mag.polarity <= 1.0):
            warnings.append(f"[{m.name}] polarity {mag.polarity} out of range [-1,1]")
        if not (0.0 <= mag.permeability <= 1.0):
            warnings.append(f"[{m.name}] permeability {mag.permeability} out of range [0,1]")

        # Validate plasma properties
        plas = m.plasma
        if plas.ionization_energy < 0.0:
            warnings.append(f"[{m.name}] ionization_energy must be >= 0")
        if plas.plasma_density < 0.0:
            warnings.append(f"[{m.name}] plasma_density must be >= 0")

        # Validate glass properties
        gl = m.glass
        if not (0.0 <= gl.transparency <= 1.0):
            warnings.append(f"[{m.name}] transparency {gl.transparency} out of range [0,1]")
        if not (1.0 <= gl.refractive_index <= 3.0):
            warnings.append(f"[{m.name}] refractive_index {gl.refractive_index} out of reasonable range [1,3]")

    return warnings
