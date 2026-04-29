from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import DATA_DIR
from app.state_store import atomic_write_json


def presets_path() -> Path:
    return DATA_DIR / "presets.json"


def load_presets() -> list[dict[str, Any]]:
    path = presets_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def save_presets(items: list[dict[str, Any]]) -> None:
    atomic_write_json(presets_path(), items)


def next_sort_order(items: list[dict[str, Any]]) -> int:
    best = 0
    for x in items:
        try:
            best = max(best, int(x.get("sort_order", 0)))
        except (TypeError, ValueError):
            continue
    return best + 1


def normalize_preset_routes(routes: Any) -> list[dict[str, int]]:
    out: list[dict[str, int]] = []
    if not isinstance(routes, list):
        return out
    for r in routes:
        if not isinstance(r, dict):
            continue
        try:
            inn = int(r["input_no"])
            outn = int(r["output_no"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (1 <= inn <= 16 and 1 <= outn <= 16):
            continue
        out.append({"input_no": inn, "output_no": outn})
    return out


def preset_by_id(items: list[dict[str, Any]], preset_id: str) -> dict[str, Any] | None:
    for x in items:
        if str(x.get("id")) == preset_id:
            return x
    return None
