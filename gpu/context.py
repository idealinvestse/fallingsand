"""ModernGL context management."""

import moderngl


class ContextManager:
    """Manages ModernGL context and window configuration."""

    def __init__(self, window_size: tuple[int, int]):
        """Initialize ModernGL context with given window size."""
        import pygame
        pygame.init()
        pygame.display.set_mode(window_size, pygame.OPENGL | pygame.DOUBLEBUF)

        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.BLEND)

        # Get actual window size from context
        self.window_size = window_size

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
