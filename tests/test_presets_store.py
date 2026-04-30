from __future__ import annotations

from app.presets_store import next_sort_order, normalize_preset_routes, preset_by_id


def test_normalize_accepts_good_rows() -> None:
    routes = [{"input_no": 1, "output_no": 2}, {"input_no": 3, "output_no": 4}]
    assert normalize_preset_routes(routes) == [
        {"input_no": 1, "output_no": 2},
        {"input_no": 3, "output_no": 4},
    ]


def test_normalize_last_wins_duplicate_output() -> None:
    """같은 output이 두 번 나오면 마지막 input이 의도적으로 적용된다."""
    routes = [{"input_no": 9, "output_no": 1}, {"input_no": 1, "output_no": 1}]
    assert normalize_preset_routes(routes) == [
        {"input_no": 9, "output_no": 1},
        {"input_no": 1, "output_no": 1},
    ]


def test_normalize_filters_invalid_range() -> None:
    routes = [{"input_no": 0, "output_no": 1}, {"input_no": 1, "output_no": 1}]
    assert normalize_preset_routes(routes) == [{"input_no": 1, "output_no": 1}]


def test_next_sort_order() -> None:
    assert next_sort_order([{"sort_order": 2}, {}]) == 3
    assert next_sort_order([]) == 1


def test_preset_by_id() -> None:
    items = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]
    assert preset_by_id(items, "a")["name"] == "A"
    assert preset_by_id(items, "x") is None
