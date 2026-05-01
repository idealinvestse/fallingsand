"""Configuration management for the simulation."""

import argparse
from dataclasses import dataclass


@dataclass(slots=True)
class SimulationConfig:
    """Configuration for the simulation."""

    # Grid settings
    width: int = 1024
    height: int = 1024
    window_width: int = 900
    window_height: int = 900

    # Physics settings
    sim_substeps: int = 1
    pressure_iterations: int = 12
    no_turbulence: bool = False
    no_wet_dry: bool = False
    no_thermal: bool = False
    gravity: float = 9.8
    vorticity_confinement: float = 0.3
    surface_tension: float = 0.5
    thermal_convection: float = 1.0
    heat_diffusion_iterations: int = 2
    use_maccormack: bool = True
    powder_friction: float = 0.35
    angle_of_repose_deg: float = 32.0
    capillary_strength: float = 0.4
    wind_field: str = "none"
    adaptive_substeps: bool = True  # Phase 6: Enable CFL-based adaptive sub-stepping
    perf_overlay: bool = False

    # Acoustic simulation settings
    no_acoustics: bool = False       # Disable acoustic solver (fallback to Poisson-only)
    sound_speed: float = 4.0        # Wave propagation speed in gas (cells/frame)
    acoustic_substeps: int = 6       # Substeps per frame for CFL stability
    atm_pressure: float = 1.0        # Normalised ambient atmospheric pressure

    # UI settings
    no_hud: bool = False
    no_stats: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "SimulationConfig":
        """Create config from argparse namespace."""
        return cls(
            width=args.width,
            height=args.height,
            window_width=args.window_width,
            window_height=args.window_height,
            sim_substeps=args.sim_substeps,
            pressure_iterations=args.pressure_iterations,
            no_turbulence=args.no_turbulence,
            no_wet_dry=args.no_wet_dry,
            no_thermal=args.no_thermal,
            no_hud=args.no_hud,
            no_stats=args.no_stats,
            heat_diffusion_iterations=getattr(args, 'heat_diffusion_iterations', 2),
            use_maccormack=getattr(args, 'use_maccormack', True),
            powder_friction=getattr(args, 'powder_friction', 0.35),
            angle_of_repose_deg=getattr(args, 'angle_of_repose_deg', 32.0),
            capillary_strength=getattr(args, 'capillary_strength', 0.4),
            wind_field=getattr(args, 'wind_field', 'none'),
            no_acoustics=getattr(args, 'no_acoustics', False),
            sound_speed=getattr(args, 'sound_speed', 4.0),
            acoustic_substeps=getattr(args, 'acoustic_substeps', 6),
            atm_pressure=getattr(args, 'atm_pressure', 1.0),
            perf_overlay=getattr(args, 'perf', False),
        )

    def validate(self) -> list[str]:
        """Validate config and return list of errors."""
        errors = []

        from .constants import (
            MAX_GRID_SIZE,
            MIN_GRID_SIZE,
            MIN_PRESSURE_ITERATIONS,
            MIN_SUBSTEPS,
            MIN_WINDOW_SIZE,
            MAX_PRESSURE_ITERATIONS,
            MAX_SUBSTEPS,
        )

        if self.width < MIN_GRID_SIZE or self.height < MIN_GRID_SIZE:
            errors.append(f"Grid size must be at least {MIN_GRID_SIZE}")
        if self.width > MAX_GRID_SIZE or self.height > MAX_GRID_SIZE:
            errors.append(f"Grid size must not exceed {MAX_GRID_SIZE}")
        if (
            self.window_width < MIN_WINDOW_SIZE
            or self.window_height < MIN_WINDOW_SIZE
        ):
            errors.append(f"Window size must be at least {MIN_WINDOW_SIZE}")
        if self.sim_substeps < MIN_SUBSTEPS or self.sim_substeps > MAX_SUBSTEPS:
            errors.append(f"sim_substeps must be between {MIN_SUBSTEPS} and {MAX_SUBSTEPS}")
        if (
            self.pressure_iterations < MIN_PRESSURE_ITERATIONS
            or self.pressure_iterations > MAX_PRESSURE_ITERATIONS
        ):
            errors.append(
                f"pressure_iterations must be between {MIN_PRESSURE_ITERATIONS} and {MAX_PRESSURE_ITERATIONS}"
            )

        return errors
