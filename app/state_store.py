from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.paths import DATA_DIR


def state_path() -> Path:
    return DATA_DIR / "state.json"


def default_state() -> dict[str, Any]:
    return {
        "connected": False,
        "last_checked_at": None,
        "outputs": [{"output_no": i, "input_no": None} for i in range(1, 17)],
        "last_error": None,
        "last_raw_preview": None,
        "last_cleaned_preview": None,
    }


def load_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return default_state()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return default_state()
    outs = data.get("outputs") or []
    if len(outs) != 16:
        base = default_state()
        base.update(
            {
                k: data.get(k)
                for k in (
                    "connected",
                    "last_checked_at",
                    "last_error",
                    "last_raw_preview",
                    "last_cleaned_preview",
                )
                if k in data
            }
        )
        return base
    return data


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(obj, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(prefix=".state_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_state(state: dict[str, Any]) -> None:
    atomic_write_json(state_path(), state)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
