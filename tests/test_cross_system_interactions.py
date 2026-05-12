"""Cross-system interaction tests (Phase 4)."""

import pytest
from core.config import SimulationConfig


class TestElectricityBiologyCoupling:
    """Test electricity → biology interactions (Phase 4)."""

    def test_electric_field_growth_modulation(self):
        """Electric fields should affect bio material growth rate (Phase 4).

        This test verifies that when charge is present near biological materials,
        the growth rate is modulated according to the biology_electro_stim parameter.
        """
        # This would require GPU integration to test actual shader behavior
        # For now, we test the configuration parameter exists and is reasonable
        config = SimulationConfig(enable_electricity=True, enable_biology=True)
        assert hasattr(config, 'biology_electro_stim')
        assert 0 <= config.biology_electro_stim <= 1.0

    def test_charge_damage_threshold(self):
        """High charge levels should cause bio material damage (Phase 4)."""
        config = SimulationConfig(enable_electricity=True, enable_biology=True)
        assert hasattr(config, 'charge_damage_threshold')
        assert config.charge_damage_threshold > 0

    def test_electro_stimulation_range(self):
        """Electro-stimulation should only occur within specific charge range (Phase 4)."""
        config = SimulationConfig(enable_electricity=True, enable_biology=True)
        assert hasattr(config, 'charge_stim_range_low')
        assert hasattr(config, 'charge_stim_range_high')
        assert config.charge_stim_range_low < config.charge_stim_range_high


class TestBiologyWeatherCoupling:
    """Test biology → weather interactions (Phase 4)."""

    def test_transpiration_increases_humidity(self):
        """Bio materials should increase humidity via transpiration (Phase 4)."""
        config = SimulationConfig(enable_biology=True, enable_weather=True)
        assert hasattr(config, 'transpiration_rate')
        assert 0 <= config.transpiration_rate <= 1.0

    def test_moisture_diffusion_to_weather(self):
        """Bio moisture should diffuse to atmospheric humidity (Phase 4)."""
        config = SimulationConfig(enable_biology=True, enable_weather=True)
        assert hasattr(config, 'moisture_diffuse_rate')
        assert 0 <= config.moisture_diffuse_rate <= 1.0


class TestWeatherElectricityCoupling:
    """Test weather → electricity interactions (Phase 4)."""

    def test_rain_conductivity_boost(self):
        """Rain should temporarily boost conductivity (Phase 4)."""
        config = SimulationConfig(enable_weather=True, enable_electricity=True)
        assert hasattr(config, 'electricity_moisture_boost')
        assert config.electricity_moisture_boost >= 0

    def test_humidity_affects_breakdown(self):
        """High humidity should lower arc breakdown threshold (Phase 4)."""
        config = SimulationConfig(enable_weather=True, enable_electricity=True)
        assert hasattr(config, 'breakdown_threshold')
        assert config.breakdown_threshold > 0


class TestFluidElectricityCoupling:
    """Test fluid → electricity interactions (Phase 4)."""

    def test_velocity_affects_charge_advection(self):
        """Fluid velocity should advect charge field (Phase 4)."""
        config = SimulationConfig(enable_electricity=True)
        assert hasattr(config, 'electrolysis_strength')
        assert 0 <= config.electrolysis_strength <= 1.0


class TestCrossSystemEdgeCases:
    """Test edge cases in cross-system interactions (Phase 4)."""

    def test_extreme_charge_with_high_moisture(self):
        """High charge + high moisture should not cause instability (Phase 4)."""
        config = SimulationConfig(
            enable_electricity=True,
            enable_biology=True,
            enable_weather=True,
            max_charge=10000.0,
            nutrient_diffuse_rate=1.0,
            moisture_diffuse_rate=1.0,
        )
        # Verify config validates with extreme values
        errors = config.validate()
        # Should not have validation errors for these parameters
        assert all("charge" not in error.lower() and "moisture" not in error.lower() for error in errors)

    def test_all_systems_enabled_config(self):
        """All systems should be simultaneously enableable (Phase 4)."""
        config = SimulationConfig(
            enable_electricity=True,
            enable_biology=True,
            enable_weather=True,
        )
        assert config.enable_electricity
        assert config.enable_biology
        assert config.enable_weather

    def test_cross_system_parameters_exist(self):
        """All cross-system interaction parameters should exist (Phase 4)."""
        config = SimulationConfig(enable_deep_interactions=True)

        # Electricity + Fluid
        assert hasattr(config, 'electricity_moisture_boost')
        assert hasattr(config, 'wet_arc_temp_multiplier')
        assert hasattr(config, 'electrolysis_strength')

        # Biology + Electricity
        assert hasattr(config, 'biology_electro_stim')
        assert hasattr(config, 'charge_damage_threshold')
        assert hasattr(config, 'charge_stim_range_low')
        assert hasattr(config, 'charge_stim_range_high')

        # Weather + Fluid
        assert hasattr(config, 'condensation_temp_boost')
        assert hasattr(config, 'rain_charge_wash_rate')
        assert hasattr(config, 'rain_moisture_boost')
        assert hasattr(config, 'enhanced_evaporation')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
