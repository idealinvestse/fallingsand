"""Brush painter for the simulation grid."""

from __future__ import annotations

from gpu.buffers import BufferManager
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
    ) -> None:
        """Paint cells onto the grid.

        Modes:
          0 – place material_id in a filled circle.
          1 – add *delta* to the temperature of cells in the circle.
          2 – same as mode 1 (caller passes a negative delta for cooling).
          3 – place material_id as a single-cell spark (radius ignored).
        """
        from simulation.materials import get_material

        mat = get_material(material_id)
        dispatch_size = max(1, radius * 2 + 1)

        self.buffers.read_buf.bind_to_storage_buffer(0)
        self.buffers.write_buf.bind_to_storage_buffer(1)
        self.buffers.rule_ssbo.bind_to_storage_buffer(2)
        self.buffers.temp_a.bind_to_image(11, read=True, write=True, level=0, format=_FMT_R32F)
        self.buffers.temp_b.bind_to_image(12, read=True, write=True, level=0, format=_FMT_R32F)

        self.shader["gridSize"] = (self.width, self.height)
        self.shader["brushCenter"] = (int(cx), int(cy))
        self.shader["brushRadius"] = int(radius)
        self.shader["materialId"] = int(material_id)
        self.shader["brushMode"] = int(mode)
        self.shader["tempDelta"] = float(delta)
        self.shader["materialTemp"] = float(mat.default_flame_temp)
        self.shader["materialLife"] = int(mat.default_flame_life)
        self.shader.run(group_x=(dispatch_size + 15) // 16, group_y=(dispatch_size + 15) // 16, group_z=1)
        self.buffers.ctx.memory_barrier()
