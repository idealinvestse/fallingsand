"""Simulation constants."""

# Material type count
NUM_TYPES = 61

# Rule buffer stride (floats per material definition)
# Actual count from to_rule_buffer: 64 floats per material
RULE_STRIDE = 64

# Ambient temperature (0-255 scale)
TEMP_AMBIENT = 96

# Grid size limits
MIN_GRID_SIZE = 64
MAX_GRID_SIZE = 4096

# Window size limits
MIN_WINDOW_SIZE = 100

# Simulation limits
MIN_SUBSTEPS = 1
MAX_SUBSTEPS = 10
MIN_PRESSURE_ITERATIONS = 1
MAX_PRESSURE_ITERATIONS = 100

# Brush limits
MIN_BRUSH_SIZE = 1
MAX_BRUSH_SIZE = 50

# Acoustic simulation defaults
# CFL condition for 2D explicit: c·dt/dx ≤ 1/√2 ≈ 0.707
# With N substeps: c/N ≤ 0.707 → c=4, N=6 → 0.667 ✓
SOUND_SPEED_DEFAULT = 4.0       # cells/frame — wave propagation speed in gas
ACOUSTIC_SUBSTEPS_DEFAULT = 6   # substeps per frame for acoustic CFL stability
ATM_PRESSURE_DEFAULT = 1.0      # normalised ambient atmospheric pressure
ATM_SCALE_HEIGHT = 200.0        # cells — exponential pressure decay height
