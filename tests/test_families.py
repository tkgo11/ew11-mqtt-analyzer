from __future__ import annotations

from conftest import mk_packet
from ew11_analyzer.families import group_families, signature
from ew11_analyzer.sources.simulator import frame


def test_signature_format():
    sig = signature(bytes.fromhex("F70C4001"), prefix_len=2)
    assert sig == "F70C:4"


def test_signature_includes_length():
    assert signature(bytes.fromhex("F70C"), 2) != signature(bytes.fromhex("F70C40"), 2)


def test_grouping():
    pkts = [
        mk_packet(0, frame(0x40, 0x01, 0x51, [0x00])),
        mk_packet(1, frame(0x40, 0x01, 0x51, [0x00])),
        mk_packet(2, frame(0x40, 0x01, 0x31, [0x00, 0x00])),
    ]
    fams = group_families(pkts, prefix_len=3)
    assert len(fams) == 2
    counts = sorted(len(v) for v in fams.values())
    assert counts == [1, 2]


def test_direction_split_with_prefix3():
    """Commands (dst=01) and broadcasts (dst=40) of equal length split at prefix 3."""
    cmd = frame(0x01, 0x40, 0x11, [0x01, 0x01, 0xFF])  # 10 bytes, dst=01
    bcast = frame(0x40, 0x01, 0x71, [0x00, 0x00, 0xAA])  # 10 bytes, dst=40
    pkts = [mk_packet(0, cmd), mk_packet(1, bcast)]
    fams = group_families(pkts, prefix_len=3)
    assert len(fams) == 2
    fams2 = group_families(pkts, prefix_len=2)
    assert len(fams2) == 1  # merged at prefix 2
