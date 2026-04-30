from __future__ import annotations

from copy import deepcopy

import pytest

from app.config_store import DEFAULT_CONFIG
from app.matrix_service import matrix_probe, matrix_send_route
from app.routing_parse import parse_ch_v_routing_table
from app.state_store import default_state


@pytest.fixture
def mock_cfg() -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg.setdefault("device", {})["transport"] = "mock"
    return cfg


def test_mock_probe(mock_cfg: dict) -> None:
    r = matrix_probe(mock_cfg)
    assert r["ok"] is True


def test_mock_route_outputs_full_ch_v_table(mock_cfg: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.matrix_service.load_state", lambda: default_state())
    r = matrix_send_route(mock_cfg, 3, 5)
    assert r.ok
    tbl = parse_ch_v_routing_table(r.raw_text or "")
    assert tbl is not None
    assert tbl[5] == 3
