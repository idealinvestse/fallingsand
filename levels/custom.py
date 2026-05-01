from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

import numpy as np

from levels.base import Level


def _levels_root() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home()
    folder = root / "fallingsand" / "levels"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "level"


@dataclass(slots=True)
class CustomLevelMeta:
    level_id: str
    name: str
    description: str
    thumbnail_color: tuple[int, int, int]
    created_at: str
    author: str
    tags: tuple[str, ...] = ()
    difficulty: int = 1
    objective: str = ""


class CustomLevelStore:
    def __init__(self) -> None:
        self.root = _levels_root()

    def save_level(
        self,
        *,
        name: str,
        description: str,
        state: np.ndarray,
        width: int,
        height: int,
        thumbnail_color: tuple[int, int, int] = (110, 120, 140),
        author: str = "local",
        tags: tuple[str, ...] = (),
        difficulty: int = 1,
        objective: str = "",
    ) -> str:
        level_id = slugify(name)
        npy_path = self.root / f"{level_id}.npy"
        meta_path = self.root / f"{level_id}.json"

        np.save(npy_path, state.astype(np.uint32, copy=False))

        meta = {
            "id": level_id,
            "name": name,
            "description": description,
            "thumbnail_color": list(thumbnail_color),
            "created_at": datetime.now(UTC).isoformat(),
            "author": author,
            "width": int(width),
            "height": int(height),
            "tags": list(tags),
            "difficulty": int(difficulty),
            "objective": objective,
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return level_id

    def list_custom_levels(self) -> list[Level]:
        levels: list[Level] = []
        for meta_path in sorted(self.root.glob("*.json")):
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            level_id = str(meta.get("id", meta_path.stem))
            npy_path = self.root / f"{level_id}.npy"
            if not npy_path.exists():
                continue

            color = tuple(meta.get("thumbnail_color", [110, 120, 140]))
            if len(color) != 3:
                color = (110, 120, 140)

            raw_tags = meta.get("tags", [])
            tags: tuple[str, ...]
            if isinstance(raw_tags, list):
                tags = tuple(str(tag) for tag in raw_tags if str(tag))
            else:
                tags = ()

            def _build(engine, _path=npy_path, _meta=meta):
                arr = np.load(_path)
                if arr.size != engine.width * engine.height:
                    expected = (_meta.get("width"), _meta.get("height"))
                    raise ValueError(
                        f"Custom level size mismatch: file has {arr.size} cells, expected {engine.width * engine.height} (saved as {expected})"
                    )
                engine.set_state(arr.astype(np.uint32, copy=False))

            levels.append(
                Level(
                    level_id=level_id,
                    name=str(meta.get("name", level_id)),
                    description=str(meta.get("description", "Custom level")),
                    thumbnail_color=(int(color[0]), int(color[1]), int(color[2])),
                    build=_build,
                    tags=tags,
                    difficulty=int(meta.get("difficulty", 1)),
                    objective=str(meta.get("objective", "")),
                    is_custom=True,
                )
            )
        return levels
