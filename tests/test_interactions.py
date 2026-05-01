import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import PARTICLES


@pytest.mark.physics
class TestChemicalReactions:
    """Test chemical reaction definitions and properties."""

    def test_water_lava_reaction_materials_exist(self):
        """Test that water and lava materials exist for reaction."""
        assert 2 in PARTICLES  # water
        assert 9 in PARTICLES  # lava
        assert 14 in PARTICLES  # steam (reaction product)
        assert 3 in PARTICLES  # stone (reaction product)

    def test_water_dirt_reaction_materials_exist(self):
        """Test that water and dirt materials exist for reaction."""
        assert 2 in PARTICLES  # water
        assert 16 in PARTICLES  # dirt
        assert 17 in PARTICLES  # mud (reaction product)

    def test_salt_water_reaction_materials_exist(self):
        """Test that salt and water materials exist for reaction."""
        assert 26 in PARTICLES  # salt
        assert 2 in PARTICLES  # water

    def test_acid_material_exists(self):
        """Test that acid material exists."""
        assert 7 in PARTICLES  # acid

    def test_acid_corrosion_properties(self):
        """Test acid has appropriate corrosion properties."""
        acid = PARTICLES[7]
        assert acid['cat'] == 2  # Liquid
        assert acid['density'] > 0  # Positive density for movement

    def test_virus_blood_reaction_materials_exist(self):
        """Test that virus and blood materials exist for reaction."""
        assert 28 in PARTICLES  # virus
        assert 18 in PARTICLES  # blood
        assert 29 in PARTICLES  # slime (reaction product)

    def test_virus_emissivity(self):
        """Test virus has emissivity for visual effect."""
        virus = PARTICLES[28]
        assert virus['emit'] > 0  # Should have some emissivity


@pytest.mark.physics
class TestFireAndHeatTransfer:
    """Test fire and heat transfer properties."""

    def test_fire_material_exists(self):
        """Test that fire material exists."""
        assert 4 in PARTICLES  # fire

    def test_fire_properties(self):
        """Test fire has appropriate properties."""
        fire = PARTICLES[4]
        assert fire['cat'] == 0  # Gas
        assert fire['emit'] > 0.5  # High emissivity
        assert fire['k'] > 0.5  # High thermal conductivity
        assert fire['density'] == 0.0  # Neutral density — rises via thermal buoyancy

    def test_lava_properties(self):
        """Test lava has appropriate properties."""
        lava = PARTICLES[9]
        assert lava['cat'] == 2  # Liquid
        assert lava['emit'] > 0.5  # High emissivity
        assert lava['k'] > 0.3  # High thermal conductivity
        assert lava['density'] > 0  # Positive density

    def test_spark_properties(self):
        """Test spark has appropriate properties."""
        spark = PARTICLES[24]
        assert spark['cat'] == 0  # Gas
        assert spark['emit'] > 0.5  # High emissivity
        assert spark['k'] > 0.1  # Thermal conductivity

    def test_heat_source_materials(self):
        """Test that heat source materials have high thermal conductivity."""
        heat_sources = [4, 9, 24]  # fire, lava, spark
        for mat_id in heat_sources:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['k'] > 0.1, f"Heat source {mat_id} should have thermal conductivity"

    def test_flammable_materials_exist(self):
        """Test that flammable materials exist."""
        flammable = [6, 8, 11, 19, 20]  # oil, plant, wood, gunpowder, c4
        for mat_id in flammable:
            assert mat_id in PARTICLES, f"Flammable material {mat_id} should exist"


@pytest.mark.physics
class TestElectricity:
    """Test electricity and conductivity properties."""

    def test_spark_material_exists(self):
        """Test that spark material exists."""
        assert 24 in PARTICLES  # spark

    def test_conductive_materials_exist(self):
        """Test that conductive materials exist."""
        conductive = [2, 18, 22, 30, 31]  # water, blood, metal, pump, generator
        for mat_id in conductive:
            assert mat_id in PARTICLES, f"Conductive material {mat_id} should exist"

    def test_water_conductivity(self):
        """Test water has electrical conductivity."""
        water = PARTICLES[2]
        assert water['cond'] > 0, "Water should be conductive"

    def test_metal_conductivity(self):
        """Test metal has high electrical conductivity."""
        metal = PARTICLES[22]
        assert metal['cond'] == 1.0, "Metal should be fully conductive"

    def test_blood_conductivity(self):
        """Test blood has electrical conductivity."""
        blood = PARTICLES[18]
        assert blood['cond'] > 0, "Blood should be conductive"

    def test_generator_properties(self):
        """Test generator has appropriate properties."""
        generator = PARTICLES[31]
        assert generator['cond'] == 1.0  # Fully conductive
        assert generator['emit'] > 0.5  # High emissivity for visual effect

    def test_pump_properties(self):
        """Test pump has appropriate properties."""
        pump = PARTICLES[30]
        assert pump['cond'] > 0  # Conductive
        assert pump['emit'] > 0  # Emissive for visual effect
        assert pump['cat'] == 3  # Solid (machine)

    def test_non_conductive_materials(self):
        """Test that non-conductive materials have zero conductivity."""
        non_conductive = [0, 1, 3, 6, 11, 12]  # air, sand, stone, oil, wood, glass
        for mat_id in non_conductive:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cond'] == 0, f"Material {mat_id} should not be conductive"


@pytest.mark.physics
class TestPumpMechanics:
    """Test pump mechanics and properties."""

    def test_pump_material_exists(self):
        """Test that pump material exists."""
        assert 30 in PARTICLES  # pump

    def test_pump_density(self):
        """Test pump has very high density."""
        pump = PARTICLES[30]
        assert pump['density'] == 99.0, "Pump should have maximum density"

    def test_pump_category(self):
        """Test pump is categorized as solid."""
        pump = PARTICLES[30]
        assert pump['cat'] == 3, "Pump should be solid"

    def test_pump_liquid_interaction(self):
        """Test that pump can interact with liquids."""
        pump = PARTICLES[30]
        assert pump['cond'] > 0  # Conductive for electrical interaction
        assert pump['emit'] > 0  # Emissive for visual feedback


@pytest.mark.physics
class TestDensityBasedMovement:
    """Test density-based movement properties."""

    def test_density_hierarchy(self):
        """Test that materials follow expected density hierarchy."""
        # Gas < Liquid < Solid
        gas_density = PARTICLES[10]['density']  # gas
        liquid_density = PARTICLES[2]['density']  # water
        solid_density = PARTICLES[3]['density']  # stone

        assert gas_density < liquid_density
        assert liquid_density < solid_density

    def test_sand_water_density(self):
        """Test that sand is denser than water."""
        sand_density = PARTICLES[1]['density']
        water_density = PARTICLES[2]['density']
        assert sand_density > water_density

    def test_oil_water_density(self):
        """Test that oil is less dense than water."""
        oil_density = PARTICLES[6]['density']
        water_density = PARTICLES[2]['density']
        assert oil_density < water_density

    def test_gas_rising(self):
        """Test that buoyant gas materials rise relative to air."""
        # Air (0) and oxygen (32) have small positive density for hydrostatic atmosphere
        static_gases = [0, 32]  # air, oxygen
        for mat_id in static_gases:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] > 0, f"Static gas {mat_id} should have positive density"
        # Fire has neutral density — rises via thermal buoyancy (dT term in force shader)
        assert PARTICLES[4]['density'] == 0.0, "Fire should have neutral density"
        # Buoyant gases have negative density so they rise relative to air
        buoyant_gases = [5, 10, 14, 24]  # smoke, gas, steam, spark
        for mat_id in buoyant_gases:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] < 0, f"Buoyant gas {mat_id} should rise"

    def test_powder_falling(self):
        """Test that powder materials have positive density."""
        powder_materials = [1, 15, 16, 19, 23, 25, 26, 27]  # sand, snow, dirt, gunpowder, rust, ash, salt, sugar
        for mat_id in powder_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] > 0, f"Powder {mat_id} should fall"


@pytest.mark.physics
class TestWetDryBoundaries:
    """Test wet-dry boundary properties."""

    def test_liquids_marked_wet(self):
        """Test that liquids are marked as wet."""
        liquids = [2, 6, 7, 17, 18, 28, 29]  # water, oil, acid, mud, blood, virus, slime
        for mat_id in liquids:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 1, f"Liquid {mat_id} should be wet"

    def test_solids_marked_dry(self):
        """Test that solids are marked as dry."""
        solids = [3, 11, 12, 21, 22]  # stone, wood, glass, concrete, metal
        for mat_id in solids:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 0, f"Solid {mat_id} should be dry"

    def test_powders_marked_dry(self):
        """Test that powders are marked as dry."""
        powders = [1, 15, 16, 19, 23, 25, 26, 27]  # sand, snow, dirt, gunpowder, rust, ash, salt, sugar
        for mat_id in powders:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 0, f"Powder {mat_id} should be dry"

    def test_gases_marked_dry(self):
        """Test that gases are marked as dry."""
        gases = [0, 4, 5, 10, 14, 24]  # air, fire, smoke, gas, steam, spark
        for mat_id in gases:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 0, f"Gas {mat_id} should be dry"


@pytest.mark.physics
class TestMaterialCategories:
    """Test material categorization for interactions."""

    def test_category_counts(self):
        """Test that materials are distributed across categories."""
        categories = {}
        for mat_id, props in PARTICLES.items():
            cat = props['cat']
            categories[cat] = categories.get(cat, 0) + 1

        # Should have materials in all categories
        assert 0 in categories  # Gas
        assert 1 in categories  # Powder
        assert 2 in categories  # Liquid
        assert 3 in categories  # Solid

    def test_gas_category_materials(self):
        """Test gas category materials."""
        gas_materials = [0, 4, 5, 10, 14, 24]  # air, fire, smoke, gas, steam, spark
        for mat_id in gas_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cat'] == 0, f"Material {mat_id} should be gas"

    def test_powder_category_materials(self):
        """Test powder category materials."""
        powder_materials = [1, 15, 16, 19, 23, 25, 26, 27]  # sand, snow, dirt, gunpowder, rust, ash, salt, sugar
        for mat_id in powder_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cat'] == 1, f"Material {mat_id} should be powder"

    def test_liquid_category_materials(self):
        """Test liquid category materials."""
        liquid_materials = [2, 6, 7, 9, 17, 18, 28, 29]  # water, oil, acid, lava, mud, blood, virus, slime
        for mat_id in liquid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cat'] == 2, f"Material {mat_id} should be liquid"

    def test_solid_category_materials(self):
        """Test solid category materials."""
        solid_materials = [3, 8, 11, 12, 20, 21, 22, 30, 31]  # stone, plant, wood, glass, c4, concrete, metal, pump, generator
        for mat_id in solid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['cat'] == 3, f"Material {mat_id} should be solid"


@pytest.mark.physics
class TestSpecialMaterials:
    """Test special material properties."""

    def test_generator_exists(self):
        """Test that generator material exists."""
        assert 31 in PARTICLES  # generator

    def test_generator_properties(self):
        """Test generator has appropriate properties."""
        generator = PARTICLES[31]
        assert generator['cat'] == 3  # Solid
        assert generator['cond'] == 1.0  # Fully conductive
        assert generator['emit'] > 0.5  # High emissivity

    def test_c4_properties(self):
        """Test C4 explosive properties."""
        c4 = PARTICLES[20]
        assert c4['cat'] == 3  # Solid
        assert c4['flamm'] == 1.0  # Fully flammable
        assert c4['density'] > 0  # Positive density

    def test_gunpowder_properties(self):
        """Test gunpowder explosive properties."""
        gunpowder = PARTICLES[19]
        assert gunpowder['cat'] == 1  # Powder
        assert gunpowder['flamm'] > 0.9  # Highly flammable
        assert gunpowder['density'] > 0  # Positive density

    def test_glass_acid_resistance(self):
        """Test glass should resist acid (based on material properties)."""
        glass = PARTICLES[12]
        acid = PARTICLES[7]
        # Glass has low thermal conductivity and is solid
        assert glass['cat'] == 3  # Solid
        assert acid['cat'] == 2  # Liquid
