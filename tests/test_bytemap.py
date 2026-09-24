from __future__ import annotations

from ew11_analyzer.bytemap import byte_map


def test_const_header_tail_roles():
    # non-sequential small value set -> 'state' (not 'counter')
    vals = [0x10, 0x20, 0x10, 0x30, 0x20, 0x10]
    samples = [bytes([0xF7, 0x08, v, 0x42, 0xEE]) for v in vals]
    bm = byte_map(samples, prefix_len=2)
    roles = {b.idx: b.role for b in bm}
    assert roles[0] == "header"
    assert roles[1] == "header"
    assert roles[2] == "state"
    assert roles[3] == "const"
    assert roles[4] == "tail"


def test_counter_detection():
    samples = [bytes([0xF7, 0x08, i % 256, 0xEE]) for i in range(10)]
    bm = byte_map(samples, prefix_len=1)
    assert bm[2].is_counter
    assert bm[2].role == "counter"


def test_checksum_role_override():
    samples = [bytes([0xF7, 0x08, i, 0xEE]) for i in range(6)]
    bm = byte_map(samples, checksum_positions={2}, prefix_len=1)
    assert bm[2].role == "checksum"


def test_high_entropy_data_role():
    samples = [bytes([0xF7, i * 37 % 256, i * 91 % 256, 0xEE]) for i in range(40)]
    bm = byte_map(samples, prefix_len=1)
    assert bm[1].role == "data"
    assert bm[1].entropy > 4


def test_empty():
    assert byte_map([]) == []


def test_top_values():
    samples = [bytes([0xF7, 0x01 if i % 2 else 0x00, 0xEE]) for i in range(10)]
    bm = byte_map(samples, prefix_len=1)
    assert bm[1].distinct == 2
    assert bm[1].top[0][1] >= 5
