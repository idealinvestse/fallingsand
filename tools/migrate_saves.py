"""Batch migration tool for FSND v7 saves to v8 chunked format.

Usage:
    python tools/migrate_saves.py <input_dir> <output_dir>
"""

import argparse
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from simulation.persistence import PersistenceManager
from simulation.persistence_v8 import V8Writer


def migrate_single_file(input_path: Path, output_path: Path) -> None:
    """Migrate a single FSND v7 save file to v8 format."""
    print(f"Migrating: {input_path.name}")

    # Create temporary persistence manager to load v7
    pm = PersistenceManager(1024, 1024)  # Will be resized based on save

    # Load v7 save
    pm.load_state(input_path)

    # Save as v8
    width = pm.width
    height = pm.height

    # Create v8 writer with actual dimensions
    w = V8Writer(width, height)
    w.add_cells(pm.buffers.save_state())
    w.add_temperature(pm.buffers.temp_a.read())
    w.add_meta()

    # Optional fields
    try:
        w.add_charge(pm.buffers.charge_a.read())
    except Exception:
        pass
    try:
        w.add_nutrient(pm.buffers.nutrient_a.read())
    except Exception:
        pass
    try:
        w.add_moisture(pm.buffers.moisture_a.read())
    except Exception:
        pass
    try:
        w.add_humidity(pm.buffers.humidity_a.read())
    except Exception:
        pass

    w.write(output_path)
    print(f"  -> {output_path}")


def migrate_directory(input_dir: Path, output_dir: Path) -> None:
    """Migrate all .fsnd files from v7 to v8."""
    if not input_dir.exists():
        print(f"Error: Input directory does not exist: {input_dir}")
        sys.exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .fsnd files
    fsnd_files = list(input_dir.rglob("*.fsnd"))
    if not fsnd_files:
        print(f"No .fsnd files found in {input_dir}")
        return

    print(f"Found {len(fsnd_files)} .fsnd files")

    migrated = 0
    failed = 0

    for fsnd_file in fsnd_files:
        # Compute relative path for output
        rel_path = fsnd_file.relative_to(input_dir)
        output_file = output_dir / rel_path
        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            migrate_single_file(fsnd_file, output_file)
            migrated += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\nMigration complete: {migrated} succeeded, {failed} failed")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate FSND v7 saves to v8 chunked format"
    )
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Input directory containing .fsnd files"
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for migrated .fsnd files"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files"
    )

    args = parser.parse_args()

    # Check if output directory exists and is not empty
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        if not args.force:
            print(f"Error: Output directory exists and is not empty: {args.output_dir}")
            print("Use --force to overwrite")
            sys.exit(1)

    migrate_directory(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
