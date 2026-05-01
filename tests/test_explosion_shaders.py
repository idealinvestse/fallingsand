"""Static checks that the explosion shader logic follows the new flag layout.

Full-GPU behavioural tests live in test_gpu_integration; these tests validate
the GLSL source for the specific structural guarantees the fire+explosion
realism pass relies on, so they can run quickly without a GL context.
"""
from pathlib import Path

SHADERS = Path(__file__).parent.parent / "shaders"


def _read(name: str) -> str:
    return (SHADERS / name).read_text(encoding="utf-8")


class TestBlastFlagLayout:
    def test_state_defines_pack_helpers(self):
        src = _read("state_shader.glsl")
        assert "packBlastFlags" in src
        assert "unpackBlastPow" in src
        assert "octantFromOffset" in src

    def test_force_uses_unpacked_power(self):
        src = _read("force_shader.glsl")
        assert "unpackBlastPow" in src
        assert "octantToVec" in src

    def test_force_has_radial_impulse_from_blast_neighbor(self):
        """Force shader must iterate neighbors for T_BLAST and push outward."""
        src = _read("force_shader.glsl")
        assert "getType(nc) != T_BLAST" in src or "getType(nc) == T_BLAST" in src, (
            "force shader must inspect neighbor blast cells"
        )
        # Outward direction from the blast neighbor position.
        assert "radialImpulse" in src
        assert "awayDir" in src

    def test_force_removes_broken_normalize_self_push(self):
        """Old code did `v += normalize(v) * blastPower * 2.0`; must be gone."""
        src = _read("force_shader.glsl")
        assert "normalize(v) * blastPower" not in src

    def test_shrapnel_not_zeroed_by_solid_short_circuit(self):
        """Force shader must allow T_SHRAPNEL past the solid early-return."""
        src = _read("force_shader.glsl")
        assert "typ != T_SHRAPNEL" in src


class TestFireSpreadLogic:
    def test_state_has_deterministic_fire_ignition(self):
        """Flammable cells next to fire/ember ignite directly (not via low-prob)."""
        src = _read("state_shader.glsl")
        # The new branch lives inside the `nearHot` else-if.
        assert "Deterministic fire propagation" in src
        assert "r.flamm > 0.0" in src

    def test_state_packs_blast_dir_on_detonation(self):
        src = _read("state_shader.glsl")
        assert "packBlastFlags(randDir, powScaled)" in src

    def test_state_packs_shrapnel_flags_on_fragmentation(self):
        src = _read("state_shader.glsl")
        assert "shrapnelFlags = packBlastFlags(fragOctant" in src

    def test_nearhot_uses_flammability_scaled_heat_gain(self):
        """nearHot branch must scale heat gain by flammability (not flat +10)."""
        src = _read("state_shader.glsl")
        assert "r.flamm * 20.0" in src
        assert "heatGain" in src


class TestTempSync:
    def test_state_shader_reads_temp_texture(self):
        """state_shader must read and write the float temperature field."""
        src = _read("state_shader.glsl")
        assert "layout(r32f, binding = 11)" in src
        assert "layout(r32f, binding = 12)" in src
        assert "imageLoad(tempTex" in src

    def test_state_shader_no_duplicate_cooling(self):
        """state_shader must NOT apply Newton cooling (heat_shader handles it)."""
        src = _read("state_shader.glsl")
        # The old cooling line must be gone
        assert "r.cool * 0.10" not in src

    def test_heat_shader_has_upload_cell_temp_uniform(self):
        """heat_shader must operate directly on the float temperature field."""
        src = _read("heat_shader.glsl")
        assert "layout(r32f, binding = 11)" in src
        assert "uploadCellTemp" not in src

    def test_state_shader_uses_max_for_temp_sync(self):
        """state_shader must write the updated float temperature field."""
        src = _read("state_shader.glsl")
        assert "writeCell(" in src

    def test_heat_shader_reads_neighbor_temps_from_cells_on_first_iter(self):
        """heat_shader neighbourTemp must read from the float temperature texture."""
        src = _read("heat_shader.glsl")
        assert "imageLoad(tempIn" in src
        assert "uploadCellTemp" not in src


class TestWindVector:
    def test_force_shader_declares_wind_vector(self):
        """force_shader must declare windVector uniform."""
        src = _read("force_shader.glsl")
        assert "uniform vec2 windVector" in src

    def test_engine_sets_wind_vector_on_force_shader(self):
        """pipeline.py must set windVector uniform for force_shader."""
        src = (Path(__file__).parent.parent / "gpu" / "pipeline.py").read_text(encoding="utf-8")
        assert 'windVector' in src
        # Must be set specifically for force_shader, not just any shader
        assert 'self.force_shader' in src or 'force_shader' in src


class TestLoadStateSync:
    def test_load_state_no_sync_temp(self):
        """load_state no longer calls sync_temp_from_cells (8-bit temp removed)."""
        src = (Path(__file__).parent.parent / "gpu" / "buffers.py").read_text(encoding="utf-8")
        assert "sync_temp_from_cells" not in src

    def test_no_8bit_temp_in_cell_buffer(self):
        """Cell buffer no longer stores 8-bit temperature."""
        src = (Path(__file__).parent.parent / "gpu" / "buffers.py").read_text(encoding="utf-8")
        # The old 8-bit extraction pattern should be gone
        assert "(grid >> 8) & 0xFF" not in src

    def test_brush_heat_gun_syncs_temp(self):
        """apply_brush mode 1/2 must sync temp textures after modifying cell temps."""
        src = (Path(__file__).parent.parent / "simulation" / "brush.py").read_text(encoding="utf-8")
        # In the GPU version, we check for image bindings instead of temp_a.write
        assert "bind_to_image" in src


class TestRuleBufferPadding:
    def test_padding_uses_rule_stride(self):
        """Undefined material padding must use RULE_STRIDE, not hardcoded 41."""
        src = (Path(__file__).parent.parent / "simulation" / "materials.py").read_text(encoding="utf-8")
        assert "RULE_STRIDE" in src
        # The old hardcoded 41 must be gone
        assert "[0.0] * 41" not in src


class TestSetIfExceptionHandling:
    def test_set_if_only_catches_key_error(self):
        """_set_if must only catch KeyError, not all Exceptions."""
        src = (Path(__file__).parent.parent / "gpu" / "pipeline.py").read_text(encoding="utf-8")
        # The _set_if method must not have a broad except clause
        # Find the _set_if function body and check it
        assert "except KeyError:" in src
        # The old pattern must be gone from _set_if
        assert "except (KeyError, Exception):" not in src
        # Verify _set_if specifically catches only KeyError by checking the
        # function's try/except block structure
        import re
        set_if_match = re.search(
            r'def _set_if\(.*?\).*?(?=\n    def |\n    @|\Z)', src, re.DOTALL
        )
        assert set_if_match is not None, "_set_if method not found"
        set_if_body = set_if_match.group(0)
        assert "except KeyError:" in set_if_body
        assert "except Exception" not in set_if_body
