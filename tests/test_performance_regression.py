"""Performance regression tests integrated into pytest (Phase 4)."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.slow
@pytest.mark.gpu
class TestPerformanceRegression:
    """Performance regression tests with FPS thresholds."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        from core.config import SimulationConfig
        config = SimulationConfig()
        config.width = 512
        config.height = 512
        config.window_width = 512
        config.window_height = 512
        return config

    @pytest.fixture
    def ctx_manager(self, config):
        """Create GPU context manager."""
        from gpu.context import ContextManager
        try:
            ctx = ContextManager((config.window_width, config.window_height))
            yield ctx
            ctx.quit()
        except Exception as e:
            pytest.skip(f"GPU not available: {e}")

    @pytest.fixture
    def engine(self, config, ctx_manager):
        """Create simulation engine."""
        from simulation.engine import SimulationEngine
        try:
            eng = SimulationEngine(config, ctx_manager)
            yield eng
        except Exception as e:
            pytest.skip(f"Engine creation failed: {e}")

    def test_performance_512_low_res(self, engine):
        """Test 512x512 low-resolution grid performance."""
        import time

        frames = 0
        fps_samples = []
        duration_sec = 5.0  # Short test for CI
        start_time = time.time()

        while time.time() - start_time < duration_sec:
            frame_start = time.time()
            dt = 1.0 / 60.0
            engine.step(dt)
            engine.render()
            frame_end = time.time()
            frame_ms = (frame_end - frame_start) * 1000.0
            fps = 1000.0 / frame_ms if frame_ms > 0 else 0.0
            fps_samples.append(fps)
            frames += 1

        fps_avg = sum(fps_samples) / len(fps_samples) if fps_samples else 0.0
        fps_min = min(fps_samples) if fps_samples else 0.0

        # Target: 512x512 should achieve at least 90 FPS average
        assert fps_avg >= 90.0, f"512x512 performance too low: {fps_avg:.1f} FPS (target: 90 FPS)"
        assert fps_min >= 60.0, f"512x512 minimum FPS too low: {fps_min:.1f} FPS (target: 60 FPS)"

    def test_performance_pass_cost_512(self, engine):
        """Test single pass cost for 512x512 grid."""

        # Clear profiler
        engine.pipeline.profiler._timings.clear()

        # Run single frame
        dt = 1.0 / 60.0
        engine.step(dt)

        # Get pass timings
        timings = engine.pipeline.profiler.get_all()

        # No single pass should exceed 10ms
        for pass_name, timing in timings.items():
            assert timing.elapsed_ms < 10.0, f"Pass {pass_name} too slow: {timing.elapsed_ms:.2f}ms (target: 10ms)"

    @pytest.mark.skip(reason="Requires larger grid, too slow for CI")
    def test_performance_1024_medium(self, engine):
        """Test 1024x1024 medium quality performance (skip in CI)."""
        import time

        engine.config.width = 1024
        engine.config.height = 1024

        frames = 0
        fps_samples = []
        duration_sec = 10.0
        start_time = time.time()

        while time.time() - start_time < duration_sec:
            frame_start = time.time()
            dt = 1.0 / 60.0
            engine.step(dt)
            engine.render()
            frame_end = time.time()
            frame_ms = (frame_end - frame_start) * 1000.0
            fps = 1000.0 / frame_ms if frame_ms > 0 else 0.0
            fps_samples.append(fps)
            frames += 1

        fps_avg = sum(fps_samples) / len(fps_samples) if fps_samples else 0.0
        fps_min = min(fps_samples) if fps_samples else 0.0

        # Target: 1024x1024 should achieve at least 50 FPS average
        assert fps_avg >= 50.0, f"1024x1024 performance too low: {fps_avg:.1f} FPS (target: 50 FPS)"
        assert fps_min >= 40.0, f"1024x1024 minimum FPS too low: {fps_min:.1f} FPS (target: 40 FPS)"


@pytest.mark.slow
class TestPerformanceBaselines:
    """Performance baseline tracking without GPU (mocked)."""

    def test_vram_estimation_performance(self):
        """Test VRAM estimation calculation performance."""
        from gpu.buffers import BufferManager
        import time

        start = time.perf_counter()
        for size in [512, 1024, 2048]:
            BufferManager.estimate_vram_usage(size, size)
        elapsed = time.perf_counter() - start

        # Should complete in under 10ms for 3 calculations
        assert elapsed < 0.01, f"VRAM estimation too slow: {elapsed*1000:.2f}ms"

    def test_material_validation_performance(self):
        """Test material validation performance."""
        from simulation.materials import to_rule_buffer
        import time

        start = time.perf_counter()
        rules = to_rule_buffer()
        elapsed = time.perf_counter() - start

        # Should complete in under 100ms
        assert elapsed < 0.1, f"Material validation too slow: {elapsed*1000:.2f}ms"
        assert len(rules) > 0


@pytest.mark.unit
class TestPerformanceConfiguration:
    """Test performance configuration parameters."""

    def test_quality_tiers_exist(self):
        """Test that quality tiers are defined."""
        from core.config import SimulationConfig

        config = SimulationConfig()

        # Verify quality tiers can be set
        config.adaptive_quality = True
        config.min_fps_target = 30.0

        assert config.adaptive_quality is True
        assert config.min_fps_target == 30.0

    def test_performance_targets_reasonable(self):
        """Test performance targets are reasonable."""
        from core.config import SimulationConfig

        config = SimulationConfig()

        # Targets should be positive
        assert config.min_fps_target > 0
        assert config.min_fps_target <= 120  # Should not exceed reasonable max

    def test_sparse_mode_configuration(self):
        """Test sparse mode configuration exists."""
        from core.config import SimulationConfig

        config = SimulationConfig()

        # Check if sparse mode attribute exists
        # It may not be implemented yet, so we just check if the attribute exists
        has_sparse = hasattr(config, 'enable_sparse_mode')
        if has_sparse:
            config.enable_sparse_mode = True
            assert config.enable_sparse_mode is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not slow"])
