from __future__ import annotations

import pygame
import moderngl

from levels import get_all_levels
from ui.overlay import OverlayRenderer
import ui.theme as theme


class PauseMenu:
    def __init__(self, ctx: moderngl.Context, window_size: tuple[int, int]):
        self._renderer = OverlayRenderer(ctx, window_size)
        self.ctx = ctx
        self.window_width, self.window_height = window_size
        self.visible = False
        self.levels = get_all_levels()
        self.selected_level = self.levels[0].level_id if self.levels else None

        self.buttons: list[tuple[str, pygame.Rect]] = []
        self.level_click_areas: list[tuple[str, pygame.Rect]] = []

    def toggle(self) -> bool:
        self.visible = not self.visible
        if self.visible:
            self.refresh_levels()
        return self.visible

    def refresh_levels(self) -> None:
        self.levels = get_all_levels()
        if self.levels and self.selected_level not in {level.level_id for level in self.levels}:
            self.selected_level = self.levels[0].level_id

    def _buttons_spec(self) -> list[str]:
        return [
            "resume",
            "load_level",
            "save_level",
            "toggle_turbulence",
            "toggle_wet_dry",
            "toggle_thermal",
            "toggle_sfx",
            "screenshot",
            "quit",
        ]

    def _pretty(self, action: str, values: dict[str, str]) -> str:
        if action in values:
            return values[action]
        return action.replace("_", " ").title()

    def _difficulty_text(self, difficulty: int) -> str:
        stars = "★" * max(1, min(5, difficulty))
        return f"Difficulty {stars}"

    def _make_surface(self, status: dict[str, str]) -> pygame.Surface:
        surf = pygame.Surface((self.window_width, self.window_height), pygame.SRCALPHA)
        # Deep dim backdrop
        surf.fill(theme.BG_SHADOW)

        panel_w, panel_h = min(860, self.window_width - 60), min(640, self.window_height - 60)
        panel = pygame.Rect((self.window_width - panel_w) // 2, (self.window_height - panel_h) // 2, panel_w, panel_h)
        theme.rounded_panel(surf, panel, fill=theme.BG_PANEL_DEEP, radius=12, shadow=True)
        theme.accent_strip(surf, panel, theme.ACCENT_AMBER, height=4)

        # Title
        title_font = theme.font(32, bold=True)
        title = title_font.render("PAUSED", True, theme.TEXT_PRIMARY)
        surf.blit(title, (panel.x + 32, panel.y + 24))
        
        # Amber underline for title
        pygame.draw.line(surf, theme.ACCENT_AMBER, (panel.x + 32, panel.y + 64), (panel.x + 140, panel.y + 64), 3)

        subtitle = theme.font(12).render("Press R to resume", True, theme.TEXT_DIM)
        surf.blit(subtitle, (panel.x + 32, panel.y + 70))

        self.buttons = []
        self.level_click_areas = []
        selected_level = next((level for level in self.levels if level.level_id == self.selected_level), None)

        labels = self._buttons_spec()
        left_x = panel.x + 32
        y_start = panel.y + 110
        btn_w = 240
        btn_h = 42
        gap = 12

        label_overrides = {
            "toggle_turbulence": f"Turbulence: {status['turbulence']}",
            "toggle_wet_dry": f"Wet/Dry: {status['wet_dry']}",
            "toggle_thermal": f"Thermal: {status['thermal']}",
            "toggle_sfx": f"SFX: {status['sfx']}",
        }

        # Draw buttons in 2 columns
        for i, action in enumerate(labels):
            col = i % 2
            row = i // 2

            bx = left_x + col * (btn_w + 24)
            by = y_start + row * (btn_h + gap)

            rect = pygame.Rect(bx, by, btn_w, btn_h)

            # Subtle gradient-like fill
            pygame.draw.rect(surf, (45, 50, 70), rect, border_radius=8)
            pygame.draw.rect(surf, theme.BORDER, rect, width=1, border_radius=8)

            # Left accent for toggle-ons
            is_on = False
            if action.startswith("toggle_"):
                key = action.replace("toggle_", "")
                if status.get(key) == "ON":
                    is_on = True

            if is_on:
                pygame.draw.rect(surf, theme.ACCENT_AMBER, (bx, by, 4, btn_h), border_radius=2)

            text = theme.font(13, bold=True).render(self._pretty(action, label_overrides), True, theme.TEXT_PRIMARY)
            surf.blit(text, (rect.x + 14, rect.y + (btn_h - text.get_height()) // 2))
            self.buttons.append((action, rect))

        # Levels section
        levels_x = panel.x + 540
        levels_title = theme.font(14, bold=True).render("LEVELS", True, theme.ACCENT_AMBER)
        surf.blit(levels_title, (levels_x, panel.y + 110))
        
        grid_x = levels_x
        grid_y = panel.y + 140
        cell_w = 140
        cell_h = 80
        l_gap = 12
        l_cols = 2

        for idx, level in enumerate(self.levels):
            row = idx // l_cols
            col = idx % l_cols
            lx = grid_x + col * (cell_w + l_gap)
            ly = grid_y + row * (cell_h + l_gap)
            rect = pygame.Rect(lx, ly, cell_w, cell_h)
            
            # Level card
            bg = (*level.thumbnail_color, 180)
            pygame.draw.rect(surf, bg, rect, border_radius=8)
            
            is_selected = level.level_id == self.selected_level
            border_color = theme.ACCENT_AMBER if is_selected else (40, 45, 60)
            pygame.draw.rect(surf, border_color, rect, width=2 if is_selected else 1, border_radius=8)
            
            if is_selected:
                # Top accent for selected level
                theme.accent_strip(surf, rect, theme.ACCENT_AMBER, height=3)

            name = theme.font(11, bold=True).render(level.name, True, (255, 255, 255))
            desc_text = level.description if len(level.description) <= 20 else level.description[:20] + "..."
            desc = theme.font(9).render(desc_text, True, (220, 220, 220))
            diff_text = theme.font(9, bold=True).render(f"D{max(1, min(5, level.difficulty))}", True, theme.TEXT_PRIMARY)
            
            # Simple shadow for text on varied backgrounds
            shad = theme.font(11, bold=True).render(level.name, True, (0, 0, 0))
            surf.blit(shad, (lx + 9, ly + 9))
            surf.blit(name, (lx + 8, ly + 8))
            surf.blit(desc, (lx + 8, ly + 28))
            surf.blit(diff_text, (lx + cell_w - diff_text.get_width() - 10, ly + 8))
            
            self.level_click_areas.append((level.level_id, rect))

        # Selected level details panel improves discovery and onboarding.
        details_rect = pygame.Rect(panel.x + 32, panel.y + 368, 468, 168)
        theme.rounded_panel(surf, details_rect, fill=(32, 36, 48, 230), radius=10, shadow=False)
        theme.accent_strip(surf, details_rect, theme.ACCENT_AMBER, height=3)

        details_title = theme.font(14, bold=True).render("SCENARIO DETAILS", True, theme.ACCENT_AMBER)
        surf.blit(details_title, (details_rect.x + 14, details_rect.y + 12))

        if selected_level is not None:
            name = theme.font(16, bold=True).render(selected_level.name.upper(), True, theme.TEXT_PRIMARY)
            surf.blit(name, (details_rect.x + 14, details_rect.y + 36))

            objective_label = theme.font(10, bold=True).render("Objective", True, theme.TEXT_DIM)
            surf.blit(objective_label, (details_rect.x + 14, details_rect.y + 62))
            objective = selected_level.objective or selected_level.description
            objective_lines = []
            words = objective.split()
            line = ""
            for word in words:
                candidate = word if not line else f"{line} {word}"
                if theme.font(10).render(candidate, True, theme.TEXT_BODY).get_width() > 410 and line:
                    objective_lines.append(line)
                    line = word
                else:
                    line = candidate
            if line:
                objective_lines.append(line)
            for i, text_line in enumerate(objective_lines[:3]):
                txt = theme.font(10).render(text_line, True, theme.TEXT_BODY)
                surf.blit(txt, (details_rect.x + 14, details_rect.y + 76 + i * 16))

            # Tags and difficulty chips make scenario selection faster.
            tags = selected_level.tags or ("sandbox",)
            chip_x = details_rect.x + 14
            chip_y = details_rect.bottom - 34
            chip_x = theme.chip(surf, chip_x, chip_y, self._difficulty_text(selected_level.difficulty), fg=theme.TEXT_PRIMARY, bg=(45, 50, 65, 220)) + 6
            for tag in tags[:4]:
                chip_x = theme.chip(surf, chip_x, chip_y, tag.replace("_", " ").title(), fg=theme.TEXT_BODY, bg=(40, 45, 60, 200)) + 6
        else:
            info = theme.font(11).render("No level selected.", True, theme.TEXT_DIM)
            surf.blit(info, (details_rect.x + 14, details_rect.y + 44))
            hint = theme.font(10).render("Press Tab to browse or Enter to load.", True, theme.TEXT_BODY)
            surf.blit(hint, (details_rect.x + 14, details_rect.y + 66))

        # Bottom hint bar with kbd chips
        hints = [
            ("R", "resume"),
            ("Q", "quit"),
            ("Tab", "cycle"),
            ("Enter", "load")
        ]
        hx = panel.x + 32
        hy = panel.bottom - 40
        for key, desc in hints:
            hx = theme.kbd_chip(surf, hx, hy, key) + 6
            txt = theme.font(10).render(desc, True, theme.TEXT_DIM)
            surf.blit(txt, (hx, hy + 2))
            hx += txt.get_width() + 20

        return surf

    def render(self, *, status: dict[str, str]) -> None:
        if not self.visible:
            return
        surface = self._make_surface(status)
        self._renderer.render_fullscreen(surface)

    def handle_click(self, mx: int, my: int) -> tuple[str, str | None] | None:
        if not self.visible:
            return None

        for level_id, rect in self.level_click_areas:
            if rect.collidepoint(mx, my):
                self.selected_level = level_id
                return ("select_level", level_id)

        for action, rect in self.buttons:
            if rect.collidepoint(mx, my):
                payload = self.selected_level if action == "load_level" else None
                return (action, payload)

        return None

    def cycle_level(self, delta: int) -> str | None:
        if not self.levels:
            self.selected_level = None
            return None
        ids = [level.level_id for level in self.levels]
        if self.selected_level not in ids:
            self.selected_level = ids[0]
            return self.selected_level
        idx = ids.index(self.selected_level)
        self.selected_level = ids[(idx + delta) % len(ids)]
        return self.selected_level

    def get_selected_level_id(self) -> str | None:
        return self.selected_level


class KeybindOverlay:
    def __init__(self, ctx: moderngl.Context, window_size: tuple[int, int]):
        self._renderer = OverlayRenderer(ctx, window_size)
        self.visible = False

    def toggle(self) -> bool:
        self.visible = not self.visible
        return self.visible

    def _surface(self) -> pygame.Surface:
        w, h = self._renderer.window_width, self._renderer.window_height
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        
        panel_w, panel_h = min(600, w - 80), min(500, h - 80)
        panel = pygame.Rect((w - panel_w) // 2, (h - panel_h) // 2, panel_w, panel_h)
        theme.rounded_panel(surf, panel, radius=12, shadow=True)
        theme.accent_strip(surf, panel, theme.ACCENT_AMBER, height=4)

        title = theme.font(20, bold=True).render("KEYBINDS", True, theme.TEXT_PRIMARY)
        surf.blit(title, (panel.x + 24, panel.y + 20))
        pygame.draw.line(surf, theme.ACCENT_AMBER, (panel.x + 24, panel.y + 50), (panel.x + 100, panel.y + 50), 2)

        lines = [
            ("LMB/RMB", "place/erase"),
            ("Scroll", "switch material"),
            ("1-4", "mat/heat/cool/spark"),
            ("[ / ]", "brush size"),
            ("S / L", "save/load grid"),
            ("C", "clear grid"),
            ("X / Shift+X", "explosion"),
            ("Arrows + W", "wind control"),
            ("V", "pressure overlay"),
            ("ESC / P", "pause menu"),
            ("Ctrl+Z", "undo"),
            ("F12", "screenshot"),
            ("H", "toggle help"),
            ("I", "toggle inspector"),
        ]

        # Draw in 2 columns
        col_w = (panel_w - 48) // 2
        y_start = panel.y + 70
        for i, (key, desc) in enumerate(lines):
            col = i // 7
            row = i % 7
            
            lx = panel.x + 24 + col * col_w
            ly = y_start + row * 32
            
            theme.kbd_chip(surf, lx, ly, key)
            txt = theme.font(11).render(desc, True, theme.TEXT_BODY)
            surf.blit(txt, (lx + 100, ly + 4))

        return surf

    def render(self) -> None:
        if not self.visible:
            return
        self._renderer.render_fullscreen(self._surface())
