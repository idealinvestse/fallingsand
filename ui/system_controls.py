"""System Controls Panel for electricity, biology, and weather systems."""

import pygame
from pygame.locals import K_e, K_b, K_w, K_ESCAPE

from ui.overlay import OverlayRenderer
import ui.theme as theme


class SystemControls(OverlayRenderer):
    """Panel for toggling and tuning new simulation systems."""

    def __init__(self, context, window_size):
        super().__init__(context, window_size)
        self.visible = False
        self.panel_rect = pygame.Rect(20, 20, 400, 320)
        self.dragging = False
        self.drag_offset = (0, 0)
        
        # System enable states
        self.electricity_enabled = False
        self.biology_enabled = False
        self.weather_enabled = False
        
        # Parameter values (0.0 to 1.0 normalized, mapped to actual ranges)
        self.charge_decay = 0.0
        self.breakdown_threshold = 0.5
        self.growth_rate = 0.1
        self.decay_rate = 0.05
        self.evaporation_rate = 0.1
        self.saturation_threshold = 0.5
        
        # Bloom parameters
        self.bloom_enabled = True
        self.bloom_threshold = 0.6
        self.bloom_intensity = 0.6
        
        # Sparse mode toggle
        self.sparse_enabled = False
        
        # Slider hitboxes
        self.sliders = {}
        self.toggles = {}
        self._build_ui()

    def _build_ui(self):
        """Build UI hitboxes."""
        x = self.panel_rect.x + 140
        y_base = self.panel_rect.y + 40
        
        # Electricity section
        self.toggles["electricity"] = pygame.Rect(x, y_base, 60, 24)
        self.sliders["charge_decay"] = pygame.Rect(x, y_base + 35, 200, 16)
        self.sliders["breakdown"] = pygame.Rect(x, y_base + 70, 200, 16)
        
        # Biology section
        y_bio = y_base + 110
        self.toggles["biology"] = pygame.Rect(x, y_bio, 60, 24)
        self.sliders["growth"] = pygame.Rect(x, y_bio + 35, 200, 16)
        self.sliders["decay"] = pygame.Rect(x, y_bio + 70, 200, 16)
        
        # Weather section
        y_weather = y_bio + 110
        self.toggles["weather"] = pygame.Rect(x, y_weather, 60, 24)
        self.sliders["evaporation"] = pygame.Rect(x, y_weather + 35, 200, 16)
        self.sliders["saturation"] = pygame.Rect(x, y_weather + 70, 200, 16)
        
        # Bloom section
        y_bloom = y_weather + 110
        self.toggles["bloom"] = pygame.Rect(x, y_bloom, 60, 24)
        self.sliders["bloom_threshold"] = pygame.Rect(x, y_bloom + 35, 200, 16)
        self.sliders["bloom_intensity"] = pygame.Rect(x, y_bloom + 70, 200, 16)
        
        # Sparse mode section
        y_sparse = y_bloom + 110
        self.toggles["sparse"] = pygame.Rect(x, y_sparse, 60, 24)

    def toggle(self):
        """Toggle panel visibility."""
        self.visible = not self.visible

    def handle_click(self, mx, my):
        """Handle mouse clicks on the panel."""
        if not self.visible:
            return None
        
        # Check panel drag
        if self.panel_rect.collidepoint(mx, my):
            self.dragging = True
            self.drag_offset = (mx - self.panel_rect.x, my - self.panel_rect.y)
            self._build_ui()
            return None
        
        # Check toggles
        for name, rect in self.toggles.items():
            if rect.collidepoint(mx, my):
                if name == "electricity":
                    self.electricity_enabled = not self.electricity_enabled
                elif name == "biology":
                    self.biology_enabled = not self.biology_enabled
                elif name == "weather":
                    self.weather_enabled = not self.weather_enabled
                elif name == "bloom":
                    self.bloom_enabled = not self.bloom_enabled
                elif name == "sparse":
                    self.sparse_enabled = not self.sparse_enabled
                return ("update_config", None)
        
        # Check sliders
        for name, rect in self.sliders.items():
            if rect.collidepoint(mx, my):
                value = (mx - rect.x) / rect.width
                value = max(0.0, min(1.0, value))
                if name == "charge_decay":
                    self.charge_decay = value
                elif name == "breakdown":
                    self.breakdown_threshold = value
                elif name == "growth":
                    self.growth_rate = value
                elif name == "decay":
                    self.decay_rate = value
                elif name == "evaporation":
                    self.evaporation_rate = value
                elif name == "saturation":
                    self.saturation_threshold = value
                elif name == "bloom_threshold":
                    self.bloom_threshold = value
                elif name == "bloom_intensity":
                    self.bloom_intensity = value
                return ("update_config", None)
        
        return None

    def handle_mouse_up(self):
        """Handle mouse up (end drag)."""
        self.dragging = False

    def handle_mouse_move(self, mx, my):
        """Handle mouse move (drag panel or sliders)."""
        if not self.visible:
            return None
        
        if self.dragging:
            self.panel_rect.x = mx - self.drag_offset[0]
            self.panel_rect.y = my - self.drag_offset[1]
            self._build_ui()
            return None
        
        # Check slider drag
        for name, rect in self.sliders.items():
            if pygame.mouse.get_pressed()[0] and rect.collidepoint(mx, my):
                value = (mx - rect.x) / rect.width
                value = max(0.0, min(1.0, value))
                if name == "charge_decay":
                    self.charge_decay = value
                elif name == "breakdown":
                    self.breakdown_threshold = value
                elif name == "growth":
                    self.growth_rate = value
                elif name == "decay":
                    self.decay_rate = value
                elif name == "evaporation":
                    self.evaporation_rate = value
                elif name == "saturation":
                    self.saturation_threshold = value
                elif name == "bloom_threshold":
                    self.bloom_threshold = value
                elif name == "bloom_intensity":
                    self.bloom_intensity = value
                return ("update_config", None)
        
        return None

    def handle_key(self, key, mods):
        """Handle keyboard shortcuts."""
        if key == K_ESCAPE:
            self.visible = False
        elif key == K_e and (mods & pygame.KMOD_CTRL):
            self.toggle()
        elif key == K_b and (mods & pygame.KMOD_CTRL):
            self.toggle()
        elif key == K_w and (mods & pygame.KMOD_CTRL):
            self.toggle()

    def render(self):
        """Render the system controls panel."""
        if not self.visible:
            return
        
        surf = pygame.Surface((self.panel_rect.width, self.panel_rect.height), pygame.SRCALPHA)
        theme.rounded_panel(surf, surf.get_rect(), fill=(18, 20, 28, 240), radius=12, shadow=True)
        theme.accent_strip(surf, surf.get_rect(), theme.ACCENT_CYAN, height=4)
        
        # Title
        title = theme.font(14, bold=True).render("System Controls", True, theme.TEXT_PRIMARY)
        surf.blit(title, (16, 16))
        
        # Helper text
        hint = theme.font(10).render("Ctrl+E to toggle", True, theme.TEXT_DIM)
        surf.blit(hint, (self.panel_rect.width - hint.get_width() - 16, 20))
        
        x = 16
        y = 50
        
        # Electricity section
        elec_title = theme.font(11, bold=True).render("Electricity", True, theme.ACCENT_CYAN)
        surf.blit(elec_title, (x, y))
        
        # Toggle
        toggle_rect = self.toggles["electricity"]
        toggle_rect_rel = (toggle_rect.x - self.panel_rect.x, toggle_rect.y - self.panel_rect.y)
        theme.toggle_switch(surf, toggle_rect_rel, self.electricity_enabled)
        
        # Sliders
        self._render_slider(surf, "Charge Decay", self.sliders["charge_decay"], self.charge_decay, y + 35)
        self._render_slider(surf, "Breakdown", self.sliders["breakdown"], self.breakdown_threshold, y + 70)
        
        # Biology section
        y += 110
        bio_title = theme.font(11, bold=True).render("Biology", True, theme.ACCENT_GREEN)
        surf.blit(bio_title, (x, y))
        
        toggle_rect = self.toggles["biology"]
        toggle_rect_rel = (toggle_rect.x - self.panel_rect.x, toggle_rect.y - self.panel_rect.y)
        theme.toggle_switch(surf, toggle_rect_rel, self.biology_enabled)
        
        self._render_slider(surf, "Growth Rate", self.sliders["growth"], self.growth_rate, y + 35)
        self._render_slider(surf, "Decay Rate", self.sliders["decay"], self.decay_rate, y + 70)
        
        # Weather section
        y += 110
        weather_title = theme.font(11, bold=True).render("Weather", True, theme.ACCENT_BLUE)
        surf.blit(weather_title, (x, y))
        
        toggle_rect = self.toggles["weather"]
        toggle_rect_rel = (toggle_rect.x - self.panel_rect.x, toggle_rect.y - self.panel_rect.y)
        theme.toggle_switch(surf, toggle_rect_rel, self.weather_enabled)
        
        self._render_slider(surf, "Evaporation", self.sliders["evaporation"], self.evaporation_rate, y + 35)
        self._render_slider(surf, "Saturation", self.sliders["saturation"], self.saturation_threshold, y + 70)
        
        # Bloom section
        y += 110
        bloom_title = theme.font(11, bold=True).render("Bloom", True, theme.ACCENT_PURPLE)
        surf.blit(bloom_title, (x, y))
        
        toggle_rect = self.toggles["bloom"]
        toggle_rect_rel = (toggle_rect.x - self.panel_rect.x, toggle_rect.y - self.panel_rect.y)
        theme.toggle_switch(surf, toggle_rect_rel, self.bloom_enabled)
        
        self._render_slider(surf, "Threshold", self.sliders["bloom_threshold"], self.bloom_threshold, y + 35)
        self._render_slider(surf, "Intensity", self.sliders["bloom_intensity"], self.bloom_intensity, y + 70)
        
        # Sparse mode section
        y += 110
        sparse_title = theme.font(11, bold=True).render("Sparse Mode", True, theme.ACCENT_ORANGE)
        surf.blit(sparse_title, (x, y))
        
        toggle_rect = self.toggles["sparse"]
        toggle_rect_rel = (toggle_rect.x - self.panel_rect.x, toggle_rect.y - self.panel_rect.y)
        theme.toggle_switch(surf, toggle_rect_rel, self.sparse_enabled)
        
        self.render_fullscreen(surf, offset=(self.panel_rect.x, self.panel_rect.y))

    def _render_slider(self, surf, label, rect, value, y):
        """Render a slider widget."""
        x = 16
        label_surf = theme.font(10).render(label, True, theme.TEXT_BODY)
        surf.blit(label_surf, (x, y - 14))
        
        rect_rel = (rect.x - self.panel_rect.x, rect.y - self.panel_rect.y)
        theme.slider_track(surf, rect_rel)
        
        handle_x = rect_rel[0] + value * rect_rel[2]
        handle_rect = (handle_x - 6, rect_rel[1] - 4, 12, 24)
        theme.slider_handle(surf, handle_rect)
        
        # Value text
        val_text = f"{value:.2f}"
        val_surf = theme.font(9).render(val_text, True, theme.TEXT_DIM)
        surf.blit(val_surf, (rect_rel[0] + rect_rel[2] + 12, rect_rel[1] + 2))

    def get_config_updates(self, config):
        """Apply UI state to config object."""
        config.enable_electricity = self.electricity_enabled
        config.enable_biology = self.biology_enabled
        config.enable_weather = self.weather_enabled
        config.bloom_enabled = self.bloom_enabled
        
        # Map normalized values to actual ranges
        config.charge_decay = self.charge_decay * 10.0
        config.breakdown_threshold = self.breakdown_threshold * 1000.0
        config.growth_rate = self.growth_rate
        config.decay_rate = self.decay_rate
        config.evaporation_rate = self.evaporation_rate
        config.saturation_threshold = self.saturation_threshold * 200.0
        config.bloom_threshold = self.bloom_threshold
        config.bloom_intensity = self.bloom_intensity
        
        # Sparse mode is handled directly via pipeline enable_sparse_mode
        return {"sparse_enabled": self.sparse_enabled}
