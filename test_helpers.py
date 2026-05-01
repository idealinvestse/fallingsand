"""
Helper module for testing - imports constants and materials from the actual source
to avoid duplication and ensure consistency.
"""
import numpy as np
from dataclasses import fields

# Import from actual source files
from core.constants import TEMP_AMBIENT
from simulation.materials import get_all_materials, pack_cell as pack_cell_impl


def _material_to_dict(mat):
    """Convert a slotted Material dataclass to a dict (backward compatible format)."""
    # Map new field names to old short field names for backward compatibility
    name_mapping = {
        'category': 'cat',
        'flammability': 'flamm',
        'thermal_conductivity': 'k',
        'phase_high_id': 'phi_h',
        'phase_high_temp': 'Th',
        'phase_low_id': 'phi_l',
        'phase_low_temp': 'Tl',
        'electrical_conductivity': 'cond',
        'emissivity': 'emit',
        'cooling_rate': 'cool',
        'burn_to': 'bto',
        'viscosity': 'visc',
        'turbulence': 'turb',
        'wet_dry': 'wd',
        'default_flame_temp': 'dft',
        'default_flame_life': 'dfl',
        'heat_capacity': 'cp',
        'melting_point': 'mp',
        'boiling_point': 'bp',
        'surface_tension': 'st',
        'solubility': 'sol',
        'cohesion': 'coh',
        'restitution': 'rest',
        'state_family': 'sf',
        'reaction_1_partner': 'rxn1_p',
        'reaction_1_product_self': 'rxn1_ps',
        'reaction_1_product_neighbor': 'rxn1_pn',
        'reaction_1_prob': 'rxn1_prob',
        'reaction_1_temp_threshold': 'rxn1_tt',
        'reaction_2_partner': 'rxn2_p',
        'reaction_2_product_self': 'rxn2_ps',
        'reaction_2_product_neighbor': 'rxn2_pn',
        'reaction_2_prob': 'rxn2_prob',
        'reaction_2_temp_threshold': 'rxn2_tt',
        'reaction_3_partner': 'rxn3_p',
        'reaction_3_product_self': 'rxn3_ps',
        'reaction_3_product_neighbor': 'rxn3_pn',
        'reaction_3_prob': 'rxn3_prob',
        'reaction_3_temp_threshold': 'rxn3_tt',
        'explosive_power': 'expPow',
        'detonation_temp': 'detTemp',
        'blast_radius': 'blastRad',
        'blast_duration': 'blastDur',
        'fragment_type': 'fragType',
        'shockwave_speed': 'swSpeed',
        'oxygen_requirement': 'o2Req',
        'oxygen_yield': 'o2Yield',
    }
    result = {}
    for f in fields(mat):
        value = getattr(mat, f.name)
        # Use old short name if mapping exists, otherwise use original name
        key = name_mapping.get(f.name, f.name)
        result[key] = value
    return result


# Backward compatibility alias
PARTICLES = {mat_id: _material_to_dict(mat) for mat_id, mat in get_all_materials().items()}

def pack_cell(typ, life=0, flags=0):
    """Pack cell data into a uint32.

    Cell packing: type[0..7] | life[8..15] | flags[16..23] | unused[24..31]
    Temperature is stored separately in r32f float textures.
    """
    return pack_cell_impl(typ, life, flags)

def make_cell(typ):
    """Create a cell with default values for the given material type.

    Temperature is stored in float textures, not in the cell uint32.
    """
    from simulation.materials import get_material
    mat = get_material(typ)
    return pack_cell(typ, mat.default_flame_life, 0)

def read_stats(buf):
    """Read statistics from grid buffer.

    Note: Temperature is no longer stored in the cell uint32.
    The avg_temp field is always 0 (temperature lives in float textures).
    """
    raw = np.frombuffer(buf.read(), dtype=np.uint32)
    types = raw & 0xFF
    return {
        "water": int(np.count_nonzero(types == 2)),
        "steam": int(np.count_nonzero(types == 14)),
        "fire": int(np.count_nonzero(types == 4)),
        "avg_temp": 0.0,  # Temperature is in float textures, not cell buffer
    }
