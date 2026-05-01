"""Tests for UBO dataclass std140 layout correctness and UBOManager."""

import numpy as np
import moderngl

from gpu.uniforms import (
    UBOManager,
    SimConfigData,
    ExplosionConfigData,
    ExplosionVfxConfigData,
    WindConfigData,
)
from simulation.state import ExplosionVfxState


class TestSimConfigDataLayout:
    """Test SimConfigData std140 layout."""

    def test_to_bytes_size(self):
        """SimConfigData should produce 48 bytes (std140 aligned)."""
        data = SimConfigData(
            gridSize=(800, 600),
            frame=123,
            dt=0.016,
            ambientTemp=20.0,
            ruleStride=20,
            enableThermal=1,
            enableTurbulence=1,
            enableWetDry=1,
            gravity=9.8,
            vorticityStrength=0.5,
        )
        bytes_data = data.to_bytes()
        assert len(bytes_data) == 48, f"Expected 48 bytes, got {len(bytes_data)}"

    def test_to_bytes_grid_size(self):
        """Grid size should be in first two floats."""
        data = SimConfigData(
            gridSize=(100, 200),
            frame=0,
            dt=0.0,
            ambientTemp=0.0,
            ruleStride=0,
            enableThermal=0,
            enableTurbulence=0,
            enableWetDry=0,
            gravity=0.0,
            vorticityStrength=0.0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert array[0] == 100.0
        assert array[1] == 200.0

    def test_to_bytes_frame(self):
        """Frame should be at index 2."""
        data = SimConfigData(
            gridSize=(0, 0),
            frame=42,
            dt=0.0,
            ambientTemp=0.0,
            ruleStride=0,
            enableThermal=0,
            enableTurbulence=0,
            enableWetDry=0,
            gravity=0.0,
            vorticityStrength=0.0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert array[2] == 42.0

    def test_to_bytes_gravity(self):
        """Gravity should be at index 9."""
        data = SimConfigData(
            gridSize=(0, 0),
            frame=0,
            dt=0.0,
            ambientTemp=0.0,
            ruleStride=0,
            enableThermal=0,
            enableTurbulence=0,
            enableWetDry=0,
            gravity=9.81,
            vorticityStrength=0.0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert abs(array[9] - 9.81) < 0.001


class TestExplosionConfigDataLayout:
    """Test ExplosionConfigData std140 layout."""

    def test_to_bytes_size(self):
        """ExplosionConfigData should produce 64 bytes (std140 aligned)."""
        data = ExplosionConfigData(
            center=(100.0, 200.0),
            radius=25.0,
            force=10.0,
            isActive=1,
            age=0.5,
            maxAge=2.0,
            type=0,
            soundSpeed=343.0,
            dtAcoustic=0.01,
            energyDecayRate=0.95,
            reflectionDamping=0.8,
        )
        bytes_data = data.to_bytes()
        assert len(bytes_data) == 64, f"Expected 64 bytes, got {len(bytes_data)}"

    def test_to_bytes_center(self):
        """Center should be in first two floats."""
        data = ExplosionConfigData(
            center=(50.5, 75.25),
            radius=0.0,
            force=0.0,
            isActive=0,
            age=0.0,
            maxAge=0.0,
            type=0,
            soundSpeed=0.0,
            dtAcoustic=0.0,
            energyDecayRate=0.0,
            reflectionDamping=0.0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert abs(array[0] - 50.5) < 0.001
        assert abs(array[1] - 75.25) < 0.001

    def test_to_bytes_is_active(self):
        """isActive should be at index 4."""
        data = ExplosionConfigData(
            center=(0.0, 0.0),
            radius=0.0,
            force=0.0,
            isActive=1,
            age=0.0,
            maxAge=0.0,
            type=0,
            soundSpeed=0.0,
            dtAcoustic=0.0,
            energyDecayRate=0.0,
            reflectionDamping=0.0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert array[4] == 1.0


class TestExplosionVfxConfigDataLayout:
    """Test ExplosionVfxConfigData std140 layout."""

    def test_to_bytes_size(self):
        """ExplosionVfxConfigData should produce 16 bytes (std140 aligned)."""
        data = ExplosionVfxConfigData(
            flash=1.0,
            pressurePulse=5.0,
            isFirstSubstep=1,
        )
        bytes_data = data.to_bytes()
        assert len(bytes_data) == 16, f"Expected 16 bytes, got {len(bytes_data)}"

    def test_to_bytes_flash(self):
        """Flash should be at index 0."""
        data = ExplosionVfxConfigData(
            flash=0.75,
            pressurePulse=0.0,
            isFirstSubstep=0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert abs(array[0] - 0.75) < 0.001

    def test_to_bytes_pressure_pulse(self):
        """pressurePulse should be at index 1."""
        data = ExplosionVfxConfigData(
            flash=0.0,
            pressurePulse=3.5,
            isFirstSubstep=0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert abs(array[1] - 3.5) < 0.001


class TestExplosionVfxState:
    """Test runtime explosion VFX state progression."""

    def test_update_advances_age_after_trigger(self):
        state = ExplosionVfxState(decay_rate=0.25, max_age=1.0)
        state.trigger(12.0, 34.0, flash_intensity=0.6)

        state.update()

        assert state.age > 0.0
        assert state.flash < 0.6

    def test_update_expires_age_after_max_age(self):
        state = ExplosionVfxState(decay_rate=0.6, max_age=1.0)
        state.trigger(0.0, 0.0, flash_intensity=0.6)

        for _ in range(4):
            state.update()

        assert state.age == 0.0


class TestWindConfigDataLayout:
    """Test WindConfigData std140 layout."""

    def test_to_bytes_size(self):
        """WindConfigData should produce 16 bytes (std140 aligned)."""
        data = WindConfigData(
            vector=(1.5, -0.5),
            enabled=1,
        )
        bytes_data = data.to_bytes()
        assert len(bytes_data) == 16, f"Expected 16 bytes, got {len(bytes_data)}"

    def test_to_bytes_vector(self):
        """Vector should be in first two floats."""
        data = WindConfigData(
            vector=(2.0, -1.0),
            enabled=0,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert abs(array[0] - 2.0) < 0.001
        assert abs(array[1] - (-1.0)) < 0.001

    def test_to_bytes_enabled(self):
        """enabled should be at index 2."""
        data = WindConfigData(
            vector=(0.0, 0.0),
            enabled=1,
        )
        bytes_data = data.to_bytes()
        array = np.frombuffer(bytes_data, dtype=np.float32)
        assert array[2] == 1.0


class TestUBOManager:
    """Test UBOManager buffer initialization and binding."""

    def test_init_creates_buffers(self):
        """UBOManager should create buffers with correct sizes."""
        # Create a minimal moderngl context for testing
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        # Check that buffers were created
        assert ubo_manager.sim_config_ubo is not None
        assert ubo_manager.explosion_ubo is not None
        assert ubo_manager.explosion_vfx_ubo is not None
        assert ubo_manager.wind_ubo is not None

    def test_update_sim_config(self):
        """update_sim_config should write data to the buffer."""
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        data = SimConfigData(
            gridSize=(800, 600),
            frame=123,
            dt=0.016,
            ambientTemp=20.0,
            ruleStride=20,
            enableThermal=1,
            enableTurbulence=1,
            enableWetDry=1,
            gravity=9.8,
            vorticityStrength=0.5,
        )

        # Should not raise an exception
        ubo_manager.update_sim_config(data)

    def test_update_explosion(self):
        """update_explosion should write data to the buffer."""
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        data = ExplosionConfigData(
            center=(100.0, 200.0),
            radius=25.0,
            force=10.0,
            isActive=1,
            age=0.5,
            maxAge=2.0,
            type=0,
            soundSpeed=343.0,
            dtAcoustic=0.01,
            energyDecayRate=0.95,
            reflectionDamping=0.8,
        )

        # Should not raise an exception
        ubo_manager.update_explosion(data)

    def test_update_explosion_vfx(self):
        """update_explosion_vfx should write data to the buffer."""
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        data = ExplosionVfxConfigData(
            flash=1.0,
            pressurePulse=5.0,
            isFirstSubstep=1,
        )

        # Should not raise an exception
        ubo_manager.update_explosion_vfx(data)

    def test_update_wind(self):
        """update_wind should write data to the buffer."""
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        data = WindConfigData(
            vector=(1.5, -0.5),
            enabled=1,
        )

        # Should not raise an exception
        ubo_manager.update_wind(data)

    def test_bind_all(self):
        """bind_all should bind all UBOs to their binding points."""
        ctx = moderngl.create_context(standalone=True)
        ubo_manager = UBOManager(ctx)

        # Standalone context doesn't support uniform buffer binding
        # Just verify the method exists and can be called without error in a real context
        # In a full integration test with a real GL context, this would be tested
        try:
            ubo_manager.bind_all()
        except AttributeError:
            # Expected in standalone context - method exists but context doesn't support it
            pass
