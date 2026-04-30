from __future__ import annotations

import secrets
import time
import webbrowser
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime
from threading import Timer

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from app.config_store import (
    io_name_maps,
    load_config,
    presets_settings,
    protocol_settings,
    save_config,
    serial_settings,
)
from app.driver import SendResult
from app.history_store import load_history, prepend_history
from app.matrix_service import format_route_command, matrix_probe, matrix_send_route
from app.presets_store import (
    load_presets,
    next_sort_order,
    normalize_preset_routes,
    preset_by_id,
    save_presets,
)
from app.routing_parse import apply_routing_table_to_state, parse_ch_v_routing_table
from app.log_setup import get_logger
from app.paths import DATA_DIR, STATIC_DIR
from app.serial_queue import SERIAL_LOCK
from app.state_store import default_state, load_state, save_state, utc_now_iso
from app.undo_store import find_undo_entry, load_undo_stack, prepend_undo, remove_undo_by_action_id

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from app.log_setup import setup_logging_once

    setup_logging_once()
    get_logger().info(
        "FastAPI 시작 — 데이터: %s, 정적 번들: %s",
        str(DATA_DIR.resolve()),
        str(STATIC_DIR.resolve()),
    )
    yield
    get_logger().info("FastAPI 종료")


app = FastAPI(title="A1616HD Matrix Control", lifespan=_lifespan)

static_dir = STATIC_DIR
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


class RouteBody(BaseModel):
    """수동 라우팅: Input → Output (장비 확인 형식 `{input}X{output}.`)."""

    input_no: int = Field(ge=1, le=16)
    output_no: int = Field(ge=1, le=16)


class IoNameRow(BaseModel):
    no: int = Field(ge=1, le=16)
    name: str = Field(default="", max_length=120)


class IoNamesBody(BaseModel):
    inputs: list[IoNameRow] | None = None
    outputs: list[IoNameRow] | None = None


class PresetRoute(BaseModel):
    input_no: int = Field(ge=1, le=16)
    output_no: int = Field(ge=1, le=16)


class PresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    confirm_before_run: bool = False
    routes: list[PresetRoute] = Field(min_length=1)
    sort_order: int | None = None


class PresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    confirm_before_run: bool | None = None
    routes: list[PresetRoute] | None = None
    sort_order: int | None = None


class PresetOrderBody(BaseModel):
    order: list[str] = Field(min_length=1)


class PresetTimingBody(BaseModel):
    """프리셋 순차 라우팅 간 지연 — 명세 4.7~4.8 (대략 0.10~0.20초)."""

    route_between_sec: float = Field(ge=0.08, le=0.35)


def new_action_id() -> str:
    return f"action_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"


def new_preset_id() -> str:
    return f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(2)}"


def _route_title(cfg: dict, input_no: int, output_no: int) -> str:
    inp_m, out_m = io_name_maps(cfg)
    iname = (inp_m.get(input_no) or "").strip()
    oname = (out_m.get(output_no) or "").strip()
    left = str(input_no) + (f" · {iname}" if iname else "")
    right = str(output_no) + (f" · {oname}" if oname else "")
    return f"{left} → {right}"


def _apply_route_send_to_state(
    st: dict,
    r: SendResult,
    input_no: int,
    output_no: int,
) -> None:
    tbl = parse_ch_v_routing_table(r.raw_text or "")
    if tbl:
        apply_routing_table_to_state(st, tbl)
        st["last_cleaned_preview"] = "Ch:V 라우팅 테이블 16채널 반영"
    else:
        for row in st["outputs"]:
            if int(row["output_no"]) == output_no:
                row["input_no"] = input_no
                break
        st["last_cleaned_preview"] = None
    st["connected"] = True
    st["last_checked_at"] = utc_now_iso()
    st["last_error"] = None
    st["last_raw_preview"] = (r.raw_text or "")[:500]


def _enrich_status(cfg: dict, state: dict) -> dict:
    inp_m, out_m = io_name_maps(cfg)
    rows: list[dict] = []
    for o in state.get("outputs") or []:
        on = int(o["output_no"])
        inn = o.get("input_no")
        oname = out_m.get(on, "").strip()
        if inn is None:
            in_key = None
            iname = ""
        else:
            try:
                in_key = int(inn)
            except (TypeError, ValueError):
                in_key = None
            iname = inp_m.get(in_key, "").strip() if in_key is not None else ""
        out_disp = str(on) + (f" · {oname}" if oname else "")
        if inn is None:
            in_disp = "—"
        else:
            in_disp = str(inn) + (f" · {iname}" if iname else "")
        rows.append(
            {
                "output_no": on,
                "input_no": inn,
                "output_display": out_disp,
                "input_display": in_disp,
                "input_alias": iname,
                "output_alias": oname,
            }
        )
    return {
        "connected": state.get("connected", False),
        "last_checked_at": state.get("last_checked_at"),
        "last_error": state.get("last_error"),
        "last_raw_preview": state.get("last_raw_preview"),
        "last_cleaned_preview": state.get("last_cleaned_preview"),
        "routes": rows,
        "routing_read_only": True,
    }


def _normalize_io_rows(rows: list[IoNameRow] | None) -> list[dict] | None:
    if rows is None:
        return None
    seen: set[int] = set()
    out: list[dict] = []
    for row in rows:
        if row.no in seen:
            continue
        seen.add(row.no)
        out.append({"no": row.no, "name": (row.name or "").strip()})
    out.sort(key=lambda x: x["no"])
    return out


def _preset_output_targets(routes: list[dict]) -> dict[int, int]:
    t: dict[int, int] = {}
    for r in routes:
        t[int(r["output_no"])] = int(r["input_no"])
    return t


def _current_input_for_output(st: dict, output_no: int) -> int | None:
    for row in st.get("outputs") or []:
        if int(row["output_no"]) == output_no:
            v = row.get("input_no")
            return int(v) if v is not None else None
    return None


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
        "presets": presets_settings(cfg),
        "inputs": cfg.get("inputs") or [],
        "outputs": cfg.get("outputs") or [],
    }


@app.put("/api/settings/presets-timing")
def put_presets_timing(body: PresetTimingBody) -> dict:
    """프리셋 실행 시 라우트 사이 `time.sleep` 값 — `config.json` `presets.route_between_sec`에 저장."""

    cfg = load_config()
    cfg.setdefault("presets", {})["route_between_sec"] = float(body.route_between_sec)
    save_config(cfg)
    return {"presets": presets_settings(cfg)}


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


def _save_io_names(body: IoNamesBody) -> dict:
    cfg = load_config()
    ni = _normalize_io_rows(body.inputs)
    no = _normalize_io_rows(body.outputs)
    if ni is not None:
        cfg["inputs"] = ni
    if no is not None:
        cfg["outputs"] = no
    if ni is None and no is None:
        raise HTTPException(status_code=400, detail="inputs 또는 outputs 중 하나 이상 필요")
    save_config(cfg)
    return {
        "inputs": cfg.get("inputs") or [],
        "outputs": cfg.get("outputs") or [],
    }


@app.put("/api/settings/io-names")
def put_io_names(body: IoNamesBody) -> dict:
    return _save_io_names(body)


@app.post("/api/settings/io-names")
def post_io_names(body: IoNamesBody) -> dict:
    """PUT과 동일 — 일부 프록시·캐시 환경에서 POST만 허용될 때 사용."""
    return _save_io_names(body)


@app.get("/api/status")
def api_status() -> dict:
    cfg = load_config()
    st = load_state()
    if not st.get("outputs"):
        st = default_state()
    return _enrich_status(cfg, st)


@app.get("/api/connection")
def api_connection() -> dict:
    """연결 상태·마지막 오류 요약(GET) — 명세 §7.`/api/connection` — probe 없이 state 반영값."""

    cfg = load_config()
    st = load_state()
    if not st.get("outputs"):
        st = default_state()
    return {
        "connected": bool(st.get("connected")),
        "last_checked_at": st.get("last_checked_at"),
        "last_error": st.get("last_error"),
        "serial": serial_settings(cfg),
    }


def _apply_probe_to_state(result: dict) -> None:
    st = load_state()
    if not st.get("outputs"):
        st = default_state()
    if result.get("ok"):
        st["connected"] = True
        st["last_checked_at"] = utc_now_iso()
        st["last_error"] = None
    else:
        st["connected"] = False
        st["last_error"] = str(result.get("message") or "연결 실패")
    save_state(st)


@app.post("/api/connection/test")
def post_connection_test() -> dict:
    """`probe_command`(기본 `.`)으로 Serial 응답 확인 — 성공/실패 시 state 반영."""

    cfg = load_config()
    with SERIAL_LOCK:
        result = matrix_probe(cfg)
        _apply_probe_to_state(result)
    msg = str(result.get("message") or "")
    get_logger().info("연결 테스트 결과 ok=%s", bool(result.get("ok")))
    prepend_history(
        cfg,
        {
            "id": new_action_id(),
            "type": "connection_test",
            "title": "연결 테스트 — " + ("성공" if result.get("ok") else "실패"),
            "success": bool(result.get("ok")),
            "undoable": False,
            "created_at": utc_now_iso(),
            "detail": msg[:300],
        },
    )
    if not result["ok"]:
        raise HTTPException(status_code=502, detail=result)
    return result


@app.get("/api/connection/test")
def get_connection_test() -> dict:
    """연결 확인만 수행(state 변경 없음)."""

    cfg = load_config()
    with SERIAL_LOCK:
        return matrix_probe(cfg)


@app.get("/api/history")
def get_history() -> dict:
    return {"items": load_history()}


@app.get("/api/undo")
def get_undo() -> dict:
    return {"items": load_undo_stack()}


@app.get("/api/presets")
def get_presets() -> dict:
    items = load_presets()
    items_sorted = sorted(items, key=lambda x: (int(x.get("sort_order", 0)), str(x.get("id", ""))))
    return {"items": items_sorted}


@app.get("/api/presets/{preset_id}")
def get_preset(preset_id: str) -> dict:
    raw = preset_by_id(load_presets(), preset_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="프리셋 없음")
    return {"preset": raw}


@app.post("/api/presets")
def post_preset(body: PresetCreate) -> dict:
    routes = [{"input_no": r.input_no, "output_no": r.output_no} for r in body.routes]
    items = load_presets()
    pid = new_preset_id()
    so = body.sort_order if body.sort_order is not None else next_sort_order(items)
    entry = {
        "id": pid,
        "name": body.name.strip(),
        "description": (body.description or "").strip(),
        "confirm_before_run": bool(body.confirm_before_run),
        "routes": routes,
        "sort_order": int(so),
    }
    items.append(entry)
    save_presets(items)
    return {"preset": entry}


@app.put("/api/presets/{preset_id}")
def put_preset(preset_id: str, body: PresetUpdate) -> dict:
    items = load_presets()
    p = preset_by_id(items, preset_id)
    if p is None:
        raise HTTPException(status_code=404, detail="프리셋 없음")
    if body.name is not None:
        p["name"] = body.name.strip()
    if body.description is not None:
        p["description"] = body.description.strip()
    if body.confirm_before_run is not None:
        p["confirm_before_run"] = body.confirm_before_run
    if body.routes is not None:
        p["routes"] = [{"input_no": r.input_no, "output_no": r.output_no} for r in body.routes]
        if not p["routes"]:
            raise HTTPException(status_code=400, detail="routes는 1개 이상")
    if body.sort_order is not None:
        p["sort_order"] = int(body.sort_order)
    save_presets(items)
    return {"preset": p}


@app.delete("/api/presets/{preset_id}")
def delete_preset(preset_id: str) -> dict:
    items = load_presets()
    new_items = [x for x in items if str(x.get("id")) != preset_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="프리셋 없음")
    save_presets(new_items)
    return {"ok": True}


@app.put("/api/presets/order")
def put_preset_order(body: PresetOrderBody) -> dict:
    items = load_presets()
    by_id = {str(x.get("id")): x for x in items}
    ordered: list[dict] = []
    for pid in body.order:
        if pid in by_id:
            ordered.append(by_id[pid])
    rest = [x for x in items if str(x.get("id")) not in body.order]
    merged = ordered + rest
    for i, x in enumerate(merged):
        x["sort_order"] = i + 1
    save_presets(merged)
    return {"items": sorted(merged, key=lambda x: int(x.get("sort_order", 0)))}


@app.post("/api/presets/{preset_id}/run")
def post_preset_run(preset_id: str) -> dict:
    cfg = load_config()
    items = load_presets()
    raw = preset_by_id(items, preset_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="프리셋 없음")
    routes = normalize_preset_routes(raw.get("routes"))
    if not routes:
        raise HTTPException(status_code=400, detail="유효한 routes 없음")

    title = str(raw.get("name") or preset_id)
    action_id = new_action_id()
    get_logger().info(
        "프리셋 Serial 실행 시작: preset_id=%s title=%s routes=%d",
        preset_id,
        title,
        len(routes),
    )

    with SERIAL_LOCK:
        st = load_state()
        if not st.get("outputs"):
            st = default_state()

        targets = _preset_output_targets(routes)
        before_routes = [
            {"output_no": o, "input_no": _current_input_for_output(st, o)}
            for o in sorted(targets.keys())
        ]
        after_routes = [{"output_no": o, "input_no": targets[o]} for o in sorted(targets.keys())]

        gap = presets_settings(cfg)["route_between_sec"]
        for idx, rt in enumerate(routes):
            if idx:
                time.sleep(gap)
            r = matrix_send_route(cfg, rt["input_no"], rt["output_no"])
            if not r.ok:
                save_state(st)
                get_logger().warning(
                    "프리셋 중단: preset_id=%s 명령=%s msg=%s",
                    preset_id,
                    r.command,
                    r.message,
                )
                prepend_history(
                    cfg,
                    {
                        "id": action_id,
                        "type": "preset_run",
                        "title": f"프리셋(중단): {title}",
                        "success": False,
                        "undoable": False,
                        "created_at": utc_now_iso(),
                        "detail": (r.message or "")[:300],
                    },
                )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "ok": False,
                        "command": r.command,
                        "message": r.message,
                        "raw": r.raw_text,
                        "partial": True,
                    },
                )
            _apply_route_send_to_state(st, r, rt["input_no"], rt["output_no"])
        save_state(st)

    prepend_history(
        cfg,
        {
            "id": action_id,
            "type": "preset_run",
            "title": f"프리셋: {title}",
            "success": True,
            "undoable": True,
            "created_at": utc_now_iso(),
        },
    )
    prepend_undo(
        cfg,
        {
            "action_id": action_id,
            "title": f"프리셋: {title}",
            "before_routes": before_routes,
            "after_routes": after_routes,
            "created_at": utc_now_iso(),
        },
    )

    return {
        "ok": True,
        "action_id": action_id,
        "state": _enrich_status(cfg, st),
    }


@app.post("/api/undo/{action_id}")
def post_undo(action_id: str) -> dict:
    """undo_stack의 before_routes로 복원(변경 Output만). input_no가 null이면 Serial 없이 state만 복원."""

    entry = find_undo_entry(action_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="해당 되돌리기 항목이 없습니다.")

    cfg = load_config()
    get_logger().info("되돌리기 시작 action_id=%s", action_id)
    before = entry.get("before_routes") or []
    if not isinstance(before, list):
        raise HTTPException(status_code=400, detail="before_routes 형식 오류")
    if not before:
        raise HTTPException(status_code=400, detail="before_routes가 비어 있습니다.")

    st = load_state()
    if not st.get("outputs"):
        st = default_state()

    last_raw_for_parse = ""

    with SERIAL_LOCK:
        for br in before:
            if not isinstance(br, dict):
                continue
            try:
                out_no = int(br["output_no"])
            except (KeyError, TypeError, ValueError):
                continue
            inn = br.get("input_no")
            prev_in: int | None
            if inn is None:
                prev_in = None
            else:
                try:
                    prev_in = int(inn)
                except (TypeError, ValueError):
                    continue

            if prev_in is not None:
                r = matrix_send_route(cfg, prev_in, out_no)
                if not r.ok:
                    raise HTTPException(
                        status_code=502,
                        detail={
                            "ok": False,
                            "message": r.message,
                            "command": r.command,
                            "raw": r.raw_text,
                            "partial": True,
                        },
                    )
                last_raw_for_parse = r.raw_text or ""

            for row in st["outputs"]:
                if int(row["output_no"]) == out_no:
                    row["input_no"] = prev_in
                    break

        tbl_undo = parse_ch_v_routing_table(last_raw_for_parse)
        if tbl_undo:
            apply_routing_table_to_state(st, tbl_undo)
            st["last_cleaned_preview"] = "Ch:V 라우팅 테이블 16채널 반영"
        else:
            st["last_cleaned_preview"] = None
        if last_raw_for_parse:
            st["last_raw_preview"] = last_raw_for_parse[:500]

        st["connected"] = True
        st["last_checked_at"] = utc_now_iso()
        st["last_error"] = None
        save_state(st)

    remove_undo_by_action_id(action_id)

    title = str(entry.get("title") or "작업")
    redo_action_id = new_action_id()
    prepend_history(
        cfg,
        {
            "id": redo_action_id,
            "type": "undo",
            "title": f"되돌리기: {title}",
            "success": True,
            "undoable": True,
            "created_at": utc_now_iso(),
            "undid_action_id": action_id,
        },
    )
    # 상호 undo: 되돌리기 직전 상태(after)로 다시 돌아갈 수 있도록 스택에 쌓음
    prepend_undo(
        cfg,
        {
            "action_id": redo_action_id,
            "title": f"되돌리기 취소(재적용): {title}",
            "before_routes": deepcopy(entry.get("after_routes") or []),
            "after_routes": deepcopy(entry.get("before_routes") or []),
            "created_at": utc_now_iso(),
        },
    )

    return {"ok": True, "state": _enrich_status(cfg, st)}


@app.post("/api/routing")
def post_routing(body: RouteBody) -> dict:
    """`{input}X{output}.` 형식으로 전송 — 성공 시 state.json 해당 출력만 갱신 + history·undo_stack."""

    cfg = load_config()
    title = _route_title(cfg, body.input_no, body.output_no)
    action_id = new_action_id()
    get_logger().info(
        "수동 라우팅 Serial: input_no=%s output_no=%s",
        body.input_no,
        body.output_no,
    )

    st0 = load_state()
    if not st0.get("outputs"):
        st0 = default_state()
    before_input: int | None = None
    for row in st0["outputs"]:
        if int(row["output_no"]) == body.output_no:
            v = row.get("input_no")
            before_input = int(v) if v is not None else None
            break

    try:
        format_route_command(cfg, body.input_no, body.output_no)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    with SERIAL_LOCK:
        r = matrix_send_route(cfg, body.input_no, body.output_no)
    cmd = r.command

    if not r.ok:
        prepend_history(
            cfg,
            {
                "id": action_id,
                "type": "manual_route",
                "title": title,
                "success": False,
                "undoable": False,
                "created_at": utc_now_iso(),
                "detail": (r.message or "")[:300],
            },
        )
        raise HTTPException(
            status_code=502,
            detail={
                "ok": False,
                "command": cmd,
                "message": r.message,
                "raw": r.raw_text,
            },
        )

    st = load_state()
    if not st.get("outputs"):
        st = default_state()
    _apply_route_send_to_state(st, r, body.input_no, body.output_no)
    save_state(st)

    prepend_history(
        cfg,
        {
            "id": action_id,
            "type": "manual_route",
            "title": title,
            "success": True,
            "undoable": True,
            "created_at": utc_now_iso(),
        },
    )
    prepend_undo(
        cfg,
        {
            "action_id": action_id,
            "title": title,
            "before_routes": [{"output_no": body.output_no, "input_no": before_input}],
            "after_routes": [{"output_no": body.output_no, "input_no": body.input_no}],
            "created_at": utc_now_iso(),
        },
    )

    return {
        "ok": True,
        "action_id": action_id,
        "command": cmd,
        "message": r.message,
        "raw": r.raw_text,
        "state": _enrich_status(cfg, st),
    }


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
