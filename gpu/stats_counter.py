"""GPU-based material statistics counter to avoid full grid readback."""

import moderngl
import numpy as np

from core.constants import NUM_TYPES


class GPUStatsCounter:
    """Counts material types on GPU to avoid expensive CPU readback."""

    def __init__(self, ctx: moderngl.Context, grid_size: tuple[int, int]):
        """Initialize GPU stats counter."""
        self.ctx = ctx
        self.width, self.height = grid_size
        self.cell_count = self.width * self.height

        # Counter buffer: one uint32 per material type
        self.counter_buf = ctx.buffer(reserve=NUM_TYPES * 4)

        # Load compute shader for counting
        self._load_shader()

        # Workgroup size
        self.gx = (self.width + 15) // 16
        self.gy = (self.height + 15) // 16

    def _load_shader(self) -> None:
        """Load the counting compute shader."""
        shader_source = f"""
#version 430
layout(local_size_x = 16, local_size_y = 16) in;

layout(std430, binding = 0) readonly buffer CellBuffer   {{ uint cells[];    }};
layout(std430, binding = 9) coherent buffer CounterBuffer {{ uint counters[]; }};

uniform uvec2 gridSize;
const uint NUM_TYPES = {NUM_TYPES}u;

uint getType(uint c) {{
    return c & 0xFFu;
}}

void main() {{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(gridSize.x) || p.y >= int(gridSize.y)) return;

    uint idx = uint(p.y) * gridSize.x + uint(p.x);
    uint typ = getType(cells[idx]);

    // SSBO-based atomic counter (atomic_uint requires a special binding
    // point which moderngl does not expose; atomicAdd works on std430 uint).
    if (typ < NUM_TYPES) {{
        atomicAdd(counters[typ], 1u);
    }}
}}
"""
        self.compute_shader = self.ctx.compute_shader(shader_source)

    def get_counts(self, cell_buffer: moderngl.Buffer) -> dict[int, int]:
        """Get material counts from GPU."""
        # Reset counters
        self.counter_buf.write(np.zeros(NUM_TYPES, dtype=np.uint32).tobytes())

        # Bind buffers (binding 9 avoids clashing with pipeline slots 0..8)
        cell_buffer.bind_to_storage_buffer(0)
        self.counter_buf.bind_to_storage_buffer(9)

        # Set uniforms
        self.compute_shader["gridSize"] = (self.width, self.height)

        # Run compute shader
        self.compute_shader.run(group_x=self.gx, group_y=self.gy, group_z=1)

        # Read back only 41 uint32s instead of entire grid
        counts = np.frombuffer(self.counter_buf.read(), dtype=np.uint32)

        return {i: int(counts[i]) for i in range(NUM_TYPES)}

    def get_stats(self, cell_buffer: moderngl.Buffer) -> dict[str, int | float]:
        """Get simulation statistics as dict."""
        counts = self.get_counts(cell_buffer)

        return {
            "water": counts[2],
            "steam": counts[14],
            "fire": counts[4],
            "ember": counts[33],
            "blast": counts[35],
        }
