"""장비 송신 — SerialCommandQueue(SERIAL_LOCK) 안에서만 호출할 것."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from app.config_store import protocol_settings, serial_settings
from app.driver import MatrixSerialDriver, SendResult
from app.log_setup import get_logger
from app.state_store import default_state, load_state


def use_mock_transport(cfg: dict[str, Any]) -> bool:
    ev = os.environ.get("MATRIXPC_MOCK_TRANSPORT", "").strip().lower()
    if ev in ("1", "true", "yes"):
        return True
    t = str(cfg.get("device", {}).get("transport", "serial")).lower().strip()
    return t == "mock"


def driver_from_cfg(cfg: dict[str, Any]) -> MatrixSerialDriver:
    s = serial_settings(cfg)
    return MatrixSerialDriver(
        port=s["port"],
        baudrate=s["baudrate"],
        bytesize=s["bytesize"],
        parity=s["parity"],
        stopbits=s["stopbits"],
        timeout=s["timeout"],
    )


def format_route_command(cfg: dict[str, Any], input_no: int, output_no: int) -> str:
    tpl = protocol_settings(cfg)["route_template"]
    try:
        return tpl.format(input=input_no, output=output_no)
    except KeyError as e:
        raise ValueError(f"route_template 에 알 수 없는 플레이스홀더: {e}") from e


def _mock_ch_v_raw_from_outputs(outputs: list[dict]) -> str:
    """16채널 Ch:V 한 줄씩 — `routing_parse`와 동일 형식."""

    lines: list[str] = []
    for ch in range(16):
        o = ch + 1
        inp: int | None = None
        for r in outputs:
            if int(r["output_no"]) == o:
                v = r.get("input_no")
                inp = int(v) if v is not None else None
                break
        hx = 0 if inp is None else int(inp)
        lines.append(f"Ch:{ch},V:{hx:02x}")
    return "\r\n".join(lines) + "\r\n"


def matrix_send_route(cfg: dict[str, Any], input_no: int, output_no: int) -> SendResult:
    """락 없음 — 호출부가 SERIAL_LOCK으로 감쌀 것."""

    cmd = format_route_command(cfg, input_no, output_no)
    if use_mock_transport(cfg):
        get_logger().info("Serial(mock) 라우팅: %s", cmd)
        st = load_state()
        if not st.get("outputs"):
            st = default_state()
        st = deepcopy(st)
        for row in st["outputs"]:
            if int(row["output_no"]) == output_no:
                row["input_no"] = input_no
                break
        raw = _mock_ch_v_raw_from_outputs(st["outputs"])
        b = raw.encode("ascii", errors="replace")
        return SendResult(
            ok=True,
            command=cmd,
            raw_text=raw,
            raw_bytes_hex=b[:256].hex(),
            message="응답(mock, Ch:V 표)",
        )

    s = serial_settings(cfg)
    drv = driver_from_cfg(cfg)
    read_to = max(3.0, float(s["timeout"]) * 2.0)
    return drv.send_command(
        cmd,
        read_timeout=read_to,
        quiet_threshold=8,
        tail_extend_sec=0.5,
    )


def matrix_probe(cfg: dict[str, Any]) -> dict:
    """락 없음 — probe 한 번."""

    proto = protocol_settings(cfg)
    probe = proto["probe_command"]
    if use_mock_transport(cfg):
        get_logger().info("Serial(mock) probe: %r", probe)
        return {
            "ok": True,
            "message": "mock 장비 연결 성공",
            "command": (probe or ".").strip() or ".",
            "raw": "MOCK\r\n",
            "raw_bytes_hex": "4d4f434b0d0a",
            "used_fallback": False,
        }
    drv = driver_from_cfg(cfg)
    return drv.test_link(probe)
