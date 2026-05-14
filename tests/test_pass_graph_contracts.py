from gpu.pass_graph import STEP_PASS_ORDER, RENDER_PASS_ORDER, default_render_passes, default_step_passes
from gpu.resources import (
    ALL_BINDINGS,
    IMAGE_BINDINGS,
    IMAGE_DISPLAY,
    IMAGE_DIVERGENCE,
    IMAGE_PRESSURE_IN,
    IMAGE_PRESSURE_OUT,
    IMAGE_TEMPERATURE_IN,
    IMAGE_TEMPERATURE_OUT,
    IMAGE_VELOCITY_IN,
    IMAGE_VELOCITY_OUT,
    IMAGE_VORTICITY,
    SSBO_BINDINGS,
    SSBO_CELLS_READ,
    SSBO_CELLS_WRITE,
    SSBO_COUNTERS,
    SSBO_RESERVATIONS,
    SSBO_RULES,
    UBO_BINDINGS,
    UBO_EXPLOSION,
    UBO_EXPLOSION_VFX,
    UBO_SIM_CONFIG,
    UBO_WIND,
    ResourceKind,
    bindings_by_kind,
    find_binding,
)


class TestResourceBindingRegistry:
    def test_expected_ssbo_bindings(self):
        bindings = {(item.name, item.binding) for item in SSBO_BINDINGS}
        assert ("cells_read", 0) in bindings
        assert ("cells_write", 1) in bindings
        assert ("rules", 2) in bindings
        assert ("reservations", 8) in bindings
        assert ("counters", 9) in bindings

    def test_expected_image_bindings(self):
        bindings = {(item.name, item.binding, item.glsl_type) for item in IMAGE_BINDINGS}
        assert ("velocity_in", 3, "rg32f") in bindings
        assert ("velocity_out", 4, "rg32f") in bindings
        assert ("divergence", 4, "r32f") in bindings
        assert ("pressure_in", 5, "r32f") in bindings
        assert ("pressure_out", 6, "r32f") in bindings
        assert ("display", 7, "rgba8") in bindings
        assert ("vorticity", 8, "r32f") in bindings
        assert ("temperature_in", 11, "r32f") in bindings
        assert ("temperature_out", 12, "r32f") in bindings

    def test_expected_ubo_bindings(self):
        bindings = {(item.name, item.binding) for item in UBO_BINDINGS}
        assert ("SimConfig", 3) in bindings
        assert ("ExplosionConfig", 4) in bindings
        assert ("ExplosionVfxConfig", 5) in bindings
        assert ("WindConfig", 6) in bindings

    def test_lookup_helpers(self):
        assert bindings_by_kind(ResourceKind.IMAGE) == IMAGE_BINDINGS
        assert find_binding(ResourceKind.SSBO, "rules").binding == 2

    def test_exported_constants_match_registry(self):
        expected = {
            "cells_read": SSBO_CELLS_READ,
            "cells_write": SSBO_CELLS_WRITE,
            "rules": SSBO_RULES,
            "reservations": SSBO_RESERVATIONS,
            "counters": SSBO_COUNTERS,
            "velocity_in": IMAGE_VELOCITY_IN,
            "velocity_out": IMAGE_VELOCITY_OUT,
            "divergence": IMAGE_DIVERGENCE,
            "pressure_in": IMAGE_PRESSURE_IN,
            "pressure_out": IMAGE_PRESSURE_OUT,
            "display": IMAGE_DISPLAY,
            "vorticity": IMAGE_VORTICITY,
            "temperature_in": IMAGE_TEMPERATURE_IN,
            "temperature_out": IMAGE_TEMPERATURE_OUT,
            "SimConfig": UBO_SIM_CONFIG,
            "ExplosionConfig": UBO_EXPLOSION,
            "ExplosionVfxConfig": UBO_EXPLOSION_VFX,
            "WindConfig": UBO_WIND,
        }
        actual = {binding.name: binding.binding for binding in ALL_BINDINGS}
        for name, binding in expected.items():
            assert actual[name] == binding


class TestPassGraphContract:
    def test_step_pass_order_matches_current_pipeline(self):
        assert tuple(pass_.name for pass_ in default_step_passes()) == STEP_PASS_ORDER
        assert STEP_PASS_ORDER == (
            "state",
            "liquid_step",
            "heat",
            "vorticity",
            "velocity_advect",
            "force",
            "divergence",
            "pressure",
            "project",
            "electricity",
            "electricity_arc",
            "biology",
            "weather",
            "acoustic_pressure",
            "acoustic_velocity",
            "advect",
        )

    def test_render_pass_order_matches_current_pipeline(self):
        assert tuple(pass_.name for pass_ in default_render_passes()) == RENDER_PASS_ORDER
        assert RENDER_PASS_ORDER == ("render",)

    def test_all_pass_resources_are_registered(self):
        registered = {binding.name for binding in ALL_BINDINGS}
        for pass_ in default_step_passes() + default_render_passes():
            for resource_name in pass_.reads + pass_.writes:
                assert resource_name in registered, f"{pass_.name} references unknown resource {resource_name}"

    def test_iterative_and_optional_flags_match_current_runtime(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        assert passes["heat"].optional and passes["heat"].iterative
        assert passes["vorticity"].optional
        assert passes["pressure"].iterative
        assert passes["acoustic_pressure"].optional and passes["acoustic_pressure"].iterative
        assert passes["acoustic_velocity"].optional and passes["acoustic_velocity"].iterative
        assert passes["electricity"].optional

    def test_electricity_bindings_registered(self):
        registered = {binding.name for binding in ALL_BINDINGS}
        assert "charge_in" in registered
        assert "charge_out" in registered

    def test_electricity_pass_resources(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        elec = passes["electricity"]
        assert "charge_in" in elec.reads
        assert "charge_out" in elec.writes
        assert "charge" in elec.swaps

    def test_electricity_arc_pass_resources(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        arc = passes["electricity_arc"]
        assert "charge_in" in arc.reads
        assert "temperature_in" in arc.reads
        assert "charge_out" in arc.writes
        assert "temperature_out" in arc.writes
        assert "divergence" in arc.writes
        assert "charge" in arc.swaps
        assert "temperature" in arc.swaps
        assert arc.optional

    def test_biology_bindings_registered(self):
        registered = {binding.name for binding in ALL_BINDINGS}
        assert "nutrient_in" in registered
        assert "nutrient_out" in registered
        assert "moisture_in" in registered
        assert "moisture_out" in registered

    def test_biology_pass_resources(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        bio = passes["biology"]
        assert "nutrient_in" in bio.reads
        assert "moisture_in" in bio.reads
        assert "temperature_in" in bio.reads
        assert "nutrient_out" in bio.writes
        assert "moisture_out" in bio.writes
        assert "nutrient" in bio.swaps
        assert "moisture" in bio.swaps
        assert bio.optional

    def test_weather_bindings_registered(self):
        registered = {binding.name for binding in ALL_BINDINGS}
        assert "humidity_in" in registered
        assert "humidity_out" in registered

    def test_weather_pass_resources(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        w = passes["weather"]
        assert "humidity_in" in w.reads
        assert "temperature_in" in w.reads
        assert "humidity_out" in w.writes
        assert "humidity" in w.swaps
        assert w.optional

    def test_state_pass_reads_fire_suppression_fields(self):
        passes = {pass_.name: pass_ for pass_ in default_step_passes()}
        state = passes["state"]
        assert "moisture_in" in state.reads
        assert "humidity_in" in state.reads
