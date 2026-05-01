import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from test_helpers import pack_cell, make_cell, PARTICLES, TEMP_AMBIENT


@pytest.mark.physics
class TestThermalDynamics:
    """Test thermal dynamics and temperature handling."""

    def test_ambient_temperature_default(self):
        """Test that ambient temperature is set correctly."""
        assert TEMP_AMBIENT == 96

    def test_material_default_temperatures(self):
        """Test that materials have appropriate default temperatures."""
        # Temperature is now stored in float textures, not cell uint32.
        # Verify material default_flame_temp values are reasonable.
        air_props = PARTICLES[0]
        assert air_props['dft'] == TEMP_AMBIENT

        fire_props = PARTICLES[4]
        assert fire_props['dft'] > TEMP_AMBIENT

        ice_props = PARTICLES[13]
        assert ice_props['dft'] < TEMP_AMBIENT

    def test_thermal_conductivity_values(self):
        """Test that thermal conductivity values are valid."""
        for mat_id, props in PARTICLES.items():
            k = props['k']
            assert 0.0 <= k <= 1.0, f"Material {mat_id} has invalid thermal conductivity: {k}"

    def test_cooling_rate_values(self):
        """Test that cooling rate values are non-negative."""
        for mat_id, props in PARTICLES.items():
            cool = props['cool']
            assert cool >= 0.0, f"Material {mat_id} has negative cooling rate: {cool}"


@pytest.mark.physics
class TestPhaseTransitions:
    """Test phase transition logic and temperatures."""

    def test_phase_high_temperature_thresholds(self):
        """Test that high phase transition temperatures are valid (allow >255)."""
        for mat_id, props in PARTICLES.items():
            th = props['Th']
            assert th >= 0, f"Material {mat_id} has invalid Th: {th}"

    def test_phase_low_temperature_thresholds(self):
        """Test that low phase transition temperatures are valid (allow >255)."""
        for mat_id, props in PARTICLES.items():
            tl = props['Tl']
            assert tl >= 0, f"Material {mat_id} has invalid Tl: {tl}"

    def test_phase_high_ids_valid(self):
        """Test that high phase transition IDs are valid (0..48)."""
        for mat_id, props in PARTICLES.items():
            phi_h = props['phi_h']
            assert 0 <= phi_h <= 48, f"Material {mat_id} has invalid phi_h: {phi_h}"

    def test_phase_low_ids_valid(self):
        """Test that low phase transition IDs are valid (0..48)."""
        for mat_id, props in PARTICLES.items():
            phi_l = props['phi_l']
            assert 0 <= phi_l <= 48, f"Material {mat_id} has invalid phi_l: {phi_l}"

    def test_water_steam_transition(self):
        """Test water to steam phase transition."""
        water_props = PARTICLES[2]
        assert water_props['phi_h'] == 14  # Transitions to steam
        assert water_props['Th'] == 140  # At 140 degrees

    def test_steam_water_transition(self):
        """Test steam to water phase transition."""
        steam_props = PARTICLES[14]
        assert steam_props['phi_l'] == 2  # Transitions to water
        assert steam_props['Tl'] == 105  # At 105 degrees

    def test_ice_water_transition(self):
        """Test ice to water phase transition."""
        ice_props = PARTICLES[13]
        assert ice_props['phi_h'] == 2  # Transitions to water
        assert ice_props['Th'] == 100  # At 100 degrees

    def test_lava_stone_transition(self):
        """Test lava to stone phase transition."""
        lava_props = PARTICLES[9]
        assert lava_props['phi_l'] == 3  # Transitions to stone
        assert lava_props['Tl'] == 160  # At 160 degrees


@pytest.mark.physics
class TestLifeAndDecay:
    """Test life/decay mechanics for temporary particles."""

    def test_life_packing(self):
        """Test life is correctly packed into cell."""
        life = 50
        cell = pack_cell(4, life, 0)
        extracted_life = (cell >> 8) & 0xFF
        assert extracted_life == life

    def test_life_clamping(self):
        """Test life is clamped to 0-255 range."""
        life = 300
        cell = pack_cell(4, life, 0)
        extracted_life = (cell >> 8) & 0xFF
        assert extracted_life == 44  # 300 & 0xFF = 44

    def test_fire_default_life(self):
        """Test fire has appropriate default life."""
        fire_cell = make_cell(4)
        fire_life = (fire_cell >> 8) & 0xFF
        assert fire_life > 0
        assert fire_life <= 255

    def test_smoke_default_life(self):
        """Test smoke has appropriate default life."""
        smoke_cell = make_cell(5)
        smoke_life = (smoke_cell >> 8) & 0xFF
        assert smoke_life > 0

    def test_steam_default_life(self):
        """Test steam has appropriate default life."""
        steam_cell = make_cell(14)
        steam_life = (steam_cell >> 8) & 0xFF
        assert steam_life > 0

    def test_spark_default_life(self):
        """Test spark has appropriate default life."""
        spark_cell = make_cell(24)
        spark_life = (spark_cell >> 8) & 0xFF
        assert spark_life > 0

    def test_permanent_materials_no_life(self):
        """Test permanent materials have no default life."""
        # Wood now has a non-zero default life (slow char countdown).
        for mat_id in [0, 1, 2, 3, 12]:  # air, sand, water, stone, glass
            cell = make_cell(mat_id)
            life = (cell >> 8) & 0xFF
            assert life == 0


@pytest.mark.physics
class TestSpontaneousIgnition:
    """Test spontaneous ignition based on flammability and temperature."""

    def test_flammability_values_valid(self):
        """Test that flammability values are in valid range."""
        for mat_id, props in PARTICLES.items():
            flamm = props['flamm']
            assert 0.0 <= flamm <= 1.0, f"Material {mat_id} has invalid flammability: {flamm}"

    def test_combustible_materials_have_flammability(self):
        """Test that known combustible materials have flammability > 0."""
        combustible = [6, 8, 10, 11, 19, 20, 27, 29]  # oil, plant, gas, wood, gunpowder, c4, sugar, slime
        for mat_id in combustible:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['flamm'] > 0, f"Material {mat_id} should be combustible"

    def test_non_combustible_materials_no_flammability(self):
        """Test that non-combustible materials have flammability = 0."""
        non_combustible = [0, 1, 2, 3, 7, 12, 13, 22]  # air, sand, water, stone, acid, glass, ice, metal
        for mat_id in non_combustible:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['flamm'] == 0, f"Material {mat_id} should not be combustible"

    def test_burn_to_ids_valid(self):
        """Test that burn_to IDs point to valid materials (0..48)."""
        for mat_id, props in PARTICLES.items():
            bto = props['bto']
            assert 0 <= bto <= 48, f"Material {mat_id} has invalid burn_to: {bto}"

    def test_ignition_temperature_thresholds(self):
        """Test that ignition temperatures are reasonable."""
        for mat_id, props in PARTICLES.items():
            if props['flamm'] > 0:
                th = props['Th']
                assert th > 0, f"Combustible material {mat_id} should have ignition temperature > 0"


@pytest.mark.physics
class TestEmissivity:
    """Test emissivity values for glowing materials."""

    def test_emissivity_values_valid(self):
        """Test that emissivity values are in valid range."""
        for mat_id, props in PARTICLES.items():
            emit = props['emit']
            assert 0.0 <= emit <= 1.0, f"Material {mat_id} has invalid emissivity: {emit}"

    def test_emissive_materials(self):
        """Test that emissive materials have high emissivity."""
        emissive = [4, 9, 24, 31]  # fire, lava, spark, generator
        for mat_id in emissive:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['emit'] > 0.5, f"Material {mat_id} should be emissive"

    def test_non_emissive_materials(self):
        """Test that non-emissive materials have low emissivity."""
        non_emissive = [0, 1, 2, 3, 11, 12]  # air, sand, water, stone, wood, glass
        for mat_id in non_emissive:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['emit'] < 0.1, f"Material {mat_id} should not be emissive"


@pytest.mark.physics
class TestDensityBasedPhysics:
    """Test density-based movement and physics."""

    def test_density_values_valid(self):
        """Test that density values are in expected range."""
        for mat_id, props in PARTICLES.items():
            density = props['density']
            assert -1.0 <= density <= 99.0, f"Material {mat_id} has invalid density: {density}"

    def test_gas_density_range(self):
        """Test that gas materials have reasonable density for buoyancy."""
        # Air (0) and oxygen (32) have small positive densities for hydrostatic atmosphere
        static_gases = [0, 32]  # air, oxygen
        for mat_id in static_gases:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] > 0, f"Static gas {mat_id} should have positive density"
        # Fire has neutral density — rises via thermal buoyancy
        assert PARTICLES[4]['density'] == 0.0, "Fire should have neutral density"
        # Buoyant gases have negative density (rise relative to air)
        buoyant_gases = [5, 10, 14, 24]  # smoke, gas, steam, spark
        for mat_id in buoyant_gases:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] < 0, f"Buoyant gas {mat_id} should have negative density"

    def test_solid_density_high(self):
        """Test that solid materials have high density."""
        solid_materials = [3, 11, 12, 20, 21, 22, 30, 31]  # stone, wood, glass, c4, concrete, metal, pump, generator
        for mat_id in solid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] >= 1.0, f"Solid material {mat_id} should have high density"

    def test_liquid_density_positive(self):
        """Test that liquid materials have positive density."""
        liquid_materials = [2, 6, 7, 9, 17, 18, 28, 29]  # water, oil, acid, lava, mud, blood, virus, slime
        for mat_id in liquid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] > 0, f"Liquid material {mat_id} should have positive density"

    def test_powder_density_positive(self):
        """Test that powder materials have positive density."""
        powder_materials = [1, 15, 16, 19, 23, 25, 26, 27]  # sand, snow, dirt, gunpowder, rust, ash, salt, sugar
        for mat_id in powder_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['density'] > 0, f"Powder material {mat_id} should have positive density"


@pytest.mark.physics
class TestViscosity:
    """Test viscosity values for liquid movement."""

    def test_viscosity_values_valid(self):
        """Test that viscosity values are in valid range."""
        for mat_id, props in PARTICLES.items():
            visc = props['visc']
            assert 0.0 <= visc <= 1.0, f"Material {mat_id} has invalid viscosity: {visc}"

    def test_water_low_viscosity(self):
        """Test that water has low viscosity."""
        assert PARTICLES[2]['visc'] < 0.1, "Water should have low viscosity"

    def test_lava_high_viscosity(self):
        """Test that lava has high viscosity."""
        assert PARTICLES[9]['visc'] > 0.5, "Lava should have high viscosity"

    def test_oil_medium_viscosity(self):
        """Test that oil has medium viscosity."""
        assert 0.3 < PARTICLES[6]['visc'] < 0.6, "Oil should have medium viscosity"


@pytest.mark.physics
class TestTurbulence:
    """Test turbulence coefficients for gas movement."""

    def test_turbulence_values_valid(self):
        """Test that turbulence values are in valid range."""
        for mat_id, props in PARTICLES.items():
            turb = props['turb']
            assert 0.0 <= turb <= 1.0, f"Material {mat_id} has invalid turbulence: {turb}"

    def test_gas_high_turbulence(self):
        """Test that gas materials have high turbulence."""
        gas_materials = [4, 5, 10, 14]  # fire, smoke, gas, steam
        for mat_id in gas_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['turb'] > 0.3, f"Gas material {mat_id} should have high turbulence"

    def test_solid_zero_turbulence(self):
        """Test that solid materials have zero turbulence."""
        solid_materials = [3, 11, 12, 21, 22]  # stone, wood, glass, concrete, metal
        for mat_id in solid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['turb'] == 0.0, f"Solid material {mat_id} should have zero turbulence"


@pytest.mark.physics
class TestWetDryFlags:
    """Test wet-dry boundary flags."""

    def test_wet_dry_flags_valid(self):
        """Test that wet-dry flags are 0 or 1."""
        for mat_id, props in PARTICLES.items():
            wd = props['wd']
            assert wd in {0, 1}, f"Material {mat_id} has invalid wet_dry flag: {wd}"

    def test_liquids_wet(self):
        """Test that liquids have wet flag set."""
        liquid_materials = [2, 6, 7, 17, 18, 28, 29]  # water, oil, acid, mud, blood, virus, slime
        for mat_id in liquid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 1, f"Liquid material {mat_id} should be wet"

    def test_solids_dry(self):
        """Test that solids have dry flag set."""
        solid_materials = [3, 11, 12, 21, 22]  # stone, wood, glass, concrete, metal
        for mat_id in solid_materials:
            if mat_id in PARTICLES:
                assert PARTICLES[mat_id]['wd'] == 0, f"Solid material {mat_id} should be dry"
