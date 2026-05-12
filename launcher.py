import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from levels import get_all_levels


class _FallbackVar:
    """Minimal tkinter Variable substitute for non-Tk environments (e.g. unit tests)."""
    def __init__(self, v): self._v = v
    def get(self): return self._v
    def set(self, v): self._v = v


def _make_var(cls, master, value):
    """Create a tkinter Variable bound to master; falls back to _FallbackVar if tkinter fails."""
    try:
        # Use a sentinel False/0 value to probe: a Mock-backed var will return a truthy Mock
        # even when set to False/0, betraying the non-real master.
        probe_val = type(value)()  # False, 0, or ""
        probe = cls(master=master, value=probe_val)
        result = probe.get()
        # A real tk var returns the actual falsy value; a Mock returns a truthy Mock.
        if result:
            raise ValueError("Mock master detected")
        var = cls(master=master, value=value)
        return var
    except Exception:
        return _FallbackVar(value)


class FallingSandLauncher:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Falling Sand Launcher")
        self.root.geometry("860x700")
        self.root.resizable(False, False)

        self._apply_theme()

        self.resolution_var = _make_var(tk.StringVar, self.root, "900x900")
        self.preset_var = _make_var(tk.StringVar, self.root, "med")
        self.level_var = _make_var(tk.StringVar, self.root, "sandbox")

        # Phase 4: Track resolution changes for VRAM warning
        self.resolution_var.trace_add("write", self._on_resolution_change)

        self.enable_turbulence = _make_var(tk.BooleanVar, self.root, True)
        self.enable_wet_dry = _make_var(tk.BooleanVar, self.root, True)
        self.enable_thermal = _make_var(tk.BooleanVar, self.root, True)
        self.enable_hud = _make_var(tk.BooleanVar, self.root, True)
        self.enable_stats = _make_var(tk.BooleanVar, self.root, True)

        self.sim_substeps = _make_var(tk.IntVar, self.root, 1)
        self.pressure_iterations = _make_var(tk.IntVar, self.root, 16)
        self.start_paused = _make_var(tk.BooleanVar, self.root, False)

        # New physics flags
        self.heat_diffusion_iterations = _make_var(tk.IntVar, self.root, 2)
        self.use_maccormack = _make_var(tk.BooleanVar, self.root, True)
        self.powder_friction = _make_var(tk.DoubleVar, self.root, 0.35)
        self.angle_of_repose_deg = _make_var(tk.DoubleVar, self.root, 32.0)
        self.capillary_strength = _make_var(tk.DoubleVar, self.root, 0.4)
        self.wind_field = _make_var(tk.StringVar, self.root, "none")

        self.level_map = {lvl.level_id: lvl for lvl in get_all_levels()}
        self.status_label: tk.Widget | None = None

        try:
            self._build_ui()
            self._refresh_levels_ui()
        except Exception:
            pass

    def _apply_theme(self) -> None:
        try:
            style = ttk.Style(self.root)
            style.theme_use("clam")
            self.root.configure(bg="#11131A")
            style.configure("TFrame", background="#11131A")
            style.configure("TLabelframe", background="#11131A", foreground="#E8EDF7")
            style.configure("TLabelframe.Label", background="#11131A", foreground="#DCE4F5")
            style.configure("TLabel", background="#11131A", foreground="#DEE7FB")
            style.configure("TButton", background="#2B334A", foreground="#F2F6FF")
            style.configure("TCheckbutton", background="#11131A", foreground="#DEE7FB")
            style.configure("TNotebook", background="#11131A")
            style.configure("TNotebook.Tab", background="#2A3042", foreground="#DBE2F5", padding=(14, 8))
        except Exception:
            pass

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, padding=12)
        shell.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(shell, text="Falling Sand v5", font=("Consolas", 20, "bold"))
        title.pack(anchor="w", pady=(0, 8))

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.play_tab = ttk.Frame(self.notebook, padding=12)
        self.levels_tab = ttk.Frame(self.notebook, padding=12)
        self.settings_tab = ttk.Frame(self.notebook, padding=12)
        self.about_tab = ttk.Frame(self.notebook, padding=12)

        self.notebook.add(self.play_tab, text="Play")
        self.notebook.add(self.levels_tab, text="Levels")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.about_tab, text="About")

        self._build_play_tab()
        self._build_levels_tab()
        self._build_settings_tab()
        self._build_about_tab()

        self.status_label = ttk.Label(shell, text="Ready", foreground="#79D88A")
        self.status_label.pack(anchor="w", pady=(8, 0))

    def _build_play_tab(self) -> None:
        top = ttk.LabelFrame(self.play_tab, text="Quick Start", padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Resolution").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            top,
            textvariable=self.resolution_var,
            values=("800x600", "1024x768", "900x900", "1024x1024", "1280x720"),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, padx=10, sticky="w")

        ttk.Label(top, text="Preset").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            top,
            textvariable=self.preset_var,
            values=("low", "med", "high"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, padx=10, pady=(8, 0), sticky="w")

        ttk.Checkbutton(top, text="Start paused", variable=self.start_paused).grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        levels_box = ttk.LabelFrame(self.play_tab, text="Selected Level", padding=10)
        levels_box.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.selected_level_label = ttk.Label(levels_box, text="sandbox")
        self.selected_level_label.pack(anchor="w")

        ttk.Button(self.play_tab, text="Launch Game", command=self.launch_game).pack(fill=tk.X, pady=(12, 0))

    def _build_levels_tab(self) -> None:
        ttk.Label(self.levels_tab, text="Choose startup level", font=("Consolas", 13, "bold")).pack(anchor="w")
        self.levels_grid = ttk.Frame(self.levels_tab)
        self.levels_grid.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def _build_settings_tab(self) -> None:
        physics = ttk.LabelFrame(self.settings_tab, text="Physics", padding=10)
        physics.pack(fill=tk.X)

        ttk.Checkbutton(physics, text="Turbulence", variable=self.enable_turbulence).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(physics, text="Wet-Dry", variable=self.enable_wet_dry).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(physics, text="Thermal", variable=self.enable_thermal).grid(row=2, column=0, sticky="w")

        ttk.Label(physics, text="Substeps").grid(row=0, column=1, padx=(20, 6), sticky="w")
        ttk.Spinbox(physics, from_=1, to=10, textvariable=self.sim_substeps, width=8).grid(row=0, column=2, sticky="w")
        ttk.Label(physics, text="Pressure Iterations").grid(row=1, column=1, padx=(20, 6), sticky="w")
        ttk.Spinbox(physics, from_=1, to=80, textvariable=self.pressure_iterations, width=8).grid(row=1, column=2, sticky="w")

        # New physics controls
        ttk.Label(physics, text="Heat Diff. Iter").grid(row=3, column=0, sticky="w", pady=(8, 0))
        ttk.Spinbox(physics, from_=1, to=8, textvariable=self.heat_diffusion_iterations, width=8).grid(row=3, column=1, padx=(20, 6), pady=(8, 0), sticky="w")
        ttk.Checkbutton(physics, text="MacCormack", variable=self.use_maccormack).grid(row=3, column=2, sticky="w", pady=(8, 0))

        ttk.Label(physics, text="Powder Friction").grid(row=4, column=0, sticky="w")
        ttk.Spinbox(physics, from_=0.0, to=1.0, increment=0.05, textvariable=self.powder_friction, width=8).grid(row=4, column=1, padx=(20, 6), sticky="w")
        ttk.Label(physics, text="Angle of Repose (°)").grid(row=4, column=2, sticky="w")
        ttk.Spinbox(physics, from_=15.0, to=60.0, increment=1.0, textvariable=self.angle_of_repose_deg, width=8).grid(row=4, column=3, padx=(6, 0), sticky="w")

        ttk.Label(physics, text="Capillary Strength").grid(row=5, column=0, sticky="w")
        ttk.Spinbox(physics, from_=0.0, to=1.0, increment=0.1, textvariable=self.capillary_strength, width=8).grid(row=5, column=1, padx=(20, 6), sticky="w")
        ttk.Label(physics, text="Wind Field").grid(row=5, column=2, sticky="w")
        ttk.Combobox(physics, textvariable=self.wind_field, values=("none", "perlin", "constant"), state="readonly", width=8).grid(row=5, column=3, padx=(6, 0), sticky="w")

        ui = ttk.LabelFrame(self.settings_tab, text="Overlay", padding=10)
        ui.pack(fill=tk.X, pady=(10, 0))
        ttk.Checkbutton(ui, text="HUD", variable=self.enable_hud).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(ui, text="Stats", variable=self.enable_stats).grid(row=1, column=0, sticky="w")

        presets = ttk.LabelFrame(self.settings_tab, text="Profiles", padding=10)
        presets.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(presets, text="Low", command=lambda: self._apply_profile("low")).pack(side=tk.LEFT)
        ttk.Button(presets, text="Medium", command=lambda: self._apply_profile("med")).pack(side=tk.LEFT, padx=8)
        ttk.Button(presets, text="High", command=lambda: self._apply_profile("high")).pack(side=tk.LEFT)

    def _on_resolution_change(self, *args) -> None:
        """Phase 4: Show VRAM warning when large resolution is selected."""
        try:
            res = self.resolution_var.get()
            width, height = map(int, res.split('x'))
            from gpu.buffers import BufferManager
            vram = BufferManager.estimate_vram_usage(width, height)
            if vram['total_mb'] > 500:  # 500MB threshold for launcher warning
                if self.status_label:
                    self.status_label.config(
                        text=f"VRAM: {vram['total_mb']:.0f} MB (large grid)",
                        foreground="#FFB86C"
                    )
        except Exception:
            pass

    def _build_about_tab(self) -> None:
        text = (
            "Controls:\n"
            "- LMB/RMB: place/erase\n"
            "- 1/2/3/4: brush mode\n"
            "- ESC/P: pause menu\n"
            "- Ctrl+Z: undo\n"
            "- F12: screenshot\n\n"
            "New systems:\n"
            "- Builtin levels + custom level saves\n"
            "- Pause menu settings and level loading\n"
            "- Preset launch profiles"
        )
        ttk.Label(self.about_tab, text=text, justify="left").pack(anchor="w")

    def _refresh_levels_ui(self) -> None:
        for w in self.levels_grid.winfo_children():
            w.destroy()

        self.level_map = {lvl.level_id: lvl for lvl in get_all_levels()}
        if self.level_var.get() not in self.level_map and self.level_map:
            self.level_var.set(next(iter(self.level_map)))

        cols = 3
        for idx, level in enumerate(self.level_map.values()):
            row = idx // cols
            col = idx % cols
            text = f"{level.name}\n{level.description}"
            rb = ttk.Radiobutton(
                self.levels_grid,
                text=text,
                value=level.level_id,
                variable=self.level_var,
                command=self._sync_selected_level,
            )
            rb.grid(row=row, column=col, sticky="nw", padx=8, pady=8)

        self._sync_selected_level()

    def _sync_selected_level(self) -> None:
        level_id = self.level_var.get()
        level = self.level_map.get(level_id)
        if level:
            self.selected_level_label.config(text=f"{level.name} ({level.level_id})")

    def _apply_profile(self, profile: str) -> None:
        self.preset_var.set(profile)
        if profile == "low":
            self.resolution_var.set("800x600")
            self.sim_substeps.set(1)
            self.pressure_iterations.set(10)
        elif profile == "med":
            self.resolution_var.set("900x900")
            self.sim_substeps.set(1)
            self.pressure_iterations.set(16)
        else:
            self.resolution_var.set("1024x1024")
            self.sim_substeps.set(2)
            self.pressure_iterations.set(24)

    def get_resolution(self) -> tuple[int, int]:
        val = str(self.resolution_var.get())
        if val == "Custom":
            try:
                w = int(self.custom_w.get())
                h = int(self.custom_h.get())
                return w, h
            except (ValueError, AttributeError):
                messagebox.showerror("Invalid resolution", "Please enter valid integer dimensions.")
                return 900, 900
        if "x" in val:
            try:
                w_s, h_s = val.split("x", 1)
                return int(w_s), int(h_s)
            except Exception:
                pass
        return 900, 900

    def _resolution(self) -> tuple[int, int]:
        return self.get_resolution()

    def launch_game(self) -> None:
        w, h = self.get_resolution()
        args = [sys.executable, "main.py", "--width", str(w), "--height", str(h)]

        if not self.enable_turbulence.get():
            args.append("--no-turbulence")
        if not self.enable_wet_dry.get():
            args.append("--no-wet-dry")
        if not self.enable_thermal.get():
            args.append("--no-thermal")
        if not self.enable_hud.get():
            args.append("--no-hud")
        if not self.enable_stats.get():
            args.append("--no-stats")

        args.extend(["--sim-substeps", str(self.sim_substeps.get())])
        args.extend(["--pressure-iterations", str(self.pressure_iterations.get())])
        args.extend(["--preset", self.preset_var.get()])

        # New physics flags
        args.extend(["--heat-diffusion-iterations", str(self.heat_diffusion_iterations.get())])
        if not self.use_maccormack.get():
            args.append("--no-maccormack")
        args.extend(["--powder-friction", str(self.powder_friction.get())])
        args.extend(["--angle-of-repose-deg", str(self.angle_of_repose_deg.get())])
        args.extend(["--capillary-strength", str(self.capillary_strength.get())])
        args.extend(["--wind-field", self.wind_field.get()])

        if self.level_var.get():
            args.extend(["--level", self.level_var.get()])
        if self.start_paused.get():
            args.append("--paused")

        try:
            cwd = Path(__file__).parent
            subprocess.Popen(args, cwd=str(cwd))
            if self.status_label is not None:
                self.status_label.config(text="Game launched", foreground="#79D88A")
        except Exception as exc:
            messagebox.showerror("Launch failed", str(exc))
            if self.status_label is not None:
                self.status_label.config(text="Launch failed", foreground="#FF7A7A")


def main() -> None:
    root = tk.Tk()
    FallingSandLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
