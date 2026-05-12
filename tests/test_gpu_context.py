"""Unit tests for GPU context management (gpu/context.py)."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestContextManagerInitialization:
    """Test ContextManager initialization and setup."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_manager_init_success(self, mock_moderngl, mock_pygame):
        """Test successful ContextManager initialization."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        mock_pygame.init.assert_called_once()
        mock_pygame.display.set_mode.assert_called_once_with(
            (800, 600), mock_pygame.OPENGL | mock_pygame.DOUBLEBUF
        )
        mock_moderngl.create_context.assert_called_once()
        mock_ctx.enable.assert_called_once_with(mock_moderngl.BLEND)
        assert ctx_manager.window_size == (800, 600)
        assert ctx_manager.context_valid is True

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_manager_init_failure(self, mock_moderngl, mock_pygame):
        """Test ContextManager initialization failure."""
        from gpu.context import ContextManager
        from moderngl import Error

        mock_moderngl.create_context.side_effect = Error("OpenGL 4.3 required")

        with pytest.raises(Error):
            ContextManager((800, 600))

        assert mock_pygame.init.called


class TestContextValidation:
    """Test context validity checking."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_check_context_valid_success(self, mock_moderngl, mock_pygame):
        """Test check_context_valid returns True when context is valid."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = {"version": "4.6"}
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        assert ctx_manager.check_context_valid() is True

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_check_context_valid_flag_false(self, mock_moderngl, mock_pygame):
        """Test check_context_valid returns False when flag is False."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        ctx_manager.context_valid = False
        assert ctx_manager.check_context_valid() is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_check_context_valid_exception(self, mock_moderngl, mock_pygame):
        """Test check_context_valid handles exception gracefully."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=RuntimeError("Context lost"))
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        assert ctx_manager.check_context_valid() is False
        assert ctx_manager.context_valid is False


class TestContextRecreation:
    """Test context recreation after loss."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_recreate_context_success(self, mock_moderngl, mock_pygame):
        """Test successful context recreation."""
        from gpu.context import ContextManager

        mock_ctx_old = MagicMock()
        mock_ctx_new = MagicMock()
        mock_moderngl.create_context.side_effect = [mock_ctx_old, mock_ctx_new]
        mock_ctx_new.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        new_ctx = ctx_manager.recreate_context()

        assert new_ctx is not None
        assert new_ctx is mock_ctx_new
        assert ctx_manager.context_valid is True
        assert mock_moderngl.create_context.call_count == 2

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_recreate_context_failure(self, mock_moderngl, mock_pygame):
        """Test context recreation failure."""
        from gpu.context import ContextManager
        from moderngl import Error

        mock_ctx_old = MagicMock()
        mock_moderngl.create_context.side_effect = [mock_ctx_old, Error("Recreation failed")]
        mock_ctx_old.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        with pytest.raises(Error):
            ctx_manager.recreate_context()

        assert ctx_manager.context_valid is False


class TestWindowResize:
    """Test window resize handling."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_resize_window(self, mock_moderngl, mock_pygame):
        """Test window resize updates window size."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        assert ctx_manager.window_size == (800, 600)

        ctx_manager.resize_window((1024, 768))
        assert ctx_manager.window_size == (1024, 768)
        mock_pygame.display.set_mode.assert_called_with(
            (1024, 768), mock_pygame.OPENGL | mock_pygame.DOUBLEBUF
        )


class TestContextAccessors:
    """Test context accessor methods."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_get_context(self, mock_moderngl, mock_pygame):
        """Test get_context returns ModernGL context."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        assert ctx_manager.get_context() is mock_ctx

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_get_window_size(self, mock_moderngl, mock_pygame):
        """Test get_window_size returns window dimensions."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        assert ctx_manager.get_window_size() == (800, 600)

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_swap_buffers(self, mock_moderngl, mock_pygame):
        """Test swap_buffers calls pygame.display.flip."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        ctx_manager.swap_buffers()
        mock_pygame.display.flip.assert_called_once()


class TestContextCleanup:
    """Test context cleanup."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_quit(self, mock_moderngl, mock_pygame):
        """Test quit calls pygame.quit."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))
        ctx_manager.quit()
        mock_pygame.quit.assert_called_once()


class TestContextLossScenarios:
    """Test context loss detection and recovery scenarios (Phase 4)."""

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_loss_during_info_query(self, mock_moderngl, mock_pygame):
        """Test context loss detected during info query."""
        from gpu.context import ContextManager

        mock_ctx = MagicMock()
        mock_ctx.info = Mock(side_effect=[{"version": "4.6"}, RuntimeError("Context lost")])
        mock_moderngl.create_context.return_value = mock_ctx
        mock_ctx.enable = Mock()

        ctx_manager = ContextManager((800, 600))

        # First check should succeed
        assert ctx_manager.check_context_valid() is True

        # Second check should detect loss
        assert ctx_manager.check_context_valid() is False
        assert ctx_manager.context_valid is False

    @patch('gpu.context.pygame')
    @patch('gpu.context.moderngl')
    def test_context_recovery_after_loss(self, mock_moderngl, mock_pygame):
        """Test context recovery after loss detection."""
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

        # Recover
        ctx_manager.recreate_context()

        # Verify recovery
        assert ctx_manager.check_context_valid() is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
