from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import DATA_DIR
from app.state_store import atomic_write_json


def undo_stack_path() -> Path:
    return DATA_DIR / "undo_stack.json"


def undo_max_items(cfg: dict[str, Any]) -> int:
    """호환용 — 되돌리기 스택은 항상 1건만 유지한다."""
    try:
        return max(1, min(100, int(cfg.get("undo", {}).get("max_items", 1))))
    except (TypeError, ValueError):
        return 1


def load_undo_stack() -> list[dict[str, Any]]:
    path = undo_stack_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    items = [x for x in data if isinstance(x, dict)]
    # 직전 작업 한 단계만: 예전 다건 스택이 있으면 최신 1건만 남기고 저장
    if len(items) > 1:
        items = items[:1]
        save_undo_stack(items)
    return items


def save_undo_stack(items: list[dict[str, Any]]) -> None:
    atomic_write_json(undo_stack_path(), items)


def prepend_undo(cfg: dict[str, Any], entry: dict[str, Any]) -> None:
    """새 항목만 스택에 둔다(이전 되돌리기 대상은 버림 — 한 단계씩만)."""
    _ = cfg
    save_undo_stack([entry])


def remove_undo_by_action_id(action_id: str) -> bool:
    items = load_undo_stack()
    new_items = [x for x in items if str(x.get("action_id")) != action_id]
    if len(new_items) == len(items):
        return False
    save_undo_stack(new_items)
    return True


def find_undo_entry(action_id: str) -> dict[str, Any] | None:
    for x in load_undo_stack():
        if str(x.get("action_id")) == action_id:
            return x
    return None
