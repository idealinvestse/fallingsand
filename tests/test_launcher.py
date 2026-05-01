import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.gui
class TestLauncherInitialization:
    """Test launcher GUI initialization."""

    def test_launcher_initialization(self):
        """Test that FallingSandLauncher initializes correctly."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)

            assert launcher.root == root
            assert hasattr(launcher, 'resolution_var')
            assert hasattr(launcher, 'enable_turbulence')
            assert hasattr(launcher, 'enable_wet_dry')
            assert hasattr(launcher, 'enable_thermal')
            assert hasattr(launcher, 'enable_hud')
            assert hasattr(launcher, 'enable_stats')

    def test_default_settings(self):
        """Test that default settings are correct."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)

            assert launcher.resolution_var.get() == "900x900"
            assert launcher.enable_turbulence.get()
            assert launcher.enable_wet_dry.get()
            assert launcher.enable_thermal.get()
            assert launcher.enable_hud.get()
            assert launcher.enable_stats.get()


@pytest.mark.gui
class TestLauncherResolution:
    """Test resolution handling."""

    def test_get_resolution_preset(self):
        """Test getting preset resolution."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.resolution_var.set("1024x768")

            w, h = launcher.get_resolution()
            assert w == 1024
            assert h == 768

    def test_get_resolution_custom_valid(self):
        """Test getting custom resolution with valid input."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.resolution_var.set("Custom")
            launcher.custom_w = Mock()
            launcher.custom_w.get = Mock(return_value="800")
            launcher.custom_h = Mock()
            launcher.custom_h.get = Mock(return_value="600")

            w, h = launcher.get_resolution()
            assert w == 800
            assert h == 600

    def test_get_resolution_custom_invalid(self):
        """Test getting custom resolution with invalid input."""
        with patch('tkinter.Tk'), \
             patch('tkinter.messagebox.showerror') as mock_showerror:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.resolution_var.set("Custom")
            launcher.custom_w = Mock()
            launcher.custom_w.get = Mock(return_value="invalid")
            launcher.custom_h = Mock()
            launcher.custom_h.get = Mock(return_value="600")

            w, h = launcher.get_resolution()
            mock_showerror.assert_called_once()
            assert w == 900  # Fallback to default
            assert h == 900

    @pytest.mark.skip(reason="Method removed - was dead code")
    def test_on_resolution_change_show_custom(self):
        """Test showing custom frame when Custom is selected."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.custom_res_frame = Mock()
            launcher.custom_res_frame.pack_forget = Mock()
            launcher.custom_res_frame.pack = Mock()

            launcher.resolution_var.set("Custom")
            launcher.on_resolution_change(None)

            launcher.custom_res_frame.pack.assert_called_once()

    @pytest.mark.skip(reason="Method removed - was dead code")
    def test_on_resolution_change_hide_custom(self):
        """Test hiding custom frame when preset is selected."""
        with patch('tkinter.Tk'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.custom_res_frame = Mock()
            launcher.custom_res_frame.pack_forget = Mock()
            launcher.custom_res_frame.pack = Mock()

            launcher.resolution_var.set("1024x768")
            launcher.on_resolution_change(None)

            launcher.custom_res_frame.pack_forget.assert_called_once()


@pytest.mark.gui
class TestLauncherLaunch:
    """Test game launch functionality."""

    def test_launch_game_default_settings(self):
        """Test launching game with default settings."""
        with patch('tkinter.Tk'), \
             patch('subprocess.Popen') as mock_popen:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)

            launcher.launch_game()

            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert 'main.py' in args
            assert '--width' in args
            assert '--height' in args

    def test_launch_game_custom_resolution(self):
        """Test launching game with custom resolution."""
        with patch('tkinter.Tk'), \
             patch('subprocess.Popen') as mock_popen:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.resolution_var.set("1280x720")

            launcher.launch_game()

            args = mock_popen.call_args[0][0]
            width_idx = args.index('--width') + 1
            height_idx = args.index('--height') + 1
            assert args[width_idx] == '1280'
            assert args[height_idx] == '720'

    def test_launch_game_disabled_features(self):
        """Test launching game with disabled features."""
        with patch('tkinter.Tk'), \
             patch('subprocess.Popen') as mock_popen:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.enable_turbulence.set(False)
            launcher.enable_wet_dry.set(False)
            launcher.enable_thermal.set(False)

            launcher.launch_game()

            args = mock_popen.call_args[0][0]
            assert '--no-turbulence' in args
            assert '--no-wet-dry' in args
            assert '--no-thermal' in args

    def test_launch_game_failure(self):
        """Test handling launch failure."""
        with patch('tkinter.Tk'), \
             patch('subprocess.Popen', side_effect=Exception("Launch failed")), \
             patch('tkinter.messagebox.showerror') as mock_showerror:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.status_label = Mock()

            launcher.launch_game()

            mock_showerror.assert_called_once()
            launcher.status_label.config.assert_called()


@pytest.mark.gui
class TestLauncherDependencies:
    """Test dependency checking functionality."""

    @pytest.mark.skip(reason="Method removed - was dead code")
    def test_check_dependencies_all_installed(self):
        """Test dependency check when all packages are installed."""
        with patch('tkinter.Tk'), \
             patch('tkinter.messagebox.showinfo') as mock_showinfo:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.status_label = Mock()
            launcher.root.update = Mock()

            launcher.check_dependencies()

            mock_showinfo.assert_called_once()
            assert "installed" in mock_showinfo.call_args[0][1].lower()

    @pytest.mark.skip(reason="Method removed - was dead code")
    def test_check_dependencies_missing_packages(self):
        """Test dependency check when packages are missing."""
        with patch('tkinter.Tk'), \
             patch('tkinter.messagebox.askyesno', return_value=False), \
             patch('tkinter.messagebox.showerror'):
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)
            launcher.status_label = Mock()
            launcher.root.update = Mock()

            # Mock __import__ to raise ImportError for pygame
            import builtins
            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == 'pygame':
                    raise ImportError("No module named 'pygame'")
                return real_import(name, *args, **kwargs)

            with patch('builtins.__import__', side_effect=mock_import):
                launcher.check_dependencies()

            launcher.status_label.config.assert_called()


@pytest.mark.gui
class TestLauncherControls:
    """Test controls display functionality."""

    @pytest.mark.skip(reason="Method removed - was dead code")
    def test_view_controls(self):
        """Test displaying controls dialog."""
        with patch('tkinter.Tk'), \
             patch('tkinter.messagebox.showinfo') as mock_showinfo:
            from launcher import FallingSandLauncher
            root = Mock()
            launcher = FallingSandLauncher(root)

            launcher.view_controls()

            mock_showinfo.assert_called_once()
            assert "CONTROLS" in mock_showinfo.call_args[0][0]
            assert "Left Click" in mock_showinfo.call_args[0][1]
            assert "Right Click" in mock_showinfo.call_args[0][1]
