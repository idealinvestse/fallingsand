# Testing

The test suite uses `pytest`.

## Headless Tests

Run tests that do not require a real GPU context:

```bash
python -m pytest tests/ -m "not gpu"
```

## GPU Tests

GPU/OpenGL tests require OpenGL 4.3+ support and a working ModernGL context:

```bash
python -m pytest tests/test_gpu_integration.py
```

## Focused Validation

Useful targeted commands:

```bash
python -m pytest tests/test_cli.py tests/test_shader_logic.py tests/test_materials.py
python -m pytest tests/test_physics_invariants.py tests/test_physics_gravity.py
python -m pytest tests/test_ubo_layouts.py
```

## Contracts to Protect

- CLI defaults and `SimulationConfig.from_args`.
- Material registry size and `RULE_STRIDE`.
- Shader bindings and image formats.
- Cell packing and save migrations.
- Gravity/buoyancy direction.
- Undo/load/clear resets of stale physics buffers.

## Performance Checks

Runtime timing output is available with:

```bash
python main.py --perf
```

Record grid size, preset, GPU, and enabled physics flags when comparing performance.
