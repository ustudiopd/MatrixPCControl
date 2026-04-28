import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.paths import DATA_DIR

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
        "auto_open_browser": True,
    },
    "device": {
        "serial": {
            "port": "COM3",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "timeout": 1.0,
        },
        "protocol": {
            "name": "A1616HD_SERIAL_DOT",
            "route_template": "{input}X{output}.",
            "probe_command": ".",
        },
    },
}


def config_path() -> Path:
    return DATA_DIR / "config.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_data_dir()
    path = config_path()
    if not path.exists():
        cfg = deepcopy(DEFAULT_CONFIG)
        save_config(cfg)
        return cfg
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict[str, Any]) -> None:
    ensure_data_dir()
    path = config_path()
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def serial_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    s = cfg.get("device", {}).get("serial", {})
    d = DEFAULT_CONFIG["device"]["serial"]
    return {
        "port": s.get("port", d["port"]),
        "baudrate": int(s.get("baudrate", d["baudrate"])),
        "bytesize": int(s.get("bytesize", d["bytesize"])),
        "parity": str(s.get("parity", d["parity"])).upper()[:1],
        "stopbits": int(s.get("stopbits", d["stopbits"])),
        "timeout": float(s.get("timeout", d["timeout"])),
    }


def protocol_settings(cfg: dict[str, Any]) -> dict[str, str]:
    p = cfg.get("device", {}).get("protocol", {})
    d = DEFAULT_CONFIG["device"]["protocol"]
    return {
        "name": str(p.get("name") or d.get("name") or "A1616HD_SERIAL_DOT"),
        "route_template": str(p.get("route_template") or d.get("route_template", "{input}X{output}.")),
        "probe_command": str(p.get("probe_command") or d.get("probe_command", ".")),
    }


def io_name_maps(cfg: dict[str, Any]) -> tuple[dict[int, str], dict[int, str]]:
    """Input/Output 번호 → 이름 (없으면 빈 문자열)."""

    def rows_to_map(key: str) -> dict[int, str]:
        m: dict[int, str] = {}
        for row in cfg.get(key) or []:
            if not isinstance(row, dict) or "no" not in row:
                continue
            try:
                n = int(row["no"])
            except (TypeError, ValueError):
                continue
            name = str(row.get("name") or "").strip()
            m[n] = name
        return m

    return rows_to_map("inputs"), rows_to_map("outputs")
