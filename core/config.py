"""Configuration management for the simulation."""

import argparse
from dataclasses import dataclass, field


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

    # Post-FX settings
    bloom_enabled: bool = True
    bloom_threshold: float = 0.6
    bloom_intensity: float = 0.6
    bloom_radius: float = 1.0
    bloom_quality: str = "medium"

    # New system settings (Phase 1)
    enable_electricity: bool = False
    enable_biology: bool = False
    enable_weather: bool = False
    charge_decay: float = 0.0
    max_charge: float = 1000.0
    breakdown_threshold: float = 500.0
    arc_temp_delta: float = 200.0
    arc_pressure_pulse: float = 5.0
    nutrient_diffuse_rate: float = 0.5
    moisture_diffuse_rate: float = 0.3
    growth_rate: float = 0.1
    decay_rate: float = 0.05
    humidity_diffuse_rate: float = 0.4
    evaporation_rate: float = 0.1
    condensation_rate: float = 0.3
    saturation_threshold: float = 100.0
    rain_speed: float = 2.0

    # Dynamic quality scaling (Phase 1)
    adaptive_quality: bool = False
    min_fps_target: float = 30.0
    quality_tiers: list = field(default_factory=lambda: [
        {"pressure_iterations": 20, "acoustic_substeps": 6, "bloom_enabled": True},
        {"pressure_iterations": 12, "acoustic_substeps": 4, "bloom_enabled": True},
        {"pressure_iterations": 8, "acoustic_substeps": 2, "bloom_enabled": False},
    ])
    transpiration_rate: float = 0.05

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
            gravity=args.gravity,
            vorticity_confinement=args.vorticity_confinement,
            surface_tension=args.surface_tension,
            thermal_convection=args.thermal_convection,
            heat_diffusion_iterations=args.heat_diffusion_iterations,
            use_maccormack=not args.no_maccormack,
            powder_friction=args.powder_friction,
            angle_of_repose_deg=args.angle_of_repose_deg,
            capillary_strength=args.capillary_strength,
            wind_field=args.wind_field,
            adaptive_substeps=args.adaptive_substeps,
            perf_overlay=args.perf,
            no_acoustics=args.no_acoustics,
            sound_speed=args.sound_speed,
            acoustic_substeps=args.acoustic_substeps,
            atm_pressure=args.atm_pressure,
            bloom_enabled=not args.no_bloom,
            bloom_threshold=args.bloom_threshold,
            bloom_intensity=getattr(args, "bloom_intensity", 0.6),
            bloom_radius=getattr(args, "bloom_radius", 1.0),
            bloom_quality=getattr(args, "bloom_quality", "medium"),
            enable_electricity=getattr(args, "enable_electricity", False),
            enable_biology=getattr(args, "enable_biology", False),
            enable_weather=getattr(args, "enable_weather", False),
            charge_decay=getattr(args, "charge_decay", 0.0),
            max_charge=getattr(args, "max_charge", 1000.0),
            breakdown_threshold=getattr(args, "breakdown_threshold", 500.0),
            arc_temp_delta=getattr(args, "arc_temp_delta", 200.0),
            arc_pressure_pulse=getattr(args, "arc_pressure_pulse", 5.0),
            nutrient_diffuse_rate=getattr(args, "nutrient_diffuse_rate", 0.5),
            moisture_diffuse_rate=getattr(args, "moisture_diffuse_rate", 0.3),
            growth_rate=getattr(args, "growth_rate", 0.1),
            decay_rate=getattr(args, "decay_rate", 0.05),
            humidity_diffuse_rate=getattr(args, "humidity_diffuse_rate", 0.4),
            evaporation_rate=getattr(args, "evaporation_rate", 0.1),
            condensation_rate=getattr(args, "condensation_rate", 0.3),
            saturation_threshold=getattr(args, "saturation_threshold", 100.0),
            rain_speed=getattr(args, "rain_speed", 2.0),
            adaptive_quality=getattr(args, "adaptive_quality", False),
            min_fps_target=getattr(args, "min_fps_target", 30.0),
            transpiration_rate=getattr(args, "transpiration_rate", 0.05),
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
