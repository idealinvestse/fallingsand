from pathlib import Path

from core.constants import NUM_TYPES, RULE_STRIDE
from simulation.persistence import _SAVE_MAGIC, _SAVE_VERSION


ROOT = Path(__file__).parent.parent


def test_readme_documents_current_save_and_temperature_contracts():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"`FSND` v{_SAVE_VERSION}" in readme
    assert "`r32f` float textures" in readme
    assert f"`RULE_STRIDE = {RULE_STRIDE}`" in readme


def test_material_docs_match_constants():
    materials_doc = (ROOT / "docs" / "MATERIALS.md").read_text(encoding="utf-8")

    assert f"`0..{NUM_TYPES - 1}`" in materials_doc
    assert f"`{NUM_TYPES}`" in materials_doc
    assert f"`{RULE_STRIDE}`" in materials_doc


def test_save_format_docs_match_persistence_constants():
    save_doc = (ROOT / "docs" / "SAVE_FORMAT.md").read_text(encoding="utf-8")

    assert _SAVE_MAGIC.decode("ascii") in save_doc
    assert f"uint32   {_SAVE_VERSION}" in save_doc
    assert "temp bytes:   width * height * 4 bytes" in save_doc


def test_binding_docs_document_r32f_temperature():
    bindings_doc = (ROOT / "shaders" / "BUFFER_BINDINGS.md").read_text(encoding="utf-8")

    assert "| 11 | R32F | tempTex / tempIn / temp_a |" in bindings_doc
    assert "| 12 | R32F | tempOut / temp_b |" in bindings_doc
    assert "R16F | temp" not in bindings_doc
