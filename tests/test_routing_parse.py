from app.routing_parse import parse_ch_v_routing_table


def test_parse_sample_from_device() -> None:
    raw = (
        "\r\n\r2X2.\r\n\rInputCh=02\r\n"
        "Ch:0,V:01\r\nCh:1,V:02\r\nCh:2,V:03\r\nCh:3,V:04\r\n"
        "Ch:4,V:05\r\nCh:5,V:0e\r\nCh:6,V:05\r\nCh:7,V:09\r\n"
        "Ch:8,V:09\r\nCh:9,V:0c\r\nCh:10,V:09\r\nCh:11,V:0d\r\n"
        "Ch:12,V:09\r\nCh:13,V:07\r\nCh:14,V:08\r\nCh:15,V:09\r\n"
    )
    t = parse_ch_v_routing_table(raw)
    assert t is not None
    assert t[1] == 1
    assert t[2] == 2
    assert t[6] == 14  # V:0e
    assert len(t) == 16


def test_parse_incomplete_returns_none() -> None:
    assert parse_ch_v_routing_table("Ch:0,V:01\nCh:1,V:02\n") is None
