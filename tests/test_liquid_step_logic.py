import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.materials import get_all_materials


class TestLiquidStepLogic:
    """Test liquid physics logic (density ordering, viscosity, surface tension)."""

    def test_mercury_denser_than_water(self):
        """Mercury (41) should be denser than water (2) for density separation."""
        materials = get_all_materials()
        mercury = materials[41]
        water = materials[2]

        assert mercury.density > water.density, "Mercury should sink below water due to higher density"
        # Density difference should be significant for clear separation
        assert mercury.density - water.density > 3.0, "Density difference should be significant"

    def test_water_denser_than_oil(self):
        """Water (2) should be denser than oil (6) for density separation."""
        materials = get_all_materials()
        water = materials[2]
        oil = materials[6]

        assert water.density > oil.density, "Water should sink below oil due to higher density"

    def test_brine_denser_than_water(self):
        """Brine (46) should be denser than water (2) for density separation."""
        materials = get_all_materials()
        brine = materials[46]
        water = materials[2]

        assert brine.density > water.density, "Brine should sink below water due to higher density"

    def test_honey_denser_than_water(self):
        """Honey (42) should be denser than water (2)."""
        materials = get_all_materials()
        honey = materials[42]
        water = materials[2]

        assert honey.density > water.density, "Honey should be denser than water"

    def test_honey_high_viscosity(self):
        """Honey (42) should have high viscosity to limit sideways spread."""
        materials = get_all_materials()
        honey = materials[42]

        assert honey.viscosity > 0.8, "Honey should have high viscosity for slow spread"
        # Viscosity should be significantly higher than water
        water = materials[2]
        assert honey.viscosity > water.viscosity + 0.5, "Honey viscosity should be much higher than water"

    def test_lava_high_viscosity(self):
        """Lava (9) should have high viscosity for slow spread."""
        materials = get_all_materials()
        lava = materials[9]

        assert lava.viscosity > 0.5, "Lava should have high viscosity for slow spread"

    def test_water_low_viscosity(self):
        """Water (2) should have low viscosity for free flow."""
        materials = get_all_materials()
        water = materials[2]

        assert water.viscosity < 0.2, "Water should have low viscosity for free flow"

    def test_water_surface_tension(self):
        """Water (2) should have moderate surface tension for grouping."""
        materials = get_all_materials()
        water = materials[2]

        assert water.surface_tension > 0, "Water should have some surface tension"
        assert water.surface_tension <= 1.0, "Surface tension should be in valid range"

    def test_honey_surface_tension(self):
        """Honey (42) should have higher surface tension than water."""
        materials = get_all_materials()
        honey = materials[42]
        water = materials[2]

        assert honey.surface_tension > water.surface_tension, "Honey should have higher surface tension"

    def test_salt_solubility(self):
        """Salt (26) should have solubility > 0 for dissolution in water."""
        materials = get_all_materials()
        salt = materials[26]

        assert salt.solubility > 0, "Salt should be soluble in water"

    def test_sugar_solubility(self):
        """Sugar (27) should have solubility > 0 for dissolution in water."""
        materials = get_all_materials()
        sugar = materials[27]

        assert sugar.solubility > 0, "Sugar should be soluble in water"

    def test_water_not_soluble(self):
        """Water (2) should have solubility = 0 (it is the solvent, not solute)."""
        materials = get_all_materials()
        water = materials[2]

        assert water.solubility == 0, "Water should not be soluble (it is the solvent)"

    def test_liquid_categories(self):
        """All liquid materials should have category 2."""
        materials = get_all_materials()
        liquid_ids = {2, 6, 7, 9, 41, 42, 43, 45, 46, 47}  # water, oil, acid, lava, mercury, honey, bleach, quicksand, brine, sap

        for mat_id in liquid_ids:
            assert mat_id in materials, f"Material ID {mat_id} missing from registry"
            assert materials[mat_id].category == 2, f"Material {mat_id} should be liquid category"

    def test_density_ordering_key_materials(self):
        """Verify density ordering of key liquid materials."""
        materials = get_all_materials()

        mercury = materials[41].density
        brine = materials[46].density
        honey = materials[42].density
        water = materials[2].density
        oil = materials[6].density

        # Expected order (heaviest to lightest): mercury > honey > brine > water > oil
        assert mercury > honey, "Mercury should be denser than honey"
        assert honey > brine, "Honey should be denser than brine"
        assert brine > water, "Brine should be denser than water"
        assert water > oil, "Water should be denser than oil"

    def test_quicksand_liquid_category(self):
        """Quicksand (45) should be liquid category despite powder-like behavior."""
        materials = get_all_materials()
        quicksand = materials[45]

        assert quicksand.category == 2, "Quicksand should be liquid category"

    def test_quicksand_viscosity(self):
        """Quicksand (45) should have moderate-high viscosity."""
        materials = get_all_materials()
        quicksand = materials[45]

        assert quicksand.viscosity > 0.5, "Quicksand should have moderate-high viscosity"

    def test_all_liquids_have_positive_density(self):
        """All liquids should have positive density (they should sink, not float)."""
        materials = get_all_materials()

        for mat_id, mat in materials.items():
            if mat.category == 2:  # Liquid
                assert mat.density > 0, f"Liquid material {mat_id} ({mat.name}) should have positive density"
