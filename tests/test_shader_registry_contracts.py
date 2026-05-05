from pathlib import Path

import pytest

from gpu.pass_graph import default_render_passes, default_step_passes
from gpu.shader_registry import SHADER_MANIFEST, load_all_shaders, reload_shader, shader_manifest_by_key

SHADERS_DIR = Path(__file__).parent.parent / "shaders"


class FakeContext:
    def __init__(self):
        self.sources: list[str] = []

    def compute_shader(self, source: str):
        self.sources.append(source)
        return {"source": source, "index": len(self.sources)}


class TestShaderManifest:
    def test_manifest_keys_are_unique(self):
        keys = [entry.key for entry in SHADER_MANIFEST]
        assert len(keys) == len(set(keys))

    def test_manifest_files_exist(self):
        for entry in SHADER_MANIFEST:
            assert (SHADERS_DIR / entry.filename).is_file()

    def test_manifest_covers_pass_graph_shader_keys(self):
        manifest_keys = set(shader_manifest_by_key())
        pass_shader_keys = {pass_.shader_key for pass_ in default_step_passes() + default_render_passes()}
        assert pass_shader_keys <= manifest_keys

    def test_manifest_by_key_returns_entries(self):
        manifest = shader_manifest_by_key()
        assert manifest["state"].filename == "state_shader.glsl"
        assert manifest["render"].filename == "render_shader.glsl"


class TestShaderLoadingAPI:
    def test_load_all_shaders_uses_manifest_keys(self):
        ctx = FakeContext()
        shaders = load_all_shaders(ctx)
        assert tuple(shaders) == tuple(entry.key for entry in SHADER_MANIFEST)
        assert len(ctx.sources) == len(SHADER_MANIFEST)
        assert all(source.startswith("#version 430") for source in ctx.sources)

    def test_reload_shader_updates_mapping(self):
        ctx = FakeContext()
        shaders = {"state": object()}
        shader = reload_shader(ctx, shaders, "state")
        assert shaders["state"] is shader
        assert shader["source"].startswith("#version 430")

    def test_reload_shader_rejects_unknown_key(self):
        ctx = FakeContext()
        with pytest.raises(KeyError):
            reload_shader(ctx, {}, "missing")
