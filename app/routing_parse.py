from __future__ import annotations

import re
from typing import Any

# 장비 응답 예: Ch:0,V:01 … Ch:15,V:09 (Ch 0-base → Output 1~16, V는 입력 채널 hex)
_CH_V = re.compile(r"Ch:\s*(\d+)\s*,\s*V:\s*([0-9a-fA-F]+)", re.IGNORECASE)


def parse_ch_v_routing_table(text: str) -> dict[int, int | None] | None:
    """
    raw 텍스트에서 Ch/V 라인을 모두 읽어 output_no(1~16) → input_no 를 만든다.
    Ch 0~15가 모두 있어야 성공(부분만 있으면 None — 기존 단일 출력 갱신으로 폴백).
    V는 16진수. 0이면 해당 출력은 입력 없음(None).
    """

    if not text or "Ch:" not in text:
        return None
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    by_ch: dict[int, int | None] = {}
    for m in _CH_V.finditer(norm):
        try:
            ch = int(m.group(1))
            v = int(m.group(2), 16)
        except ValueError:
            continue
        if ch < 0 or ch > 15:
            continue
        if v == 0:
            by_ch[ch] = None
        elif 1 <= v <= 16:
            by_ch[ch] = v
        else:
            return None
    if len(by_ch) != 16:
        return None
    for c in range(16):
        if c not in by_ch:
            return None
    return {ch + 1: by_ch[ch] for ch in range(16)}


def apply_routing_table_to_state(state: dict[str, Any], table: dict[int, int | None]) -> None:
    outs = state.get("outputs") or []
    for row in outs:
        on = int(row["output_no"])
        if on in table:
            row["input_no"] = table[on]
