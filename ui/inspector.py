"""Cell inspector panel showing properties of the cell under the mouse cursor."""
import pygame

from core.constants import TEMP_AMBIENT
from ui.overlay import OverlayRenderer
import ui.theme as theme


class InspectorPanel:
    """HUD overlay showing detailed cell information, fixed to the top-right corner."""

    def __init__(self, ctx, window_size):
        """Initialize inspector panel with OpenGL context."""
        self._renderer = OverlayRenderer(ctx, window_size)
        self.ctx = ctx
        self.window_width, self.window_height = window_size

        # Panel dimensions
        self.panel_width = 340
        self.panel_height = 360
        self.margin = 15

        # State
        self.visible = True
        self.last_mouse_xy = (0, 0)
        self.last_grid_xy = (0, 0)
        self.cached_probe = None
        self.cached_surface = None

    def set_visible(self, visible: bool) -> None:
        """Set panel visibility."""
        self.visible = visible
        if not visible:
            self.cached_probe = None
            self.cached_surface = None

    def toggle(self) -> None:
        """Toggle panel visibility."""
        self.set_visible(not self.visible)

    def _decode_flags(self, type_id: int, flags: int) -> str:
        """Decode flags based on material type."""
        if type_id in (35, 34):  # T_BLAST, T_SHRAPNEL
            dir_oct = flags & 0x7
            power = (flags >> 3) & 0x1F
            dirs = ["E", "NE", "N", "NW", "W", "SW", "S", "SE"]
            return f"dir={dirs[dir_oct]} pow={power}"
        else:
            return f"0x{flags:02X} (cool/charge)"

    def _render_surface(self, probe: dict) -> pygame.Surface:
        """Render the probe data to a pygame surface."""
        surface = pygame.Surface((self.panel_width, self.panel_height), pygame.SRCALPHA)
        panel_rect = pygame.Rect(0, 0, self.panel_width, self.panel_height)
        theme.rounded_panel(surface, panel_rect, radius=10, shadow=True)

        mat = probe.get("material")
        cell = probe.get("cell")

        if mat is None or cell is None:
            txt = theme.font(12, bold=True).render("NO CELL DATA", True, theme.TEXT_DIM)
            surface.blit(txt, (16, 16))
            return surface

        # Accent strip at top
        theme.accent_strip(surface, panel_rect, mat.color, height=4)

        # Header row
        y = 12
        # Color swatch
        swatch = pygame.Rect(12, y, 18, 18)
        pygame.draw.rect(surface, mat.color, swatch, border_radius=3)
        pygame.draw.rect(surface, theme.TEXT_PRIMARY, swatch, width=1, border_radius=3)

        # Name
        name_surf = theme.font(14, bold=True).render(mat.name.upper(), True, mat.color)
        surface.blit(name_surf, (36, y))

        # ID chip
        id_x = 36 + name_surf.get_width() + 8
        theme.chip(surface, id_x, y + 1, f"ID {cell.type_id}", fg=theme.TEXT_DIM, bg=(35, 38, 50, 180))

        y += 28

        # ── STATE ──
        y = theme.section_header(surface, 12, y, "STATE", width=self.panel_width - 24)
        lines = [
            f"Family:  {mat.state_family.name}",
            f"Category:  {mat.category.name}",
            f"Life:  {cell.life}",
            f"Flags:  {self._decode_flags(cell.type_id, cell.flags)}",
        ]
        for line in lines:
            txt = theme.font(10).render(line, True, theme.TEXT_BODY)
            surface.blit(txt, (16, y))
            y += 14
        y += 4

        # ── THERMAL ──
        y = theme.section_header(surface, 12, y, "THERMAL", width=self.panel_width - 24)
        temp_float = probe.get("temp_float")
        if temp_float is None:
            temp_float = float(TEMP_AMBIENT)
        temp_diff = temp_float - TEMP_AMBIENT

        # Temperature meter
        meter_rect = pygame.Rect(16, y, self.panel_width - 80, 10)
        theme.meter(
            surface, meter_rect, temp_float, 0.0, 300.0,
            gradient=theme.TEMP_GRADIENT,
            markers=(float(mat.melting_point), float(mat.boiling_point)),
        )
        # Temp value to the right of meter
        temp_txt = theme.font(10).render(f"{temp_float:.1f} ({temp_diff:+.1f})", True, theme.TEXT_BODY)
        surface.blit(temp_txt, (meter_rect.right + 6, y - 2))
        y += 18

        # Phase chips
        chip_x = 16
        if temp_float >= mat.melting_point:
            chip_x = theme.chip(surface, chip_x, y, ">MP", fg=(255, 255, 255), bg=(255, 120, 60, 200), radius=4) + 6
        if temp_float >= mat.boiling_point:
            chip_x = theme.chip(surface, chip_x, y, ">BP", fg=(255, 255, 255), bg=(255, 60, 60, 200), radius=4) + 6
        y += 20

        # ── MOTION ──
        y = theme.section_header(surface, 12, y, "MOTION", width=self.panel_width - 24)
        vel = probe.get("velocity")
        if vel:
            vx, vy = vel
            speed = (vx ** 2 + vy ** 2) ** 0.5
            # Speed meter
            sm_rect = pygame.Rect(16, y, self.panel_width - 80, 10)
            theme.meter(surface, sm_rect, speed, 0.0, 10.0)
            speed_txt = theme.font(10).render(f"{speed:.2f}", True, theme.TEXT_BODY)
            surface.blit(speed_txt, (sm_rect.right + 6, y - 2))
            y += 16
            vel_txt = theme.font(10).render(f"({vx:.2f}, {vy:.2f})", True, theme.TEXT_DIM)
            surface.blit(vel_txt, (16, y))
            y += 14

        wind = probe.get("wind")
        if wind:
            wx, wy = wind
            wind_txt = theme.font(10).render(f"Wind: ({wx:.2f}, {wy:.2f})", True, theme.OK_GREEN)
            surface.blit(wind_txt, (16, y))
            y += 14
        y += 4

        # ── FLUIDS ──
        y = theme.section_header(surface, 12, y, "FLUIDS", width=self.panel_width - 24)
        pressure = probe.get("pressure")
        if pressure is not None:
            pm_rect = pygame.Rect(16, y, self.panel_width - 80, 10)
            theme.signed_meter(surface, pm_rect, pressure, 5.0)
            press_txt = theme.font(10).render(f"{pressure:.3f}", True, theme.TEXT_BODY)
            surface.blit(press_txt, (pm_rect.right + 6, y - 2))
            y += 16

        divergence = probe.get("divergence")
        if divergence is not None:
            div_txt = theme.font(10).render(f"Divergence: {divergence:.3f}", True, theme.TEXT_DIM)
            surface.blit(div_txt, (16, y))
            y += 14

        vorticity = probe.get("vorticity")
        if vorticity is not None:
            vort_txt = theme.font(10).render(f"Vorticity: {vorticity:.3f}", True, theme.TEXT_DIM)
            surface.blit(vort_txt, (16, y))
            y += 14

        mass = probe.get("mass")
        if mass is not None:
            mass_txt = theme.font(10).render(f"Mass: {mass:.3f}", True, theme.TEXT_DIM)
            surface.blit(mass_txt, (16, y))
            y += 14
        y += 4

        # ── MATERIAL ──
        y = theme.section_header(surface, 12, y, "MATERIAL", width=self.panel_width - 24)
        props = [
            f"Density: {mat.density:.1f}",
            f"Flammability: {mat.flammability:.2f}",
            f"Thermal Cond: {mat.thermal_conductivity:.2f}",
            f"Viscosity: {mat.viscosity:.2f}",
            f"MP: {mat.melting_point}  BP: {mat.boiling_point}",
        ]
        for i, prop in enumerate(props):
            txt = theme.font(10).render(prop, True, theme.TEXT_DIM)
            if i < 3:
                surface.blit(txt, (16, y))
                y += 14
            else:
                if i == 3:
                    y -= 42  # back up for second column
                surface.blit(txt, (self.panel_width // 2 + 8, y))
                y += 14

        return surface

    def update(self, mouse_xy: tuple[int, int], grid_xy: tuple[int, int], probe: dict | None) -> None:
        """Update panel with new probe data."""
        self.last_mouse_xy = mouse_xy
        self.last_grid_xy = grid_xy

        if probe is None:
            self.cached_probe = None
            self.cached_surface = None
            return

        if self.cached_probe is None:
            changed = True
        else:
            cached_temp = self.cached_probe.get("temp_float")
            probe_temp = probe.get("temp_float")
            temp_changed = False
            if cached_temp is not None and probe_temp is not None:
                temp_changed = abs(cached_temp - probe_temp) > 0.01
            elif cached_temp != probe_temp:
                temp_changed = True

            changed = (
                self.cached_probe.get("cell") != probe.get("cell") or
                temp_changed or
                self.cached_probe.get("velocity") != probe.get("velocity") or
                self.cached_probe.get("pressure") != probe.get("pressure")
            )

        if changed:
            self.cached_probe = probe
            self.cached_surface = self._render_surface(probe)

    def render(self) -> None:
        """Render the panel fixed to the top-right corner."""
        if not self.visible or self.cached_surface is None:
            return

        px = self.window_width - self.panel_width - self.margin
        py = self.margin

        ndc_x = 2.0 * ((px + self.panel_width / 2.0) / self.window_width) - 1.0
        ndc_y = 1.0 - 2.0 * ((py + self.panel_height / 2.0) / self.window_height)
        scale_x = self.panel_width / self.window_width
        scale_y = self.panel_height / self.window_height

        self._renderer.render_positioned(
            self.cached_surface,
            ndc_offset=(ndc_x, ndc_y),
            ndc_scale=(scale_x, scale_y),
        )
