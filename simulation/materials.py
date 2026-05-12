"""Material definitions and registry for the falling sand simulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.constants import NUM_TYPES, RULE_STRIDE
from core.types import Material, Category, StateFamily
from simulation.yaml_loader import load_material_definitions

# Material definitions loaded from materials.yaml at import time.
# See materials.yaml for the canonical source of truth.
_MATERIAL_DEFINITIONS: dict[str, dict[str, Any]] = load_material_definitions()


class MaterialRegistry:
    """Registry for all simulation materials."""

    def __init__(self) -> None:
        self._materials: dict[int, Material] = {}
        self._initialize_materials()
        self._validate_materials()

    @classmethod
    def from_v6_yaml(cls, path: str | Path) -> "MaterialRegistry":
        """Create a MaterialRegistry from a v6-format YAML file.

        Loads the structured v6 schema, converts to legacy flat dicts,
        and initializes the registry. This provides a migration path
        from the current flat YAML to the new structured format.
        """
        from simulation.material_schema import load_materials_v6, to_legacy_defs

        v6_materials = load_materials_v6(path)
        legacy_defs = to_legacy_defs(v6_materials)

        # Temporarily replace the module-level definitions
        global _MATERIAL_DEFINITIONS
        _original = _MATERIAL_DEFINITIONS
        _MATERIAL_DEFINITIONS = legacy_defs  # type: ignore[assignment]

        try:
            registry = cls.__new__(cls)
            registry._materials = {}
            registry._initialize_materials()
            registry._validate_materials()
            return registry
        finally:
            _MATERIAL_DEFINITIONS = _original

    def _initialize_materials(self) -> None:
        """Initialize materials from definitions."""
        for mat_id_str, defs in _MATERIAL_DEFINITIONS.items():
            mat_id = int(mat_id_str)  # Convert string key to int
            self._materials[mat_id] = Material(
                name=defs["name"],
                color=defs["color"],
                density=defs["density"],
                category=Category(defs["cat"]),
                flammability=defs["flamm"],
                thermal_conductivity=defs["k"],
                phase_high_id=defs["phi_h"],
                phase_high_temp=defs["Th"],
                phase_low_id=defs["phi_l"],
                phase_low_temp=defs["Tl"],
                electrical_conductivity=defs["cond"],
                emissivity=defs["emit"],
                cooling_rate=defs["cool"],
                burn_to=defs["bto"],
                viscosity=defs["visc"],
                turbulence=defs["turb"],
                wet_dry=defs["wd"],
                default_flame_temp=defs["dft"],
                default_flame_life=defs["dfl"],
                # New fields
                heat_capacity=defs["cp"],
                melting_point=defs["mp"],
                boiling_point=defs["bp"],
                surface_tension=defs["st"],
                solubility=defs["sol"],
                cohesion=defs["coh"],
                restitution=defs["rest"],
                state_family=StateFamily(defs["sf"]),
                # Reaction slots
                reaction_1_partner=defs["rxn1_p"],
                reaction_1_product_self=defs["rxn1_ps"],
                reaction_1_product_neighbor=defs["rxn1_pn"],
                reaction_1_prob=defs["rxn1_prob"],
                reaction_1_temp_threshold=defs["rxn1_tt"],
                reaction_2_partner=defs["rxn2_p"],
                reaction_2_product_self=defs["rxn2_ps"],
                reaction_2_product_neighbor=defs["rxn2_pn"],
                reaction_2_prob=defs["rxn2_prob"],
                reaction_2_temp_threshold=defs["rxn2_tt"],
                reaction_3_partner=defs["rxn3_p"],
                reaction_3_product_self=defs["rxn3_ps"],
                reaction_3_product_neighbor=defs["rxn3_pn"],
                reaction_3_prob=defs["rxn3_prob"],
                reaction_3_temp_threshold=defs["rxn3_tt"],
                # Explosive properties (with defaults for non-explosive materials)
                explosive_power=defs.get("exp_pow", 0.0),
                detonation_temp=defs.get("det_temp", 255),
                blast_radius=defs.get("bl_rad", 0),
                blast_duration=defs.get("bl_dur", 0),
                fragment_type=defs.get("frag_t", 0),
                shockwave_speed=defs.get("sw_spd", 0.0),
                # Oxygen / combustion properties
                oxygen_requirement=defs.get("o2_req", 0.0),
                oxygen_yield=defs.get("o2_yield", 0.0),
            )

    def _validate_materials(self) -> None:
        """Validate loaded materials and rule-buffer compatibility.

        This keeps the YAML definition table and the GPU rule-buffer layout
        from drifting out of sync in ways that would be hard to diagnose at
        runtime.
        """

        def _require_range(name: str, value: float, low: float, high: float) -> None:
            if not (low <= value <= high):
                raise ValueError(f"Material {name} has out-of-range value {value!r}; expected {low}..{high}")

        for mat_id, mat in self._materials.items():
            if not 0 <= mat_id < NUM_TYPES:
                raise ValueError(f"Material ID {mat_id} is outside the supported range 0..{NUM_TYPES - 1}")

            _require_range(mat.name, mat.flammability, 0.0, 1.0)
            _require_range(mat.name, mat.thermal_conductivity, 0.0, 1.0)
            _require_range(mat.name, mat.electrical_conductivity, 0.0, 1.0)
            _require_range(mat.name, mat.emissivity, 0.0, 1.0)
            _require_range(mat.name, mat.cooling_rate, 0.0, 1.0)
            _require_range(mat.name, mat.viscosity, 0.0, 1.0)
            _require_range(mat.name, mat.turbulence, 0.0, 1.0)
            _require_range(mat.name, float(mat.wet_dry), 0.0, 1.0)
            _require_range(mat.name, mat.heat_capacity, 0.0, 10.0)
            _require_range(mat.name, mat.surface_tension, 0.0, 1.0)
            _require_range(mat.name, mat.solubility, 0.0, 1.0)
            _require_range(mat.name, mat.cohesion, 0.0, 1.0)
            _require_range(mat.name, mat.restitution, 0.0, 1.0)
            _require_range(mat.name, mat.oxygen_requirement, 0.0, 1.0)
            _require_range(mat.name, mat.oxygen_yield, 0.0, 1.0)

            for partner, prod_self, prod_neighbor, prob, temp_threshold in (
                (
                    mat.reaction_1_partner,
                    mat.reaction_1_product_self,
                    mat.reaction_1_product_neighbor,
                    mat.reaction_1_prob,
                    mat.reaction_1_temp_threshold,
                ),
                (
                    mat.reaction_2_partner,
                    mat.reaction_2_product_self,
                    mat.reaction_2_product_neighbor,
                    mat.reaction_2_prob,
                    mat.reaction_2_temp_threshold,
                ),
                (
                    mat.reaction_3_partner,
                    mat.reaction_3_product_self,
                    mat.reaction_3_product_neighbor,
                    mat.reaction_3_prob,
                    mat.reaction_3_temp_threshold,
                ),
            ):
                if partner == prod_self == prod_neighbor == 0 and prob == 0.0 and temp_threshold == 0:
                    continue
                if not 0 <= partner < NUM_TYPES:
                    raise ValueError(f"Material {mat.name} has invalid reaction partner ID {partner}")
                if not 0 <= prod_self < NUM_TYPES:
                    raise ValueError(f"Material {mat.name} has invalid reaction self product ID {prod_self}")
                if not 0 <= prod_neighbor < NUM_TYPES:
                    raise ValueError(f"Material {mat.name} has invalid reaction neighbor product ID {prod_neighbor}")
                _require_range(mat.name, prob, 0.0, 1.0)
                if temp_threshold < 0:
                    raise ValueError(f"Material {mat.name} has negative reaction temperature threshold {temp_threshold}")

        rules = self.to_rule_buffer()
        expected_len = NUM_TYPES * RULE_STRIDE
        if len(rules) != expected_len:
            raise ValueError(
                f"Rule buffer length mismatch: got {len(rules)}, expected {expected_len} ({NUM_TYPES} * {RULE_STRIDE})"
            )

    def get(self, material_id: int) -> Material:
        """Get material by ID."""
        if material_id not in self._materials:
            raise ValueError(f"Unknown material ID: {material_id}")
        return self._materials[material_id]

    def get_all(self) -> dict[int, Material]:
        """Get all materials."""
        return self._materials.copy()

    def get_by_name(self, name: str) -> Material | None:
        """Get material by name."""
        for material in self._materials.values():
            if material.name == name:
                return material
        return None

    def to_rule_buffer(self) -> list[float]:
        """Convert materials to flat float array for GPU rule buffer."""
        rules: list[float] = []
        for mat_id in range(NUM_TYPES):
            if mat_id in self._materials:
                m = self._materials[mat_id]
                rules.extend([
                    m.color[0] / 255.0,
                    m.color[1] / 255.0,
                    m.color[2] / 255.0,
                    m.density,
                    float(m.category),
                    m.flammability,
                    m.thermal_conductivity,
                    float(m.phase_high_id),
                    float(m.phase_high_temp),
                    float(m.phase_low_id),
                    float(m.phase_low_temp),
                    m.electrical_conductivity,
                    m.emissivity,
                    m.cooling_rate,
                    float(m.burn_to),
                    m.viscosity,
                    m.turbulence,
                    float(m.wet_dry),
                    # New fields (20 total so far)
                    m.heat_capacity,
                    float(m.melting_point),
                    float(m.boiling_point),
                    m.surface_tension,
                    m.solubility,
                    m.cohesion,
                    m.restitution,
                    float(m.state_family),
                    # Reaction slots (15 floats)
                    float(m.reaction_1_partner),
                    float(m.reaction_1_product_self),
                    float(m.reaction_1_product_neighbor),
                    m.reaction_1_prob,
                    float(m.reaction_1_temp_threshold),
                    float(m.reaction_2_partner),
                    float(m.reaction_2_product_self),
                    float(m.reaction_2_product_neighbor),
                    m.reaction_2_prob,
                    float(m.reaction_2_temp_threshold),
                    float(m.reaction_3_partner),
                    float(m.reaction_3_product_self),
                    float(m.reaction_3_product_neighbor),
                    m.reaction_3_prob,
                    float(m.reaction_3_temp_threshold),
                    # Explosive properties (6 floats)
                    m.explosive_power,
                    float(m.detonation_temp),
                    float(m.blast_radius),
                    float(m.blast_duration),
                    float(m.fragment_type),
                    m.shockwave_speed,
                    # Oxygen / combustion properties (2 floats)
                    m.oxygen_requirement,
                    m.oxygen_yield,
                ])
            else:
                # Pad with zeros for undefined materials
                rules.extend([0.0] * RULE_STRIDE)
        return rules

    def pack_cell(self, material_id: int, life: int | None = None, flags: int = 0) -> int:
        """Pack a cell for the given material.

        Cell packing: type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
        Temperature is stored separately in r32f float textures.
        """
        mat = self.get(material_id)
        if life is None:
            life = mat.default_flame_life
        packed = (material_id & 0xFF) | ((life & 0xFF) << 8) | ((flags & 0xFF) << 16)
        return int(packed)


# Global instance for backward compatibility
_registry = MaterialRegistry()


def get_material(material_id: int) -> Material:
    """Get material from global registry."""
    return _registry.get(material_id)


def get_all_materials() -> dict[int, Material]:
    """Get all materials from global registry."""
    return _registry.get_all()


def to_rule_buffer() -> list[float]:
    """Convert materials to rule buffer format."""
    return _registry.to_rule_buffer()


def pack_cell(material_id: int, life: int | None = None, flags: int = 0) -> int:
    """Pack a cell for the given material using global registry."""
    return _registry.pack_cell(material_id, life, flags)
