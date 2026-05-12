"""Falling Sand v6.0 — Entry Point.

v6 Genesis features:
- v6 material schema support (simulation/material_schema.py)
- FSND v8 chunked save format with CRC32 (simulation/persistence_v8.py)
- Electricity, biology, weather systems
- Bloom post-FX, AO, emissive glow, water depth rendering
- Debug overlays (Tab), inspector ecology (I)
"""

import argparse
import os
import sys
import pygame
from pygame.locals import (
    KEYDOWN,
    K_1,
    K_2,
    K_3,
    K_4,
    K_c,
    K_DOWN,
    K_e,
    K_ESCAPE,
    K_F12,
    K_h,
    K_i,
    K_LEFT,
    K_LEFTBRACKET,
    K_p,
    K_q,
    K_r,
    K_RIGHT,
    K_RIGHTBRACKET,
    K_RETURN,
    K_s,
    K_UP,
    K_v,
    K_w,
    K_x,
    K_l,
    K_TAB,
    K_z,
    MOUSEBUTTONDOWN,
    MOUSEBUTTONUP,
    MOUSEWHEEL,
    QUIT,
    VIDEORESIZE,
)
from pathlib import Path

from core.config import SimulationConfig
from gpu.context import ContextManager
from gpu.shader_registry import load_all_shaders
from levels import get_custom_store, get_level_by_id
from simulation.engine import SimulationEngine
from hud import HUD
from ui import KeybindOverlay, PauseMenu, SfxManager
from ui.inspector import InspectorPanel
from ui.overlay import OverlayRenderer
from ui.system_controls import SystemControls
from ui.performance_overlay import PerformanceOverlay
import ui.theme as theme


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Falling Sand Simulation")
    parser.add_argument("--width", type=int, default=1024, help="Simulation grid width")
    parser.add_argument("--height", type=int, default=1024, help="Simulation grid height")
    parser.add_argument("--window-width", type=int, default=900, help="Window width")
    parser.add_argument("--window-height", type=int, default=900, help="Window height")
    parser.add_argument("--no-turbulence", action="store_true", help="Disable turbulence physics")
    parser.add_argument("--no-wet-dry", action="store_true", help="Disable wet-dry physics")
    parser.add_argument("--no-thermal", action="store_true", help="Disable thermal simulation")
    parser.add_argument("--no-hud", action="store_true", help="Disable HUD overlay")
    parser.add_argument("--no-stats", action="store_true", help="Disable stats tracking")
    parser.add_argument("--sim-substeps", type=int, default=1, help="Simulation substeps per frame")
    parser.add_argument("--pressure-iterations", type=int, default=20, help="Jacobi iterations (v5 default 20)")
    parser.add_argument("--level", type=str, default="", help="Start level by id")
    parser.add_argument("--preset", choices=("low", "med", "high"), help="Graphics/physics preset")
    parser.add_argument("--paused", action="store_true", help="Start paused")
    # New physics flags
    parser.add_argument("--heat-diffusion-iterations", type=int, default=2, help="Heat diffusion iterations")
    parser.add_argument("--use-maccormack", action="store_true", default=True, help="Use MacCormack advection for liquids")
    parser.add_argument("--no-maccormack", action="store_true", help="Disable MacCormack advection")
    parser.add_argument("--powder-friction", type=float, default=0.35, help="Powder friction coefficient")
    parser.add_argument("--angle-of-repose-deg", type=float, default=32.0, help="Powder angle of repose in degrees")
    parser.add_argument("--capillary-strength", type=float, default=0.4, help="Capillary action strength")
    parser.add_argument("--wind-field", choices=("none", "perlin", "constant"), default="none", help="Wind field type")
    # Acoustic simulation flags
    parser.add_argument("--no-acoustics", action="store_true", help="Disable acoustic solver for gas")
    parser.add_argument("--sound-speed", type=float, default=4.0, help="Wave speed in gas (cells/frame)")
    parser.add_argument("--acoustic-substeps", type=int, default=6, help="Acoustic substeps per frame")
    parser.add_argument("--atm-pressure", type=float, default=1.0, help="Normalised ambient pressure")
    parser.add_argument("--perf", action="store_true", help="Print periodic performance timings")
    # Bloom post-FX flags
    parser.add_argument("--no-bloom", action="store_true", help="Disable bloom post-processing")
    parser.add_argument("--bloom-threshold", type=float, default=0.6, help="Bloom luminance threshold (0.0-1.0)")
    # Save format
    parser.add_argument("--save-format", choices=("v7", "v8"), default="v7", help="Save file format (v7 or v8)")
    # New system flags
    parser.add_argument("--enable-electricity", action="store_true", default=False, help="Enable electricity system")
    parser.add_argument("--enable-biology", action="store_true", default=False, help="Enable biology/ecology system")
    parser.add_argument("--enable-weather", action="store_true", default=False, help="Enable weather/atmospheric system")
    
    # Electricity parameters
    parser.add_argument("--charge-decay", type=float, default=0.0, help="Electricity charge decay rate")
    parser.add_argument("--max-charge", type=float, default=1000.0, help="Maximum charge capacity")
    parser.add_argument("--breakdown-threshold", type=float, default=500.0, help="Arc breakdown threshold")
    parser.add_argument("--arc-temp-delta", type=float, default=200.0, help="Temperature increase from arcs")
    parser.add_argument("--arc-pressure-pulse", type=float, default=5.0, help="Pressure pulse from arcs")
    
    # Biology parameters
    parser.add_argument("--nutrient-diffuse-rate", type=float, default=0.5, help="Nutrient diffusion rate")
    parser.add_argument("--moisture-diffuse-rate", type=float, default=0.3, help="Moisture diffusion rate")
    parser.add_argument("--growth-rate", type=float, default=0.1, help="Bio material growth rate")
    parser.add_argument("--decay-rate", type=float, default=0.05, help="Bio material decay rate")
    
    # Weather parameters
    parser.add_argument("--humidity-diffuse-rate", type=float, default=0.4, help="Humidity diffusion rate")
    parser.add_argument("--evaporation-rate", type=float, default=0.1, help="Water evaporation rate")
    parser.add_argument("--condensation-rate", type=float, default=0.3, help="Humidity condensation rate")
    parser.add_argument("--saturation-threshold", type=float, default=100.0, help="Humidity saturation threshold")
    parser.add_argument("--rain-speed", type=float, default=2.0, help="Rain falling speed")
    
    # Bloom parameters
    parser.add_argument("--bloom-intensity", type=float, default=0.6, help="Bloom intensity multiplier")
    parser.add_argument("--bloom-radius", type=float, default=1.0, help="Bloom blur radius multiplier")
    parser.add_argument("--bloom-quality", choices=("low", "medium", "high"), default="medium", help="Bloom quality setting")
    
    # Adaptive performance
    parser.add_argument("--adaptive-quality", action="store_true", default=False, help="Enable adaptive quality scaling")
    parser.add_argument("--min-fps-target", type=float, default=30.0, help="Minimum FPS target for adaptive quality")
    parser.add_argument("--transpiration-rate", type=float, default=0.05, help="Bio material transpiration rate")
    return parser.parse_args()


def apply_preset(args: argparse.Namespace) -> None:
    if not args.preset:
        return
    if args.preset == "low":
        args.width = min(args.width, 768)
        args.height = min(args.height, 768)
        args.sim_substeps = 1
        args.pressure_iterations = 10
    elif args.preset == "med":
        args.width = min(args.width, 1024)
        args.height = min(args.height, 1024)
        args.sim_substeps = max(args.sim_substeps, 1)
        args.pressure_iterations = 16
    elif args.preset == "high":
        args.width = max(args.width, 1024)
        args.height = max(args.height, 1024)
        args.sim_substeps = max(args.sim_substeps, 2)
        args.pressure_iterations = max(args.pressure_iterations, 24)


def main() -> None:
    """Main entry point."""
    args = parse_arguments()
    apply_preset(args)

    # Handle --no-maccormack flag
    if args.no_maccormack:
        args.use_maccormack = False

    # Create and validate config
    config = SimulationConfig.from_args(args)
    errors = config.validate()
    if errors:
        for error in errors:
            print(f"Error: {error}")
        sys.exit(1)

    # Phase 4: Additional VRAM warning for large grids
    from gpu.buffers import BufferManager
    vram = BufferManager.estimate_vram_usage(config.width, config.height)
    if vram['total_mb'] > 1000:
        print(f"WARNING: Large grid size {config.width}×{config.height}")
        print(f"Estimated VRAM usage: {vram['total_mb']:.1f} MB")
        print("Consider using --preset low or reducing grid size if performance is poor")

    # Initialize GPU context
    ctx_manager = ContextManager((config.window_width, config.window_height))

    # Initialize simulation engine
    engine = SimulationEngine(config, ctx_manager)

    # Set save format from CLI argument
    save_format = 8 if args.save_format == "v8" else 7
    engine.persistence.set_save_format(save_format)

    # Initialize HUD
    hud = None
    num_materials = 0
    if not config.no_hud:
        from simulation.materials import get_all_materials
        materials = get_all_materials()
        num_materials = len(materials)
        hud = HUD(ctx_manager.get_context(), (config.window_width, config.window_height), materials)
        hud.update(1, 12, 0)

    # Overlays and QoL
    pause_menu = PauseMenu(ctx_manager.get_context(), (config.window_width, config.window_height))
    keybind_overlay = KeybindOverlay(ctx_manager.get_context(), (config.window_width, config.window_height))
    sfx = SfxManager()
    inspector = InspectorPanel(ctx_manager.get_context(), (config.window_width, config.window_height))
    intro_overlay = OverlayRenderer(ctx_manager.get_context(), (config.window_width, config.window_height))
    system_controls = SystemControls(ctx_manager.get_context(), (config.window_width, config.window_height))
    performance_overlay = PerformanceOverlay(ctx_manager.get_context(), (config.window_width, config.window_height))
    performance_overlay.set_profiler(engine.pipeline.profiler)
    performance_overlay.set_pipeline(engine.pipeline)

    # Game state
    running = True
    paused = args.paused
    current_brush = 1
    brush_size = 12
    brush_mode = 0
    HEAT_DELTA = 10
    painting_active = False

    # Inspector throttling state
    last_probe_time = 0
    probe_interval = 1.0 / 15.0  # 15 Hz
    intro_visible = True
    intro_hide_at = pygame.time.get_ticks() + 9000

    if args.level:
        selected = get_level_by_id(args.level)
        if selected is None:
            print(f"Unknown level '{args.level}'.")
        else:
            engine.load_level(selected)

    def _take_screenshot() -> None:
        folder = Path(os.path.expanduser("~/Pictures/fallingsand"))
        folder.mkdir(parents=True, exist_ok=True)
        stamp = pygame.time.get_ticks()
        out = folder / f"sand_{stamp}.png"
        pygame.image.save(pygame.display.get_surface(), str(out))
        print(f"Screenshot saved: {out}")

    def _prompt_level_name() -> tuple[str, str]:
        try:
            import tkinter as tk
            from tkinter import simpledialog

            root = tk.Tk()
            root.withdraw()
            name = simpledialog.askstring("Save Level", "Level name:", parent=root) or "Custom Level"
            desc = simpledialog.askstring("Save Level", "Description:", parent=root) or "Saved in-game"
            root.destroy()
            return name, desc
        except Exception:
            return f"Custom {pygame.time.get_ticks()}", "Saved in-game"

    def _render_intro_banner() -> None:
        if not intro_visible or paused or pause_menu.visible or pygame.time.get_ticks() > intro_hide_at:
            return

        surf = pygame.Surface((config.window_width, config.window_height), pygame.SRCALPHA)
        rect = pygame.Rect(20, 20, min(560, config.window_width - 40), 132)
        theme.rounded_panel(surf, rect, fill=(18, 20, 28, 230), radius=12, shadow=True)
        theme.accent_strip(surf, rect, theme.ACCENT_AMBER, height=4)

        title = theme.font(18, bold=True).render("WELCOME TO FALLING SAND", True, theme.TEXT_PRIMARY)
        surf.blit(title, (rect.x + 16, rect.y + 14))
        subtitle = theme.font(11).render("Paint materials, pause for scenarios, and press H for the full control overlay.", True, theme.TEXT_BODY)
        surf.blit(subtitle, (rect.x + 16, rect.y + 42))

        chips = [
            ("Scroll", "Change material"),
            ("1-4", "Brush modes"),
            ("ESC", "Pause menu"),
            ("Ctrl+Z", "Undo"),
        ]
        x = rect.x + 16
        y = rect.y + 74
        for key, label in chips:
            x = theme.kbd_chip(surf, x, y, key) + 6
            txt = theme.font(10).render(label, True, theme.TEXT_DIM)
            surf.blit(txt, (x, y + 2))
            x += txt.get_width() + 16

        tip = theme.font(10, bold=True).render("Tip: use Sandbox or Pressure Lab from the pause menu.", True, theme.ACCENT_AMBER)
        surf.blit(tip, (rect.x + 16, rect.bottom - 22))

        intro_overlay.render_fullscreen(surf)

    def _run_pause_action(action: str, payload: str | None) -> None:
        nonlocal paused, running
        if action == "resume":
            paused = pause_menu.toggle()
        elif action == "select_level":
            return
        elif action == "load_level" and payload:
            level = get_level_by_id(payload)
            if level:
                engine.push_undo_snapshot()
                engine.load_level(level)
                sfx.play_event("load_level")
        elif action == "save_level":
            name, desc = _prompt_level_name()
            store = get_custom_store()
            store.save_level(
                name=name,
                description=desc,
                state=engine.get_state(),
                width=config.width,
                height=config.height,
            )
            pause_menu.refresh_levels()
        elif action == "toggle_turbulence":
            config.no_turbulence = not config.no_turbulence
        elif action == "toggle_wet_dry":
            config.no_wet_dry = not config.no_wet_dry
        elif action == "toggle_thermal":
            config.no_thermal = not config.no_thermal
        elif action == "toggle_sfx":
            sfx.toggle()
        elif action == "screenshot":
            _take_screenshot()
        elif action == "quit":
            running = False

    # Main loop
    clock = pygame.time.Clock()

    while running:
        frame_start = pygame.time.get_ticks()
        dt = clock.tick(60) / 1000.0  # Target 60 FPS

        # Event handling
        for ev in pygame.event.get():
            if ev.type in (KEYDOWN, MOUSEBUTTONDOWN, MOUSEWHEEL):
                intro_visible = False
            if ev.type == QUIT:
                running = False
            elif ev.type == VIDEORESIZE:
                # Phase 4: Handle window resize
                new_width, new_height = ev.w, ev.h
                print(f"Window resized to {new_width}x{new_height}")
                config.window_width = new_width
                config.window_height = new_height
                ctx_manager.resize_window((new_width, new_height))
                # Update UI overlays
                pause_menu.resize((new_width, new_height))
                keybind_overlay.resize((new_width, new_height))
                inspector.resize((new_width, new_height))
                intro_overlay.resize((new_width, new_height))
                system_controls.resize((new_width, new_height))
                performance_overlay.resize((new_width, new_height))
                if hud:
                    hud.resize((new_width, new_height))
            elif ev.type == MOUSEBUTTONDOWN and paused and ev.button == 1:
                action_payload = pause_menu.handle_click(*ev.pos)
                if action_payload is not None:
                    action, payload = action_payload
                    _run_pause_action(action, payload)
            elif ev.type == MOUSEBUTTONUP:
                system_controls.handle_mouse_up()
            elif ev.type == MOUSEWHEEL:
                if paused:
                    continue
                current_brush = (current_brush + ev.y) % num_materials if num_materials > 0 else 0
                if hud:
                    hud.update(current_brush, brush_size, brush_mode)
            elif ev.type == KEYDOWN:
                if ev.key in (K_ESCAPE, K_p):
                    paused = pause_menu.toggle()
                    continue
                if ev.key == K_h:
                    keybind_overlay.toggle()
                    continue
                if ev.key == K_F12:
                    _take_screenshot()
                    continue
                if ev.key == K_z and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    if engine.undo():
                        print("Undo")
                    continue

                if paused:
                    if ev.key == K_TAB:
                        delta = -1 if (pygame.key.get_mods() & pygame.KMOD_SHIFT) else 1
                        pause_menu.cycle_level(delta)
                    elif ev.key == K_RETURN:
                        _run_pause_action("load_level", pause_menu.get_selected_level_id())
                    elif ev.key == K_r:
                        _run_pause_action("resume", None)
                    elif ev.key == K_q:
                        _run_pause_action("quit", None)
                    continue

                if ev.key == K_s:
                    engine.save_state(Path("save_grid.npy"))
                    print("Saved!")
                elif ev.key == K_l:
                    try:
                        engine.push_undo_snapshot()
                        engine.load_state(Path("save_grid.npy"))
                        print("Loaded!")
                    except FileNotFoundError:
                        print("No save file found")
                elif ev.key == K_1:
                    brush_mode = 0
                elif ev.key == K_2:
                    brush_mode = 1
                elif ev.key == K_3:
                    brush_mode = 2
                elif ev.key == K_4:
                    brush_mode = 3
                elif ev.key == K_LEFTBRACKET:
                    brush_size = max(1, brush_size - 2)
                elif ev.key == K_RIGHTBRACKET:
                    brush_size = min(64, brush_size + 2)

                # Update HUD after brush changes
                if hud and ev.key in (K_1, K_2, K_3, K_4, K_LEFTBRACKET, K_RIGHTBRACKET):
                    hud.update(current_brush, brush_size, brush_mode)
                elif ev.key == K_c:
                    # Clear grid
                    engine.push_undo_snapshot()
                    engine.clear_grid()
                elif ev.key == K_x:
                    # Trigger explosion at mouse position with type based on modifiers
                    mx, my = pygame.mouse.get_pos()
                    sx, sy = config.width / config.window_width, config.height / config.window_height
                    gx, gy = int(mx * sx), config.height - int(my * sy) - 1
                    if 0 <= gx < config.width and 0 <= gy < config.height:
                        engine.push_undo_snapshot()
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            engine.trigger_big_explosion(gx, gy)
                        elif mods & pygame.KMOD_CTRL:
                            engine.trigger_thermobaric(gx, gy)
                        elif mods & pygame.KMOD_ALT:
                            engine.trigger_deflagration(gx, gy)
                        else:
                            engine.trigger_explosion(gx, gy)
                        sfx.play_event("explosion")
                elif ev.key == K_LEFT:
                    engine.adjust_wind(-0.1, 0.0)
                elif ev.key == K_RIGHT:
                    engine.adjust_wind(0.1, 0.0)
                elif ev.key == K_UP:
                    engine.adjust_wind(0.0, -0.1)
                elif ev.key == K_DOWN:
                    engine.adjust_wind(0.0, 0.1)
                elif ev.key == K_w:
                    engine.toggle_wind()
                elif ev.key == K_v:
                    show = engine.toggle_pressure_overlay()
                    print(f"Pressure overlay: {'ON' if show else 'OFF'}")
                elif ev.key == K_i:
                    inspector.toggle()
                elif ev.key == K_TAB:
                    view = engine.cycle_debug_view()
                    names = ["off", "pressure", "charge", "nutrient", "moisture", "humidity"]
                    print(f"Debug view: {names[view]}")
                elif ev.key == K_e and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    system_controls.toggle()
                elif ev.key == K_p and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                    performance_overlay.toggle()
                else:
                    # Pass other keys to system controls if visible
                    if system_controls.visible:
                        system_controls.handle_key(ev.key, pygame.key.get_mods())

        # Mouse handling
        mx, my = pygame.mouse.get_pos()
        
        if system_controls.visible:
            # Handle system controls panel interactions
            action = system_controls.handle_click(mx, my)
            if action and action[0] == "update_config":
                system_controls.get_config_updates(config)
                if action[1] and "sparse_enabled" in action[1]:
                    engine.pipeline.enable_sparse_mode(action[1]["sparse_enabled"])
            system_controls.handle_mouse_move(mx, my)
        elif paused:
            # Do not paint while paused
            left, _, right = (False, False, False)
            painting_active = False
        else:
            left, _, right = pygame.mouse.get_pressed()

        if left or right:
            mx, my = pygame.mouse.get_pos()

            # Handle HUD palette clicks
            if hud and left:
                new_brush = hud.handle_click(mx, my)
                if new_brush is not None:
                    current_brush = new_brush

            # Apply brush to simulation
            sx, sy = config.width / config.window_width, config.height / config.window_height
            gx, gy = int(mx * sx), config.height - int(my * sy) - 1
            if 0 <= gx < config.width and 0 <= gy < config.height:
                if not painting_active:
                    engine.push_undo_snapshot()
                    painting_active = True
                if right and brush_mode == 0:
                    engine.apply_brush(gx, gy, brush_size, 0, brush_mode)
                elif brush_mode == 0:
                    engine.apply_brush(gx, gy, brush_size, current_brush, brush_mode)
                elif brush_mode == 1:
                    engine.apply_brush(gx, gy, brush_size, current_brush, brush_mode, HEAT_DELTA)
                elif brush_mode == 2:
                    engine.apply_brush(gx, gy, brush_size, current_brush, brush_mode, -HEAT_DELTA)
                elif brush_mode == 3 and left:
                    engine.apply_brush(gx, gy, brush_size, 24, brush_mode)  # Spark
        else:
            painting_active = False

        # Inspector update (throttled to ~15 Hz)
        if inspector.visible and not paused:
            mx, my = pygame.mouse.get_pos()
            sx, sy = config.width / config.window_width, config.height / config.window_height
            gx, gy = int(mx * sx), config.height - int(my * sy) - 1

            current_time = pygame.time.get_ticks() / 1000.0
            if (current_time - last_probe_time >= probe_interval or 
                (gx, gy) != inspector.last_grid_xy):
                probe = engine.probe_cell(gx, gy)
                # Inspector now ignores mouse_xy for layout, but we pass it for consistency
                inspector.update((mx, my), (gx, gy), probe)
                last_probe_time = current_time
        else:
            inspector.update((0, 0), (0, 0), None)

        # Step simulation
        if not paused:
            try:
                engine.step(dt)
                performance_overlay.update_fps(dt)
                engine.pipeline.update_quality_tier(performance_overlay.current_fps)
            except Exception as e:
                # Phase 4: Handle context errors during simulation step
                if "context" in str(e).lower() or "opengl" in str(e).lower():
                    print(f"OpenGL context error during simulation: {e}")
                    try:
                        # Attempt context recovery
                        ctx_manager.recreate_context()
                        shaders = load_all_shaders(ctx_manager.get_context())
                        engine.pipeline.set_shaders(shaders)
                        print("Context recovery successful")
                    except Exception as recovery_error:
                        print(f"Context recovery failed: {recovery_error}")
                        running = False
                else:
                    raise

        # Render
        try:
            engine.render()
        except Exception as e:
            # Phase 4: Handle context errors during render
            if "context" in str(e).lower() or "opengl" in str(e).lower():
                print(f"OpenGL context error during render: {e}")
                try:
                    # Attempt context recovery
                    ctx_manager.recreate_context()
                    shaders = load_all_shaders(ctx_manager.get_context())
                    engine.pipeline.set_shaders(shaders)
                    print("Context recovery successful")
                except Exception as recovery_error:
                    print(f"Context recovery failed: {recovery_error}")
                    running = False
            else:
                raise

        # Render HUD
        if hud:
            hud.render()

        # Render inspector
        inspector.render()

        # Render system controls
        system_controls.render()

        # Render performance overlay
        performance_overlay.render()

        keybind_overlay.render()
        pause_menu.render(
            status={
                "turbulence": "ON" if not config.no_turbulence else "OFF",
                "wet_dry": "ON" if not config.no_wet_dry else "OFF",
                "thermal": "ON" if not config.no_thermal else "OFF",
                "sfx": "ON" if sfx.enabled else "OFF",
            }
        )
        _render_intro_banner()

        # Present
        ctx_manager.swap_buffers()
        if config.perf_overlay and engine.frame % 60 == 0:
            frame_ms = pygame.time.get_ticks() - frame_start
            print(f"frame={frame_ms:.1f}ms sim={engine.pipeline.last_step_ms:.2f}ms render={engine.pipeline.last_render_ms:.2f}ms")

    # Cleanup
    ctx_manager.quit()
    pygame.quit()


if __name__ == "__main__":
    main()
