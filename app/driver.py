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

    def _read_until_quiet(self, ser: Serial, total_timeout: float) -> bytes:
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
                if quiet_loops >= 3 and not ser.in_waiting:
                    break
            else:
                time.sleep(0.02)
        return bytes(buf)

    def send_command(self, command: str, read_timeout: float | None = None) -> SendResult:
        to = read_timeout if read_timeout is not None else max(self.timeout, 0.5)
        try:
            with self._open() as ser:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
                ser.write(command.encode("ascii", errors="strict"))
                ser.flush()
                raw = self._read_until_quiet(ser, to)
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

    def test_connection(
        self,
        status_cmd: str,
        version_cmd: str,
    ) -> dict:
        """Status. 후 무응답이면 %Version; 시도 (명세 4.2)."""

        def to_dict(r: SendResult, used_fallback: bool) -> dict:
            return {
                "ok": r.ok,
                "message": r.message,
                "command": r.command,
                "raw": r.raw_text,
                "raw_bytes_hex": r.raw_bytes_hex,
                "used_fallback": used_fallback,
            }

        first = self.send_command(status_cmd)
        if first.ok:
            return to_dict(first, False)

        second = self.send_command(version_cmd)
        if second.ok:
            return to_dict(second, True)

        return {
            "ok": False,
            "message": f"{first.message} / 보조: {second.message}",
            "command": status_cmd,
            "raw": first.raw_text or second.raw_text,
            "raw_bytes_hex": first.raw_bytes_hex or second.raw_bytes_hex,
            "used_fallback": False,
        }
