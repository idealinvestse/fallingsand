"""CLI argument parsing and config validation (v5)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import SimulationConfig  # noqa: E402
import main as main_mod  # noqa: E402


def _parse(argv):
    with patch.object(sys, "argv", ["main.py", *argv]):
        return main_mod.parse_arguments()


class TestDefaults:
    def test_default_values(self):
        args = _parse([])
        assert args.width == 1024
        assert args.height == 1024
        assert args.window_width == 900
        assert args.window_height == 900
        assert args.no_turbulence is False
        assert args.no_wet_dry is False
        assert args.no_thermal is False
        assert args.no_hud is False
        assert args.no_stats is False
        assert args.sim_substeps == 1
        assert args.pressure_iterations == 20  # v5 default
        assert args.level == ""
        assert args.preset is None
        assert args.paused is False

    def test_no_single_pass_flag(self):
        """--single-pass was removed in v5."""
        with pytest.raises(SystemExit):
            _parse(["--single-pass"])


class TestCustom:
    def test_custom_width_height(self):
        args = _parse(["--width", "512", "--height", "256"])
        assert args.width == 512
        assert args.height == 256

    def test_custom_window_size(self):
        args = _parse(["--window-width", "800", "--window-height", "600"])
        assert (args.window_width, args.window_height) == (800, 600)

    @pytest.mark.parametrize("flag,attr", [
        ("--no-turbulence", "no_turbulence"),
        ("--no-wet-dry", "no_wet_dry"),
        ("--no-thermal", "no_thermal"),
        ("--no-hud", "no_hud"),
        ("--no-stats", "no_stats"),
    ])
    def test_feature_flag(self, flag, attr):
        args = _parse([flag])
        assert getattr(args, attr) is True

    def test_multiple_flags(self):
        args = _parse(["--no-turbulence", "--no-wet-dry", "--no-thermal"])
        assert args.no_turbulence and args.no_wet_dry and args.no_thermal

    def test_new_cli_flags(self):
        args = _parse(["--level", "volcano", "--preset", "high", "--paused"])
        assert args.level == "volcano"
        assert args.preset == "high"
        assert args.paused is True


class TestConfigValidation:
    def _config(self, **kwargs):
        return SimulationConfig(**kwargs)

    def test_grid_size_min_rejected(self):
        c = self._config(width=32, height=32)
        assert c.validate(), "width=32 should produce errors"

    def test_grid_size_max_rejected(self):
        c = self._config(width=5000, height=5000)
        assert c.validate()

    def test_window_size_min_rejected(self):
        c = self._config(window_width=50, window_height=50)
        assert c.validate()

    def test_grid_size_boundaries_accepted(self):
        assert self._config(width=64, height=64).validate() == []
        assert self._config(width=4096, height=4096).validate() == []

    def test_window_size_boundary_accepted(self):
        assert self._config(window_width=100, window_height=100).validate() == []

    def test_combined_valid(self):
        c = self._config(
            width=800, height=600,
            window_width=1024, window_height=768,
            no_turbulence=True, no_wet_dry=True, no_thermal=True,
            no_hud=True, no_stats=True,
        )
        assert c.validate() == []
