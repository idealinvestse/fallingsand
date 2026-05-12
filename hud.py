"""OpenGL-based HUD for Falling Sand simulation."""

import pygame

import ui.theme as theme
from ui.overlay import OverlayRenderer


class HUD:
    """HUD overlay with material palette, brush info, and help text."""

    def __init__(self, ctx, window_size, particles):
        self._renderer = OverlayRenderer(ctx, window_size)
        self.ctx = ctx
        self.window_width, self.window_height = window_size
        self.particles = particles
        self.num_types = len(particles)

        # Layout constants
        self.palette_margin = 15
        self.palette_cell_size = 26
        self.palette_gap = 3
        self.palette_cols = 16
        self.palette_rows = 4
        self.palette_y = 15

        self.brush_info_x = 15
        self.brush_info_y = 15
        self.brush_info_w = 280
        self.brush_info_h = 80

        self.help_h = 36
        self.help_y = self.window_height - self.help_h - 15

        # State
        self.current_brush = 1
        self.brush_size = 12
        self.brush_mode = 0
        self.mode_names = ["material", "heat", "cool", "spark"]
        self.hover_cell = -1

        # Cached HUD surface
        self._hud_surface: pygame.Surface | None = None
        self._render_hud()

    def _create_palette_surface(self):
        """Create the material palette with colored cells."""
        inner_w = self.palette_cols * (self.palette_cell_size + self.palette_gap) + self.palette_gap
        inner_h = self.palette_rows * (self.palette_cell_size + self.palette_gap) + self.palette_gap
        
        # Rounded panel dimensions
        panel_w = inner_w + 20
        panel_h = inner_h + 20
        surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        
        rect = pygame.Rect(0, 0, panel_w, panel_h)
        theme.rounded_panel(surface, rect, radius=12, shadow=True)
        theme.accent_strip(surface, rect, theme.ACCENT_AMBER, height=3)

        start_x, start_y = 10, 10

        for i in range(self.num_types):
            row = i // self.palette_cols
            col = i % self.palette_cols

            x = start_x + col * (self.palette_cell_size + self.palette_gap)
            y = start_y + row * (self.palette_cell_size + self.palette_gap)

            particle = self.particles[i]
            color = particle.color
            
            cell_rect = pygame.Rect(x, y, self.palette_cell_size, self.palette_cell_size)
            
            # Hover effect: pop up slightly
            draw_y = y
            if i == self.hover_cell:
                draw_y -= 2
                # Glow under hover
                glow_rect = cell_rect.inflate(4, 4)
                pygame.draw.rect(surface, (*color, 60), glow_rect, border_radius=6)

            # Draw cell
            pygame.draw.rect(surface, color, (x, draw_y, self.palette_cell_size, self.palette_cell_size), border_radius=4)

            # Selection highlight
            if i == self.current_brush:
                # Outer amber border
                pygame.draw.rect(surface, theme.ACCENT_AMBER, (x-1, draw_y-1, self.palette_cell_size+2, self.palette_cell_size+2), width=2, border_radius=5)
            else:
                pygame.draw.rect(surface, (40, 45, 60), (x, draw_y, self.palette_cell_size, self.palette_cell_size), width=1, border_radius=4)

            # Draw number for first 9 materials
            if i < 9:
                # Pill background for contrast
                pill_w, pill_h = 10, 10
                pill_rect = pygame.Rect(x + 2, draw_y + 2, pill_w, pill_h)
                pygame.draw.rect(surface, (20, 20, 30, 180), pill_rect, border_radius=3)
                num_text = theme.font(8, bold=True).render(str(i + 1), True, (240, 240, 240))
                surface.blit(num_text, (x + 3, draw_y + 1))

        return surface

    def _palette_origin(self, palette_width: int) -> tuple[int, int]:
        """Place the palette to the right of the brush info card when possible."""
        x = self.brush_info_x + self.brush_info_w + 16
        max_x = self.window_width - palette_width - self.palette_margin
        if x > max_x:
            x = max(self.palette_margin, max_x)
        y = self.palette_y
        return x, y

    def _create_brush_info_surface(self):
        """Create brush info card."""
        surface = pygame.Surface((self.brush_info_w, self.brush_info_h), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, self.brush_info_w, self.brush_info_h)
        theme.rounded_panel(surface, rect, radius=10, shadow=True)
        
        particle = self.particles[self.current_brush]
        theme.accent_strip(surface, rect, particle.color, height=4)

        # Swatch
        swatch_rect = pygame.Rect(12, 16, 48, 48)
        pygame.draw.rect(surface, particle.color, swatch_rect, border_radius=8)
        pygame.draw.rect(surface, theme.BORDER_BRIGHT, swatch_rect, width=1, border_radius=8)

        # Name
        name_text = theme.font(14, bold=True).render(particle.name.upper(), True, theme.TEXT_PRIMARY)
        surface.blit(name_text, (70, 16))

        # Stats
        y = 40
        # Mode chip
        theme.chip(surface, 70, y, f"MODE: {self.mode_names[self.brush_mode]}", fg=theme.TEXT_BODY, bg=(40, 45, 60, 200))
        # Size chip
        theme.chip(surface, 180, y, f"SIZE: {self.brush_size}", fg=theme.TEXT_BODY, bg=(40, 45, 60, 200))

        return surface

    def _create_props_surface(self):
        """Create material properties panel."""
        w, h = 300, 140
        surface = pygame.Surface((w, h), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, w, h)
        theme.rounded_panel(surface, rect, radius=10, shadow=True)
        
        y = 8
        y = theme.section_header(surface, 12, y, "MATERIAL PROPERTIES", width=w-24)
        
        particle = self.particles[self.current_brush]
        props = [
            f"Density: {particle.density:.1f}",
            f"Flammability: {particle.flammability:.2f}",
            f"Thermal Cond: {particle.thermal_conductivity:.2f}",
            f"Viscosity: {particle.viscosity:.2f}",
            f"Melting Pt: {particle.melting_point}",
            f"Boiling Pt: {particle.boiling_point}",
        ]

        start_y = y
        for i, prop in enumerate(props):
            txt = theme.font(10).render(prop, True, theme.TEXT_BODY)
            if i < 3:
                surface.blit(txt, (16, y))
                y += 18
            else:
                if i == 3:
                    y = start_y
                surface.blit(txt, (150, y))
                y += 18

        return surface

    def _create_help_surface(self):
        """Create centered help bar with kbd chips."""
        # Calculate width dynamically based on content
        font_obj = theme.font(10)
        items = [
            ("1-4", "Mode"),
            ("[ / ]", "Size"),
            ("Scroll", "Material"),
            ("LMB", "Paint"),
            ("RMB", "Erase"),
            ("I", "Inspector"),
            ("H", "Help"),
            ("Esc", "Pause")
        ]
        
        # Measure
        total_w = 20 # start padding
        for key, desc in items:
            key_w = font_obj.render(key, True, (0,0,0)).get_width() + 10 # kbd_chip padding
            desc_w = font_obj.render(desc, True, (0,0,0)).get_width()
            total_w += key_w + desc_w + 25 # gap
        
        surface = pygame.Surface((total_w, self.help_h), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, total_w, self.help_h)
        theme.rounded_panel(surface, rect, radius=18, fill=(18, 20, 28, 200), border=theme.BORDER)
        
        x = 12
        for key, desc in items:
            x = theme.kbd_chip(surface, x, 8, key) + 6
            txt = font_obj.render(desc, True, theme.TEXT_DIM)
            surface.blit(txt, (x, 10))
            x += txt.get_width() + 18
            
        return surface

    def _render_hud(self):
        """Render complete HUD to cached surface."""
        hud_surface = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        
        # 1. Palette (top row, to the right of the brush card)
        palette = self._create_palette_surface()
        px, py = self._palette_origin(palette.get_width())
        hud_surface.blit(palette, (px, py))

        palette_bottom = py + palette.get_height()
        info_y = palette_bottom + 10
        
        # Tooltip if hovering
        if 0 <= self.hover_cell < self.num_types:
            material = self.particles[self.hover_cell]
            name = material.name.upper()
            description = getattr(material, 'description', '')
            
            # Calculate tooltip size
            name_txt = theme.font(11, bold=True).render(name, True, theme.TEXT_PRIMARY)
            name_w = name_txt.get_width()
            
            if description:
                # Word wrap description
                desc_words = description.split()
                desc_lines = []
                current_line = []
                current_width = 0
                max_width = 300
                
                for word in desc_words:
                    word_width = theme.font(10).render(word, True, theme.TEXT_BODY).get_width()
                    if current_width + word_width + 4 <= max_width:
                        current_line.append(word)
                        current_width += word_width + 4
                    else:
                        desc_lines.append(' '.join(current_line))
                        current_line = [word]
                        current_width = word_width + 4
                if current_line:
                    desc_lines.append(' '.join(current_line))
                
                # Calculate dimensions
                tw = max(name_w + 20, max_width + 20)
                th = 24 + len(desc_lines) * 14 + 8
            else:
                tw = name_w + 20
                th = 24
            
            tx = (self.window_width - tw) // 2
            ty = palette_bottom + 5
            t_rect = pygame.Rect(tx, ty, tw, th)
            theme.rounded_panel(hud_surface, t_rect, radius=6, fill=(30, 35, 50, 240), shadow=False)
            
            # Render name
            hud_surface.blit(name_txt, (tx + 10, ty + 4))
            
            # Render description
            if description:
                desc_y = ty + 24
                for line in desc_lines:
                    desc_txt = theme.font(10).render(line, True, theme.TEXT_BODY)
                    hud_surface.blit(desc_txt, (tx + 10, desc_y))
                    desc_y += 14

        # 2. Brush Info (left column under the palette)
        info = self._create_brush_info_surface()
        hud_surface.blit(info, (self.brush_info_x, info_y))
        
        # 3. Material Properties (below info)
        props = self._create_props_surface()
        hud_surface.blit(props, (self.brush_info_x, info_y + self.brush_info_h + 10))

        # 4. Help Bar (bottom center)
        help_bar = self._create_help_surface()
        hx = (self.window_width - help_bar.get_width()) // 2
        hud_surface.blit(help_bar, (hx, self.help_y))

        self._hud_surface = hud_surface

    def update(self, current_brush, brush_size, brush_mode):
        """Update HUD state and re-render if changed."""
        mx, my = pygame.mouse.get_pos()
        hover = self._get_cell_at(mx, my)
        
        changed = (
            self.current_brush != current_brush or
            self.brush_size != brush_size or
            self.brush_mode != brush_mode or
            self.hover_cell != hover
        )

        if changed:
            self.current_brush = current_brush
            self.brush_size = brush_size
            self.brush_mode = brush_mode
            self.hover_cell = hover
            self._render_hud()

    def render(self):
        """Render HUD overlay."""
        if self._hud_surface:
            self._renderer.render_fullscreen(self._hud_surface)

    def _get_cell_at(self, mx, my) -> int:
        """Helper to find which palette cell is under the mouse."""
        inner_w = self.palette_cols * (self.palette_cell_size + self.palette_gap) + self.palette_gap
        palette_width = inner_w + 20
        palette_x, palette_y = self._palette_origin(palette_width)
        palette_x += 10
        palette_y += 10
        
        rel_x = mx - palette_x
        rel_y = my - palette_y
        
        if rel_x < 0 or rel_y < 0:
            return -1
        
        col = rel_x // (self.palette_cell_size + self.palette_gap)
        row = rel_y // (self.palette_cell_size + self.palette_gap)
        
        # Check if actually inside a cell (not in the gap)
        cell_rel_x = rel_x % (self.palette_cell_size + self.palette_gap)
        cell_rel_y = rel_y % (self.palette_cell_size + self.palette_gap)
        
        if cell_rel_x >= self.palette_cell_size or cell_rel_y >= self.palette_cell_size:
            return -1

        if 0 <= col < self.palette_cols and 0 <= row < self.palette_rows:
            index = row * self.palette_cols + col
            if index < self.num_types:
                return index
        return -1

    def handle_click(self, mx, my):
        """Handle mouse click for material selection."""
        cell = self._get_cell_at(mx, my)
        return cell if cell != -1 else None

