"""Shader loading utilities with preprocessing support for #include directives."""

from typing import Any

import re
from pathlib import Path


def load_shader(path: Path, common_path: Path | None = None) -> str:
    """
    Load a shader file with preprocessing support.

    Preprocessing steps:
    1. Replace #include "common.glsl" with the actual content
    2. Handle #include directives recursively

    Args:
        path: Path to the shader file to load
        common_path: Path to the common.glsl file (defaults to same directory)

    Returns:
        The preprocessed shader source code
    """
    if common_path is None:
        common_path = path.parent / "common.glsl"

    # Read the shader source
    source = path.read_text(encoding='utf-8')

    # Process includes
    source = _process_includes(source, path.parent, set[str]())

    return source


def _process_includes(source: str, base_dir: Path, included: set[str]) -> str:
    """
    Recursively process #include directives.

    Args:
        source: Shader source code
        base_dir: Base directory for relative include paths
        included: Set of already-included files (prevents cycles)

    Returns:
        Source with includes expanded
    """
    # Pattern to match #include "filename"
    include_pattern = r'#include\s+"([^"]+)"'

    def replace_include(match: re.Match[str]) -> str:
        filename = match.group(1)
        include_path = base_dir / filename

        # Prevent duplicate includes and cycles
        resolved = str(include_path.resolve())
        if resolved in included:
            return f"// Already included: {filename}\n"
        included.add(resolved)

        # Check if file exists
        if not include_path.exists():
            raise FileNotFoundError(f"Include file not found: {include_path}")

        # Read and recursively process the include
        include_source = include_path.read_text(encoding='utf-8')
        return _process_includes(include_source, base_dir, included)

    return re.sub(include_pattern, replace_include, source)


def load_shader_with_defines(path: Path, defines: dict[str, Any] | None = None, common_path: Path | None = None) -> str:
    """
    Load a shader with custom #define directives prepended.

    Args:
        path: Path to the shader file
        defines: Dictionary of macro name -> value to define
        common_path: Path to common.glsl

    Returns:
        The preprocessed shader source with defines prepended
    """
    source = load_shader(path, common_path)

    if defines:
        define_block = "\n".join(f"#define {k} {v}" for k, v in defines.items())
        source = define_block + "\n" + source

    return source
