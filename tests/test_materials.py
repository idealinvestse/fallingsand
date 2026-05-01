import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NUM_TYPES, RULE_STRIDE
from simulation.materials import get_all_materials, to_rule_buffer
from test_helpers import PARTICLES


class TestMaterialDefinitions:
    """Test material definition data validation."""

    def test_all_material_ids_exist(self):
        """Test that IDs 0-31 exist in the legacy PARTICLES dict."""
        for i in range(32):
            assert i in PARTICLES, f"Material ID {i} is missing from PARTICLES dict"

    def test_required_properties_exist(self):
        """Test that each material has all required properties."""
        required_props = [
            'color', 'density', 'cat', 'flamm', 'k', 
            'phi_h', 'Th', 'phi_l', 'Tl', 'cond', 
            'emit', 'cool', 'bto', 'visc', 'turb', 
            'wd', 'dft', 'dfl'
        ]

        for mat_id, props in PARTICLES.items():
            for prop in required_props:
                assert prop in props, f"Material {mat_id} missing property '{prop}'"

    def test_color_validity(self):
        """Test that color values are valid RGB tuples (0-255)."""
        for mat_id, props in PARTICLES.items():
            color = props['color']
            assert isinstance(color, tuple), f"Material {mat_id} color is not a tuple"
            assert len(color) == 3, f"Material {mat_id} color does not have 3 components"

            for c in color:
                assert isinstance(c, int), f"Material {mat_id} has non-int color component"
                assert 0 <= c <= 255, f"Material {mat_id} has color component out of range: {c}"

    def test_density_range(self):
        """Test that density values are within expected range."""
        for mat_id, props in PARTICLES.items():
            density = props['density']
            assert isinstance(density, (int, float)), f"Material {mat_id} density is not numeric"
            assert -1.0 <= density <= 99.0, f"Material {mat_id} density out of range: {density}"

    def test_category_validity(self):
        """Test that category values are valid (0=Gas, 1=Powder, 2=Liquid, 3=Solid)."""
        valid_categories = {0, 1, 2, 3}
        for mat_id, props in PARTICLES.items():
            cat = props['cat']
            assert cat in valid_categories, f"Material {mat_id} has invalid category: {cat}"

    def test_flammability_range(self):
        """Test that flammability values are in range [0.0, 1.0]."""
        for mat_id, props in PARTICLES.items():
            flamm = props['flamm']
            assert isinstance(flamm, (int, float)), f"Material {mat_id} flamm is not numeric"
            assert 0.0 <= flamm <= 1.0, f"Material {mat_id} flammability out of range: {flamm}"

    def test_thermal_conductivity_range(self):
        """Test that thermal conductivity (k) is non-negative."""
        for mat_id, props in PARTICLES.items():
            k = props['k']
            assert isinstance(k, (int, float)), f"Material {mat_id} k is not numeric"
            assert k >= 0.0, f"Material {mat_id} thermal conductivity is negative: {k}"

    def test_phase_transition_ids_valid(self):
        """Test that phase transition IDs are valid material IDs (0..48)."""
        for mat_id, props in PARTICLES.items():
            phi_h = props['phi_h']
            phi_l = props['phi_l']

            assert 0 <= phi_h <= 48, f"Material {mat_id} phi_h is invalid: {phi_h}"
            assert 0 <= phi_l <= 48, f"Material {mat_id} phi_l is invalid: {phi_l}"

    def test_phase_transition_temperatures_valid(self):
        """Test that phase transition temperatures are valid (allow >255)."""
        for mat_id, props in PARTICLES.items():
            th = props['Th']
            tl = props['Tl']

            assert th >= 0, f"Material {mat_id} Th out of range: {th}"
            assert tl >= 0, f"Material {mat_id} Tl out of range: {tl}"

    def test_electrical_conductivity_range(self):
        """Test that electrical conductivity is in range [0.0, 1.0]."""
        for mat_id, props in PARTICLES.items():
            cond = props['cond']
            assert isinstance(cond, (int, float)), f"Material {mat_id} cond is not numeric"
            assert 0.0 <= cond <= 1.0, f"Material {mat_id} electrical conductivity out of range: {cond}"

    def test_emissivity_range(self):
        """Test that emissivity is in range [0.0, 1.0]."""
        for mat_id, props in PARTICLES.items():
            emit = props['emit']
            assert isinstance(emit, (int, float)), f"Material {mat_id} emit is not numeric"
            assert 0.0 <= emit <= 1.0, f"Material {mat_id} emissivity out of range: {emit}"

    def test_cooling_rate_non_negative(self):
        """Test that cooling rate is non-negative."""
        for mat_id, props in PARTICLES.items():
            cool = props['cool']
            assert isinstance(cool, (int, float)), f"Material {mat_id} cool is not numeric"
            assert cool >= 0.0, f"Material {mat_id} cooling rate is negative: {cool}"

    def test_burn_to_id_valid(self):
        """Test that burn_to ID is a valid material ID (0..48)."""
        for mat_id, props in PARTICLES.items():
            bto = props['bto']
            assert 0 <= bto <= 48, f"Material {mat_id} burn_to is invalid: {bto}"

    def test_viscosity_range(self):
        """Test that viscosity is in range [0.0, 1.0]."""
        for mat_id, props in PARTICLES.items():
            visc = props['visc']
            assert isinstance(visc, (int, float)), f"Material {mat_id} visc is not numeric"
            assert 0.0 <= visc <= 1.0, f"Material {mat_id} viscosity out of range: {visc}"

    def test_turbulence_range(self):
        """Test that turbulence coefficient is in range [0.0, 1.0]."""
        for mat_id, props in PARTICLES.items():
            turb = props['turb']
            assert isinstance(turb, (int, float)), f"Material {mat_id} turb is not numeric"
            assert 0.0 <= turb <= 1.0, f"Material {mat_id} turbulence out of range: {turb}"

    def test_wet_dry_flag_valid(self):
        """Test that wet_dry flag is 0 or 1."""
        for mat_id, props in PARTICLES.items():
            wd = props['wd']
            assert wd in {0, 1}, f"Material {mat_id} wet_dry flag is invalid: {wd}"

    def test_default_temp_valid(self):
        """Test that default temperature is valid (allow >255)."""
        for mat_id, props in PARTICLES.items():
            dft = props['dft']
            assert dft >= 0, f"Material {mat_id} default temp out of range: {dft}"

    def test_default_life_valid(self):
        """Test that default life is in range [0, 255]."""
        for mat_id, props in PARTICLES.items():
            dfl = props['dfl']
            assert 0 <= dfl <= 255, f"Material {mat_id} default life out of range: {dfl}"

    def test_material_names_unique(self):
        """Test that material names are unique."""
        names = [props['name'] for props in PARTICLES.values()]
        assert len(names) == len(set(names)), "Material names are not unique"

    def test_gas_category_materials(self):
        """Test that gas category materials have reasonable density for buoyancy."""
        # Air (0) and oxygen (32) have small positive density for hydrostatic atmosphere
        static_gas_ids = {0, 32}
        # Fire (4) has neutral density — rises via thermal buoyancy (dT term)
        neutral_gas_ids = {4}
        for mat_id, props in PARTICLES.items():
            if props['cat'] == 0:  # Gas
                if mat_id in static_gas_ids:
                    assert props['density'] > 0, f"Static gas {mat_id} should have positive density"
                elif mat_id in neutral_gas_ids:
                    assert props['density'] == 0.0, f"Neutral gas {mat_id} should have zero density"
                else:
                    assert props['density'] < 0, f"Buoyant gas {mat_id} should have negative density"

    def test_solid_category_materials(self):
        """Test that solid category materials have high density."""
        for mat_id, props in PARTICLES.items():
            if props['cat'] == 3:  # Solid
                assert props['density'] >= 1.0, f"Solid material {mat_id} should have high density"

    def test_liquid_category_materials(self):
        """Test that liquid category materials have positive density."""
        for mat_id, props in PARTICLES.items():
            if props['cat'] == 2:  # Liquid
                assert props['density'] > 0, f"Liquid material {mat_id} should have positive density"

    def test_powder_category_materials(self):
        """Test that powder category materials have positive density."""
        for mat_id, props in PARTICLES.items():
            if props['cat'] == 1:  # Powder
                assert props['density'] > 0, f"Powder material {mat_id} should have positive density"

    def test_combustible_materials(self):
        """Test that combustible materials have flammability > 0."""
        combustible_ids = {6, 8, 11, 19, 20, 27, 29, 10}  # oil, plant, wood, gunpowder, c4, sugar, slime, gas
        for mat_id in combustible_ids:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['flamm'] > 0, f"Material {mat_id} should be combustible"

    def test_conductive_materials(self):
        """Test that conductive materials have cond > 0."""
        conductive_ids = {2, 18, 22, 30, 31}  # water, blood, metal, pump, generator
        for mat_id in conductive_ids:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cond'] > 0, f"Material {mat_id} should be conductive"

    def test_specific_material_properties(self):
        """Test specific known material properties."""
        # Air
        assert PARTICLES[0]['name'] == 'air'
        assert PARTICLES[0]['density'] == 0.12  # Hydrostatic atmosphere density
        assert PARTICLES[0]['cat'] == 0  # Gas

        # Sand
        assert PARTICLES[1]['name'] == 'sand'
        assert PARTICLES[1]['cat'] == 1  # Powder
        assert PARTICLES[1]['density'] == 3.0

        # Water
        assert PARTICLES[2]['name'] == 'water'
        assert PARTICLES[2]['cat'] == 2  # Liquid
        assert PARTICLES[2]['density'] == 2.0
        assert PARTICLES[2]['wd'] == 1  # Wet

        # Fire
        assert PARTICLES[4]['name'] == 'fire'
        assert PARTICLES[4]['cat'] == 0  # Gas
        assert PARTICLES[4]['emit'] > 0.5  # High emissivity

        # Lava
        assert PARTICLES[9]['name'] == 'lava'
        assert PARTICLES[9]['cat'] == 2  # Liquid
        assert PARTICLES[9]['emit'] > 0.5  # High emissivity
        assert PARTICLES[9]['k'] > 0.3  # High thermal conductivity


class TestMaterialRegistrySanity:
    """Sanity checks against the authoritative material registry."""

    def test_registry_covers_all_material_ids(self):
        materials = get_all_materials()
        assert len(materials) == NUM_TYPES
        assert set(materials) == set(range(NUM_TYPES))

    def test_rule_buffer_length_matches_stride(self):
        rules = to_rule_buffer()
        assert len(rules) == NUM_TYPES * RULE_STRIDE

    def test_reaction_slots_are_valid(self):
        materials = get_all_materials()
        for mat_id, mat in materials.items():
            slots = (
                (mat.reaction_1_partner, mat.reaction_1_product_self, mat.reaction_1_product_neighbor, mat.reaction_1_prob, mat.reaction_1_temp_threshold),
                (mat.reaction_2_partner, mat.reaction_2_product_self, mat.reaction_2_product_neighbor, mat.reaction_2_prob, mat.reaction_2_temp_threshold),
                (mat.reaction_3_partner, mat.reaction_3_product_self, mat.reaction_3_product_neighbor, mat.reaction_3_prob, mat.reaction_3_temp_threshold),
            )
            for partner, prod_self, prod_neighbor, prob, temp_threshold in slots:
                if partner == prod_self == prod_neighbor == 0 and prob == 0.0 and temp_threshold == 0:
                    continue
                assert 0 <= partner < NUM_TYPES, f"Material {mat_id} has invalid reaction partner {partner}"
                assert 0 <= prod_self < NUM_TYPES, f"Material {mat_id} has invalid reaction self product {prod_self}"
                assert 0 <= prod_neighbor < NUM_TYPES, f"Material {mat_id} has invalid reaction neighbor product {prod_neighbor}"
                assert 0.0 <= prob <= 1.0, f"Material {mat_id} has invalid reaction probability {prob}"
                assert temp_threshold >= 0, f"Material {mat_id} has negative reaction temp threshold {temp_threshold}"
