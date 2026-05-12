"""Unit tests for context loss detection and recovery (Phase 4)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestContextLossDetection:
    """Test context loss detection mechanisms."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_loss_detected_via_info_query(self, mock_moderngl, mock_pygame):
        """Test context loss detected when context.info raises exception."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Context lost"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Context should be marked as invalid after detection
        is_valid = ctx_manager.check_context_valid()
        assert is_valid is False
        assert ctx_manager.context_valid is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_loss_detected_via_none_info(self, mock_moderngl, mock_pygame):
        """Test context loss detected when context.info is None."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = None
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Context should be marked as invalid
        is_valid = ctx_manager.check_context_valid()
        assert is_valid is False
        assert ctx_manager.context_valid is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_valid_flag_prevents_check(self, mock_moderngl, mock_pygame):
        """Test that context_valid=False bypasses info query."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Should not be called"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        ctx_manager.context_valid = False

        # Should return False without calling info
        is_valid = ctx_manager.check_context_valid()
        assert is_valid is False
        mock_ctx.info.assert_not_called()


class TestContextRecovery:
    """Test context recovery after loss."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_recovery_success(self, mock_moderngl, mock_pygame):
        """Test successful context recovery after loss."""
        from gpu.context import ContextManager

        mock_ctx_old = MagicMock()
        mock_ctx_new = MagicMock()
        mock_ctx_old.info = Mock(side_effect=RuntimeError("Context lost"))
        mock_ctx_new.info = {"version": "4.6"}
        mock_moderngl.create_context.side_effect = [mock_ctx_old, mock_ctx_new]
        mock_ctx_new.enable = Mock()
        mock_ctx_old.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Detect loss
        assert ctx_manager.check_context_valid() is False

        # Recover context
        recovered_ctx = ctx_manager.recreate_context()

        # Verify recovery
        assert recovered_ctx is mock_ctx_new
        assert ctx_manager.context_valid is True
        assert ctx_manager.check_context_valid() is True

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_recovery_failure(self, mock_moderngl, mock_pygame):
        """Test context recovery failure."""
        from gpu.context import ContextManager
        from moderngl import Error

        mock_ctx_old = MagicMock()
        mock_moderngl.create_context.side_effect = [mock_ctx_old, Error("Recovery failed")]
        mock_ctx_old.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Attempt recovery should raise exception
        with pytest.raises(Error):
            ctx_manager.recreate_context()

        # Context should remain invalid
        assert ctx_manager.context_valid is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_recovery_reinitializes_state(self, mock_moderngl, mock_pygame):
        """Test context recovery reinitializes context state."""
        from gpu.context import ContextManager

        mock_ctx_old = MagicMock()
        mock_ctx_new = MagicMock()
        mock_moderngl.create_context.side_effect = [mock_ctx_old, mock_ctx_new]
        mock_ctx_new.enable = Mock()
        mock_ctx_old.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Recover
        ctx_manager.recreate_context()

        # Verify BLEND is enabled on new context
        mock_ctx_new.enable.assert_called_once()

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_recovery_preserves_window_size(self, mock_moderngl, mock_pygame):
        """Test context recovery preserves window size."""
        from gpu.context import ContextManager

        mock_ctx_old = MagicMock()
        mock_ctx_new = MagicMock()
        mock_moderngl.create_context.side_effect = [mock_ctx_old, mock_ctx_new]
        mock_ctx_new.enable = Mock()
        mock_ctx_old.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        original_size = ctx_manager.window_size

        ctx_manager.recreate_context()

        # Window size should be preserved
        assert ctx_manager.window_size == original_size


class TestContextLossScenarios:
    """Test realistic context loss scenarios."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_display_sleep_context_loss(self, mock_moderngl, mock_pygame):
        """Test context loss due to display sleep (common scenario)."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        # Simulate display sleep: context.info becomes inaccessible
        mock_ctx.info = Mock(side_effect=RuntimeError("Display sleep"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Detect loss
        is_valid = ctx_manager.check_context_valid()
        assert is_valid is False

        # Should be recoverable
        mock_ctx.info = Mock(side_effect=[RuntimeError("Sleep"), {"version": "4.6"}])
        mock_moderngl.create_context.side_effect = [mock_ctx, MagicMock()]
        ctx_manager.recreate_context()

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_driver_update_context_loss(self, mock_moderngl, mock_pygame):
        """Test context loss due to driver update."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Driver update"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Detect loss
        assert ctx_manager.check_context_valid() is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_multi_monitor_context_loss(self, mock_moderngl, mock_pygame):
        """Test context loss due to multi-monitor setup changes."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Monitor configuration changed"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Detect loss
        assert ctx_manager.check_context_valid() is False


class TestContextLossIntegration:
    """Test context loss integration with simulation engine."""

    @patch('simulation.engine.BufferManager')
    @patch('simulation.engine.UBOManager')
    @patch('simulation.engine.GPUStatsCounter')
    @patch('simulation.engine.Pipeline')
    @patch('simulation.engine.BrushPainter')
    @patch('simulation.engine.PersistenceManager')
    @patch('simulation.engine.load_all_shaders')
    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_engine_handles_context_loss_during_step(
        self, mock_moderngl, mock_pygame, mock_load_shaders,
        mock_persistence, mock_brush, mock_pipeline, mock_stats,
        mock_ubo, mock_buffer
    ):
        """Test simulation engine handles context loss during step (Phase 4)."""
        from simulation.engine import SimulationEngine
        from core.config import SimulationConfig

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=[{"version": "4.6"}, RuntimeError("Context lost")])
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        config = SimulationConfig(width=512, height=512)
        ctx_manager = Mock()
        ctx_manager.get_context.return_value = mock_ctx
        ctx_manager.check_context_valid.side_effect = [True, False]

        # Mock pipeline
        mock_pipeline_instance = MagicMock()
        mock_pipeline.return_value = mock_pipeline_instance

        engine = SimulationEngine(config, ctx_manager)

        # First step should succeed
        engine.step(0.016)

        # Context loss detected
        assert ctx_manager.check_context_valid() is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_loss_does_not_crash_check(self, mock_moderngl, mock_pygame):
        """Test context loss detection never crashes simulation."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=Exception("Unexpected error"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Should handle exception gracefully
        is_valid = ctx_manager.check_context_valid()
        assert is_valid is False
        assert ctx_manager.context_valid is False


class TestWindowResizeWithContext:
    """Test window resize interactions with context."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_resize_does_not_lose_context(self, mock_moderngl, mock_pygame):
        """Test window resize does not cause context loss."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = {"version": "4.6"}
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Resize
        ctx_manager.resize_window((1024, 768))

        # Context should still be valid
        assert ctx_manager.check_context_valid() is True

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_resize_after_context_loss(self, mock_moderngl, mock_pygame):
        """Test window resize after context loss."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Context lost"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # Context is lost
        assert ctx_manager.check_context_valid() is False

        # Resize should still work
        ctx_manager.resize_window((1024, 768))
        assert ctx_manager.window_size == (1024, 768)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
