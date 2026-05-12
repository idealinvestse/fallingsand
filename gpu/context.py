"""ModernGL context management."""

import moderngl


class ContextManager:
    """Manages ModernGL context and window configuration.

    Phase 4: Added context loss detection and recovery capabilities.
    """

    def __init__(self, window_size: tuple[int, int]):
        """Initialize ModernGL context with given window size."""
        import pygame
        pygame.init()
        pygame.display.set_mode(window_size, pygame.OPENGL | pygame.DOUBLEBUF)

        self.window_size = window_size
        self.context_valid = True
        self._init_context()

    def _init_context(self) -> None:
        """Initialize or reinitialize ModernGL context."""
        try:
            self.ctx = moderngl.create_context()
            self.ctx.enable(moderngl.BLEND)
            self.context_valid = True
        except Exception as e:
            print(f"Failed to create OpenGL context: {e}")
            self.context_valid = False
            raise

    def check_context_valid(self) -> bool:
        """Check if context is still valid."""
        if not self.context_valid:
            return False
        try:
            # Simple validity check - try to query a basic property
            _ = self.ctx.info
            return True
        except Exception:
            self.context_valid = False
            return False

    def recreate_context(self) -> moderngl.Context:
        """Recreate OpenGL context after loss.

        This is called when context loss is detected (e.g., display sleep,
        driver update, multi-monitor setup changes). The caller is responsible
        for reloading shaders and recreating buffers.

        Returns:
            The new ModernGL context.
        """
        print("Recreating OpenGL context after loss...")
        self._init_context()
        return self.ctx

    def resize_window(self, new_size: tuple[int, int]) -> None:
        """Handle window resize by updating window size.

        The ModernGL context should auto-adapt to the new window size,
        but we update our tracked size for reference.

        Args:
            new_size: New window dimensions (width, height).
        """
        import pygame
        self.window_size = new_size
        pygame.display.set_mode(new_size, pygame.OPENGL | pygame.DOUBLEBUF)

    def get_context(self) -> moderngl.Context:
        """Get the ModernGL context."""
        return self.ctx

    def get_window_size(self) -> tuple[int, int]:
        """Get window size."""
        return self.window_size

    def swap_buffers(self) -> None:
        """Swap display buffers."""
        pygame = __import__("pygame")
        pygame.display.flip()

    def quit(self) -> None:
        """Clean up context."""
        pygame = __import__("pygame")
        pygame.quit()
