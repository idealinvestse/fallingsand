"""
PyInstaller build script for Falling Sand standalone executable (Phase 4 enhanced).

Usage:
    python tools/build_exe.py [--debug] [--onefile]

This script creates a standalone executable in the dist/ directory.
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Build Falling Sand executable")
    parser.add_argument("--debug", action="store_true", help="Build with console output")
    parser.add_argument("--onefile", action="store_true", help="Build as single file (slower startup)")
    args = parser.parse_args()

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # PyInstaller spec file
    spec_file = project_root / "fallingsand.spec"

    # Create enhanced spec file (Phase 4)
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('shaders', 'shaders'),
        ('simulation', 'simulation'),
        ('simulation/materials.yaml', 'simulation'),
        ('core', 'core'),
        ('gpu', 'gpu'),
        ('ui', 'ui'),
        ('levels', 'levels'),
        ('docs', 'docs'),
    ],
    hiddenimports=[
        'PyOpenGL',
        'PyOpenGL.GL',
        'PyOpenGL.GL.shaders',
        'pygame',
        'numpy',
        'yaml',
        'moderngl',
        'moderngl.window',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FallingSand',
    debug={str(args.debug).lower()},
    bootloader_ignore_signals=False,
    strip=not args.debug,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={str(args.debug).lower()},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path when available
)
"""

    if args.onefile:
        # Modify spec for onefile build
        spec_content = spec_content.replace(
            "name='FallingSand',",
            "name='FallingSand',\n    onefile=True,"
        )

    spec_file.write_text(spec_content)

    # Run PyInstaller
    print("Building standalone executable with PyInstaller...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--clean"],
        cwd=project_root,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Build failed!")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    print("Build successful!")

    if args.onefile:
        exe_path = project_root / 'dist' / 'FallingSand.exe'
    else:
        exe_path = project_root / 'dist' / 'FallingSand' / 'FallingSand.exe'

    print(f"Executable location: {exe_path}")

    # Copy README to dist (Phase 4)
    readme_src = project_root / "README.md"
    if readme_src.exists():
        readme_dst = project_root / "dist" / "README.md"
        shutil.copy(readme_src, readme_dst)
        print(f"README copied to: {readme_dst}")

    # Create version info file (Phase 4)
    version_file = project_root / "dist" / "VERSION.txt"
    version_file.write_text("Falling Sand v7.0 Evolution\n")
    print(f"Version file created: {version_file}")


if __name__ == "__main__":
    main()
