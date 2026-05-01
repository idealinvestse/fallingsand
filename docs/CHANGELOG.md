# Changelog

This changelog consolidates the root implementation summaries into a single maintenance history.

## Current Development State

- Multi-pass GPU pipeline is the active architecture.
- Save format is `FSND` v7.
- Temperature is stored in `r32f` textures, not in packed cells.
- Materials are YAML-driven and packed into a `RULE_STRIDE = 49` GPU rule buffer.
- Levels, pause menu, inspector, pressure overlay, undo, screenshots, and launcher support are present.

## Physics and Stability Work

- Added dedicated heat diffusion and removed legacy packed-cell temperature storage.
- Added liquid step, velocity advection, pressure projection, vorticity, acoustic pressure/velocity passes.
- Added explosion variants, fragmentation/shrapnel behavior, crater/scatter concepts, and VFX state.
- Corrected gravity direction and improved substep behavior for frame-time stability.
- Added runtime material validation and material registry tests.

## Documentation Consolidation

- README now focuses on user setup, controls, CLI, and documentation index.
- Architecture, GPU pipeline, materials, save format, and testing docs are split into dedicated files.
- Shader binding documentation is expected to match current host/shader resource contracts.

## Known Maintenance Items

- Establish a clean Git baseline; the current working tree may not have historical commits.
- Keep app version labels, save format version, and shader comments distinct.
- Add more scenario-based tests before large solver or architecture refactors.
