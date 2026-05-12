# Release Checklist for Falling Sand v7.0 Evolution

This checklist ensures all release preparation tasks are completed before publishing v7.0.

## Pre-Release

- [ ] All Phase 4 critical bug fixes implemented and tested
  - [ ] Pressure solver stabilization (enhanced clamping, emergency reset, monitoring)
  - [ ] Hydrostatic pressure initialization refinement (grid-size-aware gradient)
  - [ ] OpenGL context loss handling (detection, recovery, window resize)
  - [ ] Memory management for large grids (VRAM estimation, warnings)
  - [ ] Material property validation (GPU-safe ranges, NaN/inf detection)

- [ ] All Phase 4 comprehensive tests passing
  - [ ] Cross-system interaction tests (test_cross_system_interactions.py)
  - [ ] Edge-case tests (test_edge_cases.py)
  - [ ] Save/load migration tests (test_save_load_migration.py)
  - [ ] Manual checklist automation (test_manual_checklist_automation.py)
  - [ ] Pressure stability tests (test_pressure_stability.py)
  - [ ] Material validation tests (test_material_validation.py)

- [ ] Documentation updated
  - [ ] CHANGELOG.md updated with v7.0 release notes
  - [ ] README.md polished with v7.0 features
  - [ ] Architecture docs updated if needed
  - [ ] Performance docs updated if needed

## Build & Package

- [ ] Standalone executable built
  - [ ] Run `python tools/build_exe.py` to build default executable
  - [ ] Run `python tools/build_exe.py --debug` to build debug version
  - [ ] Test executable launches successfully
  - [ ] Test executable runs without errors on clean Windows machine

- [ ] Build artifacts verified
  - [ ] README.md copied to dist/
  - [ ] VERSION.txt created in dist/
  - [ ] All required data files included (shaders, materials.yaml, etc.)

## Testing

- [ ] Manual testing checklist completed
  - [ ] CLI flags tested
  - [ ] System controls tested
  - [ ] Performance overlay tested
  - [ ] Cross-system coupling tested
  - [ ] Save/load preservation tested
  - [ ] All systems enabled tested
  - [ ] Large grid performance tested (1024×1024)

- [ ] Automated test suite passing
  - [ ] Run `pytest tests/` - all tests pass
  - [ ] Run `pytest tests/test_pressure_stability.py` - passes
  - [ ] Run `pytest tests/test_cross_system_interactions.py` - passes
  - [ ] Run `pytest tests/test_edge_cases.py` - passes
  - [ ] Run `pytest tests/test_save_load_migration.py` - passes
  - [ ] Run `pytest tests/test_manual_checklist_automation.py` - passes
  - [ ] Run `pytest tests/test_material_validation.py` - passes

## Release Assets

- [ ] Demo video created
  - [ ] Scripted demo capture using tools/capture_demo.py (when available)
  - [ ] Video shows key features (electricity, biology, weather, explosions)
  - [ ] Video is high quality (1080p or higher)
  - [ ] Video is under 2 minutes

- [ ] Screenshots created
  - [ ] Screenshot showing electricity system
  - [ ] Screenshot showing biology system
  - [ ] Screenshot showing weather system
  - [ ] Screenshot showing explosions
  - [ ] Screenshot showing performance overlay
  - [ ] All screenshots are high resolution

- [ ] GIFs created (optional)
  - [ ] GIF showing material interactions
  - [ ] GIF showing explosion chain reaction
  - [ ] GIFs are optimized for web

## GitHub Release

- [ ] Git tag created
  - [ ] Version: `v7.0`
  - [ ] Tag message: "Falling Sand v7.0 Evolution - Final Polish & Release"

- [ ] GitHub release created
  - [ ] Title: "Falling Sand v7.0 Evolution"
  - [ ] Release notes copied from CHANGELOG.md v7.0 section
  - [ ] Attachments:
    - [ ] FallingSand.exe (standalone executable)
    - [ ] Demo video (or link to YouTube)
    - [ ] Screenshots
    - [ ] GIFs (if created)

- [ ] Release published
  - [ ] Marked as latest release
  - [ ] Release notes visible on GitHub

## itch.io Page

- [ ] itch.io page prepared
  - [ ] Title: "Falling Sand v7.0 Evolution"
  - [ ] Description copied from README.md
  - [ ] Screenshots uploaded
  - [ ] Demo video embedded
  - [ ] Executable uploaded
  - [ ] Pricing set (free or paid)
  - [ ] Tags added (simulation, physics, gpu, etc.)

- [ ] itch.io page published
  - [ ] Page is public
  - [ ] Download works
  - [ ] Preview images load

## Post-Release

- [ ] Monitor issues
  - [ ] Watch GitHub issues for bug reports
  - [ ] Watch itch.io comments for feedback
  - [ ] Respond to user questions

- [ ] Plan bugfix releases
  - [ ] If critical bugs found, plan v7.0.1
  - [ ] Document known issues in README or issues

## Final Verification

- [ ] All checklist items completed
- [ ] Release is stable and polished
- [ ] Documentation is comprehensive
- [ ] User experience is professional

---

**Notes:**
- This checklist should be completed in order
- Each item should be checked off only when fully completed
- If any item fails, resolve the issue before proceeding
- Keep this checklist in version control for future releases
