from __future__ import annotations

from ew11_analyzer.packets import normalize_payload


def test_hex_plain():
    payload, fmt, _ = normalize_payload(b"F70C40011 1".replace(b" ", b""))
    assert fmt == "hex"
    assert payload == bytes.fromhex("F70C400111")


def test_hex_with_separators():
    for s in (b"F7 0C 40 01", b"F7-0C-40-01", b"0xF7,0x0C,0x40,0x01", b"F7:0C:40:01"):
        payload, fmt, _ = normalize_payload(s)
        assert fmt == "hex", s
        assert payload == bytes.fromhex("F70C4001")


def test_hex_upper_lower():
    payload, fmt, _ = normalize_payload(b"f70c4001")
    assert fmt == "hex"
    assert payload[0] == 0xF7


def test_raw_binary():
    data = b"\xf7\x0c\x40\x01\xff\x00"
    payload, fmt, _ = normalize_payload(data)
    assert fmt == "raw"
    assert payload == data


def test_json_string_field():
    payload, fmt, _ = normalize_payload(b'{"payload": "F7 0C 40 01"}')
    assert fmt == "json"
    assert payload == bytes.fromhex("F70C4001")


def test_json_data_field():
    payload, fmt, _ = normalize_payload(b'{"data": "aabbccdd"}')
    assert fmt == "json"
    assert payload == bytes.fromhex("AABBCCDD")


def test_json_byte_array():
    payload, fmt, _ = normalize_payload(b'{"payload": [247, 12, 64, 1]}')
    assert fmt == "json"
    assert payload == bytes([247, 12, 64, 1])


def test_json_without_known_field():
    payload, fmt, _ = normalize_payload(b'{"foo": 1}')
    assert fmt == "json"
    assert payload == b'{"foo": 1}'


def test_plain_text_not_hex():
    # 'l' and 'o' aren't hex chars -> raw
    _payload, fmt, _ = normalize_payload(b"hello world")
    assert fmt == "raw"


def test_odd_hex_length_falls_back_to_raw():
    _, fmt, _ = normalize_payload(b"ABC")
    assert fmt == "raw"


def test_empty():
    payload, fmt, _ = normalize_payload(b"")
    assert fmt == "raw"
    assert payload == b""


def test_short_hex_falls_back():
    # 1-byte hex string is ambiguous with text -> treated as raw
    _, fmt, _ = normalize_payload(b"FF")
    assert fmt == "raw"
