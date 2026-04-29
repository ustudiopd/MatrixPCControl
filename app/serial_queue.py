"""단일 Serial 실행 경로 — 동시 요청 시 순차 처리."""

from __future__ import annotations

import threading

# RLock: 프리셋·되돌리기 등 한 요청 안에서 여러 번 송신할 때 중첩 허용
SERIAL_LOCK = threading.RLock()
