from __future__ import annotations

import webbrowser
from threading import Timer

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.config_store import io_name_maps, load_config, protocol_settings, save_config, serial_settings
from app.driver import MatrixSerialDriver
from app.paths import ROOT
from app.state_store import default_state, load_state, save_state, utc_now_iso
from app.status_parse import parse_status_response, strip_command_echo

app = FastAPI(title="A1616HD Matrix Control")

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


def _enrich_status(cfg: dict, state: dict) -> dict:
    inp_m, out_m = io_name_maps(cfg)
    rows: list[dict] = []
    for o in state.get("outputs") or []:
        on = int(o["output_no"])
        inn = o.get("input_no")
        oname = out_m.get(on, "").strip()
        iname = inp_m.get(int(inn), "").strip() if inn is not None else ""
        out_disp = f"Output {on}" + (f" / {oname}" if oname else "")
        if inn is None:
            in_disp = "— (미수신)"
        else:
            in_disp = f"Input {inn}" + (f" / {iname}" if iname else "")
        rows.append(
            {
                "output_no": on,
                "input_no": inn,
                "output_display": out_disp,
                "input_display": in_disp,
            }
        )
    return {
        "connected": state.get("connected", False),
        "last_checked_at": state.get("last_checked_at"),
        "last_error": state.get("last_error"),
        "last_raw_preview": state.get("last_raw_preview"),
        "routes": rows,
        "routing_read_only": True,
    }


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


@app.get("/api/status")
def api_status() -> dict:
    cfg = load_config()
    st = load_state()
    if not st.get("outputs"):
        st = default_state()
    return _enrich_status(cfg, st)


@app.post("/api/status/refresh")
def api_status_refresh() -> dict:
    """Status. 만 전송 — 라우팅 변경 없음. 파싱 실패 시 outputs 는 이전 값 유지."""

    cfg = load_config()
    s = serial_settings(cfg)
    proto = protocol_settings(cfg)
    cmd = proto["status_command"]
    drv = _driver_from_cfg(cfg)
    read_to = max(3.0, float(s["timeout"]) * 2.0)

    r = drv.send_command(cmd, read_timeout=read_to, quiet_threshold=12)
    st = load_state()
    if not st.get("outputs"):
        st = default_state()

    if not r.ok:
        st["connected"] = False
        st["last_error"] = r.message
        st["last_raw_preview"] = (r.raw_text or "")[:2000]
        save_state(st)
        return {
            "ok": False,
            "serial_ok": False,
            "parse_ok": False,
            "message": r.message,
            "raw": r.raw_text,
            "state": _enrich_status(cfg, st),
        }

    cleaned = strip_command_echo(r.raw_text, cmd)
    outputs, parsed = parse_status_response(cleaned)

    if not parsed:
        st["connected"] = True
        st["last_checked_at"] = utc_now_iso()
        st["last_error"] = (
            "응답은 수신했으나 Ch:V 형식의 라우팅 줄을 찾지 못했습니다. "
            "아래 raw 를 확인하세요. 이전에 파싱된 표는 유지됩니다."
        )
        st["last_raw_preview"] = (r.raw_text or "")[:2000]
        save_state(st)
        return {
            "ok": True,
            "serial_ok": True,
            "parse_ok": False,
            "message": st["last_error"],
            "raw": r.raw_text,
            "state": _enrich_status(cfg, st),
        }

    st["connected"] = True
    st["last_checked_at"] = utc_now_iso()
    st["outputs"] = outputs
    st["last_error"] = None
    st["last_raw_preview"] = (r.raw_text or "")[:500]
    save_state(st)
    return {
        "ok": True,
        "serial_ok": True,
        "parse_ok": True,
        "message": "라우팅 상태를 갱신했습니다.",
        "raw": r.raw_text,
        "state": _enrich_status(cfg, st),
    }


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
