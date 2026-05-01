# Architecture

Falling Sand is organized around a Python runtime shell and a GPU-resident simulation core.

## Runtime Layers

1. **Application shell**
   - `main.py` parses CLI flags, creates the window/context, manages UI state, handles input, steps the simulation, renders overlays, and presents frames.
   - `launcher.py` provides a Tk-based launcher for play/settings/about workflows.

2. **Simulation API**
   - `simulation/engine.py` exposes actions such as `step`, `render`, `apply_brush`, `trigger_explosion`, `save_state`, `load_state`, `undo`, and `probe_cell`.
   - UI code should prefer this API instead of directly mutating GPU buffers.

3. **GPU infrastructure**
   - `gpu/context.py` creates the Pygame OpenGL context.
   - `gpu/buffers.py` owns SSBOs and textures.
   - `gpu/uniforms.py` packs UBO data.
   - `gpu/shader_registry.py` loads every compute shader with `shaders/common.glsl` prepended.
   - `gpu/pipeline.py` binds resources and dispatches compute passes.

4. **Domain data**
   - `simulation/materials.yaml` is the material source of truth.
   - `simulation/materials.py` validates the registry and creates the GPU rule buffer.
   - `simulation/state.py` owns runtime explosion, VFX, and wind state.
   - `simulation/persistence.py` owns save/load/undo behavior.

5. **Presentation**
   - `hud.py` renders material/brush HUD.
   - `ui/` renders pause menu, inspector, overlays, theme helpers, and sound placeholders.
   - `levels/` provides built-in and persisted custom levels.

## Key Data Flow

1. `main.py` builds `SimulationConfig`.
2. `SimulationEngine` allocates buffers, UBOs, shaders, brush painter, and persistence manager.
3. User input calls engine methods.
4. `Pipeline.step()` updates UBOs and dispatches compute passes.
5. `Pipeline.render()` writes `display_texture` and blits it to the default framebuffer.
6. UI overlays render after the simulation frame.

## High-Risk Couplings

- Shader bindings must match `gpu/pipeline.py`, `gpu/buffers.py`, `gpu/uniforms.py`, and `shaders/BUFFER_BINDINGS.md`.
- Cell packing must match `core/types.py`, `simulation/materials.py`, `shaders/common.glsl`, and `simulation/persistence.py`.
- Material rule stride must match `core/constants.py`, `simulation/materials.py`, and `shaders/common.glsl`.
- Save format migration must remain compatible with older saves.
- Main-loop refactors require tests for input, pause, save/load, brush, and overlay behavior.
