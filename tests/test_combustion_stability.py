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
        assert "wetSuppression" in src
        assert "wetSuppression * 32.0" in src

    def test_wind_affects_fire_and_byproducts(self):
        src = (ROOT / "shaders" / "force_shader.glsl").read_text(encoding="utf-8")
        assert "T_FIRE || typ == T_EMBER || typ == T_CHAR || typ == T_SOOT" in src
        assert "windCoupling" in src
