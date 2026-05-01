"""Shared theme constants, fonts, and UI draw helpers for HUD overlays."""

from __future__ import annotations

import pygame

# ── Palette ───────────────────────────────────────────────────────────
BG_PANEL = (18, 20, 28, 235)
BG_PANEL_DEEP = (12, 14, 22, 240)
BG_SHADOW = (0, 0, 0, 110)
BORDER = (90, 95, 120, 255)
BORDER_BRIGHT = (130, 145, 180, 255)
ACCENT_AMBER = (230, 180, 90)
TEXT_PRIMARY = (232, 236, 250)
TEXT_BODY = (200, 204, 214)
TEXT_DIM = (140, 148, 168)
OK_GREEN = (120, 220, 120)
WARN_ORANGE = (240, 160, 60)
DANGER_RED = (255, 90, 90)
INFO_BLUE = (100, 180, 255)

# Common gradient stops for temperature meter
TEMP_GRADIENT = [
    (0.0, (100, 180, 255)),
    (0.32, (220, 220, 230)),
    (0.67, (255, 160, 60)),
    (1.0, (255, 60, 60)),
]

# ── Fonts ─────────────────────────────────────────────────────────────
_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}


def font(size: int, bold: bool = False) -> pygame.font.Font:
    """Return cached Consolas font at given size."""
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = pygame.font.SysFont("Consolas", size, bold=bold)
    return _FONT_CACHE[key]


# ── Draw helpers ──────────────────────────────────────────────────────


def rounded_panel(
    surf: pygame.Surface,
    rect: pygame.Rect,
    *,
    radius: int = 10,
    fill: tuple[int, ...] = BG_PANEL,
    border: tuple[int, ...] | None = BORDER,
    shadow: bool = True,
) -> None:
    """Draw a rounded panel with optional drop shadow and border."""
    if shadow:
        shadow_rect = rect.move(3, 3)
        pygame.draw.rect(surf, BG_SHADOW, shadow_rect, border_radius=radius)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width=1, border_radius=radius)


def accent_strip(
    surf: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
    height: int = 4,
) -> pygame.Rect:
    """Draw a colored accent strip at the top of rect. Returns the strip rect."""
    strip = pygame.Rect(rect.x, rect.y, rect.width, height)
    pygame.draw.rect(surf, color, strip, border_radius=max(0, height // 2))
    return strip


def section_header(
    surf: pygame.Surface,
    x: int,
    y: int,
    text: str,
    *,
    width: int = 0,
    color: tuple[int, int, int] = ACCENT_AMBER,
) -> int:
    """Draw a section header with a thin divider above it. Returns next y."""
    font_obj = font(11, bold=True)
    # Divider line
    line_y = y
    if width:
        pygame.draw.line(surf, (*color, 80), (x, line_y), (x + width, line_y))
    y += 3
    rendered = font_obj.render(text, True, color)
    surf.blit(rendered, (x, y))
    return y + rendered.get_height() + 2


def chip(
    surf: pygame.Surface,
    x: int,
    y: int,
    text: str,
    *,
    fg: tuple[int, int, int] = TEXT_PRIMARY,
    bg: tuple[int, ...] = (45, 50, 65, 200),
    border: tuple[int, ...] | None = (70, 80, 100, 255),
    radius: int = 6,
) -> int:
    """Draw a rounded label chip. Returns rightmost x coordinate."""
    font_obj = font(10)
    rendered = font_obj.render(text, True, fg)
    pad_x, pad_y = 6, 2
    w, h = rendered.get_width() + pad_x * 2, rendered.get_height() + pad_y * 2
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surf, border, rect, width=1, border_radius=radius)
    surf.blit(rendered, (x + pad_x, y + pad_y))
    return x + w


def _with_alpha(color: tuple[int, ...], alpha: int) -> tuple[int, int, int, int]:
    """Return an RGBA color from an RGB or RGBA tuple."""
    if len(color) == 4:
        return color[0], color[1], color[2], color[3]
    return color[0], color[1], color[2], alpha


def _lerp_color(
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """Linearly interpolate between two RGB colors."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))  # type: ignore[return-value]


def _value_to_color(
    value: float,
    vmin: float,
    vmax: float,
    stops: list[tuple[float, tuple[int, int, int]]],
) -> tuple[int, int, int]:
    """Map a value to a color using gradient stops."""
    if value <= vmin:
        return stops[0][1]
    if value >= vmax:
        return stops[-1][1]
    t = (value - vmin) / (vmax - vmin)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            local_t = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
            return _lerp_color(c0, c1, local_t)
    return stops[-1][1]


def meter(
    surf: pygame.Surface,
    rect: pygame.Rect,
    value: float,
    vmin: float,
    vmax: float,
    *,
    gradient: list[tuple[float, tuple[int, int, int]]] | None = None,
    markers: tuple[float, ...] = (),
    marker_color: tuple[int, int, int] = TEXT_PRIMARY,
) -> None:
    """Draw a horizontal meter bar."""
    if gradient is None:
        gradient = [(0.0, OK_GREEN), (0.5, WARN_ORANGE), (1.0, DANGER_RED)]
    if vmax == vmin:
        vmax = vmin + 1.0

    # Background track
    pygame.draw.rect(surf, (30, 35, 45, 200), rect, border_radius=4)

    # Fill
    t = max(0.0, min(1.0, (value - vmin) / (vmax - vmin))) if vmax != vmin else 0.0
    fill_w = int(rect.width * t)
    if fill_w > 0:
        color = _value_to_color(value, vmin, vmax, gradient)
        fill_rect = pygame.Rect(rect.x, rect.y, fill_w, rect.height)
        pygame.draw.rect(surf, color, fill_rect, border_radius=4)

    # Border
    pygame.draw.rect(surf, BORDER, rect, width=1, border_radius=4)

    # Markers
    for m in markers:
        mt = max(0.0, min(1.0, (m - vmin) / (vmax - vmin))) if vmax != vmin else 0.0
        mx = rect.x + int(rect.width * mt)
        pygame.draw.line(
            surf, marker_color, (mx, rect.y - 1), (mx, rect.y + rect.height + 1), 2
        )


def signed_meter(
    surf: pygame.Surface,
    rect: pygame.Rect,
    value: float,
    abs_max: float,
    *,
    neg_color: tuple[int, int, int] = INFO_BLUE,
    pos_color: tuple[int, int, int] = DANGER_RED,
    zero_color: tuple[int, int, int] = TEXT_DIM,
    markers: tuple[float, ...] = (),
) -> None:
    """Draw a signed meter centered at 0."""
    if abs_max == 0:
        abs_max = 1.0
    pygame.draw.rect(surf, (30, 35, 45, 200), rect, border_radius=4)
    center_x = rect.x + rect.width // 2

    # Zero line
    pygame.draw.line(
        surf, zero_color, (center_x, rect.y), (center_x, rect.y + rect.height), 2
    )

    # Fill
    t = max(-1.0, min(1.0, value / abs_max)) if abs_max != 0 else 0.0
    fill_w = int((rect.width // 2) * abs(t))
    if fill_w > 0:
        if t > 0:
            fill_rect = pygame.Rect(center_x, rect.y, fill_w, rect.height)
            color = pos_color
        else:
            fill_rect = pygame.Rect(center_x - fill_w, rect.y, fill_w, rect.height)
            color = neg_color
        pygame.draw.rect(surf, color, fill_rect, border_radius=4)

    pygame.draw.rect(surf, BORDER, rect, width=1, border_radius=4)

    for m in markers:
        if -abs_max <= m <= abs_max:
            mt = m / abs_max
            mx = center_x + int((rect.width // 2) * mt)
            pygame.draw.line(
                surf, TEXT_PRIMARY, (mx, rect.y - 1), (mx, rect.y + rect.height + 1), 2
            )


def kbd_chip(
    surf: pygame.Surface,
    x: int,
    y: int,
    text: str,
    *,
    fg: tuple[int, int, int] = TEXT_BODY,
    bg: tuple[int, ...] = (55, 60, 75, 200),
    border: tuple[int, ...] = (90, 100, 125, 255),
    radius: int = 4,
) -> int:
    """Draw a keyboard-key style chip. Returns rightmost x coordinate."""
    font_obj = font(10)
    rendered = font_obj.render(text, True, fg)
    pad_x, pad_y = 5, 2
    w, h = rendered.get_width() + pad_x * 2, rendered.get_height() + pad_y * 2
    rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, bg, rect, border_radius=radius)
    pygame.draw.rect(surf, border, rect, width=1, border_radius=radius)
    # Highlight top edge
    highlight = pygame.Rect(
        rect.x + 1,
        rect.y + 1,
        rect.width - 2,
        rect.height // 2 - 1,
    )
    pygame.draw.rect(
        surf,
        (
            min(255, bg[0] + 20),
            min(255, bg[1] + 20),
            min(255, bg[2] + 20),
            (_with_alpha(bg, 200))[3] // 2,
        ),
        highlight,
        border_radius=max(0, radius - 1),
    )
    surf.blit(rendered, (x + pad_x, y + pad_y))
    return x + w
