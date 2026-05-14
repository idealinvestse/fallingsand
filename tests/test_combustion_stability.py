"""Regression coverage for the combustion overhaul balance rules."""

from pathlib import Path

from simulation.materials import get_material


ROOT = Path(__file__).parent.parent


class TestAtmosphereIgnitionStability:
    def test_gas_requires_high_heat_and_oxidizer(self):
        gas = get_material(10)
        assert gas.flammability <= 0.5
        assert gas.phase_high_temp >= 190
        assert gas.oxygen_requirement >= 0.65

    def test_air_only_ignition_is_weak_and_gated(self):
        src = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        assert "weakAirOnly" in src
        assert "airCount >= 3" in src
        assert "strongIgnition" in src
        assert "explicitO2Count > 0 || (weakAirOnly && strongIgnition)" in src


class TestCombustionStagesAndByproducts:
    def test_organic_fuels_have_char_stage(self):
        src = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        for token in ("T_WOOD", "T_PLANT", "T_SUGAR", "T_HONEY", "T_SAP"):
            assert token in src
        assert "writeCell(idx, p, T_CHAR" in src

    def test_char_and_soot_are_balanced_byproducts(self):
        char = get_material(57)
        soot = get_material(58)
        assert char.name == "char"
        assert char.phase_high_id == 33
        assert char.burn_to == 25
        assert soot.name == "soot"
        assert soot.category.value == 0
        assert soot.flammability == 0.0

    def test_dirty_fuels_make_soot_based_on_oxygen_availability(self):
        src = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        assert "nearDirtyFuel" in src
        assert "oxygenAvailability" in src
        assert "sootProb *= mix(1.45, 0.45, oxygenAvailability)" in src


class TestMoistureWeatherSuppression:
    def test_moisture_and_humidity_suppress_fire(self):
        src = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        assert "moistureIn" in src
        assert "humidityIn" in src
        assert "effectiveWet" in src
        assert "wetIgnitionBoost" in src

    def test_wind_affects_fire_and_byproducts(self):
        src = (ROOT / "shaders" / "force_shader.glsl").read_text(encoding="utf-8")
        assert "T_FIRE || typ == T_EMBER || typ == T_CHAR || typ == T_SOOT" in src
        assert "windCoupling" in src


class TestMoistureMaterialProperties:
    def test_wood_is_more_moisture_sensitive_than_coal(self):
        wood = get_material(11)
        coal = get_material(36)
        assert wood.moisture_resistance < coal.moisture_resistance
        assert wood.wet_ignition_penalty > coal.wet_ignition_penalty
        assert wood.wet_burn_rate_multiplier < coal.wet_burn_rate_multiplier

    def test_hot_ash_can_reignite_after_balance_pass(self):
        hot_ash = get_material(59)
        assert 0.15 <= hot_ash.flammability <= 0.25
        src = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        assert "typ == T_HOT_ASH" in src
        assert "adjacentFuel" in src

    def test_new_byproducts_have_rendering_paths(self):
        src = (ROOT / "shaders" / "render_shader.glsl").read_text(encoding="utf-8")
        assert "typ == T_CHAR" in src
        assert "typ == T_SOOT" in src
        assert "typ == T_HOT_ASH" in src


class TestOilRegression:
    def test_oil_ignition_is_not_overly_strict(self):
        oil = get_material(6)
        assert oil.oxygen_requirement <= 0.45
        assert oil.phase_high_temp <= 175
        assert oil.wet_ignition_penalty <= 26
        assert oil.viscosity >= 0.55

    def test_oil_water_layering_logic_exists(self):
        advect = (ROOT / "shaders" / "advect_shader.glsl").read_text(encoding="utf-8")
        force = (ROOT / "shaders" / "force_shader.glsl").read_text(encoding="utf-8")
        assert "oilWaterLayering" in advect
        assert "ambientLiquidDensity" in force
        assert "liquidSep" in force

    def test_oil_fire_is_damped_not_takeover_plume(self):
        state = (ROOT / "shaders" / "state_shader.glsl").read_text(encoding="utf-8")
        force = (ROOT / "shaders" / "force_shader.glsl").read_text(encoding="utf-8")
        assert "oilFireDamp" in state
        assert "typ == T_OIL ? 1u : 0u" in state
        assert "(flg & 1u) != 0u" in force
