"""Brush painter for the simulation grid."""

from __future__ import annotations

from gpu.buffers import BufferManager
from gpu.resources import (
    IMAGE_CHARGE_IN,
    IMAGE_CHARGE_OUT,
    IMAGE_TEMPERATURE_IN,
    IMAGE_TEMPERATURE_OUT,
    SSBO_CELLS_READ,
    SSBO_CELLS_WRITE,
    SSBO_RULES,
)
from shader_loader import load_shader

_FMT_R32F = 0x822E


class BrushPainter:
    """Paints materials and temperature deltas onto the GPU grid."""

    def __init__(self, buffers: BufferManager, grid_size: tuple[int, int]):
        self.buffers = buffers
        self.width, self.height = grid_size
        shader_path = __import__("pathlib").Path(__file__).parent.parent / "shaders" / "brush_shader.glsl"
        self.shader = buffers.ctx.compute_shader(load_shader(shader_path))

    def apply_brush(
        self,
        cx: int,
        cy: int,
        radius: int,
        material_id: int,
        mode: int = 0,
        delta: int = 0,
        **kwargs,
    ) -> None:
        """Paint cells onto the grid.

        Modes:
          0 – place material_id in a filled circle.
          1 – add *delta* to the temperature of cells in the circle.
          2 – same as mode 1 (caller passes a negative delta for cooling).
          3 – place material_id as a single-cell spark (radius ignored).
          4 – inject chargeDelta into charge field (pass charge_delta in kwargs).
        """
        from simulation.materials import get_material

        mat = get_material(material_id)
        dispatch_size = max(1, radius * 2 + 1)

        self.buffers.read_buf.bind_to_storage_buffer(SSBO_CELLS_READ)
        self.buffers.write_buf.bind_to_storage_buffer(SSBO_CELLS_WRITE)
        self.buffers.rule_ssbo.bind_to_storage_buffer(SSBO_RULES)
        self.buffers.temp_a.bind_to_image(IMAGE_TEMPERATURE_IN, read=True, write=True, level=0, format=_FMT_R32F)
        self.buffers.temp_b.bind_to_image(IMAGE_TEMPERATURE_OUT, read=True, write=True, level=0, format=_FMT_R32F)
        self.buffers.charge_a.bind_to_image(IMAGE_CHARGE_IN, read=True, write=True, level=0, format=_FMT_R32F)
        self.buffers.charge_b.bind_to_image(IMAGE_CHARGE_OUT, read=True, write=True, level=0, format=_FMT_R32F)

        self.shader["gridSize"] = (self.width, self.height)
        self.shader["brushCenter"] = (int(cx), int(cy))
        self.shader["brushRadius"] = int(radius)
        self.shader["materialId"] = int(material_id)
        self.shader["brushMode"] = int(mode)
        self.shader["tempDelta"] = float(delta)
        self.shader["chargeDelta"] = float(kwargs.get("charge_delta", 0.0))
        self.shader["materialTemp"] = float(mat.default_flame_temp)
        self.shader["materialLife"] = int(mat.default_flame_life)
        self.shader.run(group_x=(dispatch_size + 15) // 16, group_y=(dispatch_size + 15) // 16, group_z=1)
        self.buffers.ctx.memory_barrier()
