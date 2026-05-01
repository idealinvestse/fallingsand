import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.materials import get_all_materials


class TestChemicalReactions:
    """Test chemical reaction definitions from materials.yaml."""

    def test_acid_dissolves_stone(self):
        """Acid (7) should have a reaction with stone (3) to produce air."""
        materials = get_all_materials()
        acid = materials[7]

        # Check reaction slot 1: acid + stone -> air
        assert acid.reaction_1_partner == 3, "Acid should react with stone"
        assert acid.reaction_1_product_self == 0, "Acid should become air when reacting with stone"
        assert acid.reaction_1_prob > 0, "Acid-stone reaction should have positive probability"

    def test_acid_dissolves_metal(self):
        """Acid (7) should have a reaction with metal (22) to produce rust and steam."""
        materials = get_all_materials()
        acid = materials[7]

        # Check reaction slot 2: acid + metal -> rust + steam
        assert acid.reaction_2_partner == 22, "Acid should react with metal"
        assert acid.reaction_2_product_self == 23, "Acid should become rust when reacting with metal"
        assert acid.reaction_2_product_neighbor == 14, "Metal should become steam"
        assert acid.reaction_2_prob > 0, "Acid-metal reaction should have positive probability"

    def test_acid_dissolves_glass(self):
        """Acid (7) should have a reaction with glass (12) to produce air."""
        materials = get_all_materials()
        acid = materials[7]

        # Check reaction slot 3: acid + glass -> air
        assert acid.reaction_3_partner == 12, "Acid should react with glass"
        assert acid.reaction_3_product_self == 0, "Acid should become air when reacting with glass"
        assert acid.reaction_3_prob > 0, "Acid-glass reaction should have positive probability"

    def test_salt_dissolves_in_water(self):
        """Salt (26) should dissolve in water (2) to become brine (46)."""
        materials = get_all_materials()
        salt = materials[26]

        # Check reaction slot 1: salt + water -> brine
        assert salt.reaction_1_partner == 2, "Salt should react with water"
        assert salt.reaction_1_product_self == 46, "Salt should become brine"
        assert salt.reaction_1_prob > 0, "Salt-water reaction should have positive probability"

    def test_cement_hardens_with_water(self):
        """Cement (44) should react with water (2) to become concrete (21)."""
        materials = get_all_materials()
        cement = materials[44]

        # Check reaction slot 1: cement + water -> concrete
        assert cement.reaction_1_partner == 2, "Cement should react with water"
        assert cement.reaction_1_product_self == 21, "Cement should become concrete"
        assert cement.reaction_1_prob > 0, "Cement-water reaction should have positive probability"
        # Slow reaction
        assert cement.reaction_1_prob < 0.1, "Cement hardening should be slow (low probability)"

    def test_bleach_kills_blood(self):
        """Bleach (43) should react with blood (18) to produce steam."""
        materials = get_all_materials()
        bleach = materials[43]

        # Check reaction slot 1: bleach + blood -> steam
        assert bleach.reaction_1_partner == 18, "Bleach should react with blood"
        assert bleach.reaction_1_product_self == 14, "Bleach should become steam when reacting with blood"
        assert bleach.reaction_1_prob > 0, "Bleach-blood reaction should have positive probability"

    def test_bleach_kills_virus(self):
        """Bleach (43) should react with virus (28) to produce air."""
        materials = get_all_materials()
        bleach = materials[43]

        # Check reaction slot 2: bleach + virus -> air
        assert bleach.reaction_2_partner == 28, "Bleach should react with virus"
        assert bleach.reaction_2_product_self == 0, "Bleach should become air when reacting with virus"
        assert bleach.reaction_2_prob > 0, "Bleach-virus reaction should have positive probability"

    def test_bleach_kills_slime(self):
        """Bleach (43) should react with slime (29) to produce air."""
        materials = get_all_materials()
        bleach = materials[43]

        # Check reaction slot 3: bleach + slime -> air
        assert bleach.reaction_3_partner == 29, "Bleach should react with slime"
        assert bleach.reaction_3_product_self == 0, "Bleach should become air when reacting with slime"
        assert bleach.reaction_3_prob > 0, "Bleach-slime reaction should have positive probability"

    def test_metal_corrodes_in_water_at_temp(self):
        """Metal (22) should slowly corrode in water (2) at elevated temperature to become rust."""
        materials = get_all_materials()
        metal = materials[22]

        # Check reaction slot 2: metal + water @ temp -> rust
        assert metal.reaction_2_partner == 2, "Metal should react with water"
        assert metal.reaction_2_product_self == 23, "Metal should become rust"
        assert metal.reaction_2_temp_threshold > 0, "Metal corrosion should require elevated temperature"
        assert metal.reaction_2_prob > 0, "Metal-water reaction should have positive probability"

    def test_plant_exudes_sap_with_water(self):
        """Plant (8) should react with water (2) to exude sap (47)."""
        materials = get_all_materials()
        plant = materials[8]

        # Check reaction slot 2: plant + water -> sap
        assert plant.reaction_2_partner == 2, "Plant should react with water"
        assert plant.reaction_2_product_self == 47, "Plant should exude sap"
        assert plant.reaction_2_prob > 0, "Plant-water reaction should have positive probability"

    def test_lava_with_water_produces_glass(self):
        """Lava (9) should react with water (2) to produce glass (12)."""
        materials = get_all_materials()
        lava = materials[9]

        # Check reaction slot 2: lava + water -> glass
        assert lava.reaction_2_partner == 2, "Lava should react with water"
        assert lava.reaction_2_product_self == 12, "Lava should become glass with water"
        assert lava.reaction_2_prob > 0, "Lava-water glass reaction should have positive probability"

    def test_dirt_to_mud_probability_reduced(self):
        """Dirt (16) + water (2) should have reduced probability to become mud."""
        materials = get_all_materials()
        dirt = materials[16]

        # Check reaction slot 1: dirt + water -> mud
        assert dirt.reaction_1_partner == 2, "Dirt should react with water"
        assert dirt.reaction_1_product_self == 17, "Dirt should become mud"
        # Probability should be significantly less than 1.0 (was 1.0, now 0.3)
        assert dirt.reaction_1_prob < 0.5, "Dirt-to-mud probability should be reduced"

    def test_new_materials_exist(self):
        """Verify all new materials (41-48) exist in the registry."""
        materials = get_all_materials()
        new_materials = {
            41: "mercury",
            42: "honey",
            43: "bleach",
            44: "cement",
            45: "quicksand",
            46: "brine",
            47: "sap",
            48: "magma",
        }

        for mat_id, expected_name in new_materials.items():
            assert mat_id in materials, f"Material ID {mat_id} missing from registry"
            assert materials[mat_id].name == expected_name, f"Material {mat_id} has wrong name: {materials[mat_id].name}"

    def test_mercury_electrical_conductivity(self):
        """Mercury (41) should be electrically conductive."""
        materials = get_all_materials()
        mercury = materials[41]

        assert mercury.electrical_conductivity > 0.5, "Mercury should be highly conductive"

    def test_mercury_density(self):
        """Mercury (41) should be denser than water (2)."""
        materials = get_all_materials()
        mercury = materials[41]
        water = materials[2]

        assert mercury.density > water.density, "Mercury should be denser than water"

    def test_honey_high_viscosity(self):
        """Honey (42) should have high viscosity."""
        materials = get_all_materials()
        honey = materials[42]

        assert honey.viscosity > 0.8, "Honey should have high viscosity"

    def test_honey_flammable(self):
        """Honey (42) should be flammable."""
        materials = get_all_materials()
        honey = materials[42]

        assert honey.flammability > 0.5, "Honey should be flammable"

    def test_brine_lower_freeze_point(self):
        """Brine (46) should have a lower freeze point than water."""
        materials = get_all_materials()
        brine = materials[46]
        water = materials[2]

        assert brine.phase_low_temp < water.phase_low_temp, "Brine should freeze at lower temperature than water"

    def test_magma_high_temperature(self):
        """Magma (48) should have high default temperature."""
        materials = get_all_materials()
        magma = materials[48]

        assert magma.default_flame_temp > 200, "Magma should have high default temperature"

    def test_magma_reacts_with_water(self):
        """Magma (48) should react with water (2) to produce stone and steam."""
        materials = get_all_materials()
        magma = materials[48]

        # Check reaction slot 1: magma + water -> stone + steam
        assert magma.reaction_1_partner == 2, "Magma should react with water"
        assert magma.reaction_1_product_self == 3, "Magma should become stone with water"
        assert magma.reaction_1_product_neighbor == 14, "Water should become steam"
        assert magma.reaction_1_prob > 0, "Magma-water reaction should have positive probability"
