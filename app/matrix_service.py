"""장비 송신 — SerialCommandQueue(SERIAL_LOCK) 안에서만 호출할 것."""

from __future__ import annotations

from typing import Any

from app.config_store import protocol_settings, serial_settings
from app.driver import MatrixSerialDriver, SendResult


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


def matrix_send_route(cfg: dict[str, Any], input_no: int, output_no: int) -> SendResult:
    """락 없음 — 호출부가 SERIAL_LOCK으로 감쌀 것."""
    cmd = format_route_command(cfg, input_no, output_no)
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
    drv = driver_from_cfg(cfg)
    return drv.test_link(probe)
