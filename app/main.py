from __future__ import annotations

import webbrowser
from threading import Timer

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.config_store import load_config, protocol_settings, save_config, serial_settings
from app.driver import MatrixSerialDriver
from app.paths import ROOT

app = FastAPI(title="A1616HD Matrix Signal Check")

static_dir = ROOT / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class SerialUpdate(BaseModel):
    port: str | None = None
    baudrate: int | None = Field(default=None, ge=300)
    bytesize: int | None = Field(default=None, ge=7, le=8)
    parity: str | None = None
    stopbits: int | None = Field(default=None, ge=1, le=2)
    timeout: float | None = Field(default=None, ge=0.1, le=30.0)

    @field_validator("parity")
    @classmethod
    def upper_parity(cls, v: str | None) -> str | None:
        if v is None:
            return None
        u = v.strip().upper()[:1]
        if u not in ("N", "E", "O", "M", "S"):
            raise ValueError("parity는 N,E,O,M,S 중 하나")
        return u


def _driver_from_cfg(cfg: dict) -> MatrixSerialDriver:
    s = serial_settings(cfg)
    return MatrixSerialDriver(
        port=s["port"],
        baudrate=s["baudrate"],
        bytesize=s["bytesize"],
        parity=s["parity"],
        stopbits=s["stopbits"],
        timeout=s["timeout"],
    )


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    html_path = static_dir / "index.html"
    if not html_path.exists():
        return "<p>static/index.html 없음</p>"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/settings")
def get_settings() -> dict:
    cfg = load_config()
    return {
        "serial": serial_settings(cfg),
        "protocol": protocol_settings(cfg),
    }


@app.put("/api/settings/serial")
def put_serial(body: SerialUpdate) -> dict:
    cfg = load_config()
    dev = cfg.setdefault("device", {})
    ser = dev.setdefault("serial", {})
    if body.port is not None:
        ser["port"] = body.port.strip()
    if body.baudrate is not None:
        ser["baudrate"] = body.baudrate
    if body.bytesize is not None:
        ser["bytesize"] = body.bytesize
    if body.parity is not None:
        ser["parity"] = body.parity
    if body.stopbits is not None:
        ser["stopbits"] = body.stopbits
    if body.timeout is not None:
        ser["timeout"] = body.timeout
    save_config(cfg)
    return {"serial": serial_settings(cfg)}


@app.post("/api/connection/test")
def test_connection() -> dict:
    cfg = load_config()
    drv = _driver_from_cfg(cfg)
    proto = protocol_settings(cfg)
    result = drv.test_connection(
        status_cmd=proto["status_command"],
        version_cmd=proto["version_command"],
    )
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/connection/test")
def test_connection_safe() -> dict:
    """HTTP 200 + body.ok 로 실패 전달 (브라우저에서 fetch 편의)."""

    cfg = load_config()
    drv = _driver_from_cfg(cfg)
    proto = protocol_settings(cfg)
    return drv.test_connection(
        status_cmd=proto["status_command"],
        version_cmd=proto["version_command"],
    )


def _open_browser(host: str, port: int) -> None:
    webbrowser.open(f"http://{host}:{port}/")


def main() -> None:
    import uvicorn

    cfg = load_config()
    srv = cfg.get("server", {})
    host = str(srv.get("host", "127.0.0.1"))
    port = int(srv.get("port", 8000))
    if srv.get("auto_open_browser", True):
        Timer(1.0, _open_browser, args=(host, port)).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
