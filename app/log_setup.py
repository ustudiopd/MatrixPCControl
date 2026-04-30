"""회전 로그 — 명세 §10: `data/logs/app.log`, 최대 10MB, 5개 백업."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.paths import DATA_DIR

_LOGGER_NAME = "matrixpc.control"


def get_logger() -> logging.Logger:
    setup_logging_once()
    return logging.getLogger(_LOGGER_NAME)


def setup_logging_once() -> None:
    """프로세스당 초기화(핸들러가 있으면 생략)."""

    lg = logging.getLogger(_LOGGER_NAME)
    if lg.handlers:
        lg.setLevel(logging.INFO)
        return

    lg.setLevel(logging.INFO)
    lg.propagate = False

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "app.log"

    h = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s"))
    lg.addHandler(h)


def reset_logging_for_tests() -> None:
    lg = logging.getLogger(_LOGGER_NAME)
    lg.handlers.clear()
