"""GPU buffer management for simulation."""

import moderngl
import numpy as np

from gpu.resources import SSBO_CELLS_READ, SSBO_CELLS_WRITE, SSBO_RESERVATIONS, SSBO_RULES


class BufferManager:
    """Manages GPU buffers for simulation (cell data, velocity, pressure)."""

    def __init__(self, ctx: moderngl.Context, grid_size: tuple[int, int]):
        """Initialize all GPU buffers and set up persistent bindings."""
        self.ctx = ctx
        self.width, self.height = grid_size
        self.grid_size = grid_size
        self.cell_count = self.width * self.height

        # Cell buffers (double buffering for ping-pong)
        self.read_buf = ctx.buffer(reserve=self.cell_count * 4)
        self.write_buf = ctx.buffer(reserve=self.cell_count * 4)

        # Velocity textures
        self.vel_a = ctx.texture((self.width, self.height), 2, dtype='f4')
        self.vel_b = ctx.texture((self.width, self.height), 2, dtype='f4')

        # Pressure textures (scalar r32f)
        self.pres_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.pres_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Divergence texture (scalar r32f)
        self.div_tex = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Vorticity texture (scalar r32f) for vorticity confinement
        self.vorticity_tex = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Mass textures (r16f) for fractional fill / wet mass per cell
        self.mass_a = ctx.texture((self.width, self.height), 1, dtype='f2')
        self.mass_b = ctx.texture((self.width, self.height), 1, dtype='f2')

        # Temperature textures (r32f) for continuous float temperature
        self.temp_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.temp_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Wind texture (rg16f) for environmental wind field
        self.wind_tex = ctx.texture((self.width, self.height), 2, dtype='f2')

        # Charge textures (r32f) for electricity potential/charge field
        self.charge_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.charge_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Nutrient textures (r32f) for biology/ecology nutrient field
        self.nutrient_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.nutrient_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Moisture textures (r32f) for biology/ecology moisture field
        self.moisture_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.moisture_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Humidity textures (r32f) for weather/atmospheric humidity
        self.humidity_a = ctx.texture((self.width, self.height), 1, dtype='f4')
        self.humidity_b = ctx.texture((self.width, self.height), 1, dtype='f4')

        # Reservation SSBO for conflict-free cell motion (advect pass)
        self.reservations_buf = ctx.buffer(reserve=self.cell_count * 4)
        self._zero_reservations = np.zeros(self.cell_count, dtype=np.uint32).tobytes()
        self.reservations_buf.write(self._zero_reservations)

        # Initialize new textures to zero
        zero_mass = np.zeros((self.width, self.height, 1), dtype=np.float16)
        self.mass_a.write(zero_mass.tobytes())
        self.mass_b.write(zero_mass.tobytes())

        # Initialize temp to ambient temperature
        from core.constants import TEMP_AMBIENT
        ambient_temp_arr = np.full((self.width, self.height, 1), float(TEMP_AMBIENT), dtype=np.float32)
        self.temp_a.write(ambient_temp_arr.tobytes())
        self.temp_b.write(ambient_temp_arr.tobytes())

        # Initialize wind to zero
        zero_wind = np.zeros((self.width, self.height, 2), dtype=np.float16)
        self.wind_tex.write(zero_wind.tobytes())

        # Initialize charge to zero
        zero_charge = np.zeros((self.width, self.height, 1), dtype=np.float32)
        self.charge_a.write(zero_charge.tobytes())
        self.charge_b.write(zero_charge.tobytes())

        # Initialize nutrient and moisture to zero
        zero_scalar = np.zeros((self.width, self.height, 1), dtype=np.float32)
        self.nutrient_a.write(zero_scalar.tobytes())
        self.nutrient_b.write(zero_scalar.tobytes())
        self.moisture_a.write(zero_scalar.tobytes())
        self.moisture_b.write(zero_scalar.tobytes())
        self.humidity_a.write(zero_scalar.tobytes())
        self.humidity_b.write(zero_scalar.tobytes())

        # Display texture
        self.display_texture = ctx.texture((self.width, self.height), 4, dtype='f1')
        self.display_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # Rule buffer (material properties)
        self.rule_ssbo = self._create_rule_buffer()

        # Set up persistent buffer bindings (bind once, use forever)
        self._setup_persistent_bindings()

    def _create_rule_buffer(self) -> moderngl.Buffer:
        """Create rule buffer from material definitions."""
        # Import here to avoid circular dependency
        from simulation.materials import to_rule_buffer

        rules = to_rule_buffer()
        return self.ctx.buffer(np.array(rules, dtype='f4'))

    def _setup_persistent_bindings(self) -> None:
        """Set up persistent buffer bindings to avoid per-frame rebinding."""
        # Bind cell buffers to binding points 0 (read) and 1 (write). Without this
        # initial bind, the first compute dispatch of every frame-0 pipeline runs
        # against unbound SSBOs, corrupting the grid before the first swap.
        self.read_buf.bind_to_storage_buffer(SSBO_CELLS_READ)
        self.write_buf.bind_to_storage_buffer(SSBO_CELLS_WRITE)
        # Bind rule buffer to binding point 2 (persistent)
        self.rule_ssbo.bind_to_storage_buffer(SSBO_RULES)
        # Bind reservations buffer to binding point 8 (used by advect pass)
        self.reservations_buf.bind_to_storage_buffer(SSBO_RESERVATIONS)

    def clear_reservations(self) -> None:
        """Zero the reservations buffer. Call once per frame before advect."""
        self.reservations_buf.clear()

    def clear_write_buf_to_air(self) -> None:
        """Fill the write (output) cell buffer with air cells.

        The advect pass assumes its output buffer is pre-cleared so that
        cells that fall off the grid leave air behind and winning movers do
        not race with stationary air cells.
        """
        self.write_buf.clear()

    def swap_cell_buffers(self) -> None:
        """Swap read and write cell buffers."""
        self.read_buf, self.write_buf = self.write_buf, self.read_buf
        # Re-bind to maintain persistent binding point 0 and 1
        self.read_buf.bind_to_storage_buffer(SSBO_CELLS_READ)
        self.write_buf.bind_to_storage_buffer(SSBO_CELLS_WRITE)

    def swap_velocity_buffers(self) -> None:
        """Swap velocity buffers."""
        self.vel_a, self.vel_b = self.vel_b, self.vel_a

    def swap_pressure_buffers(self) -> None:
        """Swap pressure buffers."""
        self.pres_a, self.pres_b = self.pres_b, self.pres_a

    def swap_mass_buffers(self) -> None:
        """Swap mass buffers."""
        self.mass_a, self.mass_b = self.mass_b, self.mass_a

    def swap_temp_buffers(self) -> None:
        """Swap temperature buffers."""
        self.temp_a, self.temp_b = self.temp_b, self.temp_a

    def swap_charge_buffers(self) -> None:
        """Swap charge/potential buffers."""
        self.charge_a, self.charge_b = self.charge_b, self.charge_a

    def swap_nutrient_buffers(self) -> None:
        """Swap nutrient buffers."""
        self.nutrient_a, self.nutrient_b = self.nutrient_b, self.nutrient_a

    def swap_moisture_buffers(self) -> None:
        """Swap moisture buffers."""
        self.moisture_a, self.moisture_b = self.moisture_b, self.moisture_a

    def swap_humidity_buffers(self) -> None:
        """Swap humidity buffers."""
        self.humidity_a, self.humidity_b = self.humidity_b, self.humidity_a

    def clear_mass_buffers(self) -> None:
        """Zero the mass buffers."""
        zero_mass = np.zeros((self.width, self.height, 1), dtype=np.float16)
        self.mass_a.write(zero_mass.tobytes())
        self.mass_b.write(zero_mass.tobytes())

    def clear_temp_buffers(self, ambient_temp: float = 96.0) -> None:
        """Fill temperature buffers with ambient value in simulation temperature units."""
        ambient_temp_arr = np.full((self.width, self.height, 1), ambient_temp, dtype=np.float32)
        self.temp_a.write(ambient_temp_arr.tobytes())
        self.temp_b.write(ambient_temp_arr.tobytes())

    def clear_physics_buffers(self, ambient_pressure: float = 1.0) -> None:
        """Reset velocity, pressure, divergence, and vorticity to clean state.

        Call after undo, clear, or load_level to prevent stale fluid dynamics
        from affecting the restored / fresh cell configuration.
        """
        zero_vel = np.zeros((self.width, self.height, 2), dtype=np.float32)
        self.vel_a.write(zero_vel.tobytes())
        self.vel_b.write(zero_vel.tobytes())
        zero_scalar = np.zeros((self.width, self.height, 1), dtype=np.float32)
        self.div_tex.write(zero_scalar.tobytes())
        self.vorticity_tex.write(zero_scalar.tobytes())
        ambient_pres = np.full((self.width, self.height, 1), ambient_pressure, dtype=np.float32)
        self.pres_a.write(ambient_pres.tobytes())
        self.pres_b.write(ambient_pres.tobytes())
        zero_charge = np.zeros((self.width, self.height, 1), dtype=np.float32)
        self.charge_a.write(zero_charge.tobytes())
        self.charge_b.write(zero_charge.tobytes())
        self.nutrient_a.write(zero_scalar.tobytes())
        self.nutrient_b.write(zero_scalar.tobytes())
        self.moisture_a.write(zero_scalar.tobytes())
        self.moisture_b.write(zero_scalar.tobytes())
        self.humidity_a.write(zero_scalar.tobytes())
        self.humidity_b.write(zero_scalar.tobytes())

    def get_read_buf(self) -> moderngl.Buffer:
        """Get current read buffer."""
        return self.read_buf

    def get_write_buf(self) -> moderngl.Buffer:
        """Get current write buffer."""
        return self.write_buf

    def get_rule_buffer(self) -> moderngl.Buffer:
        """Get rule buffer."""
        return self.rule_ssbo

    def save_state(self) -> bytes:
        """Save current simulation state to bytes."""
        return self.read_buf.read()

    def load_state(self, data: bytes) -> None:
        """Load simulation state from bytes (cell data only).

        Temperature is stored separately in r32f float textures.
        Callers that need to also restore temperature should write to
        temp_a/temp_b directly.
        """
        self.read_buf.write(data)
        self.write_buf.write(data)

    def resize(self, new_width: int, new_height: int) -> None:
        """Resize all buffers to new grid dimensions."""
        # Note: This is a simplified resize - in production, you'd want to
        # preserve existing data or implement proper resizing logic
        self.width = new_width
        self.height = new_height
        self.grid_size = (new_width, new_height)
        self.cell_count = new_width * new_height

        # Recreate cell buffers
        self.read_buf = self.ctx.buffer(reserve=self.cell_count * 4)
        self.write_buf = self.ctx.buffer(reserve=self.cell_count * 4)

        # Recreate velocity textures
        self.vel_a = self.ctx.texture((new_width, new_height), 2, dtype='f4')
        self.vel_b = self.ctx.texture((new_width, new_height), 2, dtype='f4')
        self.vorticity_tex = self.ctx.texture((new_width, new_height), 1, dtype='f4')

        # Recreate pressure textures
        self.pres_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.pres_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.div_tex = self.ctx.texture((new_width, new_height), 1, dtype='f4')

        # Recreate mass textures (were missing!)
        self.mass_a = self.ctx.texture((new_width, new_height), 1, dtype='f2')
        self.mass_b = self.ctx.texture((new_width, new_height), 1, dtype='f2')
        zero_mass = np.zeros((new_width, new_height, 1), dtype=np.float16)
        self.mass_a.write(zero_mass.tobytes())
        self.mass_b.write(zero_mass.tobytes())

        # Recreate temperature textures (were missing!)
        self.temp_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.temp_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        from core.constants import TEMP_AMBIENT
        ambient_temp_arr = np.full((new_width, new_height, 1), float(TEMP_AMBIENT), dtype=np.float32)
        self.temp_a.write(ambient_temp_arr.tobytes())
        self.temp_b.write(ambient_temp_arr.tobytes())

        # Recreate wind texture (was missing!)
        self.wind_tex = self.ctx.texture((new_width, new_height), 2, dtype='f2')
        zero_wind = np.zeros((new_width, new_height, 2), dtype=np.float16)
        self.wind_tex.write(zero_wind.tobytes())

        # Recreate charge textures
        self.charge_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.charge_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        zero_charge = np.zeros((new_width, new_height, 1), dtype=np.float32)
        self.charge_a.write(zero_charge.tobytes())
        self.charge_b.write(zero_charge.tobytes())

        # Recreate nutrient and moisture textures
        self.nutrient_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.nutrient_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.moisture_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.moisture_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        zero_scalar = np.zeros((new_width, new_height, 1), dtype=np.float32)
        self.nutrient_a.write(zero_scalar.tobytes())
        self.nutrient_b.write(zero_scalar.tobytes())
        self.moisture_a.write(zero_scalar.tobytes())
        self.moisture_b.write(zero_scalar.tobytes())

        # Recreate humidity textures
        self.humidity_a = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.humidity_b = self.ctx.texture((new_width, new_height), 1, dtype='f4')
        self.humidity_a.write(zero_scalar.tobytes())
        self.humidity_b.write(zero_scalar.tobytes())

        # Recreate display texture
        self.display_texture = self.ctx.texture((new_width, new_height), 4, dtype='f1')
        self.display_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # Recreate reservation buffer
        self.reservations_buf = self.ctx.buffer(reserve=self.cell_count * 4)
        self._zero_reservations = np.zeros(self.cell_count, dtype=np.uint32).tobytes()
        self.reservations_buf.write(self._zero_reservations)

        # Recreate rule buffer
        self.rule_ssbo = self._create_rule_buffer()

        # Re-establish persistent bindings
        self._setup_persistent_bindings()
