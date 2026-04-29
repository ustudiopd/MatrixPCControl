from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import DATA_DIR
from app.state_store import atomic_write_json


def history_path() -> Path:
    return DATA_DIR / "history.json"


def history_max_items(cfg: dict[str, Any]) -> int:
    try:
        return max(1, min(500, int(cfg.get("history", {}).get("max_items", 50))))
    except (TypeError, ValueError):
        return 50


def load_history() -> list[dict[str, Any]]:
    path = history_path()
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


def save_history(items: list[dict[str, Any]]) -> None:
    atomic_write_json(history_path(), items)


def prepend_history(cfg: dict[str, Any], entry: dict[str, Any]) -> None:
    items = load_history()
    items.insert(0, entry)
    save_history(items[: history_max_items(cfg)])
