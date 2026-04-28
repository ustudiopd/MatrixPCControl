from __future__ import annotations

import time
from dataclasses import dataclass
import serial
from serial import Serial, SerialException


def _parity_const(parity: str) -> int:
    p = (parity or "N").upper()[:1]
    if p == "E":
        return serial.PARITY_EVEN
    if p == "O":
        return serial.PARITY_ODD
    if p == "M":
        return serial.PARITY_MARK
    if p == "S":
        return serial.PARITY_SPACE
    return serial.PARITY_NONE


def _stopbits_const(stopbits: int) -> float:
    if stopbits == 2:
        return serial.STOPBITS_TWO
    return serial.STOPBITS_ONE


def _bytesize_const(size: int) -> int:
    if size == 7:
        return serial.SEVENBITS
    return serial.EIGHTBITS


@dataclass
class SendResult:
    ok: bool
    command: str
    raw_text: str
    raw_bytes_hex: str
    message: str


class MatrixSerialDriver:
    """최소 Serial 송수신 — 연결·응답 확인용."""

    def __init__(
        self,
        port: str,
        baudrate: int = 9600,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 1.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.timeout = timeout

    def _open(self) -> Serial:
        return Serial(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=_bytesize_const(self.bytesize),
            parity=_parity_const(self.parity),
            stopbits=_stopbits_const(self.stopbits),
            timeout=self.timeout,
        )

    def _read_until_quiet(
        self,
        ser: Serial,
        total_timeout: float,
        quiet_threshold: int = 3,
        tail_extend_sec: float = 0.35,
    ) -> bytes:
        deadline = time.monotonic() + total_timeout
        buf = bytearray()
        quiet_loops = 0
        while time.monotonic() < deadline:
            n = ser.in_waiting
            if n:
                buf.extend(ser.read(n))
                quiet_loops = 0
            elif buf:
                quiet_loops += 1
                time.sleep(0.02)
                if quiet_loops >= quiet_threshold and not ser.in_waiting:
                    break
            else:
                time.sleep(0.02)
        # 늦게 도착하는 줄(멀티라인 응답) 추가 수신
        tail_deadline = time.monotonic() + tail_extend_sec
        while time.monotonic() < tail_deadline:
            if ser.in_waiting:
                buf.extend(ser.read(ser.in_waiting))
                tail_deadline = time.monotonic() + tail_extend_sec
            else:
                time.sleep(0.025)
        return bytes(buf)

    def send_command(
        self,
        command: str,
        read_timeout: float | None = None,
        quiet_threshold: int = 3,
        tail_extend_sec: float = 0.35,
    ) -> SendResult:
        to = read_timeout if read_timeout is not None else max(self.timeout, 0.5)
        try:
            with self._open() as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(command.encode("ascii", errors="strict"))
                ser.flush()
                raw = self._read_until_quiet(
                    ser,
                    to,
                    quiet_threshold=quiet_threshold,
                    tail_extend_sec=tail_extend_sec,
                )
        except SerialException as e:
            return SendResult(
                ok=False,
                command=command,
                raw_text="",
                raw_bytes_hex="",
                message=f"Serial 오류: {e}",
            )
        except OSError as e:
            return SendResult(
                ok=False,
                command=command,
                raw_text="",
                raw_bytes_hex="",
                message=f"포트 오류: {e}",
            )

        text = raw.decode("ascii", errors="replace")
        hex_preview = raw[:256].hex()
        if not raw.strip():
            return SendResult(
                ok=False,
                command=command,
                raw_text=text,
                raw_bytes_hex=hex_preview,
                message="응답 없음(timeout 또는 장비 무응답)",
            )
        return SendResult(
            ok=True,
            command=command,
            raw_text=text,
            raw_bytes_hex=hex_preview,
            message="응답 수신",
        )

    def test_link(self, probe_command: str) -> dict:
        """Serial 연결 확인 — 기본은 `.` 전송 후 응답 수신(Status/Version 미사용)."""

        cmd = (probe_command or ".").strip() or "."
        r = self.send_command(
            cmd,
            read_timeout=max(2.0, self.timeout * 2),
            quiet_threshold=6,
            tail_extend_sec=0.4,
        )
        return {
            "ok": r.ok,
            "message": r.message,
            "command": r.command,
            "raw": r.raw_text,
            "raw_bytes_hex": r.raw_bytes_hex,
            "used_fallback": False,
        }
