"""Performance overlay for real-time visualization of GPU pass timings."""

import pygame
from collections import deque
from ui.overlay import OverlayRenderer
import ui.theme as theme


class PerformanceOverlay(OverlayRenderer):
    """Real-time performance visualization overlay."""

    def __init__(self, ctx, window_size):
        """Initialize performance overlay."""
        super().__init__(ctx, window_size)
        self.visible = False
        self.panel_rect = pygame.Rect(window_size[0] - 320, 20, 300, 280)
        self.profiler = None
        self.pipeline = None
        
        # FPS history for graph (last 60 frames)
        self.fps_history = deque(maxlen=60)
        self.current_fps = 60.0
        
        # Budget settings
        self.budget_ms = 16.67  # 60fps target
        
        self._build_ui()

    def set_pipeline(self, pipeline):
        """Set the Pipeline instance."""
        self.pipeline = pipeline

    def _build_ui(self):
        """Build UI hitboxes (not interactive)."""
        pass

    def toggle(self):
        """Toggle overlay visibility."""
        self.visible = not self.visible

    def set_profiler(self, profiler):
        """Set the PassProfiler instance."""
        self.profiler = profiler

    def update_fps(self, dt: float):
        """Update FPS history."""
        fps = 1.0 / dt if dt > 0 else 60.0
        self.current_fps = fps
        self.fps_history.append(fps)

    def render(self):
        """Render the performance overlay."""
        if not self.visible or self.profiler is None:
            return

        surf = pygame.Surface((self.panel_rect.width, self.panel_rect.height), pygame.SRCALPHA)
        theme.rounded_panel(surf, surf.get_rect(), fill=(18, 20, 28, 240), radius=12, shadow=True)
        theme.accent_strip(surf, surf.get_rect(), theme.ACCENT_PURPLE, height=4)

        # Title
        title = theme.font(14, bold=True).render("Performance", True, theme.TEXT_PRIMARY)
        surf.blit(title, (16, 16))

        # Helper text
        hint = theme.font(10).render("Ctrl+P to toggle", True, theme.TEXT_DIM)
        surf.blit(hint, (self.panel_rect.width - hint.get_width() - 16, 20))

        # FPS display
        fps_color = theme.ACCENT_GREEN if self.current_fps >= 55 else (theme.ACCENT_RED if self.current_fps < 30 else theme.ACCENT_YELLOW)
        fps_text = theme.font(20, bold=True).render(f"{self.current_fps:.1f} FPS", True, fps_color)
        surf.blit(fps_text, (16, 45))

        # FPS graph
        self._render_fps_graph(surf)

        # Per-pass timing bars
        self._render_pass_timings(surf)

        # Memory usage (placeholder)
        self._render_memory_usage(surf)

        self.render_fullscreen(surf, offset=(self.panel_rect.x, self.panel_rect.y))

    def _render_fps_graph(self, surf):
        """Render FPS history graph."""
        graph_rect = pygame.Rect(16, 75, 268, 50)
        pygame.draw.rect(surf, (10, 12, 16), graph_rect, border_radius=4)

        if len(self.fps_history) < 2:
            return

        # Draw graph lines
        points = []
        for i, fps in enumerate(self.fps_history):
            x = graph_rect.x + (i / (len(self.fps_history) - 1)) * graph_rect.width
            # Normalize FPS to 0-60 range
            normalized = min(fps / 60.0, 1.0)
            y = graph_rect.bottom - normalized * graph_rect.height
            points.append((x, y))

        if len(points) >= 2:
            pygame.draw.lines(surf, theme.ACCENT_CYAN, False, points, 2)

        # Draw budget line (target FPS)
        target_fps = 55.0
        budget_y = graph_rect.bottom - (target_fps / 60.0) * graph_rect.height
        pygame.draw.line(surf, theme.ACCENT_GREEN, (graph_rect.x, budget_y), (graph_rect.right, budget_y), 1)

    def _render_pass_timings(self, surf):
        """Render per-pass timing bars."""
        timings = self.profiler.get_all()
        if not timings:
            return

        y = 135
        font = theme.font(9)

        # Sort by timing (slowest first)
        sorted_timings = sorted(timings.items(), key=lambda x: x[1].elapsed_ms, reverse=True)
        
        # Show top 8 passes
        for pass_name, timing in sorted_timings[:8]:
            elapsed = timing.elapsed_ms
            percent = (elapsed / self.budget_ms) * 100
            
            # Color based on budget
            bar_color = theme.ACCENT_GREEN if percent < 50 else (theme.ACCENT_YELLOW if percent < 100 else theme.ACCENT_RED)
            
            # Label
            label = font.render(pass_name[:15], True, theme.TEXT_BODY)
            surf.blit(label, (16, y))
            
            # Timing text
            time_text = font.render(f"{elapsed:.2f}ms", True, bar_color)
            surf.blit(time_text, (200, y))
            
            # Bar background
            bar_bg_rect = pygame.Rect(16, y + 12, 268, 6)
            pygame.draw.rect(surf, (10, 12, 16), bar_bg_rect, border_radius=3)
            
            # Bar fill
            bar_width = min(percent / 100.0 * 268, 268)
            bar_rect = pygame.Rect(16, y + 12, bar_width, 6)
            pygame.draw.rect(surf, bar_color, bar_rect, border_radius=3)
            
            y += 28

    def _render_memory_usage(self, surf):
        """Render memory usage, quality tier, and status indicators."""
        y = 220
        font = theme.font(9)

        # Quality tier indicator
        if self.pipeline and self.pipeline.config.adaptive_quality:
            tier_names = ["High", "Medium", "Low"]
            tier_idx = self.pipeline.quality_tier_index
            tier_name = self.pipeline.config.quality_tiers[tier_idx].get("name", tier_names[tier_idx])
            tier_color = theme.ACCENT_GREEN if tier_idx == 0 else (theme.ACCENT_YELLOW if tier_idx == 1 else theme.ACCENT_RED)
            tier_text = font.render(f"Quality: {tier_name}", True, tier_color)
            surf.blit(tier_text, (16, y))
            y += 12

        # Sparse mode status
        if self.pipeline:
            sparse_enabled = self.pipeline.sparse_mask.sparse_enabled
            sparse_text = f"Sparse: {'ON' if sparse_enabled else 'OFF'}"
            sparse_color = theme.ACCENT_GREEN if sparse_enabled else theme.TEXT_DIM
            surf.blit(font.render(sparse_text, True, sparse_color), (16, y))
            y += 12

        # Adaptive quality status
        if self.pipeline and self.pipeline.config.adaptive_quality:
            adaptive_text = "Adaptive: ON"
            surf.blit(font.render(adaptive_text, True, theme.ACCENT_GREEN), (16, y))
            y += 12

        # VRAM estimation (based on grid size and textures)
        if self.pipeline:
            # Estimate VRAM: cells (4 bytes * width * height * 2 for double buffer)
            # + textures (velocity, pressure, temperature, etc.)
            grid_mb = (self.pipeline.width * self.pipeline.height * 4 * 2) / (1024 * 1024)
            textures_mb = 100  # Approximate texture memory
            total_mb = grid_mb + textures_mb
            mem_text = font.render(f"VRAM: ~{total_mb:.0f} MB (est.)", True, theme.TEXT_DIM)
            surf.blit(mem_text, (16, y))
