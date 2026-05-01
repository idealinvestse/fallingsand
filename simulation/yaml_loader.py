"""YAML-based material definition loader."""

from __future__ import annotations

from pathlib import Path

import yaml

from core.constants import TEMP_AMBIENT

_YAML_PATH = Path(__file__).parent / "materials.yaml"

# Keys that reference the TEMP_AMBIENT constant — resolved at load time.
_CONSTANT_KEYS = {"dft"}


def load_material_definitions(path: Path | None = None) -> dict[int, dict]:
    """Load material definitions from YAML, returning {id: {key: value, ...}}.

    Values of ``dft`` equal to the string ``"TEMP_AMBIENT"`` are replaced
    with the numeric constant from ``core.constants``.
    """
    src = path or _YAML_PATH
    with open(src, encoding="utf-8") as f:
        raw: dict = yaml.safe_load(f)

    definitions: dict[int, dict] = {}
    for mat_id, props in raw.items():
        mat_id = int(mat_id)
        defs = dict(props)
        # Resolve constant references
        for key in _CONSTANT_KEYS:
            if defs.get(key) == "TEMP_AMBIENT":
                defs[key] = TEMP_AMBIENT
        # Ensure color is a tuple (YAML loads as list)
        if "color" in defs and isinstance(defs["color"], list):
            defs["color"] = tuple(defs["color"])
        definitions[mat_id] = defs
    return definitions
