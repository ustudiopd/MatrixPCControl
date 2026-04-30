"""경로 헬퍼 — 개발 트리 vs PyInstaller 배포(EXE 옆 데이터, 번들 내 static)."""

from __future__ import annotations

import sys
from pathlib import Path


def _dev_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def writable_base_dir() -> Path:
    """config·state 등 — 배포 시 EXE 폴더, 개발 시 리포지토리 루트."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _dev_repo_root()


def package_resource_root() -> Path:
    """정적 번들 리소스 — frozen 시 `_MEIPASS`, 개발 시 리포지토리 루트."""

    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS)
    return _dev_repo_root()


DATA_DIR = writable_base_dir() / "data"
STATIC_DIR = package_resource_root() / "static"
