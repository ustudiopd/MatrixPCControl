from __future__ import annotations

import re
from typing import Any

# 명세 예: Ch:0,V:01 — Ch 0-base → Output 1~16, V 는 10진 또는 16진
_CH_V_LINE = re.compile(
    r"^\s*Ch\s*:\s*(\d+)\s*,\s*V\s*:\s*(\S+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _parse_v_token(v: str) -> int | None:
    v = v.strip()
    if not v:
        return None
    if v.isdigit():
        n = int(v, 10)
        return n if 1 <= n <= 16 else None
    try:
        n = int(v, 16)
        return n if 1 <= n <= 16 else None
    except ValueError:
        return None


def strip_command_echo(text: str, command: str) -> str:
    """응답 앞쪽에 붙는 명령 에코·빈 줄 제거."""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cmd_stripped = command.strip()
    out: list[str] = []
    skip_leading = True
    for line in lines:
        if skip_leading:
            s = line.strip()
            if not s or s == cmd_stripped or s.rstrip(".") == cmd_stripped.rstrip("."):
                continue
            skip_leading = False
        out.append(line)
    return "\n".join(out).strip()


def parse_status_response(text: str) -> tuple[list[dict[str, Any]], bool]:
    """
    Ch:V 줄이 하나 이상 파싱되면 성공.
    반환: (outputs 1~16 각 {output_no, input_no|null}, 파싱 성공 여부)
    """

    by_out: dict[int, int] = {}
    for m in _CH_V_LINE.finditer(text):
        ch = int(m.group(1))
        vtok = m.group(2).strip().rstrip(".")
        out_no = ch + 1
        if out_no < 1 or out_no > 16:
            continue
        inp = _parse_v_token(vtok)
        if inp is None:
            continue
        by_out[out_no] = inp

    if not by_out:
        return [], False

    ordered = [{"output_no": i, "input_no": by_out.get(i)} for i in range(1, 17)]
    return ordered, True
